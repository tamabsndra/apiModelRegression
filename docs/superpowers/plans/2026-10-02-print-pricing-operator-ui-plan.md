# Operator Labeling UI (web) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a hash-routed owner area to the existing React SPA for login, sample upload + labeling, retrain preview, and model-version activation/rollback.

**Architecture:** Keep the single-page app and add a `#/operator` route handled in `App.tsx`. A small `useHashRoute` hook drives navigation. Operator components live under `components/operator/` and call the Flask `/api/label/*` routes with `credentials: "include"` and `X-Requested-With`. No new dependencies.

**Tech Stack:** Vite, React 18, TypeScript, Tailwind v4, daisyUI 5, motion.

**Spec:** `docs/superpowers/specs/2026-10-02-print-pricing-labeling-retrain-design.md`

## Global Constraints

- No new npm dependencies; reuse `motion`, existing components, and the Artivity design tokens (neu surfaces, ink/blue/rose palette, Nunito/Geist/Questrial fonts).
- Indonesian copy; explicit form labels; focus order; errors not by color alone; touch targets >= 44px.
- All mutating requests send `X-Requested-With: XMLHttpRequest` and `credentials: "include"`.
- The public calculator stays the default view; `/api/v3/upload` flow must not regress.
- Gate: `npm run typecheck && npm run build` (via `make web-build`).

---

### Task 1: Label API client + shared operator types

**Files:**
- Modify: `web/src/lib/types.ts`
- Create: `web/src/lib/labelApi.ts`

**Interfaces:**
- Produces types: `OperatorUser`, `SampleSummary`, `SampleDetail`, `SamplePage`, `DatasetVersion`, `ModelVersion`, `RetrainResult`.
- Produces functions: `labelApi.login`, `logout`, `me`, `listSamples`, `getSample`, `deleteSample`, `patchPage`, `uploadSample`, `retrain`, `listModelVersions`, `activateModelVersion`.

- [ ] **Step 1: Append operator types to `web/src/lib/types.ts`**

```ts
export type OperatorUser = { id: string; name?: string; email?: string; role?: { name: string } };

export type SamplePage = {
  id: string;
  sample_id: string;
  page_number: number;
  bw_area: number;
  color_area: number;
  print_area: number;
  thumbnail_base64?: string;
  labeled_price: number | null;
};

export type SampleSummary = {
  id: string;
  original_filename: string;
  page_count: number;
  status: "labeling" | "completed" | "discarded";
  created_at: string;
};

export type SampleDetail = SampleSummary & { pages: SamplePage[] };

export type DatasetVersion = {
  id: string;
  row_count: number;
  note?: string;
  created_at: string;
};

export type ModelVersion = {
  id: string;
  dataset_version_id: string;
  status: "candidate" | "active" | "archived";
  intercept: number;
  metrics: { n_rows?: number; mean_abs_error?: number; max_abs_error?: number; p95_abs_error?: number };
  created_at: string;
  activated_at?: string | null;
};

export type RetrainResult = ModelVersion;
```

- [ ] **Step 2: Create `web/src/lib/labelApi.ts`**

```ts
import type {
  ModelVersion,
  OperatorUser,
  RetrainResult,
  SampleDetail,
  SampleSummary,
} from "./types";

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const method = (init.method ?? "GET").toUpperCase();
  const headers: Record<string, string> = { ...(init.headers as Record<string, string>) };
  if (method !== "GET" && method !== "HEAD") {
    headers["X-Requested-With"] = "XMLHttpRequest";
  }
  const res = await fetch(path, { ...init, headers, credentials: "include" });
  if (res.status === 204) return undefined as T;
  const body = await res.json().catch(() => null);
  if (!res.ok) {
    const detail = (body as { detail?: string } | null)?.detail ?? `HTTP ${res.status}`;
    throw new Error(detail);
  }
  return body as T;
}

export const labelApi = {
  login: (email: string, password: string) =>
    request<{ user: OperatorUser }>("/api/label/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    }),

  logout: () => request<{ ok: boolean }>("/api/label/auth/logout", { method: "POST" }),

  me: () => request<{ user: OperatorUser }>("/api/label/auth/me"),

  listSamples: () => request<SampleSummary[]>("/api/label/samples"),

  getSample: (id: string) => request<SampleDetail>(`/api/label/samples/${id}`),

  deleteSample: (id: string) => request<void>(`/api/label/samples/${id}`, { method: "DELETE" }),

  patchPage: (pageId: string, labeledPrice: number) =>
    request(`/api/label/pages/${pageId}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ labeled_price: labeledPrice }),
    }),

  retrain: () => request<RetrainResult>("/api/label/retrain", { method: "POST" }),

  listModelVersions: () => request<ModelVersion[]>("/api/label/model-versions"),

  activateModelVersion: (id: string) =>
    request<ModelVersion>(`/api/label/model-versions/${id}/activate`, { method: "POST" }),
};

export function uploadSample(
  file: File,
  onProgress?: (percent: number) => void,
): Promise<SampleDetail> {
  return new Promise((resolve, reject) => {
    const form = new FormData();
    form.append("file", file);
    const xhr = new XMLHttpRequest();
    xhr.open("POST", "/api/label/samples");
    xhr.withCredentials = true;
    xhr.setRequestHeader("X-Requested-With", "XMLHttpRequest");
    xhr.upload.addEventListener("progress", (event) => {
      if (event.lengthComputable && onProgress) {
        onProgress(Math.round((event.loaded / event.total) * 100));
      }
    });
    xhr.addEventListener("load", () => {
      let body: unknown;
      try {
        body = JSON.parse(xhr.responseText);
      } catch {
        reject(new Error("Respons server tidak bisa dibaca."));
        return;
      }
      if (xhr.status >= 200 && xhr.status < 300) resolve(body as SampleDetail);
      else reject(new Error((body as { detail?: string })?.detail ?? "Upload gagal."));
    });
    xhr.addEventListener("error", () => reject(new Error("Tidak bisa menghubungi server.")));
    xhr.send(form);
  });
}
```

- [ ] **Step 3: Typecheck**

Run: `cd web && npm run typecheck`
Expected: PASS (no errors).

- [ ] **Step 4: Commit**

```bash
git add web/src/lib/types.ts web/src/lib/labelApi.ts
git commit -m "feat(web): operator label API client and types"
```

---

### Task 2: Hash routing + operator link

**Files:**
- Create: `web/src/lib/useHashRoute.ts`
- Modify: `web/src/App.tsx`
- Modify: `web/src/components/Header.tsx`

**Interfaces:**
- Produces: `useHashRoute(): string` returning the current hash path (e.g. `/operator`).

- [ ] **Step 1: Create the hook**

```ts
import { useEffect, useState } from "react";

function current(): string {
  const raw = window.location.hash.replace(/^#/, "");
  return raw === "" ? "/" : raw;
}

export function useHashRoute(): string {
  const [route, setRoute] = useState(current);
  useEffect(() => {
    const onChange = () => setRoute(current());
    window.addEventListener("hashchange", onChange);
    return () => window.removeEventListener("hashchange", onChange);
  }, []);
  return route;
}
```

- [ ] **Step 2: Wire routing into `App.tsx`**

At the top of the component add:

```tsx
import { useHashRoute } from "./lib/useHashRoute";
import { OperatorApp } from "./components/operator/OperatorApp";

// inside App():
const route = useHashRoute();
```

Then, immediately before the existing `return (`:

```tsx
if (route === "/operator") {
  return <OperatorApp />;
}
```

- [ ] **Step 3: Add the operator link to `Header.tsx`**

Add an anchor before the `CmykBar` in the right-hand group:

```tsx
<a
  href="#/operator"
  className="neu-raised-sm neu-press hidden min-h-[36px] items-center rounded-lg px-3 font-mono text-[10px] uppercase tracking-[0.12em] text-ink-soft hover:text-ink sm:inline-flex"
>
  operator
</a>
```

- [ ] **Step 4: Typecheck and commit**

```bash
cd web && npm run typecheck
cd ..
git add web/src/lib/useHashRoute.ts web/src/App.tsx web/src/components/Header.tsx
git commit -m "feat(web): hash routing and operator entry link"
```

Note: `OperatorApp` does not exist until Task 3; create a one-line placeholder in the same commit if you want the typecheck to pass before Task 3:

```tsx
// web/src/components/operator/OperatorApp.tsx (temporary)
export function OperatorApp() {
  return <div className="p-10 font-display text-ink">Operator</div>;
}
```

---

### Task 3: Login + shell

**Files:**
- Create: `web/src/components/operator/OperatorApp.tsx`
- Create: `web/src/components/operator/OperatorLogin.tsx`

**Interfaces:**
- Consumes: `labelApi.me`, `labelApi.login`, `labelApi.logout`.
- Produces: `OperatorApp` (checks session, renders login or dashboard).

- [ ] **Step 1: Write `OperatorLogin.tsx`**

```tsx
import { useState, type FormEvent } from "react";
import { labelApi } from "../../lib/labelApi";

export function OperatorLogin({ onLoggedIn }: { onLoggedIn: () => void }) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await labelApi.login(email, password);
      onLoggedIn();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Login gagal.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="mx-auto max-w-md px-5 py-16">
      <p className="font-accent text-[11px] uppercase tracking-[0.16em] text-brand-blue">
        area operator
      </p>
      <h1 className="mt-2 font-display text-2xl font-extrabold text-ink">Masuk sebagai owner</h1>
      <form onSubmit={submit} className="neu-raised mt-6 space-y-4 rounded-[20px] p-6">
        <div>
          <label htmlFor="op-email" className="font-mono text-[11px] uppercase tracking-[0.1em] text-ink-muted">
            email
          </label>
          <input
            id="op-email"
            type="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="neu-inset-sm mt-1.5 min-h-[44px] w-full rounded-xl px-3 text-[15px] text-ink outline-none"
          />
        </div>
        <div>
          <label htmlFor="op-password" className="font-mono text-[11px] uppercase tracking-[0.1em] text-ink-muted">
            password
          </label>
          <input
            id="op-password"
            type="password"
            required
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="neu-inset-sm mt-1.5 min-h-[44px] w-full rounded-xl px-3 text-[15px] text-ink outline-none"
          />
        </div>
        {error ? (
          <p role="alert" className="font-mono text-[12px] text-error">
            {error}
          </p>
        ) : null}
        <button
          type="submit"
          disabled={busy}
          className="neu-raised-sm neu-press min-h-[44px] w-full rounded-xl bg-brand-blue px-5 font-display text-[15px] font-bold text-surface-white disabled:opacity-60"
        >
          {busy ? "Memeriksa…" : "Masuk"}
        </button>
      </form>
      <p className="mt-4 text-center font-mono text-[10px] uppercase tracking-[0.1em] text-ink-muted">
        hanya akun owner yang bisa mengubah standar harga
      </p>
    </main>
  );
}
```

- [ ] **Step 2: Write `OperatorApp.tsx` shell**

```tsx
import { useCallback, useEffect, useState } from "react";
import { labelApi } from "../../lib/labelApi";
import { OperatorLogin } from "./OperatorLogin";
import { OperatorDashboard } from "./OperatorDashboard";

export function OperatorApp() {
  const [state, setState] = useState<"loading" | "anon" | "ready">("loading");

  const refresh = useCallback(() => {
    labelApi
      .me()
      .then(() => setState("ready"))
      .catch(() => setState("anon"));
  }, []);

  useEffect(refresh, [refresh]);

  if (state === "loading") {
    return (
      <main className="mx-auto max-w-3xl px-5 py-20 text-center font-mono text-[12px] text-ink-muted">
        memuat…
      </main>
    );
  }

  return (
    <div className="dot-grid min-h-[100dvh]">
      {state === "anon" ? (
        <OperatorLogin onLoggedIn={refresh} />
      ) : (
        <OperatorDashboard
          onLoggedOut={() => setState("anon")}
        />
      )}
    </div>
  );
}
```

- [ ] **Step 3: Create a temporary `OperatorDashboard` stub so the typecheck passes**

```tsx
// web/src/components/operator/OperatorDashboard.tsx (temporary, replaced in Task 4)
export function OperatorDashboard({ onLoggedOut }: { onLoggedOut: () => void }) {
  return (
    <div className="p-10">
      dashboard
      <button type="button" onClick={onLoggedOut}>keluar</button>
    </div>
  );
}
```

- [ ] **Step 4: Typecheck and commit**

```bash
cd web && npm run typecheck
cd ..
git add web/src/components/operator/
git commit -m "feat(web): operator login and shell"
```

---

### Task 4: Dashboard (samples + active model)

**Files:**
- Modify: `web/src/components/operator/OperatorDashboard.tsx`
- Create: `web/src/components/operator/SampleLabeling.tsx` (stub here, filled in Task 5)

**Interfaces:**
- Consumes: `labelApi.listSamples`, `labelApi.listModelVersions`, `labelApi.deleteSample`, `uploadSample`.
- Produces: `OperatorDashboard({ onLoggedOut })`; it selects a sample and renders `SampleLabeling`.

- [ ] **Step 1: Replace `OperatorDashboard.tsx`**

```tsx
import { useCallback, useEffect, useRef, useState } from "react";
import { labelApi, uploadSample } from "../../lib/labelApi";
import { formatIDR, formatNumber } from "../../lib/format";
import type { ModelVersion, SampleSummary } from "../../lib/types";
import { SampleLabeling } from "./SampleLabeling";

export function OperatorDashboard({ onLoggedOut }: { onLoggedOut: () => void }) {
  const [samples, setSamples] = useState<SampleSummary[]>([]);
  const [versions, setVersions] = useState<ModelVersion[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const load = useCallback(() => {
    labelApi.listSamples().then(setSamples).catch(() => setSamples([]));
    labelApi.listModelVersions().then(setVersions).catch(() => setVersions([]));
  }, []);

  useEffect(load, [load]);

  async function onFile(file: File) {
    setBusy(true);
    try {
      const sample = await uploadSample(file);
      setSelected(sample.id);
      load();
    } catch (err) {
      alert(err instanceof Error ? err.message : "Upload gagal.");
    } finally {
      setBusy(false);
    }
  }

  async function remove(id: string) {
    if (!confirm("Hapus sample ini?")) return;
    await labelApi.deleteSample(id);
    load();
  }

  const active = versions.find((v) => v.status === "active");

  return (
    <main className="mx-auto max-w-5xl px-5 py-10 sm:px-8">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="font-display text-2xl font-extrabold text-ink">Standar harga cetak</h1>
        <button
          type="button"
          onClick={() => {
            labelApi.logout().finally(onLoggedOut);
          }}
          className="neu-raised-sm neu-press min-h-[40px] rounded-lg px-3 font-mono text-[10px] uppercase tracking-[0.1em] text-ink-soft"
        >
          keluar
        </button>
      </div>

      <section className="neu-raised mt-6 rounded-[20px] p-5">
        <p className="font-accent text-[11px] uppercase tracking-[0.14em] text-ink-muted">
          model aktif
        </p>
        {active ? (
          <div className="mt-2 flex flex-wrap items-baseline gap-3">
            <span className="font-display text-lg font-bold text-ink">versi {active.id.slice(0, 8)}</span>
            <span className="font-mono text-[12px] text-ink-soft">
              MAE {formatIDR(Math.round(active.metrics.mean_abs_error ?? 0))} · {formatNumber(active.metrics.n_rows ?? 0)} baris
            </span>
          </div>
        ) : (
          <p className="mt-2 text-[14px] text-ink-soft">
            Belum ada model hasil retrain — harga memakai model bawaan.
          </p>
        )}
      </section>

      <section className="mt-6">
        <div className="flex items-center justify-between">
          <h2 className="font-display text-lg font-bold text-ink">Sample dokumen</h2>
          <button
            type="button"
            disabled={busy}
            onClick={() => inputRef.current?.click()}
            className="neu-raised-sm neu-press min-h-[44px] rounded-xl bg-brand-rose px-4 font-display text-[14px] font-bold text-surface-white disabled:opacity-60"
          >
            {busy ? "Mengunggah…" : "Upload sample"}
          </button>
          <input
            ref={inputRef}
            type="file"
            accept=".pdf,application/pdf"
            className="sr-only"
            onChange={(e) => {
              const file = e.target.files?.[0];
              e.target.value = "";
              if (file) onFile(file);
            }}
          />
        </div>

        <ul className="mt-3 space-y-2">
          {samples.map((s) => (
            <li key={s.id} className="neu-raised-sm flex items-center justify-between gap-3 rounded-xl px-4 py-3">
              <button
                type="button"
                onClick={() => setSelected(s.id)}
                className="min-w-0 flex-1 truncate text-left text-[14px] text-ink hover:underline"
              >
                {s.original_filename} · {formatNumber(s.page_count)} hal
              </button>
              <button
                type="button"
                onClick={() => remove(s.id)}
                className="font-mono text-[10px] uppercase tracking-[0.1em] text-error"
              >
                hapus
              </button>
            </li>
          ))}
          {samples.length === 0 ? (
            <li className="font-mono text-[11px] text-ink-muted">belum ada sample</li>
          ) : null}
        </ul>
      </section>

      {selected ? (
        <SampleLabeling
          sampleId={selected}
          onClose={() => setSelected(null)}
          onChanged={load}
        />
      ) : null}
    </main>
  );
}
```

- [ ] **Step 2: Create the `SampleLabeling` stub**

```tsx
// web/src/components/operator/SampleLabeling.tsx (temporary, filled in Task 5)
export function SampleLabeling({
  sampleId,
  onClose,
  onChanged,
}: {
  sampleId: string;
  onClose: () => void;
  onChanged: () => void;
}) {
  return (
    <div className="p-6">
      sample {sampleId}
      <button type="button" onClick={() => { onChanged(); onClose(); }}>tutup</button>
    </div>
  );
}
```

- [ ] **Step 3: Typecheck and commit**

```bash
cd web && npm run typecheck
cd ..
git add web/src/components/operator/
git commit -m "feat(web): operator dashboard"
```

---

### Task 5: Sample labeling + retrain preview

**Files:**
- Modify: `web/src/components/operator/SampleLabeling.tsx`
- Create: `web/src/components/operator/RetrainPreview.tsx`
- Create: `web/src/components/operator/ModelVersions.tsx`

**Interfaces:**
- Consumes: `labelApi.getSample`, `labelApi.patchPage`, `labelApi.retrain`, `labelApi.listModelVersions`, `labelApi.activateModelVersion`.
- Produces: `SampleLabeling`, `RetrainPreview`, `ModelVersions`.

- [ ] **Step 1: Replace `SampleLabeling.tsx`**

```tsx
import { useCallback, useEffect, useState } from "react";
import { labelApi } from "../../lib/labelApi";
import type { RetrainResult, SampleDetail } from "../../lib/types";
import { RetrainPreview } from "./RetrainPreview";

export function SampleLabeling({
  sampleId,
  onClose,
  onChanged,
}: {
  sampleId: string;
  onClose: () => void;
  onChanged: () => void;
}) {
  const [sample, setSample] = useState<SampleDetail | null>(null);
  const [draft, setDraft] = useState<Record<string, string>>({});
  const [candidate, setCandidate] = useState<RetrainResult | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(() => {
    labelApi.getSample(sampleId).then((s) => {
      setSample(s);
      const next: Record<string, string> = {};
      for (const p of s.pages) next[p.id] = p.labeled_price != null ? String(p.labeled_price) : "";
      setDraft(next);
    });
  }, [sampleId]);

  useEffect(load, [load]);

  async function savePage(pageId: string) {
    const value = Number(draft[pageId]);
    if (!Number.isFinite(value) || value <= 0) return;
    await labelApi.patchPage(pageId, Math.round(value));
    onChanged();
  }

  async function runRetrain() {
    setBusy(true);
    try {
      setCandidate(await labelApi.retrain());
    } catch (err) {
      alert(err instanceof Error ? err.message : "Retrain gagal.");
    } finally {
      setBusy(false);
    }
  }

  if (!sample) {
    return <p className="mt-6 font-mono text-[12px] text-ink-muted">memuat sample…</p>;
  }

  const labeled = sample.pages.filter((p) => p.labeled_price != null).length;

  return (
    <section className="mt-8">
      <div className="flex items-center justify-between">
        <h2 className="font-display text-lg font-bold text-ink">
          Label harga · {sample.original_filename}
        </h2>
        <button
          type="button"
          onClick={onClose}
          className="font-mono text-[10px] uppercase tracking-[0.1em] text-ink-muted"
        >
          tutup
        </button>
      </div>
      <p className="mt-1 font-mono text-[11px] text-ink-muted">
        {labeled}/{sample.pages.length} halaman berlabel
      </p>

      <ul className="mt-4 space-y-3">
        {sample.pages.map((page) => (
          <li key={page.id} className="neu-raised-sm grid grid-cols-[64px_1fr_auto] items-center gap-4 rounded-xl p-3">
            {page.thumbnail_base64 ? (
              <img
                src={`data:image/jpeg;base64,${page.thumbnail_base64}`}
                alt={`Halaman ${page.page_number}`}
                className="h-20 w-16 rounded-md border border-hairline object-cover"
              />
            ) : (
              <span className="neu-inset-sm grid h-20 w-16 place-items-center font-mono text-[10px] text-ink-muted">
                {page.page_number}
              </span>
            )}
            <div className="min-w-0">
              <p className="font-display text-[14px] font-bold text-ink">Halaman {page.page_number}</p>
              <p className="font-mono text-[11px] text-ink-soft">
                print {page.print_area.toFixed(1)}% · color {page.color_area.toFixed(1)}% · bw {page.bw_area.toFixed(1)}%
              </p>
            </div>
            <div className="flex items-center gap-2">
              <label htmlFor={`price-${page.id}`} className="sr-only">
                Harga halaman {page.page_number}
              </label>
              <input
                id={`price-${page.id}`}
                type="number"
                min={1}
                inputMode="numeric"
                value={draft[page.id] ?? ""}
                onChange={(e) => setDraft((d) => ({ ...d, [page.id]: e.target.value }))}
                placeholder="harga"
                className="neu-inset-sm min-h-[44px] w-28 rounded-lg px-3 text-right font-mono text-[13px] text-ink outline-none"
              />
              <button
                type="button"
                onClick={() => savePage(page.id)}
                className="neu-raised-sm neu-press min-h-[44px] rounded-lg px-3 font-mono text-[10px] uppercase tracking-[0.1em] text-ink-soft"
              >
                simpan
              </button>
            </div>
          </li>
        ))}
      </ul>

      <div className="mt-6 flex items-center justify-between gap-3">
        <p className="font-mono text-[11px] text-ink-muted">
          retrain memakai semua halaman berlabel
        </p>
        <button
          type="button"
          disabled={busy || labeled === 0}
          onClick={runRetrain}
          className="neu-raised-sm neu-press min-h-[44px] rounded-xl bg-brand-blue px-5 font-display text-[14px] font-bold text-surface-white disabled:opacity-60"
        >
          {busy ? "Melatih model…" : "Retrain model"}
        </button>
      </div>

      {candidate ? (
        <RetrainPreview
          candidate={candidate}
          onClose={() => setCandidate(null)}
          onActivated={() => {
            setCandidate(null);
            onChanged();
          }}
        />
      ) : null}
    </section>
  );
}
```

- [ ] **Step 2: Write `RetrainPreview.tsx`**

```tsx
import { labelApi } from "../../lib/labelApi";
import { formatIDR, formatNumber } from "../../lib/format";
import type { RetrainResult } from "../../lib/types";

export function RetrainPreview({
  candidate,
  onClose,
  onActivated,
}: {
  candidate: RetrainResult;
  onClose: () => void;
  onActivated: () => void;
}) {
  const m = candidate.metrics;
  return (
    <div className="neu-raised mt-6 rounded-[20px] p-5">
      <p className="font-accent text-[11px] uppercase tracking-[0.14em] text-brand-blue">
        pratinjau retrain
      </p>
      <dl className="mt-3 grid gap-3 sm:grid-cols-3">
        <div>
          <dt className="font-mono text-[10px] uppercase text-ink-muted">baris</dt>
          <dd className="tabnum font-display text-lg font-bold text-ink">{formatNumber(m.n_rows ?? 0)}</dd>
        </div>
        <div>
          <dt className="font-mono text-[10px] uppercase text-ink-muted">rata-rata selisih</dt>
          <dd className="tabnum font-display text-lg font-bold text-ink">{formatIDR(Math.round(m.mean_abs_error ?? 0))}</dd>
        </div>
        <div>
          <dt className="font-mono text-[10px] uppercase text-ink-muted">selisih maks</dt>
          <dd className="tabnum font-display text-lg font-bold text-ink">{formatIDR(Math.round(m.max_abs_error ?? 0))}</dd>
        </div>
      </dl>
      <div className="mt-5 flex gap-3">
        <button
          type="button"
          onClick={async () => {
            await labelApi.activateModelVersion(candidate.id);
            onActivated();
          }}
          className="neu-raised-sm neu-press min-h-[44px] rounded-xl bg-brand-blue px-5 font-display text-[14px] font-bold text-surface-white"
        >
          Aktifkan model ini
        </button>
        <button
          type="button"
          onClick={onClose}
          className="neu-raised-sm neu-press min-h-[44px] rounded-xl px-5 font-display text-[14px] font-bold text-ink-soft"
        >
          Batal
        </button>
      </div>
    </div>
  );
}
```

- [ ] **Step 3: Write `ModelVersions.tsx`**

```tsx
import { labelApi } from "../../lib/labelApi";
import { formatIDR, formatNumber } from "../../lib/format";
import type { ModelVersion } from "../../lib/types";

export function ModelVersions({
  versions,
  onChanged,
}: {
  versions: ModelVersion[];
  onChanged: () => void;
}) {
  return (
    <section className="mt-8">
      <h2 className="font-display text-lg font-bold text-ink">Riwayat model</h2>
      <ul className="mt-3 space-y-2">
        {versions.map((v) => (
          <li key={v.id} className="neu-raised-sm flex items-center justify-between gap-3 rounded-xl px-4 py-3">
            <div className="min-w-0">
              <p className="font-mono text-[12px] text-ink">
                {v.id.slice(0, 8)} · <span className="uppercase text-ink-muted">{v.status}</span>
              </p>
              <p className="font-mono text-[10px] text-ink-muted">
                MAE {formatIDR(Math.round(v.metrics.mean_abs_error ?? 0))} · {formatNumber(v.metrics.n_rows ?? 0)} baris
              </p>
            </div>
            {v.status !== "active" ? (
              <button
                type="button"
                onClick={async () => {
                  await labelApi.activateModelVersion(v.id);
                  onChanged();
                }}
                className="neu-raised-sm neu-press min-h-[40px] rounded-lg px-3 font-mono text-[10px] uppercase tracking-[0.1em] text-ink-soft"
              >
                aktifkan
              </button>
            ) : (
              <span className="font-mono text-[10px] uppercase tracking-[0.1em] text-success">aktif</span>
            )}
          </li>
        ))}
      </ul>
    </section>
  );
}
```

- [ ] **Step 4: Render `ModelVersions` from the dashboard**

In `OperatorDashboard.tsx`, after the samples section, add:

```tsx
import { ModelVersions } from "./ModelVersions";
// ...
<ModelVersions versions={versions} onChanged={load} />
```

- [ ] **Step 5: Typecheck, build, and commit**

```bash
cd web && npm run typecheck && npm run build
cd ..
git add web/src/components/operator/
git commit -m "feat(web): sample labeling, retrain preview, model versions"
```

---

### Task 6: Accessibility + manual QA + docs

**Files:**
- Modify: `web/src/components/operator/*` (contrast/labels only if QA finds gaps)
- Modify: `README.md`

- [ ] **Step 1: Manual QA checklist (documented in the commit message or README)**

- Keyboard: tab order reaches login fields, upload, each price input, save, retrain, activate.
- Focus visible on all interactive elements (neu-raised focus ring).
- Price inputs have accessible labels (sr-only `<label htmlFor>`).
- Error messages use `role="alert"` and text, not color alone.
- Touch targets >= 44px on mobile (test at 375px width).
- `#/operator` while logged out shows login; after login shows dashboard.

- [ ] **Step 2: Add a README section**

Document: owner-only access, login via artivity-server, upload → label → retrain → preview → activate/rollback, and that the public calculator is unchanged.

- [ ] **Step 3: Full gate**

```bash
make lint && make test && make web-build
```
Expected: all pass.

- [ ] **Step 4: Commit**

```bash
git add web/ README.md
git commit -m "feat(web): operator labeling UI polish and docs"
```

---

## Notes for the executor

- `formatIDR`, `formatNumber` already exist in `web/src/lib/format.ts` (used by `ResultSummary`). Reuse them.
- `App.tsx` currently has no router; the hash route is deliberately minimal. Do not add `react-router`.
- The public calculator's `ApiKeyField` and `uploadPdf` flow must remain untouched.
- `OperatorDashboard`'s `alert`/`confirm` are acceptable for an internal tool; replace with inline UI only if the reviewer asks.
- After `make web-build`, the Flask app serves the updated bundle from `public/`.
