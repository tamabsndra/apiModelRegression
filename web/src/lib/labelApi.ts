import type {
  ModelVersion,
  OperatorUser,
  RetrainResult,
  SampleDetail,
  SampleSummary,
} from "./types";

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const method = (init.method ?? "GET").toUpperCase();
  const headers: Record<string, string> = { ...(init.headers as Record<string, string>) };
  if (method !== "GET" && method !== "HEAD") {
    headers["X-Requested-With"] = "XMLHttpRequest";
  }
  const res = await fetch(path, { ...init, headers, credentials: "include" });
  if (res.status === 204) return undefined as T;
  const body = await res.json().catch(() => null);
  if (!res.ok) {
    const detail = (body as { detail?: string } | null)?.detail ?? `HTTP ${res.status}`;
    throw new Error(detail);
  }
  return body as T;
}

export const labelApi = {
  login: (email: string, password: string) =>
    request<{ user: OperatorUser }>("/api/label/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    }),

  logout: () => request<{ ok: boolean }>("/api/label/auth/logout", { method: "POST" }),

  me: () => request<{ user: OperatorUser }>("/api/label/auth/me"),

  listSamples: () => request<SampleSummary[]>("/api/label/samples"),

  getSample: (id: string) => request<SampleDetail>(`/api/label/samples/${id}`),

  deleteSample: (id: string) => request<void>(`/api/label/samples/${id}`, { method: "DELETE" }),

  patchPage: (pageId: string, labeledPrice: number) =>
    request(`/api/label/pages/${pageId}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ labeled_price: labeledPrice }),
    }),

  retrain: () => request<RetrainResult>("/api/label/retrain", { method: "POST" }),

  listModelVersions: () => request<ModelVersion[]>("/api/label/model-versions"),

  activateModelVersion: (id: string) =>
    request<ModelVersion>(`/api/label/model-versions/${id}/activate`, { method: "POST" }),
};

export function uploadSample(
  file: File,
  onProgress?: (percent: number) => void,
): Promise<SampleDetail> {
  return new Promise((resolve, reject) => {
    const form = new FormData();
    form.append("file", file);
    const xhr = new XMLHttpRequest();
    xhr.open("POST", "/api/label/samples");
    xhr.withCredentials = true;
    xhr.setRequestHeader("X-Requested-With", "XMLHttpRequest");
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
        reject(new Error("Respons server tidak bisa dibaca."));
        return;
      }
      if (xhr.status >= 200 && xhr.status < 300) resolve(body as SampleDetail);
      else reject(new Error((body as { detail?: string })?.detail ?? "Upload gagal."));
    });
    xhr.addEventListener("error", () => reject(new Error("Tidak bisa menghubungi server.")));
    xhr.send(form);
  });
}