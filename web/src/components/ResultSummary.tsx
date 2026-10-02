import { motion } from "motion/react";
import { CmykBar } from "./Prepress";
import { formatDuration, formatIDR, formatNumber } from "../lib/format";
import type { UploadResult } from "../lib/types";

export function ResultSummary({
  result,
  filename,
  elapsedMs,
}: {
  result: UploadResult;
  filename: string;
  elapsedMs: number;
}) {
  const colorPremium = result.pages.reduce((sum, page) => sum + page.color_price, 0);
  const bwOnly = result.pages.reduce((sum, page) => sum + page.bw_price, 0);
  const colorPages = result.pages.filter((page) => page.color_pct > 0).length;

  return (
    <motion.section
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35, ease: "easeOut" }}
      className="neu-raised overflow-hidden rounded-[20px]"
      aria-label="Ringkasan hasil"
    >
      <div className="grid gap-6 p-6 sm:p-7 lg:grid-cols-[minmax(0,1.15fr)_minmax(0,1fr)]">
        <div>
          <p className="font-accent text-[11px] uppercase tracking-[0.16em] text-brand-blue">
            total harga cetak
          </p>
          <p className="tabnum mt-2 font-display text-[42px] font-extrabold leading-none tracking-tight text-ink sm:text-[52px]">
            {formatIDR(result.price)}
          </p>
          <p className="mt-2 truncate text-[14px] text-ink-soft" title={filename}>
            {filename}
          </p>
          <div className="mt-5 flex flex-wrap gap-2">
            <span className="neu-inset-sm rounded-lg px-3 py-1.5 font-mono text-[11px] text-ink-soft">
              {formatNumber(result.page)} halaman
            </span>
            <span className="neu-inset-sm rounded-lg px-3 py-1.5 font-mono text-[11px] text-ink-soft">
              {colorPages} berwarna
            </span>
            <span className="neu-inset-sm rounded-lg px-3 py-1.5 font-mono text-[11px] text-ink-soft">
              {formatDuration(elapsedMs)}
            </span>
          </div>
        </div>

        <div className="neu-inset rounded-2xl p-5">
          <p className="font-accent text-[11px] uppercase tracking-[0.14em] text-ink-muted">
            rincian perhitungan
          </p>
          <dl className="mt-4 space-y-3 text-[14px]">
            <div className="flex items-baseline justify-between gap-4">
              <dt className="text-ink-soft">Kalau hitam putih semua</dt>
              <dd className="tabnum font-mono text-ink">{formatIDR(bwOnly)}</dd>
            </div>
            <div className="flex items-baseline justify-between gap-4">
              <dt className="text-ink-soft">Tambahan karena warna</dt>
              <dd className="tabnum font-mono text-brand-blue">+ {formatIDR(colorPremium)}</dd>
            </div>
            <div className="perforated my-1" aria-hidden="true" />
            <div className="flex items-baseline justify-between gap-4">
              <dt className="font-display font-bold text-ink">Total</dt>
              <dd className="tabnum font-mono text-[16px] font-bold text-ink">
                {formatIDR(result.price)}
              </dd>
            </div>
          </dl>
          <div className="mt-5 flex items-center justify-between">
            <CmykBar compact />
            <span className="font-mono text-[9px] uppercase tracking-[0.12em] text-ink-muted">
              {formatNumber(result.page)} × lembar
            </span>
          </div>
        </div>
      </div>
    </motion.section>
  );
}
