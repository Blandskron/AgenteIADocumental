export type Metadata = Record<string, unknown>;
export interface BlobResponse {
  blob: Blob;
  contentType: string;
  contentDisposition: string;
}
export type RequestOptions = RequestInit & { responseType?: "json" | "blob" };
export type JsonRequestOptions = RequestInit & { responseType?: "json" };
export interface ApiClient {
  (
    path: string,
    options: RequestOptions & { responseType: "blob" },
  ): Promise<BlobResponse>;
  <T = unknown>(path: string, options?: JsonRequestOptions): Promise<T>;
}
export type MaybeClient = ApiClient | null;
export interface Page<T> {
  items: T[];
  hasMore: boolean;
  nextOffset: number;
}
export interface PageOptions {
  limit?: number;
  offset?: number;
}

export function requireClient(client: MaybeClient): ApiClient {
  if (!client) throw new Error("Inicia sesión para continuar.");
  return client;
}
