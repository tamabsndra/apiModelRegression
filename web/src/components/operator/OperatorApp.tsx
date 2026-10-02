import { useCallback, useEffect, useState } from "react";
import { labelApi } from "../../lib/labelApi";
import { OperatorLogin } from "./OperatorLogin";
import { OperatorDashboard } from "./OperatorDashboard";

export function OperatorApp() {
  const [state, setState] = useState<"loading" | "anon" | "ready">("loading");

  const refresh = useCallback(() => {
    labelApi
      .me()
      .then(() => setState("ready"))
      .catch(() => setState("anon"));
  }, []);

  useEffect(refresh, [refresh]);

  if (state === "loading") {
    return (
      <main className="mx-auto max-w-3xl px-5 py-20 text-center font-mono text-[12px] text-ink-muted">
        memuat…
      </main>
    );
  }

  return (
    <div className="dot-grid min-h-[100dvh]">
      {state === "anon" ? (
        <OperatorLogin onLoggedIn={refresh} />
      ) : (
        <OperatorDashboard
          onLoggedOut={() => setState("anon")}
        />
      )}
    </div>
  );
}