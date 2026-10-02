import { motion } from "motion/react";
import { formatIDR, formatNumber } from "../lib/format";
import type { PublicConfig } from "../lib/config";

export function PricingRules({ config }: { config: PublicConfig }) {
  const rules = [
    {
      label: "harga minimum hitam putih",
      value: formatIDR(config.price_floor_bw),
      note: "berlaku walau halaman hampir kosong",
    },
    {
      label: "harga minimum berwarna",
      value: formatIDR(config.price_floor_color),
      note: "sekali ada tinta warna di halaman",
    },
    {
      label: "pembulatan harga",
      value: config.price_step > 0 ? `kelipatan ${formatNumber(config.price_step)}` : "tanpa pembulatan",
      note: "dibulatkan ke tangga terdekat, bukan selalu ke atas",
    },
    {
      label: "batas harga per halaman",
      value: config.price_cap === null ? "tanpa batas" : formatIDR(config.price_cap),
      note: "dihitung per halaman, bukan total dokumen",
    },
  ];

  return (
    <motion.section
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.3, delay: 0.1 }}
      className="neu-raised mt-6 rounded-2xl p-5 sm:p-6"
      aria-label="Aturan perhitungan harga"
    >
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 className="font-display text-[16px] font-bold text-ink">Aturan perhitungan</h2>
        <p className="font-mono text-[10px] uppercase tracking-[0.1em] text-ink-muted">
          aktif di server ini
        </p>
      </div>
      <dl className="mt-4 grid gap-x-8 gap-y-4 sm:grid-cols-2">
        {rules.map((rule) => (
          <div key={rule.label} className="flex gap-3">
            <span
              className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-brand-blue"
              aria-hidden="true"
            />
            <div>
              <dt className="font-mono text-[10px] uppercase tracking-[0.1em] text-ink-muted">
                {rule.label}
              </dt>
              <dd className="tabnum mt-0.5 font-display text-[15px] font-bold text-ink">
                {rule.value}
              </dd>
              <p className="mt-0.5 text-[13px] leading-snug text-ink-soft">{rule.note}</p>
            </div>
          </div>
        ))}
      </dl>
    </motion.section>
  );
}
