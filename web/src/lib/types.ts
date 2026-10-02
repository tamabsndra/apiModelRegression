export type PageDetail = {
  index: number;
  print_pct: number;
  color_pct: number;
  bw_pct: number;
  latent: number;
  bw_price: number;
  color_price: number;
  price: number;
};

export type UploadResult = {
  message: string;
  price: number;
  page: number;
  bw_price: number;
  pages: PageDetail[];
};

export type UploadError = {
  error: string;
  detail: string;
};

export type JobState =
  | { status: "idle" }
  | { status: "uploading"; filename: string; progress: number }
  | { status: "processing"; filename: string }
  | { status: "done"; filename: string; result: UploadResult; elapsedMs: number }
  | { status: "error"; filename: string; message: string; code?: string };

export type OperatorUser = { id: string; name?: string; email?: string; role?: { name: string } };

export type SamplePage = {
  id: string;
  sample_id: string;
  page_number: number;
  bw_area: number;
  color_area: number;
  print_area: number;
  thumbnail_base64?: string;
  labeled_price: number | null;
};

export type SampleSummary = {
  id: string;
  original_filename: string;
  page_count: number;
  status: "labeling" | "completed" | "discarded";
  created_at: string;
};

export type SampleDetail = SampleSummary & { pages: SamplePage[] };

export type DatasetVersion = {
  id: string;
  row_count: number;
  note?: string;
  created_at: string;
};

export type ModelVersion = {
  id: string;
  dataset_version_id: string;
  status: "candidate" | "active" | "archived";
  intercept: number;
  metrics: { n_rows?: number; mean_abs_error?: number; max_abs_error?: number; p95_abs_error?: number };
  created_at: string;
  activated_at?: string | null;
};

export type RetrainResult = ModelVersion;