import type { UploadError, UploadResult } from "./types";

export class ApiError extends Error {
  code: string;
  status: number;

  constructor(message: string, code: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.code = code;
    this.status = status;
  }
}

export type UploadOptions = {
  file: File;
  apiKey: string;
  onProgress?: (percent: number) => void;
  signal?: AbortSignal;
};

export function uploadPdf({ file, apiKey, onProgress, signal }: UploadOptions): Promise<UploadResult> {
  return new Promise((resolve, reject) => {
    const form = new FormData();
    form.append("file", file);

    const xhr = new XMLHttpRequest();
    xhr.open("POST", "/api/v3/upload");
    xhr.setRequestHeader("api-key", apiKey);
    xhr.responseType = "text";

    xhr.upload.addEventListener("progress", (event) => {
      if (event.lengthComputable && onProgress) {
        onProgress(Math.round((event.loaded / event.total) * 100));
      }
    });

    xhr.addEventListener("load", () => {
      let body: unknown;
      try {
        body = JSON.parse(xhr.responseText);
      } catch {
        reject(new ApiError("Server mengirim respons yang tidak bisa dibaca.", "bad_response", xhr.status));
        return;
      }

      if (xhr.status >= 200 && xhr.status < 300) {
        resolve(body as UploadResult);
        return;
      }

      const err = body as Partial<UploadError>;
      reject(new ApiError(err.detail ?? "Terjadi kesalahan.", err.error ?? "unknown", xhr.status));
    });

    xhr.addEventListener("error", () => {
      reject(new ApiError("Tidak bisa menghubungi server. Cek koneksi lalu coba lagi.", "network", 0));
    });

    xhr.addEventListener("abort", () => {
      reject(new ApiError("Upload dibatalkan.", "aborted", 0));
    });

    if (signal) {
      signal.addEventListener("abort", () => xhr.abort(), { once: true });
    }

    xhr.send(form);
  });
}
