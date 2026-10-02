import { CmykBar, RegistrationMark } from "./Prepress";

export function Header({ hasResult }: { hasResult: boolean }) {
  return (
    <header className="border-b border-hairline/70 bg-surface-white/85 backdrop-blur-[6px]">
      <div className="mx-auto flex h-16 max-w-6xl items-center justify-between px-5 sm:px-8">
        <div className="flex items-center gap-3">
          <span
            className="grid h-9 w-9 place-items-center rounded-xl bg-ink text-surface-white"
            aria-hidden="true"
          >
            <span className="font-display text-[15px] font-extrabold leading-none">A</span>
          </span>
          <div className="leading-tight">
            <p className="font-display text-[15px] font-bold text-ink">Artivity</p>
            <p className="font-accent text-[10px] uppercase tracking-[0.16em] text-ink-muted">
              Print Calculator
            </p>
          </div>
        </div>

        <div className="flex items-center gap-4">
          <a
            href="#/operator"
            className="neu-raised-sm neu-press hidden min-h-[36px] items-center rounded-lg px-3 font-mono text-[10px] uppercase tracking-[0.12em] text-ink-soft hover:text-ink sm:inline-flex"
          >
            operator
          </a>
          {hasResult ? (
            <span className="hidden font-mono text-[10px] uppercase tracking-[0.12em] text-success sm:inline">
              siap dihitung ulang
            </span>
          ) : null}
          <div className="hidden sm:block">
            <RegistrationMark label="CALIBRATED" />
          </div>
          <CmykBar compact />
        </div>
      </div>
    </header>
  );
}
