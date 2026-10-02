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