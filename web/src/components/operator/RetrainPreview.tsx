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