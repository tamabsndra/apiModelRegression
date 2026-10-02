import { useCallback, useEffect, useRef, useState } from "react";
import { AnimatePresence } from "motion/react";
import { ApiKeyField, readStoredApiKey } from "./components/ApiKeyField";
import { Header } from "./components/Header";
import { PageBreakdown } from "./components/PageBreakdown";
import { PricingRules } from "./components/PricingRules";
import { ResultSummary } from "./components/ResultSummary";
import { StatusBanner } from "./components/StatusBanner";
import { UploadDropzone } from "./components/UploadDropzone";
import { ApiError, uploadPdf } from "./lib/api";
import { CONFIG_FALLBACK, fetchPublicConfig, type PublicConfig } from "./lib/config";
import type { JobState } from "./lib/types";
import { useHashRoute } from "./lib/useHashRoute";
import { OperatorApp } from "./components/operator/OperatorApp";

export default function App() {
  const [apiKey, setApiKey] = useState("");
  const [job, setJob] = useState<JobState>({ status: "idle" });
  const [dismissedError, setDismissedError] = useState(false);
  const [config, setConfig] = useState<PublicConfig>(CONFIG_FALLBACK);
  const abortRef = useRef<AbortController | null>(null);
  const resultRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    setApiKey(readStoredApiKey());
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    fetchPublicConfig(controller.signal)
      .then(setConfig)
      .catch(() => {
        /* keep the fallback so the UI still states something honest */
      });
    return () => controller.abort();
  }, []);

  const busy = job.status === "uploading" || job.status === "processing";

  const handleFile = useCallback(
    async (file: File) => {
      setDismissedError(false);
      setJob({ status: "uploading", filename: file.name, progress: 0 });

      const controller = new AbortController();
      abortRef.current = controller;
      const startedAt = performance.now();

      try {
        const result = await uploadPdf({
          file,
          apiKey,
          signal: controller.signal,
          onProgress: (progress) => {
            setJob((prev) =>
              prev.status === "uploading" ? { ...prev, progress } : prev,
            );
            if (progress >= 100) {
              setJob({ status: "processing", filename: file.name });
            }
          },
        });

        setJob({
          status: "done",
          filename: file.name,
          result,
          elapsedMs: performance.now() - startedAt,
        });
        requestAnimationFrame(() => {
          resultRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
        });
      } catch (error) {
        if (error instanceof ApiError && error.code === "aborted") {
          setJob({ status: "idle" });
          return;
        }
        const apiError = error instanceof ApiError ? error : null;
        setJob({
          status: "error",
          filename: file.name,
          message: apiError?.message ?? "Terjadi kesalahan yang tidak terduga.",
          code: apiError?.code,
        });
      } finally {
        abortRef.current = null;
      }
    },
    [apiKey],
  );

  function cancel() {
    abortRef.current?.abort();
    abortRef.current = null;
    setJob({ status: "idle" });
  }

  function reset() {
    setJob({ status: "idle" });
    setDismissedError(false);
  }

  const route = useHashRoute();
  if (route === "/operator") {
    return <OperatorApp />;
  }

  return (
    <div className="dot-grid min-h-[100dvh]">
      <Header hasResult={job.status === "done"} />

      <main className="mx-auto max-w-6xl px-5 pb-20 pt-10 sm:px-8 sm:pt-14">
        <div className="mx-auto max-w-3xl text-center">
          <p className="font-accent text-[11px] uppercase tracking-[0.16em] text-brand-blue">
            kalkulator cetak per halaman
          </p>
          <h1 className="mt-3 font-display text-[30px] font-extrabold leading-tight text-ink sm:text-[40px]">
            Upload PDF, lihat harga <span className="text-brand-blue">tiap lembar</span> sebelum
            masuk produksi.
          </h1>
          <p className="mx-auto mt-3 max-w-xl text-[15px] leading-relaxed text-ink-soft sm:text-[16px]">
            Hitungannya transparan: ketebalan tinta warna, tinta hitam, dan harga dasar model
            ditampilkan satu per satu. Tidak ada angka yang disembunyikan.
          </p>
        </div>

        <div className="mx-auto mt-8 max-w-3xl">
          <ApiKeyField value={apiKey} onChange={setApiKey} />
        </div>

        <div className="mx-auto mt-6 max-w-3xl">
          <UploadDropzone
            disabled={!apiKey}
            busy={busy}
            maxPages={config.max_pages}
            maxBytes={config.max_content_length}
            progress={job.status === "uploading" ? job.progress : job.status === "processing" ? 100 : 0}
            onFile={handleFile}
            onCancel={cancel}
          />
          {!apiKey ? (
            <p className="mt-3 text-center font-mono text-[11px] uppercase tracking-[0.08em] text-ink-muted">
              isi api key dulu untuk membuka upload
            </p>
          ) : null}
        </div>

        {job.status === "idle" ? (
          <div className="mx-auto max-w-3xl">
            <PricingRules config={config} />
          </div>
        ) : null}

        <AnimatePresence>
          {job.status === "error" && !dismissedError ? (
            <div className="mx-auto mt-6 max-w-3xl">
              <StatusBanner
                code={job.code}
                message={job.message}
                onDismiss={() => setDismissedError(true)}
              />
            </div>
          ) : null}
        </AnimatePresence>

        <div ref={resultRef} className="scroll-mt-6">
          <AnimatePresence mode="wait">
            {job.status === "done" ? (
              <div key={`${job.filename}-${job.result.page}`} className="mt-10">
                <ResultSummary
                  result={job.result}
                  filename={job.filename}
                  elapsedMs={job.elapsedMs}
                />
                <PageBreakdown pages={job.result.pages} />
                <div className="mt-8 flex justify-center">
                  <button
                    type="button"
                    onClick={reset}
                    className="neu-raised-sm neu-press rounded-xl px-5 py-2.5 font-display text-[15px] font-bold text-ink-soft hover:text-ink"
                  >
                    Hitung file lain
                  </button>
                </div>
              </div>
            ) : null}
          </AnimatePresence>
        </div>
      </main>

      <footer className="border-t border-hairline/70 bg-surface-white">
        <div className="mx-auto flex max-w-6xl flex-col gap-3 px-5 py-6 sm:flex-row sm:items-center sm:justify-between sm:px-8">
          <p className="font-mono text-[10px] uppercase tracking-[0.12em] text-ink-muted">
            Artivity · print calculator · harga per halaman
          </p>
          <p className="font-mono text-[10px] uppercase tracking-[0.12em] text-ink-muted">
            file diproses lalu langsung dihapus dari server
          </p>
        </div>
      </footer>
    </div>
  );
}
