export type PublicConfig = {
  max_pages: number;
  max_content_length: number;
  price_step: number;
  price_cap: number | null;
  price_floor_bw: number;
  price_floor_color: number;
};

export const CONFIG_FALLBACK: PublicConfig = {
  max_pages: 500,
  max_content_length: 52428800,
  price_step: 250,
  price_cap: 3000,
  price_floor_bw: 300,
  price_floor_color: 500,
};

export async function fetchPublicConfig(signal?: AbortSignal): Promise<PublicConfig> {
  const res = await fetch("/api/v3/config", { signal });
  if (!res.ok) throw new Error(`config ${res.status}`);
  return (await res.json()) as PublicConfig;
}
