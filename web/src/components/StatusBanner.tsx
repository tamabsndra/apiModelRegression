import { motion } from "motion/react";

export type BannerTone = "error" | "info";

const COPY: Record<string, { title: string; hint: string }> = {
  unauthorized: {
    title: "API key ditolak",
    hint: "Cek lagi key-nya di kolom atas. Key kosong akan selalu ditolak.",
  },
  invalid_pdf: {
    title: "PDF tidak bisa dibaca",
    hint: "File mungkin rusak atau bukan PDF asli. Coba ekspor ulang dari sumbernya.",
  },
  bad_request: {
    title: "File tidak diterima",
    hint: "Pastikan yang diunggah benar-benar file PDF.",
  },
  payload_too_large: {
    title: "File terlalu besar",
    hint: "Batas unggah 50 MB. Kompres atau pecah dokumennya dulu.",
  },
  too_many_pages: {
    title: "Halaman melebihi batas",
    hint: "Maksimal 500 halaman per file. Pecah jadi beberapa PDF.",
  },
  network: {
    title: "Server tidak terjangkau",
    hint: "Cek koneksi internet lalu coba lagi.",
  },
  internal_error: {
    title: "Server gagal memproses",
    hint: "Coba lagi sebentar. Kalau tetap gagal, kabari tim internal.",
  },
};

export function StatusBanner({
  code,
  message,
  onDismiss,
}: {
  code?: string;
  message: string;
  onDismiss?: () => void;
}) {
  const copy = (code && COPY[code]) || {
    title: "Upload gagal",
    hint: "Periksa kembali file dan API key sebelum mencoba lagi.",
  };

  return (
    <motion.div
      role="alert"
      initial={{ opacity: 0, y: -6 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -6 }}
      transition={{ duration: 0.2 }}
      className="neu-raised rounded-2xl border-l-4 border-l-error p-4"
    >
      <div className="flex items-start gap-3">
        <span
          className="mt-0.5 grid h-7 w-7 shrink-0 place-items-center rounded-lg bg-error/10 text-error"
          aria-hidden="true"
        >
          <svg width="15" height="15" viewBox="0 0 16 16" fill="none">
            <path
              d="M8 5v4m0 2.5h.01M8 1.8 1.6 13.2A1 1 0 0 0 2.5 14.7h11a1 1 0 0 0 .9-1.5L8 1.8Z"
              stroke="currentColor"
              strokeWidth="1.3"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
        </span>
        <div className="min-w-0 flex-1">
          <p className="font-display text-[15px] font-bold text-ink">{copy.title}</p>
          <p className="mt-0.5 text-[14px] text-ink-soft">{message}</p>
          <p className="mt-1.5 font-mono text-[10px] uppercase tracking-[0.08em] text-ink-muted">
            {copy.hint}
          </p>
        </div>
        {onDismiss ? (
          <button
            type="button"
            onClick={onDismiss}
            className="neu-raised-sm neu-press rounded-lg px-2 py-1 font-mono text-[10px] uppercase tracking-[0.1em] text-ink-muted hover:text-ink"
            aria-label="Tutup pesan"
          >
            tutup
          </button>
        ) : null}
      </div>
    </motion.div>
  );
}
