# Print Pricing (artivity-server) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `print_pricing` module to artivity-server that stores labeled sample pages, freezes dataset versions, stores model versions, and orchestrates retraining + activation — all gated to role `owner`.

**Architecture:** Handler → Service → Store (repo convention). New tables in Postgres (one migration). Owner routes use `auth.WithRoleJWTAuth(..., []string{"owner"})`. Two service endpoints use `middleware.WithPrintPricingServiceToken`. Retrain snapshots labels, POSTs them to apiModelRegression `/internal/train`, stores the returned coefficients as a `candidate`, and activation flips the single-active row in one transaction.

**Tech Stack:** Go 1.24, gorilla/mux, PostgreSQL (raw SQL, lib/pq), golang-migrate, golang-jwt, testify.

**Spec:** `app/apiModelRegression/docs/superpowers/specs/2026-10-02-print-pricing-labeling-retrain-design.md`

## Global Constraints

- Migration conventions: `id uuid DEFAULT public.uuidv7() NOT NULL PRIMARY KEY`, `internal_id bigserial UNIQUE NOT NULL`, `timestamp with time zone DEFAULT CURRENT_TIMESTAMP NOT NULL`, FK to `users(internal_id)`.
- Respond with `utils.WriteDataResponse(w, status, data)` and `utils.WriteAppError(w, utils.NewXError(...))`; parse JSON with `utils.ParseJSON`; validate UUIDs with `utils.IsValidUUID`.
- Owner gate is role-based: `auth.WithRoleJWTAuth(handler, userStore, []string{"owner"})`. Do not use permission checks for owner.
- Service endpoints require header `X-API-Key` == env `PRINT_PRICING_SERVICE_TOKEN`, constant-time compare, fail-closed (503 if unset).
- At most one model version with `status = 'active'` (enforced by partial unique index).
- Retrain uses **replace semantics**: the dataset snapshot is all labeled, non-discarded pages at snapshot time.
- `MIN_TRAINING_ROWS` default 20; retrain rejects with a clear 400 when below it.
- Do not break existing routes/tests. Run `make fmt && make lint && make test-unit` before each commit; `make test-integration` for DB tests.

---

### Task 1: Migration + types + sample/page store

**Files:**
- Create: `db/migrations/20261002120000_create_print_pricing_tables.up.sql`
- Create: `db/migrations/20261002120000_create_print_pricing_tables.down.sql`
- Create: `types/printpricing.go`
- Create: `services/printpricing/store.go`
- Test: `services/printpricing/store_test.go`

**Interfaces:**
- Produces (types): `types.PrintPricingSample`, `types.PrintPricingPage`, `types.PrintPricingDatasetVersion`, `types.PrintPricingDatasetRow`, `types.PrintPricingModelVersion`, `types.CreateSampleInput`, `types.CreateSamplePageInput`, `types.CreateModelVersionInput`.
- Produces (store): `NewStore(db *sql.DB) *Store`, `(*Store).CreateSample`, `.GetSample`, `.ListSamples`, `.DeleteSample`, `.SetPageLabel`.

- [ ] **Step 1: Write the migration (up)**

```sql
-- db/migrations/20261002120000_create_print_pricing_tables.up.sql
-- Print pricing: labeled PDF samples, frozen datasets, and model versions.
-- Single-active model enforced by a partial unique index. No seed rows: the
-- service falls back to its baked model until the first activation.

CREATE TABLE public.print_pricing_samples (
    id                uuid DEFAULT public.uuidv7() NOT NULL PRIMARY KEY,
    internal_id       bigserial UNIQUE NOT NULL,
    original_filename character varying(255) NOT NULL,
    page_count        integer NOT NULL,
    uploaded_by       integer REFERENCES public.users(internal_id) ON DELETE SET NULL,
    status            character varying(20) NOT NULL DEFAULT 'labeling',
    created_at        timestamp with time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at        timestamp with time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    CONSTRAINT print_pricing_samples_status_check CHECK (status IN ('labeling', 'completed', 'discarded'))
);

CREATE TABLE public.print_pricing_pages (
    id            uuid DEFAULT public.uuidv7() NOT NULL PRIMARY KEY,
    internal_id   bigserial UNIQUE NOT NULL,
    sample_id     uuid NOT NULL REFERENCES public.print_pricing_samples(id) ON DELETE CASCADE,
    page_number   integer NOT NULL,
    bw_area       double precision NOT NULL,
    color_area    double precision NOT NULL,
    print_area    double precision GENERATED ALWAYS AS (bw_area + color_area) STORED,
    thumbnail     bytea,
    labeled_price integer,
    labeled_by    integer REFERENCES public.users(internal_id) ON DELETE SET NULL,
    labeled_at    timestamp with time zone,
    created_at    timestamp with time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at    timestamp with time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    CONSTRAINT uq_print_pricing_pages_sample_page UNIQUE (sample_id, page_number)
);

CREATE TABLE public.print_pricing_dataset_versions (
    id          uuid DEFAULT public.uuidv7() NOT NULL PRIMARY KEY,
    internal_id bigserial UNIQUE NOT NULL,
    row_count   integer NOT NULL DEFAULT 0,
    created_by  integer REFERENCES public.users(internal_id) ON DELETE SET NULL,
    note        text,
    created_at  timestamp with time zone DEFAULT CURRENT_TIMESTAMP NOT NULL
);

CREATE TABLE public.print_pricing_dataset_rows (
    id                 uuid DEFAULT public.uuidv7() NOT NULL PRIMARY KEY,
    internal_id        bigserial UNIQUE NOT NULL,
    dataset_version_id uuid NOT NULL REFERENCES public.print_pricing_dataset_versions(id) ON DELETE CASCADE,
    page_id            uuid,
    bw_area            double precision NOT NULL,
    color_area         double precision NOT NULL,
    print_area         double precision NOT NULL,
    price              double precision NOT NULL,
    created_at         timestamp with time zone DEFAULT CURRENT_TIMESTAMP NOT NULL
);

CREATE INDEX idx_print_pricing_dataset_rows_dataset
    ON public.print_pricing_dataset_rows (dataset_version_id);

CREATE TABLE public.print_pricing_model_versions (
    id                 uuid DEFAULT public.uuidv7() NOT NULL PRIMARY KEY,
    internal_id        bigserial UNIQUE NOT NULL,
    dataset_version_id uuid NOT NULL REFERENCES public.print_pricing_dataset_versions(id),
    status             character varying(20) NOT NULL DEFAULT 'candidate',
    intercept          double precision NOT NULL,
    print_thresholds   jsonb NOT NULL DEFAULT '[]'::jsonb,
    print_values       jsonb NOT NULL DEFAULT '[]'::jsonb,
    color_thresholds   jsonb NOT NULL DEFAULT '[]'::jsonb,
    color_values       jsonb NOT NULL DEFAULT '[]'::jsonb,
    metrics            jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_by         integer REFERENCES public.users(internal_id) ON DELETE SET NULL,
    created_at         timestamp with time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    activated_at       timestamp with time zone,
    activated_by       integer REFERENCES public.users(internal_id) ON DELETE SET NULL,
    CONSTRAINT print_pricing_model_versions_status_check CHECK (status IN ('candidate', 'active', 'archived'))
);

CREATE UNIQUE INDEX uq_print_pricing_model_single_active
    ON public.print_pricing_model_versions ((true)) WHERE status = 'active';
```

- [ ] **Step 2: Write the migration (down)**

```sql
-- db/migrations/20261002120000_create_print_pricing_tables.down.sql
DROP TABLE IF EXISTS public.print_pricing_model_versions;
DROP TABLE IF EXISTS public.print_pricing_dataset_rows;
DROP TABLE IF EXISTS public.print_pricing_dataset_versions;
DROP TABLE IF EXISTS public.print_pricing_pages;
DROP TABLE IF EXISTS public.print_pricing_samples;
```

- [ ] **Step 3: Write `types/printpricing.go`**

```go
package types

import "time"

type PrintPricingSample struct {
	ID               string             `json:"id"`
	OriginalFilename string             `json:"original_filename"`
	PageCount        int                `json:"page_count"`
	UploadedBy       *int               `json:"uploaded_by,omitempty"`
	Status           string             `json:"status"`
	CreatedAt        time.Time          `json:"created_at"`
	UpdatedAt        time.Time          `json:"updated_at"`
	Pages            []PrintPricingPage `json:"pages,omitempty"`
}

type PrintPricingPage struct {
	ID              string     `json:"id"`
	SampleID        string     `json:"sample_id"`
	PageNumber      int        `json:"page_number"`
	BWArea          float64    `json:"bw_area"`
	ColorArea       float64    `json:"color_area"`
	PrintArea       float64    `json:"print_area"`
	ThumbnailBase64 string     `json:"thumbnail_base64,omitempty"`
	LabeledPrice    *int       `json:"labeled_price"`
	LabeledBy       *int       `json:"labeled_by,omitempty"`
	LabeledAt       *time.Time `json:"labeled_at,omitempty"`
}

type PrintPricingDatasetVersion struct {
	ID        string    `json:"id"`
	RowCount  int       `json:"row_count"`
	CreatedBy *int      `json:"created_by,omitempty"`
	Note      string    `json:"note,omitempty"`
	CreatedAt time.Time `json:"created_at"`
}

type PrintPricingDatasetRow struct {
	BWArea    float64 `json:"bw_area"`
	ColorArea float64 `json:"color_area"`
	PrintArea float64 `json:"print_area"`
	Price     float64 `json:"price"`
}

type PrintPricingModelVersion struct {
	ID              string         `json:"id"`
	DatasetVersion  string         `json:"dataset_version_id"`
	Status          string         `json:"status"`
	Intercept       float64        `json:"intercept"`
	PrintThresholds []float64      `json:"print_thresholds"`
	PrintValues     []float64      `json:"print_values"`
	ColorThresholds []float64      `json:"color_thresholds"`
	ColorValues     []float64      `json:"color_values"`
	Metrics         map[string]any `json:"metrics"`
	CreatedBy       *int           `json:"created_by,omitempty"`
	CreatedAt       time.Time      `json:"created_at"`
	ActivatedAt     *time.Time     `json:"activated_at,omitempty"`
	ActivatedBy     *int           `json:"activated_by,omitempty"`
}

type CreateSamplePageInput struct {
	PageNumber      int     `json:"page_number" validate:"required"`
	BWArea          float64 `json:"bw_area"`
	ColorArea       float64 `json:"color_area"`
	ThumbnailBase64 string  `json:"thumbnail_base64"`
}

type CreateSampleInput struct {
	OriginalFilename string                  `json:"original_filename" validate:"required"`
	PageCount        int                     `json:"page_count" validate:"required"`
	UploadedBy       *int                    `json:"-"`
	Pages            []CreateSamplePageInput `json:"pages" validate:"required,dive"`
}

type CreateModelVersionInput struct {
	DatasetVersionID string         `json:"dataset_version_id"`
	Intercept        float64        `json:"intercept"`
	PrintThresholds  []float64      `json:"print_thresholds"`
	PrintValues      []float64      `json:"print_values"`
	ColorThresholds  []float64      `json:"color_thresholds"`
	ColorValues      []float64      `json:"color_values"`
	Metrics          map[string]any `json:"metrics"`
	CreatedBy        *int           `json:"-"`
}
```

- [ ] **Step 4: Write the store (samples + pages)**

```go
package printpricing

import (
	"database/sql"
	"encoding/base64"
	"time"

	"github.com/sae-project/artivity-server/types"
)

type Store struct {
	db *sql.DB
}

func NewStore(db *sql.DB) *Store { return &Store{db: db} }

func (s *Store) CreateSample(in types.CreateSampleInput) (*types.PrintPricingSample, error) {
	tx, err := s.db.Begin()
	if err != nil {
		return nil, err
	}
	defer tx.Rollback()

	sample := types.PrintPricingSample{}
	err = tx.QueryRow(`
		INSERT INTO print_pricing_samples (original_filename, page_count, uploaded_by)
		VALUES ($1, $2, $3)
		RETURNING id, original_filename, page_count, uploaded_by, status, created_at, updated_at`,
		in.OriginalFilename, in.PageCount, in.UploadedBy,
	).Scan(&sample.ID, &sample.OriginalFilename, &sample.PageCount, &sample.UploadedBy,
		&sample.Status, &sample.CreatedAt, &sample.UpdatedAt)
	if err != nil {
		return nil, err
	}

	for _, p := range in.Pages {
		var thumb []byte
		if p.ThumbnailBase64 != "" {
			if thumb, err = base64.StdEncoding.DecodeString(p.ThumbnailBase64); err != nil {
				return nil, err
			}
		}
		page := types.PrintPricingPage{}
		err = tx.QueryRow(`
			INSERT INTO print_pricing_pages (sample_id, page_number, bw_area, color_area, thumbnail)
			VALUES ($1, $2, $3, $4, $5)
			RETURNING id, sample_id, page_number, bw_area, color_area, print_area, labeled_price`,
			sample.ID, p.PageNumber, p.BWArea, p.ColorArea, thumb,
		).Scan(&page.ID, &page.SampleID, &page.PageNumber, &page.BWArea, &page.ColorArea, &page.PrintArea, &page.LabeledPrice)
		if err != nil {
			return nil, err
		}
		if thumb != nil {
			page.ThumbnailBase64 = base64.StdEncoding.EncodeToString(thumb)
		}
		sample.Pages = append(sample.Pages, page)
	}

	if err := tx.Commit(); err != nil {
		return nil, err
	}
	return &sample, nil
}

func (s *Store) ListSamples() ([]types.PrintPricingSample, error) {
	rows, err := s.db.Query(`
		SELECT s.id, s.original_filename, s.page_count, s.uploaded_by, s.status, s.created_at, s.updated_at,
		       COUNT(p.id), COUNT(p.labeled_price)
		FROM print_pricing_samples s
		LEFT JOIN print_pricing_pages p ON p.sample_id = s.id
		GROUP BY s.id
		ORDER BY s.created_at DESC`)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	out := []types.PrintPricingSample{}
	for rows.Next() {
		m := types.PrintPricingSample{}
		var pageTotal, pageLabeled int
		if err := rows.Scan(&m.ID, &m.OriginalFilename, &m.PageCount, &m.UploadedBy, &m.Status,
			&m.CreatedAt, &m.UpdatedAt, &pageTotal, &pageLabeled); err != nil {
			return nil, err
		}
		out = append(out, m)
	}
	return out, rows.Err()
}

func (s *Store) GetSample(id string) (*types.PrintPricingSample, error) {
	sample := types.PrintPricingSample{}
	err := s.db.QueryRow(`
		SELECT id, original_filename, page_count, uploaded_by, status, created_at, updated_at
		FROM print_pricing_samples WHERE id = $1`, id,
	).Scan(&sample.ID, &sample.OriginalFilename, &sample.PageCount, &sample.UploadedBy,
		&sample.Status, &sample.CreatedAt, &sample.UpdatedAt)
	if err == sql.ErrNoRows {
		return nil, nil
	}
	if err != nil {
		return nil, err
	}

	rows, err := s.db.Query(`
		SELECT id, sample_id, page_number, bw_area, color_area, print_area, thumbnail,
		       labeled_price, labeled_by, labeled_at
		FROM print_pricing_pages WHERE sample_id = $1 ORDER BY page_number`, id)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	for rows.Next() {
		p := types.PrintPricingPage{}
		var thumb []byte
		if err := rows.Scan(&p.ID, &p.SampleID, &p.PageNumber, &p.BWArea, &p.ColorArea, &p.PrintArea,
			&thumb, &p.LabeledPrice, &p.LabeledBy, &p.LabeledAt); err != nil {
			return nil, err
		}
		if thumb != nil {
			p.ThumbnailBase64 = base64.StdEncoding.EncodeToString(thumb)
		}
		sample.Pages = append(sample.Pages, p)
	}
	return &sample, rows.Err()
}

func (s *Store) DeleteSample(id string) error {
	_, err := s.db.Exec(`DELETE FROM print_pricing_samples WHERE id = $1`, id)
	return err
}

func (s *Store) SetPageLabel(pageID string, price int, labeledBy *int) (*types.PrintPricingPage, error) {
	p := types.PrintPricingPage{}
	err := s.db.QueryRow(`
		UPDATE print_pricing_pages
		SET labeled_price = $2, labeled_by = $3, labeled_at = $4, updated_at = $4
		WHERE id = $1
		RETURNING id, sample_id, page_number, bw_area, color_area, print_area, labeled_price, labeled_by, labeled_at`,
		pageID, price, labeledBy, time.Now(),
	).Scan(&p.ID, &p.SampleID, &p.PageNumber, &p.BWArea, &p.ColorArea, &p.PrintArea,
		&p.LabeledPrice, &p.LabeledBy, &p.LabeledAt)
	if err == sql.ErrNoRows {
		return nil, nil
	}
	return &p, err
}
```

- [ ] **Step 5: Write the failing store test**

```go
// services/printpricing/store_test.go
package printpricing

import (
	"testing"

	"github.com/sae-project/artivity-server/configs"
	"github.com/sae-project/artivity-server/db"
	"github.com/sae-project/artivity-server/types"
)

func newTestStore(t *testing.T) *Store {
	t.Helper()
	conn, err := db.NewPostgresStorage(configs.Envs.TestDBConnectionString)
	if err != nil {
		t.Fatal(err)
	}
	return NewStore(conn)
}

func TestCreateSampleAndLabelPage(t *testing.T) {
	store := newTestStore(t)

	price := 1500
	sample, err := store.CreateSample(types.CreateSampleInput{
		OriginalFilename: "sample.pdf",
		PageCount:        1,
		Pages: []types.CreateSamplePageInput{
			{PageNumber: 1, BWArea: 0.5, ColorArea: 40.0, ThumbnailBase64: ""},
		},
	})
	if err != nil {
		t.Fatal(err)
	}

	got, err := store.GetSample(sample.ID)
	if err != nil {
		t.Fatal(err)
	}
	if got == nil || len(got.Pages) != 1 {
		t.Fatalf("expected 1 page, got %+v", got)
	}
	if got.Pages[0].PrintArea != 40.5 {
		t.Fatalf("print_area = %v, want 40.5", got.Pages[0].PrintArea)
	}

	labeled, err := store.SetPageLabel(got.Pages[0].ID, price, nil)
	if err != nil {
		t.Fatal(err)
	}
	if labeled.LabeledPrice == nil || *labeled.LabeledPrice != price {
		t.Fatalf("labeled_price = %v, want %d", labeled.LabeledPrice, price)
	}

	if err := store.DeleteSample(sample.ID); err != nil {
		t.Fatal(err)
	}
	if after, _ := store.GetSample(sample.ID); after != nil {
		t.Fatal("sample should be deleted")
	}
}
```

- [ ] **Step 6: Apply migration to the test DB and run the test**

```bash
cd app/artivity-server
scripts/sync_test_db.sh
go test ./services/printpricing/ -run TestCreateSampleAndLabelPage -v
```
Expected: PASS.

- [ ] **Step 7: Run lint and commit**

```bash
make fmt && make lint
git add db/migrations/20261002120000_create_print_pricing_tables.* types/printpricing.go services/printpricing/store.go services/printpricing/store_test.go
git commit -m "feat(print-pricing): migration, types, sample/page store"
```

---

### Task 2: Dataset version snapshot (replace semantics)

**Files:**
- Modify: `services/printpricing/store.go`
- Test: `services/printpricing/store_test.go`

**Interfaces:**
- Consumes: `Store` from Task 1, `types.PrintPricingDatasetVersion`, `types.PrintPricingDatasetRow`.
- Produces: `(*Store).CreateDatasetVersion(createdBy *int, note string) (*types.PrintPricingDatasetVersion, error)`, `(*Store).GetDatasetVersion(id string) (*types.PrintPricingDatasetVersion, error)`, `(*Store).ListDatasetVersions() ([]types.PrintPricingDatasetVersion, error)`, `(*Store).GetDatasetRows(datasetVersionID string) ([]types.PrintPricingDatasetRow, error)`.

- [ ] **Step 1: Write the failing test**

```go
func TestCreateDatasetVersionSnapshotsLabeledPages(t *testing.T) {
	store := newTestStore(t)

	sample, err := store.CreateSample(types.CreateSampleInput{
		OriginalFilename: "ds.pdf", PageCount: 2,
		Pages: []types.CreateSamplePageInput{
			{PageNumber: 1, BWArea: 1, ColorArea: 10},
			{PageNumber: 2, BWArea: 2, ColorArea: 20},
		},
	})
	if err != nil {
		t.Fatal(err)
	}
	got, _ := store.GetSample(sample.ID)
	if _, err := store.SetPageLabel(got.Pages[0].ID, 1000, nil); err != nil {
		t.Fatal(err)
	}

	ds, err := store.CreateDatasetVersion(nil, "first run")
	if err != nil {
		t.Fatal(err)
	}
	if ds.RowCount != 1 {
		t.Fatalf("row_count = %d, want 1 (only labeled pages)", ds.RowCount)
	}
	rows, err := store.GetDatasetRows(ds.ID)
	if err != nil {
		t.Fatal(err)
	}
	if len(rows) != 1 || rows[0].Price != 1000 || rows[0].PrintArea != 11 {
		t.Fatalf("unexpected rows: %+v", rows)
	}
}
```

- [ ] **Step 2: Run to verify it fails**

Run: `go test ./services/printpricing/ -run TestCreateDatasetVersionSnapshotsLabeledPages -v`
Expected: FAIL with "not enough arguments" / undefined method.

- [ ] **Step 3: Implement in `store.go`**

```go
func (s *Store) CreateDatasetVersion(createdBy *int, note string) (*types.PrintPricingDatasetVersion, error) {
	tx, err := s.db.Begin()
	if err != nil {
		return nil, err
	}
	defer tx.Rollback()

	ds := types.PrintPricingDatasetVersion{}
	err = tx.QueryRow(`
		INSERT INTO print_pricing_dataset_versions (created_by, note)
		VALUES ($1, $2)
		RETURNING id, created_by, note, created_at`, createdBy, note,
	).Scan(&ds.ID, &ds.CreatedBy, &ds.Note, &ds.CreatedAt)
	if err != nil {
		return nil, err
	}

	res, err := tx.Exec(`
		INSERT INTO print_pricing_dataset_rows (dataset_version_id, page_id, bw_area, color_area, print_area, price)
		SELECT $1, p.id, p.bw_area, p.color_area, p.print_area, p.labeled_price
		FROM print_pricing_pages p
		JOIN print_pricing_samples s ON s.id = p.sample_id
		WHERE p.labeled_price IS NOT NULL AND s.status <> 'discarded'`, ds.ID)
	if err != nil {
		return nil, err
	}
	affected, err := res.RowsAffected()
	if err != nil {
		return nil, err
	}
	if _, err := tx.Exec(`UPDATE print_pricing_dataset_versions SET row_count = $2 WHERE id = $1`, ds.ID, affected); err != nil {
		return nil, err
	}
	ds.RowCount = int(affected)

	if err := tx.Commit(); err != nil {
		return nil, err
	}
	return &ds, nil
}

func (s *Store) GetDatasetVersion(id string) (*types.PrintPricingDatasetVersion, error) {
	ds := types.PrintPricingDatasetVersion{}
	err := s.db.QueryRow(`
		SELECT id, row_count, created_by, note, created_at
		FROM print_pricing_dataset_versions WHERE id = $1`, id,
	).Scan(&ds.ID, &ds.RowCount, &ds.CreatedBy, &ds.Note, &ds.CreatedAt)
	if err == sql.ErrNoRows {
		return nil, nil
	}
	return &ds, err
}

func (s *Store) ListDatasetVersions() ([]types.PrintPricingDatasetVersion, error) {
	rows, err := s.db.Query(`
		SELECT id, row_count, created_by, note, created_at
		FROM print_pricing_dataset_versions ORDER BY created_at DESC`)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	out := []types.PrintPricingDatasetVersion{}
	for rows.Next() {
		ds := types.PrintPricingDatasetVersion{}
		if err := rows.Scan(&ds.ID, &ds.RowCount, &ds.CreatedBy, &ds.Note, &ds.CreatedAt); err != nil {
			return nil, err
		}
		out = append(out, ds)
	}
	return out, rows.Err()
}

func (s *Store) GetDatasetRows(datasetVersionID string) ([]types.PrintPricingDatasetRow, error) {
	rows, err := s.db.Query(`
		SELECT bw_area, color_area, print_area, price
		FROM print_pricing_dataset_rows WHERE dataset_version_id = $1`, datasetVersionID)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	out := []types.PrintPricingDatasetRow{}
	for rows.Next() {
		r := types.PrintPricingDatasetRow{}
		if err := rows.Scan(&r.BWArea, &r.ColorArea, &r.PrintArea, &r.Price); err != nil {
			return nil, err
		}
		out = append(out, r)
	}
	return out, rows.Err()
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `go test ./services/printpricing/ -run TestCreateDatasetVersionSnapshotsLabeledPages -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add services/printpricing/store.go services/printpricing/store_test.go
git commit -m "feat(print-pricing): dataset version snapshot (replace semantics)"
```

---

### Task 3: Model versions store (candidate, list, activate, active)

**Files:**
- Modify: `services/printpricing/store.go`
- Test: `services/printpricing/store_test.go`

**Interfaces:**
- Consumes: `types.CreateModelVersionInput`, `types.PrintPricingModelVersion`.
- Produces: `(*Store).CreateModelVersion(in types.CreateModelVersionInput) (*types.PrintPricingModelVersion, error)`, `(*Store).ListModelVersions() ([]types.PrintPricingModelVersion, error)`, `(*Store).ActivateModelVersion(id string, activatedBy *int) (*types.PrintPricingModelVersion, error)`, `(*Store).GetActiveModel() (*types.PrintPricingModelVersion, error)`.

- [ ] **Step 1: Write the failing test**

```go
func TestActivateModelVersionIsExclusive(t *testing.T) {
	store := newTestStore(t)

	ds, err := store.CreateDatasetVersion(nil, "seed")
	if err != nil {
		t.Fatal(err)
	}
	base := types.CreateModelVersionInput{
		DatasetVersionID: ds.ID,
		Intercept:        1600, PrintThresholds: []float64{0, 50}, PrintValues: []float64{0, 100},
		ColorThresholds: []float64{0, 50}, ColorValues: []float64{0, 200},
		Metrics: map[string]any{"n_rows": 1},
	}
	v1, err := store.CreateModelVersion(base)
	if err != nil {
		t.Fatal(err)
	}
	v2, err := store.CreateModelVersion(base)
	if err != nil {
		t.Fatal(err)
	}
	if v1.Status != "candidate" {
		t.Fatalf("new version status = %q, want candidate", v1.Status)
	}

	if _, err := store.ActivateModelVersion(v1.ID, nil); err != nil {
		t.Fatal(err)
	}
	if _, err := store.ActivateModelVersion(v2.ID, nil); err != nil {
		t.Fatal(err)
	}

	active, err := store.GetActiveModel()
	if err != nil {
		t.Fatal(err)
	}
	if active == nil || active.ID != v2.ID {
		t.Fatalf("active = %+v, want %s", active, v2.ID)
	}

	all, err := store.ListModelVersions()
	if err != nil {
		t.Fatal(err)
	}
	activeCount := 0
	for _, m := range all {
		if m.Status == "active" {
			activeCount++
		}
	}
	if activeCount != 1 {
		t.Fatalf("active count = %d, want 1", activeCount)
	}
}
```

- [ ] **Step 2: Run to verify it fails**

Run: `go test ./services/printpricing/ -run TestActivateModelVersionIsExclusive -v`
Expected: FAIL (undefined methods).

- [ ] **Step 3: Implement in `store.go`**

```go
func marshalFloats(v []float64) ([]byte, error) { return json.Marshal(v) }

func (s *Store) scanModelVersion(row interface {
	Scan(dest ...any) error
}) (*types.PrintPricingModelVersion, error) {
	m := types.PrintPricingModelVersion{}
	var pt, pv, ct, cv, metrics []byte
	if err := row.Scan(&m.ID, &m.DatasetVersion, &m.Status, &m.Intercept, &pt, &pv, &ct, &cv,
		&metrics, &m.CreatedBy, &m.CreatedAt, &m.ActivatedAt, &m.ActivatedBy); err != nil {
		return nil, err
	}
	_ = json.Unmarshal(pt, &m.PrintThresholds)
	_ = json.Unmarshal(pv, &m.PrintValues)
	_ = json.Unmarshal(ct, &m.ColorThresholds)
	_ = json.Unmarshal(cv, &m.ColorValues)
	_ = json.Unmarshal(metrics, &m.Metrics)
	return &m, nil
}

const modelVersionColumns = `id, dataset_version_id, status, intercept,
	print_thresholds, print_values, color_thresholds, color_values, metrics,
	created_by, created_at, activated_at, activated_by`

func (s *Store) CreateModelVersion(in types.CreateModelVersionInput) (*types.PrintPricingModelVersion, error) {
	pt, _ := marshalFloats(in.PrintThresholds)
	pv, _ := marshalFloats(in.PrintValues)
	ct, _ := marshalFloats(in.ColorThresholds)
	cv, _ := marshalFloats(in.ColorValues)
	metrics, err := json.Marshal(in.Metrics)
	if err != nil {
		return nil, err
	}
	return s.scanModelVersion(s.db.QueryRow(`
		INSERT INTO print_pricing_model_versions
			(dataset_version_id, intercept, print_thresholds, print_values, color_thresholds, color_values, metrics, created_by)
		VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
		RETURNING `+modelVersionColumns,
		in.DatasetVersionID, in.Intercept, pt, pv, ct, cv, metrics, in.CreatedBy))
}

func (s *Store) ListModelVersions() ([]types.PrintPricingModelVersion, error) {
	rows, err := s.db.Query(`SELECT ` + modelVersionColumns + ` FROM print_pricing_model_versions ORDER BY created_at DESC`)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	out := []types.PrintPricingModelVersion{}
	for rows.Next() {
		m, err := s.scanModelVersion(rows)
		if err != nil {
			return nil, err
		}
		out = append(out, *m)
	}
	return out, rows.Err()
}

func (s *Store) ActivateModelVersion(id string, activatedBy *int) (*types.PrintPricingModelVersion, error) {
	tx, err := s.db.Begin()
	if err != nil {
		return nil, err
	}
	defer tx.Rollback()

	if _, err := tx.Exec(`UPDATE print_pricing_model_versions SET status = 'archived' WHERE status = 'active' AND id <> $1`, id); err != nil {
		return nil, err
	}
	m, err := s.scanModelVersion(tx.QueryRow(`
		UPDATE print_pricing_model_versions
		SET status = 'active', activated_at = CURRENT_TIMESTAMP, activated_by = $2
		WHERE id = $1
		RETURNING `+modelVersionColumns, id, activatedBy))
	if err == sql.ErrNoRows {
		return nil, nil
	}
	if err != nil {
		return nil, err
	}
	if err := tx.Commit(); err != nil {
		return nil, err
	}
	return m, nil
}

func (s *Store) GetActiveModel() (*types.PrintPricingModelVersion, error) {
	m, err := s.scanModelVersion(s.db.QueryRow(`SELECT ` + modelVersionColumns + ` FROM print_pricing_model_versions WHERE status = 'active' LIMIT 1`))
	if err == sql.ErrNoRows {
		return nil, nil
	}
	return m, err
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `go test ./services/printpricing/ -run TestActivateModelVersionIsExclusive -v`
Expected: PASS. If it fails with a unique-violation on the partial index, the archive-before-activate order is broken.

- [ ] **Step 5: Run the whole package and commit**

```bash
go test ./services/printpricing/ -v
git add services/printpricing/store.go services/printpricing/store_test.go
git commit -m "feat(print-pricing): model versions store with single-active invariant"
```

---

### Task 4: Service + owner HTTP handlers/routes

**Files:**
- Create: `services/printpricing/service.go`
- Create: `services/printpricing/handler.go`
- Create: `services/printpricing/routes.go`
- Test: `services/printpricing/routes_test.go`

**Interfaces:**
- Consumes: `Store` (Tasks 1–3), `types.UserStore`, `auth.WithRoleJWTAuth`.
- Produces: `NewService(db *sql.DB) *Service`, `NewHandler(userStore types.UserStore, service *Service) *Handler`, `(*Handler).RegisterRoutes(router *mux.Router)`.
- Store interface consumed by `Service`:

```go
type Store interface {
	CreateSample(in types.CreateSampleInput) (*types.PrintPricingSample, error)
	ListSamples() ([]types.PrintPricingSample, error)
	GetSample(id string) (*types.PrintPricingSample, error)
	DeleteSample(id string) error
	SetPageLabel(pageID string, price int, labeledBy *int) (*types.PrintPricingPage, error)
	CreateDatasetVersion(createdBy *int, note string) (*types.PrintPricingDatasetVersion, error)
	GetDatasetVersion(id string) (*types.PrintPricingDatasetVersion, error)
	ListDatasetVersions() ([]types.PrintPricingDatasetVersion, error)
	GetDatasetRows(datasetVersionID string) ([]types.PrintPricingDatasetRow, error)
	CreateModelVersion(in types.CreateModelVersionInput) (*types.PrintPricingModelVersion, error)
	ListModelVersions() ([]types.PrintPricingModelVersion, error)
	ActivateModelVersion(id string, activatedBy *int) (*types.PrintPricingModelVersion, error)
	GetActiveModel() (*types.PrintPricingModelVersion, error)
}
```

- [ ] **Step 1: Write `service.go`**

```go
package printpricing

import (
	"database/sql"
	"errors"

	"github.com/sae-project/artivity-server/types"
)

var (
	ErrNotFound     = errors.New("not found")
	ErrBelowMinimum = errors.New("below minimum training rows")
)

type Service struct {
	db    *sql.DB
	store Store
}

func NewService(db *sql.DB) *Service { return &Service{db: db, store: NewStore(db)} }

func (s *Service) CreateSample(in types.CreateSampleInput) (*types.PrintPricingSample, error) {
	return s.store.CreateSample(in)
}

func (s *Service) ListSamples() ([]types.PrintPricingSample, error) { return s.store.ListSamples() }

func (s *Service) GetSample(id string) (*types.PrintPricingSample, error) { return s.store.GetSample(id) }

func (s *Service) DeleteSample(id string) error { return s.store.DeleteSample(id) }

func (s *Service) SetPageLabel(pageID string, price int, labeledBy *int) (*types.PrintPricingPage, error) {
	return s.store.SetPageLabel(pageID, price, labeledBy)
}

func (s *Service) CreateDatasetVersion(createdBy *int, note string) (*types.PrintPricingDatasetVersion, error) {
	return s.store.CreateDatasetVersion(createdBy, note)
}

func (s *Service) GetDatasetVersion(id string) (*types.PrintPricingDatasetVersion, error) {
	return s.store.GetDatasetVersion(id)
}

func (s *Service) ListDatasetVersions() ([]types.PrintPricingDatasetVersion, error) {
	return s.store.ListDatasetVersions()
}

func (s *Service) GetDatasetRows(id string) ([]types.PrintPricingDatasetRow, error) {
	return s.store.GetDatasetRows(id)
}

func (s *Service) ListModelVersions() ([]types.PrintPricingModelVersion, error) {
	return s.store.ListModelVersions()
}

func (s *Service) ActivateModelVersion(id string, activatedBy *int) (*types.PrintPricingModelVersion, error) {
	return s.store.ActivateModelVersion(id, activatedBy)
}

func (s *Service) GetActiveModel() (*types.PrintPricingModelVersion, error) {
	return s.store.GetActiveModel()
}
```

- [ ] **Step 2: Write `handler.go` and `routes.go`**

```go
// handler.go
package printpricing

import (
	"net/http"

	"github.com/gorilla/mux"

	"github.com/sae-project/artivity-server/services/auth"
	"github.com/sae-project/artivity-server/types"
	"github.com/sae-project/artivity-server/utils"
)

type Handler struct {
	userStore types.UserStore
	service   *Service
}

func NewHandler(userStore types.UserStore, service *Service) *Handler {
	return &Handler{userStore: userStore, service: service}
}

func (h *Handler) handleCreateSample(w http.ResponseWriter, r *http.Request) {
	var in types.CreateSampleInput
	if err := utils.ParseJSON(r.Body, &in); err != nil {
		utils.WriteAppError(w, utils.NewBadRequestError(err.Error()))
		return
	}
	if validationErrors, ok := utils.ValidateStruct(in); !ok {
		utils.WriteValidationErrorResponse(w, validationErrors)
		return
	}
	internal := auth.GetInternalUserIDFromContext(r.Context())
	in.UploadedBy = &internal
	sample, err := h.service.CreateSample(in)
	if err != nil {
		utils.WriteAppError(w, utils.NewInternalError("failed to create sample", err))
		return
	}
	utils.WriteDataResponse(w, http.StatusCreated, sample)
}

func (h *Handler) handleListSamples(w http.ResponseWriter, r *http.Request) {
	samples, err := h.service.ListSamples()
	if err != nil {
		utils.WriteAppError(w, utils.NewInternalError("failed to list samples", err))
		return
	}
	utils.WriteDataResponse(w, http.StatusOK, samples)
}

func (h *Handler) handleGetSample(w http.ResponseWriter, r *http.Request) {
	id := mux.Vars(r)["sampleID"]
	if !utils.IsValidUUID(id) {
		utils.WriteAppError(w, utils.NewBadRequestError("invalid sample id"))
		return
	}
	sample, err := h.service.GetSample(id)
	if err != nil {
		utils.WriteAppError(w, utils.NewInternalError("failed to get sample", err))
		return
	}
	if sample == nil {
		utils.WriteAppError(w, utils.NewNotFoundError("sample"))
		return
	}
	utils.WriteDataResponse(w, http.StatusOK, sample)
}

func (h *Handler) handleDeleteSample(w http.ResponseWriter, r *http.Request) {
	id := mux.Vars(r)["sampleID"]
	if !utils.IsValidUUID(id) {
		utils.WriteAppError(w, utils.NewBadRequestError("invalid sample id"))
		return
	}
	if err := h.service.DeleteSample(id); err != nil {
		utils.WriteAppError(w, utils.NewInternalError("failed to delete sample", err))
		return
	}
	utils.WriteDataResponse(w, http.StatusOK, nil)
}

func (h *Handler) handlePatchPage(w http.ResponseWriter, r *http.Request) {
	id := mux.Vars(r)["pageID"]
	if !utils.IsValidUUID(id) {
		utils.WriteAppError(w, utils.NewBadRequestError("invalid page id"))
		return
	}
	var body struct {
		LabeledPrice int `json:"labeled_price" validate:"required,min=1"`
	}
	if err := utils.ParseJSON(r.Body, &body); err != nil {
		utils.WriteAppError(w, utils.NewBadRequestError(err.Error()))
		return
	}
	if validationErrors, ok := utils.ValidateStruct(body); !ok {
		utils.WriteValidationErrorResponse(w, validationErrors)
		return
	}
	internal := auth.GetInternalUserIDFromContext(r.Context())
	page, err := h.service.SetPageLabel(id, body.LabeledPrice, &internal)
	if err != nil {
		utils.WriteAppError(w, utils.NewInternalError("failed to label page", err))
		return
	}
	if page == nil {
		utils.WriteAppError(w, utils.NewNotFoundError("page"))
		return
	}
	utils.WriteDataResponse(w, http.StatusOK, page)
}

func (h *Handler) handleCreateDatasetVersion(w http.ResponseWriter, r *http.Request) {
	var body struct {
		Note string `json:"note"`
	}
	_ = utils.ParseJSON(r.Body, &body) // note is optional
	internal := auth.GetInternalUserIDFromContext(r.Context())
	ds, err := h.service.CreateDatasetVersion(&internal, body.Note)
	if err != nil {
		utils.WriteAppError(w, utils.NewInternalError("failed to create dataset version", err))
		return
	}
	utils.WriteDataResponse(w, http.StatusCreated, ds)
}

func (h *Handler) handleListDatasetVersions(w http.ResponseWriter, r *http.Request) {
	versions, err := h.service.ListDatasetVersions()
	if err != nil {
		utils.WriteAppError(w, utils.NewInternalError("failed to list dataset versions", err))
		return
	}
	utils.WriteDataResponse(w, http.StatusOK, versions)
}

func (h *Handler) handleGetDatasetVersion(w http.ResponseWriter, r *http.Request) {
	id := mux.Vars(r)["datasetID"]
	if !utils.IsValidUUID(id) {
		utils.WriteAppError(w, utils.NewBadRequestError("invalid dataset id"))
		return
	}
	ds, err := h.service.GetDatasetVersion(id)
	if err != nil {
		utils.WriteAppError(w, utils.NewInternalError("failed to get dataset version", err))
		return
	}
	if ds == nil {
		utils.WriteAppError(w, utils.NewNotFoundError("dataset version"))
		return
	}
	rows, err := h.service.GetDatasetRows(id)
	if err != nil {
		utils.WriteAppError(w, utils.NewInternalError("failed to get dataset rows", err))
		return
	}
	utils.WriteDataResponse(w, http.StatusOK, map[string]any{"dataset": ds, "rows": rows})
}

func (h *Handler) handleListModelVersions(w http.ResponseWriter, r *http.Request) {
	versions, err := h.service.ListModelVersions()
	if err != nil {
		utils.WriteAppError(w, utils.NewInternalError("failed to list model versions", err))
		return
	}
	utils.WriteDataResponse(w, http.StatusOK, versions)
}

func (h *Handler) handleActivateModelVersion(w http.ResponseWriter, r *http.Request) {
	id := mux.Vars(r)["versionID"]
	if !utils.IsValidUUID(id) {
		utils.WriteAppError(w, utils.NewBadRequestError("invalid version id"))
		return
	}
	internal := auth.GetInternalUserIDFromContext(r.Context())
	version, err := h.service.ActivateModelVersion(id, &internal)
	if err != nil {
		utils.WriteAppError(w, utils.NewInternalError("failed to activate model version", err))
		return
	}
	if version == nil {
		utils.WriteAppError(w, utils.NewNotFoundError("model version"))
		return
	}
	utils.WriteDataResponse(w, http.StatusOK, version)
}

// routes.go
func (h *Handler) RegisterRoutes(router *mux.Router) {
	owner := func(fn http.HandlerFunc) http.HandlerFunc {
		return auth.WithRoleJWTAuth(fn, h.userStore, []string{"owner"})
	}
	router.HandleFunc("/print-pricing/samples", owner(h.handleCreateSample)).Methods(http.MethodPost)
	router.HandleFunc("/print-pricing/samples", owner(h.handleListSamples)).Methods(http.MethodGet)
	router.HandleFunc("/print-pricing/samples/{sampleID}", owner(h.handleGetSample)).Methods(http.MethodGet)
	router.HandleFunc("/print-pricing/samples/{sampleID}", owner(h.handleDeleteSample)).Methods(http.MethodDelete)
	router.HandleFunc("/print-pricing/pages/{pageID}", owner(h.handlePatchPage)).Methods(http.MethodPatch)
	router.HandleFunc("/print-pricing/dataset-versions", owner(h.handleCreateDatasetVersion)).Methods(http.MethodPost)
	router.HandleFunc("/print-pricing/dataset-versions", owner(h.handleListDatasetVersions)).Methods(http.MethodGet)
	router.HandleFunc("/print-pricing/dataset-versions/{datasetID}", owner(h.handleGetDatasetVersion)).Methods(http.MethodGet)
	router.HandleFunc("/print-pricing/model-versions", owner(h.handleListModelVersions)).Methods(http.MethodGet)
	router.HandleFunc("/print-pricing/model-versions/{versionID}/activate", owner(h.handleActivateModelVersion)).Methods(http.MethodPost)
}
```

- [ ] **Step 3: Write the failing route test (owner allowed, non-owner forbidden)**

```go
// routes_test.go
package printpricing

import (
	"bytes"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"

	"github.com/gorilla/mux"

	"github.com/sae-project/artivity-server/configs"
	"github.com/sae-project/artivity-server/db"
	"github.com/sae-project/artivity-server/services/user"
)

func TestCreateSampleRequiresOwnerRole(t *testing.T) {
	conn, err := db.NewPostgresStorage(configs.Envs.TestDBConnectionString)
	if err != nil {
		t.Fatal(err)
	}
	router := mux.NewRouter()
	NewHandler(user.NewStore(conn), NewService(conn)).RegisterRoutes(router)

	ownerToken, err := user.GetUserToken([]byte(`{"email":"owner@mail.test","password":"password"}`))
	if err != nil {
		t.Fatal(err)
	}

	body := []byte(`{"original_filename":"x.pdf","page_count":1,"pages":[{"page_number":1,"bw_area":1,"color_area":2}]}`)

	t.Run("owner is allowed", func(t *testing.T) {
		req := httptest.NewRequest(http.MethodPost, "/print-pricing/samples", bytes.NewReader(body))
		req.Header.Set("Authorization", "Bearer "+ownerToken)
		rr := httptest.NewRecorder()
		router.ServeHTTP(rr, req)
		if rr.Code != http.StatusCreated {
			t.Fatalf("status = %d, body = %s", rr.Code, rr.Body.String())
		}
		var resp map[string]any
		_ = json.NewDecoder(rr.Body).Decode(&resp)
		if _, ok := resp["data"]; !ok {
			t.Fatal("expected data envelope")
		}
	})

	t.Run("anonymous is rejected", func(t *testing.T) {
		req := httptest.NewRequest(http.MethodPost, "/print-pricing/samples", bytes.NewReader(body))
		rr := httptest.NewRecorder()
		router.ServeHTTP(rr, req)
		if rr.Code != http.StatusForbidden {
			t.Fatalf("status = %d, want 403", rr.Code)
		}
	})
}
```

- [ ] **Step 4: Run the test to verify it fails, then implement until green**

Run: `go test ./services/printpricing/ -run TestCreateSampleRequiresOwnerRole -v`
Expected first: FAIL. After wiring `RegisterRoutes`, expected PASS with owner 201 and anonymous 403.

- [ ] **Step 5: Run package tests, lint, commit**

```bash
go test ./services/printpricing/ -v
make fmt && make lint
git add services/printpricing/service.go services/printpricing/handler.go services/printpricing/routes.go services/printpricing/routes_test.go
git commit -m "feat(print-pricing): owner handlers and routes"
```

---

### Task 5: Service-token `/active-model` endpoint

**Files:**
- Modify: `middleware/apikey.go`
- Modify: `services/printpricing/routes.go`, `services/printpricing/handler.go`
- Test: `services/printpricing/routes_test.go`

**Interfaces:**
- Produces: `middleware.WithPrintPricingServiceToken(handlerFunc http.HandlerFunc) http.HandlerFunc`.
- Route: `GET /print-pricing/active-model` returns `{data: <model>}` or `{data: null}` when no active model.

- [ ] **Step 1: Add the middleware**

```go
// middleware/apikey.go (append)
// WithPrintPricingServiceToken validates X-API-Key against
// PRINT_PRICING_SERVICE_TOKEN. Fail-closed when the env var is unset.
func WithPrintPricingServiceToken(handlerFunc http.HandlerFunc) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		apiKey := r.Header.Get("X-API-Key")
		if apiKey == "" {
			_ = utils.WriteAppError(w, utils.NewUnauthorizedError("missing API key"))
			return
		}
		expected := os.Getenv("PRINT_PRICING_SERVICE_TOKEN")
		if expected == "" {
			utils.Error("[SECURITY] print pricing service token rejected: PRINT_PRICING_SERVICE_TOKEN not configured (fail-closed)")
			_ = utils.WriteErrorResponse(w, http.StatusServiceUnavailable, utils.ErrCodeInternal, "API key not configured on server")
			return
		}
		if !constantTimeCompare(apiKey, expected) {
			_ = utils.WriteAppError(w, utils.NewForbiddenError("invalid API key"))
			return
		}
		handlerFunc(w, r)
	}
}
```

- [ ] **Step 2: Write the failing test**

```go
func TestActiveModelRequiresServiceToken(t *testing.T) {
	conn, _ := db.NewPostgresStorage(configs.Envs.TestDBConnectionString)
	router := mux.NewRouter()
	NewHandler(user.NewStore(conn), NewService(conn)).RegisterRoutes(router)

	t.Setenv("PRINT_PRICING_SERVICE_TOKEN", "svc-test-token")

	req := httptest.NewRequest(http.MethodGet, "/print-pricing/active-model", nil)
	rr := httptest.NewRecorder()
	router.ServeHTTP(rr, req)
	if rr.Code != http.StatusUnauthorized {
		t.Fatalf("missing token status = %d, want 401", rr.Code)
	}

	req = httptest.NewRequest(http.MethodGet, "/print-pricing/active-model", nil)
	req.Header.Set("X-API-Key", "svc-test-token")
	rr = httptest.NewRecorder()
	router.ServeHTTP(rr, req)
	if rr.Code != http.StatusOK {
		t.Fatalf("valid token status = %d, want 200", rr.Code)
	}
}
```

- [ ] **Step 3: Implement the handler + route**

```go
// handler.go (append)
func (h *Handler) handleGetActiveModel(w http.ResponseWriter, r *http.Request) {
	model, err := h.service.GetActiveModel()
	if err != nil {
		utils.WriteAppError(w, utils.NewInternalError("failed to get active model", err))
		return
	}
	utils.WriteDataResponse(w, http.StatusOK, model)
}

// routes.go, inside RegisterRoutes:
router.HandleFunc("/print-pricing/active-model", middleware.WithPrintPricingServiceToken(h.handleGetActiveModel)).Methods(http.MethodGet)
```

- [ ] **Step 4: Run tests, lint, commit**

```bash
go test ./services/printpricing/ ./middleware/ -v
make fmt && make lint
git add middleware/apikey.go services/printpricing/handler.go services/printpricing/routes.go services/printpricing/routes_test.go
git commit -m "feat(print-pricing): service-token active-model endpoint"
```

---

### Task 6: Retrain orchestration (`/retrain`) + trainer client

**Files:**
- Create: `services/printpricing/trainer.go`
- Modify: `services/printpricing/service.go`, `services/printpricing/handler.go`, `services/printpricing/routes.go`
- Modify: `configs/envs.go`
- Test: `services/printpricing/trainer_test.go`, `services/printpricing/routes_test.go`

**Interfaces:**
- Produces: `Trainer` interface `{ Train(ctx context.Context, in TrainRequest) (*TrainResult, error) }`, `NewHTTPTrainer(baseURL, token string) *HTTPTrainer`.
- `Service.InjectTrainer(t Trainer)` for tests (the production constructor wires `NewHTTPTrainer(configs.Envs.APIModelRegressionURL, configs.Envs.PrintPricingServiceToken)` in the registrar).
- `Service.Retrain(ctx context.Context, createdBy *int) (*types.PrintPricingModelVersion, error)`.
- Route: `POST /print-pricing/retrain` (owner).

- [ ] **Step 1: Add config fields**

```go
// configs/envs.go — Config struct (near PrintRelayToken):
	APIModelRegressionURL    string
	PrintPricingServiceToken string
	MinTrainingRows          int

// initConfig() return literal (near PrintRelayToken: ...):
	APIModelRegressionURL:    getEnv("API_MODEL_REGRESSION_URL", ""),
	PrintPricingServiceToken: getEnv("PRINT_PRICING_SERVICE_TOKEN", ""),
	MinTrainingRows:          int(getEnvAsInt("MIN_TRAINING_ROWS", 20)),
```

- [ ] **Step 2: Write the trainer client and failing client test**

```go
// trainer.go
package printpricing

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"net/http"
	"time"
)

type TrainRequest struct {
	Rows      []TrainRow `json:"rows"`
	PriceStep int        `json:"price_step"`
	FloorBW   int        `json:"price_floor_bw"`
	FloorColor int       `json:"price_floor_color"`
	Cap       *int       `json:"price_cap"`
}

type TrainRow struct {
	BWArea    float64 `json:"bw_area"`
	ColorArea float64 `json:"color_area"`
	PrintArea float64 `json:"print_area"`
	Price     float64 `json:"price"`
}

type TrainResult struct {
	Intercept       float64        `json:"intercept"`
	PrintThresholds []float64      `json:"print_thresholds"`
	PrintValues     []float64      `json:"print_values"`
	ColorThresholds []float64      `json:"color_thresholds"`
	ColorValues     []float64      `json:"color_values"`
	Metrics         map[string]any `json:"metrics"`
}

type Trainer interface {
	Train(ctx context.Context, in TrainRequest) (*TrainResult, error)
}

type HTTPTrainer struct {
	baseURL string
	token   string
	client  *http.Client
}

func NewHTTPTrainer(baseURL, token string) *HTTPTrainer {
	return &HTTPTrainer{baseURL: baseURL, token: token, client: &http.Client{Timeout: 60 * time.Second}}
}

func (c *HTTPTrainer) Train(ctx context.Context, in TrainRequest) (*TrainResult, error) {
	body, err := json.Marshal(in)
	if err != nil {
		return nil, err
	}
	req, err := http.NewRequestWithContext(ctx, http.MethodPost, c.baseURL+"/internal/train", bytes.NewReader(body))
	if err != nil {
		return nil, err
	}
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("X-API-Key", c.token)
	resp, err := c.client.Do(req)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()
	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("trainer returned status %d", resp.StatusCode)
	}
	var envelope struct {
		Data TrainResult `json:"data"`
	}
	if err := json.NewDecoder(resp.Body).Decode(&envelope); err != nil {
		return nil, err
	}
	return &envelope.Data, nil
}
```

```go
// trainer_test.go
package printpricing

import (
	"context"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"
)

func TestHTTPTrainerParsesDataEnvelope(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.Header.Get("X-API-Key") != "tok" {
			t.Errorf("missing service token")
		}
		_ = json.NewEncoder(w).Encode(map[string]any{
			"data": TrainResult{Intercept: 1600, Metrics: map[string]any{"n_rows": float64(3)}},
		})
	}))
	defer srv.Close()

	got, err := NewHTTPTrainer(srv.URL, "tok").Train(context.Background(), TrainRequest{})
	if err != nil {
		t.Fatal(err)
	}
	if got.Intercept != 1600 {
		t.Fatalf("intercept = %v, want 1600", got.Intercept)
	}
}
```

- [ ] **Step 3: Implement `Service.Retrain` with advisory lock + min rows**

```go
// service.go additions
func (s *Service) InjectTrainer(t Trainer) { s.trainer = t }

func (s *Service) Retrain(ctx context.Context, createdBy *int) (*types.PrintPricingModelVersion, error) {
	conn, err := s.db.Conn(ctx)
	if err != nil {
		return nil, err
	}
	defer conn.Close()

	var locked bool
	if err := conn.QueryRowContext(ctx, `SELECT pg_try_advisory_lock($1)`, advisoryLockKey).Scan(&locked); err != nil {
		return nil, err
	}
	if !locked {
		return nil, ErrRetrainInProgress
	}
	defer conn.ExecContext(context.Background(), `SELECT pg_advisory_unlock($1)`, advisoryLockKey)

	ds, err := s.store.CreateDatasetVersion(createdBy, "retrain")
	if err != nil {
		return nil, err
	}
	if ds.RowCount < s.minTrainingRows {
		return nil, ErrBelowMinimum
	}
	rows, err := s.store.GetDatasetRows(ds.ID)
	if err != nil {
		return nil, err
	}

	trainRows := make([]TrainRow, 0, len(rows))
	for _, r := range rows {
		trainRows = append(trainRows, TrainRow{BWArea: r.BWArea, ColorArea: r.ColorArea, PrintArea: r.PrintArea, Price: r.Price})
	}
	result, err := s.trainer.Train(ctx, TrainRequest{
		Rows: trainRows, PriceStep: s.priceStep, FloorBW: s.floorBW, FloorColor: s.floorColor, Cap: s.cap,
	})
	if err != nil {
		return nil, err
	}
	return s.store.CreateModelVersion(types.CreateModelVersionInput{
		DatasetVersionID: ds.ID,
		Intercept:        result.Intercept,
		PrintThresholds:  result.PrintThresholds,
		PrintValues:      result.PrintValues,
		ColorThresholds:  result.ColorThresholds,
		ColorValues:      result.ColorValues,
		Metrics:          result.Metrics,
		CreatedBy:        createdBy,
	})
}
```

Add to `service.go` struct + errors:

```go
const advisoryLockKey int64 = 918273645

var ErrRetrainInProgress = errors.New("retrain in progress")

type Service struct {
	db              *sql.DB
	store           Store
	trainer         Trainer
	minTrainingRows int
	priceStep       int
	floorBW         int
	floorColor      int
	cap             *int
}

func NewService(db *sql.DB) *Service {
	return &Service{
		db: db, store: NewStore(db),
		minTrainingRows: 20, priceStep: 250, floorBW: 300, floorColor: 500, cap: ptr(3000),
	}
}

// WithMinTrainingRows overrides the retrain floor; the registrar passes
// configs.Envs.MinTrainingRows so the value is env-driven.
func (s *Service) WithMinTrainingRows(n int) *Service {
	if n > 0 {
		s.minTrainingRows = n
	}
	return s
}

func ptr[T any](v T) *T { return &v }
```

- [ ] **Step 4: Add handler + route, write the route test**

```go
// handler.go
func (h *Handler) handleRetrain(w http.ResponseWriter, r *http.Request) {
	internal := auth.GetInternalUserIDFromContext(r.Context())
	version, err := h.service.Retrain(r.Context(), &internal)
	switch {
	case errors.Is(err, ErrRetrainInProgress):
		utils.WriteAppError(w, utils.NewConflictError("retrain already in progress"))
	case errors.Is(err, ErrBelowMinimum):
		utils.WriteAppError(w, utils.NewBadRequestError("not enough labeled pages to retrain"))
	case err != nil:
		utils.WriteAppError(w, utils.NewInternalError("retrain failed", err))
	default:
		utils.WriteDataResponse(w, http.StatusOK, version)
	}
}

// routes.go
router.HandleFunc("/print-pricing/retrain", owner(h.handleRetrain)).Methods(http.MethodPost)
```

```go
// routes_test.go — inject a stub trainer so no network is needed
type stubTrainer struct{ result TrainResult }

func (s stubTrainer) Train(context.Context, TrainRequest) (*TrainResult, error) {
	return &s.result, nil
}

func TestRetrainRejectsWhenBelowMinimum(t *testing.T) {
	conn, _ := db.NewPostgresStorage(configs.Envs.TestDBConnectionString)
	svc := NewService(conn)
	svc.minTrainingRows = 20
	if _, err := svc.CreateDatasetVersion(nil, "x"); err != nil {
		t.Fatal(err)
	}
	if _, err := svc.Retrain(context.Background(), nil); !errors.Is(err, ErrBelowMinimum) {
		t.Fatalf("err = %v, want ErrBelowMinimum", err)
	}
}
```

- [ ] **Step 5: Run tests, lint, commit**

```bash
go test ./services/printpricing/ -v
make fmt && make lint
git add configs/envs.go services/printpricing/
git commit -m "feat(print-pricing): retrain orchestration with advisory lock and min-rows guard"
```

---

### Task 7: Registrar wiring, env example, API docs

**Files:**
- Create: `cmd/api/registrar_print_pricing.go`
- Modify: `cmd/api/api.go`
- Modify: `.env.example`
- Modify: `docs/API_OVERVIEW.md`
- Test: existing full gates.

**Interfaces:**
- Consumes: `printpricing.NewService`, `.NewHandler`, `.InjectTrainer`, `.RegisterRoutes`, `configs.Envs`.

- [ ] **Step 1: Write the registrar**

```go
// cmd/api/registrar_print_pricing.go
package api

import (
	"github.com/gorilla/mux"

	"github.com/sae-project/artivity-server/configs"
	"github.com/sae-project/artivity-server/services/printpricing"
)

func registerPrintPricing(subrouter *mux.Router, reg *Registry) {
	service := printpricing.NewService(reg.DB).
		WithMinTrainingRows(configs.Envs.MinTrainingRows)
	service.InjectTrainer(printpricing.NewHTTPTrainer(
		configs.Envs.APIModelRegressionURL,
		configs.Envs.PrintPricingServiceToken,
	))
	printpricing.NewHandler(reg.UserStore, service).RegisterRoutes(subrouter)
}
```

- [ ] **Step 2: Call it from `api.go`**

```go
// cmd/api/api.go — after registerAI(subrouter, reg):
	registerPrintPricing(subrouter, reg)
```

- [ ] **Step 3: Document env vars**

```bash
# .env.example (append)
# Print pricing retrain integration
# In-network address of the Dokploy compose service (see docker-compose.yml).
API_MODEL_REGRESSION_URL=http://api-model-regression:8080
PRINT_PRICING_SERVICE_TOKEN=change-me-print-pricing-service-token
MIN_TRAINING_ROWS=20
```

- [ ] **Step 4: Run the full gate**

```bash
make fmt && make lint && make test-unit
scripts/sync_test_db.sh && go test ./services/printpricing/ -v
```
Expected: all PASS. `make test-integration` may be run if the local DB policy allows.

- [ ] **Step 5: Add the routes to `docs/API_OVERVIEW.md` and commit**

List the seven owner routes plus `GET /active-model` under a "Print Pricing" section.

```bash
git add cmd/api/registrar_print_pricing.go cmd/api/api.go .env.example docs/API_OVERVIEW.md
git commit -m "feat(print-pricing): wire module into the API and document config"
```

---

## Notes for the executor

- `utils.NewConflictError` and `utils.NewNotFoundError` exist in `utils/errors.go`; if `NewConflictError` is missing, add it there alongside the other constructors in a one-line change.
- `auth.GetInternalUserIDFromContext` is defined in `services/auth/jwt.go:331`.
- Integration tests need the test DB: run `scripts/sync_test_db.sh` first (it drops/recreates `artivity_test`; do not run while you need the live dev DB).
- If `WithRoleJWTAuth` returns 403 for the owner token, check the role name comparison in `services/auth/jwt.go:166`.
