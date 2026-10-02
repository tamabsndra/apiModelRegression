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