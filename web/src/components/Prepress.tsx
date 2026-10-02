const CMYK = [
  { name: "C", hex: "#00a3e0" },
  { name: "M", hex: "#e11d62" },
  { name: "Y", hex: "#ffdc00" },
  { name: "K", hex: "#0f172a" },
] as const;

export function CmykBar({ compact = false }: { compact?: boolean }) {
  return (
    <div className="flex items-center gap-1.5" aria-hidden="true">
      {CMYK.map((chip) => (
        <span
          key={chip.name}
          className={compact ? "h-1.5 w-4 rounded-[2px]" : "h-2 w-6 rounded-[3px]"}
          style={{ backgroundColor: chip.hex }}
        />
      ))}
    </div>
  );
}

export function RegistrationMark({ label = "REG // 01-A" }: { label?: string }) {
  return (
    <div className="flex items-center gap-2 text-ink-muted">
      <svg width="14" height="14" viewBox="0 0 14 14" aria-hidden="true" className="shrink-0">
        <circle cx="7" cy="7" r="3.2" fill="none" stroke="currentColor" strokeWidth="1" />
        <path d="M7 0.5v13M0.5 7h13" stroke="currentColor" strokeWidth="1" />
      </svg>
      <span className="font-mono text-[9px] uppercase tracking-[0.12em]">{label}</span>
    </div>
  );
}
