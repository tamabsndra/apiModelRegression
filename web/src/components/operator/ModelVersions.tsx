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