import { useState, type FormEvent } from "react";
import { labelApi } from "../../lib/labelApi";

export function OperatorLogin({ onLoggedIn }: { onLoggedIn: () => void }) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await labelApi.login(email, password);
      onLoggedIn();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Login gagal.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="mx-auto max-w-md px-5 py-16">
      <p className="font-accent text-[11px] uppercase tracking-[0.16em] text-brand-blue">
        area operator
      </p>
      <h1 className="mt-2 font-display text-2xl font-extrabold text-ink">Masuk sebagai owner</h1>
      <form onSubmit={submit} className="neu-raised mt-6 space-y-4 rounded-[20px] p-6">
        <div>
          <label htmlFor="op-email" className="font-mono text-[11px] uppercase tracking-[0.1em] text-ink-muted">
            email
          </label>
          <input
            id="op-email"
            type="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="neu-inset-sm mt-1.5 min-h-[44px] w-full rounded-xl px-3 text-[15px] text-ink outline-none"
          />
        </div>
        <div>
          <label htmlFor="op-password" className="font-mono text-[11px] uppercase tracking-[0.1em] text-ink-muted">
            password
          </label>
          <input
            id="op-password"
            type="password"
            required
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="neu-inset-sm mt-1.5 min-h-[44px] w-full rounded-xl px-3 text-[15px] text-ink outline-none"
          />
        </div>
        {error ? (
          <p role="alert" className="font-mono text-[12px] text-error">
            {error}
          </p>
        ) : null}
        <button
          type="submit"
          disabled={busy}
          className="neu-raised-sm neu-press min-h-[44px] w-full rounded-xl bg-brand-blue px-5 font-display text-[15px] font-bold text-surface-white disabled:opacity-60"
        >
          {busy ? "Memeriksa…" : "Masuk"}
        </button>
      </form>
      <p className="mt-4 text-center font-mono text-[10px] uppercase tracking-[0.1em] text-ink-muted">
        hanya akun owner yang bisa mengubah standar harga
      </p>
    </main>
  );
}