import { useMemo, useState } from "react";
import { AnimatePresence, motion } from "motion/react";
import { CoverageBar } from "./CoverageBar";
import { formatIDR } from "../lib/format";
import type { PageDetail } from "../lib/types";

type SortKey = "index" | "price" | "print_pct";

export function PageBreakdown({ pages }: { pages: PageDetail[] }) {
  const [sort, setSort] = useState<SortKey>("index");
  const [onlyColor, setOnlyColor] = useState(false);
  const [open, setOpen] = useState<number | null>(null);

  const rows = useMemo(() => {
    const filtered = onlyColor ? pages.filter((page) => page.color_pct > 0) : pages;
    const sorted = [...filtered];
    if (sort === "price") sorted.sort((a, b) => b.price - a.price);
    else if (sort === "print_pct") sorted.sort((a, b) => b.print_pct - a.print_pct);
    else sorted.sort((a, b) => a.index - b.index);
    return sorted;
  }, [pages, sort, onlyColor]);

  const mostExpensive = useMemo(
    () => pages.reduce((max, page) => (page.price > max.price ? page : max), pages[0]),
    [pages],
  );

  return (
    <section className="mt-6" aria-label="Rincian per halaman">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h2 className="font-display text-[22px] font-bold text-ink">Rincian per halaman</h2>
          <p className="mt-1 text-[14px] text-ink-soft">
            Harga tiap lembar, lengkap dengan ketebalan tinta yang terbaca.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <button
            type="button"
            onClick={() => setOnlyColor((prev) => !prev)}
            aria-pressed={onlyColor}
            className={[
              "neu-press rounded-lg px-3 py-1.5 font-mono text-[10px] uppercase tracking-[0.1em] transition-colors",
              onlyColor ? "neu-inset text-brand-blue" : "neu-raised-sm text-ink-soft hover:text-ink",
            ].join(" ")}
          >
            hanya berwarna
          </button>

          <div
            className="neu-inset-sm flex rounded-lg p-0.5"
            role="group"
            aria-label="Urutkan halaman"
          >
            {(
              [
                ["index", "no."],
                ["price", "harga"],
                ["print_pct", "tinta"],
              ] as const
            ).map(([key, label]) => (
              <button
                key={key}
                type="button"
                onClick={() => setSort(key)}
                aria-pressed={sort === key}
                className={[
                  "rounded-[7px] px-3 py-1 font-mono text-[10px] uppercase tracking-[0.1em] transition-colors",
                  sort === key ? "bg-surface-white text-ink shadow-[var(--shadow-subtle)]" : "text-ink-muted hover:text-ink-soft",
                ].join(" ")}
              >
                {label}
              </button>
            ))}
          </div>
        </div>
      </div>

      <div className="mt-4 space-y-3">
        <AnimatePresence initial={false}>
          {rows.map((page, position) => {
            const expanded = open === page.index;
            const isPriciest = page.index === mostExpensive?.index;
            return (
              <motion.article
                key={page.index}
                layout="position"
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -6 }}
                transition={{ duration: 0.22, delay: Math.min(position * 0.02, 0.3) }}
                className="neu-raised overflow-hidden rounded-2xl"
              >
                <button
                  type="button"
                  onClick={() => setOpen(expanded ? null : page.index)}
                  aria-expanded={expanded}
                  className="flex w-full items-center gap-4 p-4 text-left sm:p-5"
                >
                  <span className="neu-inset-sm tabnum grid h-11 w-11 shrink-0 place-items-center rounded-xl font-mono text-[13px] font-semibold text-ink">
                    {page.index}
                  </span>

                  <span className="min-w-0 flex-1">
                    <span className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
                      <span className="tabnum font-display text-[18px] font-bold text-ink">
                        {formatIDR(page.price)}
                      </span>
                      {page.color_price > 0 ? (
                        <span className="font-mono text-[11px] text-brand-blue">
                          +{formatIDR(page.color_price)} warna
                        </span>
                      ) : (
                        <span className="font-mono text-[11px] text-ink-muted">hitam putih</span>
                      )}
                      {isPriciest && pages.length > 1 ? (
                        <span className="rounded-[5px] bg-ink px-1.5 py-0.5 font-mono text-[9px] uppercase tracking-[0.1em] text-surface-white">
                          termahal
                        </span>
                      ) : null}
                    </span>
                    <span className="mt-2 block max-w-md">
                      <CoverageBar
                        printPct={page.print_pct}
                        colorPct={page.color_pct}
                        bwPct={page.bw_pct}
                      />
                    </span>
                  </span>

                  <svg
                    width="16"
                    height="16"
                    viewBox="0 0 16 16"
                    fill="none"
                    aria-hidden="true"
                    className={[
                      "shrink-0 text-ink-muted transition-transform duration-200",
                      expanded ? "rotate-180" : "",
                    ].join(" ")}
                  >
                    <path d="m4 6 4 4 4-4" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
                  </svg>
                </button>

                <AnimatePresence initial={false}>
                  {expanded ? (
                    <motion.div
                      initial={{ height: 0, opacity: 0 }}
                      animate={{ height: "auto", opacity: 1 }}
                      exit={{ height: 0, opacity: 0 }}
                      transition={{ duration: 0.2, ease: "easeOut" }}
                      className="overflow-hidden"
                    >
                      <div className="px-4 pb-5 sm:px-5">
                        <div className="perforated mb-4" aria-hidden="true" />
                        <p className="mb-3 font-mono text-[10px] uppercase tracking-[0.1em] text-ink-muted">
                          rincian harga
                        </p>
                        <dl className="grid grid-cols-2 gap-x-6 gap-y-3 sm:grid-cols-4">
                          <Stat label="harga dasar model" value={formatIDR(page.latent)} />
                          <Stat label="harga hitam putih" value={formatIDR(page.bw_price)} />
                          <Stat
                            label="selisih warna"
                            value={formatIDR(page.color_price)}
                            tone="blue"
                          />
                          <Stat label="harga akhir" value={formatIDR(page.price)} strong />
                        </dl>
                        <p className="mt-4 font-mono text-[10px] uppercase tracking-[0.1em] text-ink-muted">
                          harga dasar model = hasil model isotonik sebelum pembulatan tangga dan
                          batas harga
                        </p>
                      </div>
                    </motion.div>
                  ) : null}
                </AnimatePresence>
              </motion.article>
            );
          })}
        </AnimatePresence>
      </div>

      {rows.length === 0 ? (
        <p className="neu-inset mt-3 rounded-2xl p-6 text-center text-[14px] text-ink-soft">
          Tidak ada halaman berwarna di file ini. Matikan filter untuk melihat semua halaman.
        </p>
      ) : null}
    </section>
  );
}

function Stat({
  label,
  value,
  tone,
  strong,
}: {
  label: string;
  value: string;
  tone?: "blue";
  strong?: boolean;
}) {
  return (
    <div>
      <dt className="font-mono text-[10px] uppercase tracking-[0.1em] text-ink-muted">{label}</dt>
      <dd
        className={[
          "tabnum mt-0.5 font-mono text-[13px]",
          tone === "blue" ? "text-brand-blue" : "text-ink-soft",
          strong ? "font-semibold text-ink" : "",
        ].join(" ")}
      >
        {value}
      </dd>
    </div>
  );
}
