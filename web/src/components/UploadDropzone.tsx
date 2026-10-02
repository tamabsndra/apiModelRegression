import { useRef, useState } from "react";
import { motion } from "motion/react";
import { formatBytes, formatBytesShort } from "../lib/format";

type Props = {
  disabled: boolean;
  busy: boolean;
  progress: number;
  maxPages: number;
  maxBytes: number;
  onFile: (file: File) => void;
  onCancel: () => void;
};

const ACCEPT = ".pdf,application/pdf";

export function UploadDropzone({
  disabled,
  busy,
  progress,
  maxPages,
  maxBytes,
  onFile,
  onCancel,
}: Props) {
  const [dragging, setDragging] = useState(false);
  const [rejected, setRejected] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  function accept(file: File | undefined) {
    if (!file) return;
    const isPdf = file.type === "application/pdf" || file.name.toLowerCase().endsWith(".pdf");
    if (!isPdf) {
      setRejected(`${file.name} bukan PDF (${formatBytes(file.size)}).`);
      return;
    }
    setRejected(null);
    onFile(file);
  }

  return (
    <div>
      <motion.div
        onDragOver={(event) => {
          event.preventDefault();
          if (!disabled && !busy) setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={(event) => {
          event.preventDefault();
          setDragging(false);
          if (disabled || busy) return;
          accept(event.dataTransfer.files[0]);
        }}
        animate={{ scale: dragging ? 1.01 : 1 }}
        transition={{ type: "spring", stiffness: 340, damping: 26 }}
        className={[
          "crop-marks relative overflow-hidden rounded-[20px] px-6 py-10 text-center transition-colors sm:px-10 sm:py-14",
          dragging ? "neu-inset" : "neu-raised",
          disabled ? "opacity-60" : "",
        ].join(" ")}
      >
        <input
          ref={inputRef}
          id="pdf-file-input"
          type="file"
          accept={ACCEPT}
          className="sr-only"
          onChange={(event) => {
            accept(event.target.files?.[0]);
            event.target.value = "";
          }}
          disabled={disabled || busy}
          aria-label="Pilih file PDF"
        />

        {busy ? (
          <div className="mx-auto max-w-md">
            <p className="font-accent text-[11px] uppercase tracking-[0.16em] text-brand-blue">
              memproses
            </p>
            <p className="mt-2 font-display text-lg font-bold text-ink">
              {progress < 100 ? "Mengunggah PDF" : "Menghitung tiap halaman"}
            </p>
            <div
              className="neu-inset-sm mt-5 h-2.5 w-full overflow-hidden rounded-full"
              role="progressbar"
              aria-valuemin={0}
              aria-valuemax={100}
              aria-valuenow={progress}
              aria-label="Progres upload"
            >
              <motion.div
                className="h-full rounded-full bg-brand-blue"
                animate={{ width: `${progress}%` }}
                transition={{ ease: "easeOut", duration: 0.25 }}
              />
            </div>
            <p className="tabnum mt-2 font-mono text-[11px] text-ink-muted">{progress}%</p>
            <button
              type="button"
              onClick={onCancel}
              className="neu-raised-sm neu-press mt-5 rounded-lg px-3 py-1.5 font-mono text-[10px] uppercase tracking-[0.1em] text-ink-soft hover:text-ink"
            >
              batalkan
            </button>
          </div>
        ) : (
          <div className="mx-auto max-w-lg">
            <span
              className="neu-raised-sm mx-auto grid h-14 w-14 place-items-center rounded-2xl text-brand-blue"
              aria-hidden="true"
            >
              <svg width="24" height="24" viewBox="0 0 24 24" fill="none">
                <path
                  d="M12 16V4m0 0L7.5 8.5M12 4l4.5 4.5M4 15v3a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-3"
                  stroke="currentColor"
                  strokeWidth="1.6"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
              </svg>
            </span>
            <h2 className="mt-4 font-display text-xl font-bold text-ink sm:text-2xl">
              Lepas PDF di sini
            </h2>
            <p className="mt-1.5 text-[15px] text-ink-soft">
              Setiap halaman dihitung terpisah. Hasilnya lengkap sampai harga per lembar.
            </p>
            <button
              type="button"
              onClick={() => inputRef.current?.click()}
              disabled={disabled}
              className="neu-raised-sm neu-press mt-5 min-h-[44px] rounded-xl bg-brand-rose px-6 py-3 font-display text-[15px] font-bold text-surface-white shadow-[0_10px_20px_rgba(225,29,98,0.22)] disabled:cursor-not-allowed disabled:opacity-60"
            >
              Pilih file PDF
            </button>
            <p className="mt-3 font-mono text-[10px] uppercase tracking-[0.1em] text-ink-muted">
              maks {formatBytesShort(maxBytes)} · sampai {maxPages} halaman
            </p>
          </div>
        )}
      </motion.div>

      {rejected ? (
        <p role="alert" className="mt-3 font-mono text-[11px] text-error">
          {rejected}
        </p>
      ) : null}
    </div>
  );
}
