import { useEffect, useState } from "react";

const STORAGE_KEY = "artivity.print.apiKey";

export function readStoredApiKey(): string {
  try {
    return localStorage.getItem(STORAGE_KEY) ?? "";
  } catch {
    return "";
  }
}

export function ApiKeyField({
  value,
  onChange,
}: {
  value: string;
  onChange: (next: string) => void;
}) {
  const [revealed, setRevealed] = useState(false);
  const [persisted, setPersisted] = useState(false);

  useEffect(() => {
    setPersisted(value.length > 0 && readStoredApiKey() === value);
  }, [value]);

  function commit(next: string) {
    onChange(next);
    try {
      if (next) {
        localStorage.setItem(STORAGE_KEY, next);
      } else {
        localStorage.removeItem(STORAGE_KEY);
      }
    } catch {
      /* storage can be blocked; the key still works for this session */
    }
  }

  return (
    <div className="neu-inset rounded-2xl p-3">
      <div className="flex items-center gap-3">
        <svg
          width="16"
          height="16"
          viewBox="0 0 16 16"
          fill="none"
          aria-hidden="true"
          className="shrink-0 text-ink-muted"
        >
          <path
            d="M6.5 9.5 9.5 6.5M5 11 3.5 12.5a2.1 2.1 0 0 1-3-3L4 6a2.1 2.1 0 0 1 3 0M11 5l1.5-1.5a2.1 2.1 0 0 1 3 3L12 10a2.1 2.1 0 0 1-3 0"
            stroke="currentColor"
            strokeWidth="1.3"
            strokeLinecap="round"
          />
        </svg>
        <label htmlFor="api-key" className="sr-only">
          API key
        </label>
        <input
          id="api-key"
          type={revealed ? "text" : "password"}
          value={value}
          autoComplete="off"
          spellCheck={false}
          placeholder="Tempel API key di sini"
          onChange={(event) => commit(event.target.value)}
          className="min-w-0 flex-1 bg-transparent font-mono text-[13px] text-ink outline-none placeholder:text-ink-muted/70"
        />
        <button
          type="button"
          onClick={() => setRevealed((prev) => !prev)}
          className="neu-raised-sm neu-press min-h-[32px] rounded-lg px-2.5 py-1 font-mono text-[10px] uppercase tracking-[0.1em] text-ink-soft hover:text-ink"
          aria-label={revealed ? "Sembunyikan API key" : "Tampilkan API key"}
        >
          {revealed ? "sembunyi" : "lihat"}
        </button>
      </div>
      <p className="mt-2 pl-7 font-mono text-[10px] tracking-[0.06em] text-ink-muted">
        {persisted
          ? "tersimpan di browser ini"
          : value
            ? "dipakai untuk sesi ini saja"
            : "wajib diisi sebelum upload"}
      </p>
    </div>
  );
}
