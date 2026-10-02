import { formatPct } from "../lib/format";

const MAX_VISIBLE_PCT = 100;

export function CoverageBar({
  printPct,
  colorPct,
  bwPct,
}: {
  printPct: number;
  colorPct: number;
  bwPct: number;
}) {
  const scale = (value: number) => `${Math.min(100, (value / MAX_VISIBLE_PCT) * 100)}%`;
  const colorWidth = scale(colorPct);
  const bwWidth = scale(bwPct);

  return (
    <div>
      <div className="neu-inset-sm relative h-3 overflow-hidden rounded-full">
        <div
          className="absolute inset-y-0 left-0 bg-cmyk-cyan"
          style={{ width: colorWidth }}
          aria-hidden="true"
        />
        <div
          className="absolute inset-y-0 bg-ink/75"
          style={{ left: colorWidth, width: bwWidth }}
          aria-hidden="true"
        />
      </div>
      <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 font-mono text-[10px] uppercase tracking-[0.08em] text-ink-muted">
        <span className="flex items-center gap-1.5">
          <span className="h-2 w-2 rounded-full bg-cmyk-cyan" aria-hidden="true" />
          warna <span className="tabnum text-ink-soft">{formatPct(colorPct)}</span>
        </span>
        <span className="flex items-center gap-1.5">
          <span className="h-2 w-2 rounded-full bg-ink/75" aria-hidden="true" />
          hitam <span className="tabnum text-ink-soft">{formatPct(bwPct)}</span>
        </span>
        <span className="flex items-center gap-1.5">
          total tinta <span className="tabnum text-ink-soft">{formatPct(printPct)}</span>
        </span>
      </div>
    </div>
  );
}
