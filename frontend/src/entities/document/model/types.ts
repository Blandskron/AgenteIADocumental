import type { Metadata } from "@/shared/api/types.ts";
export interface DocumentItem {
  documentId: string;
  filename: string;
  status: string;
  mimeType?: string;
  chunkCount?: number;
  updatedAt?: string;
  createdAt?: string;
  processedAt?: string | null;
  snippet?: string;
  isFavorite?: boolean;
  size_bytes?: number;
}
export interface Folder {
  folderId: string;
  name: string;
  parentFolderId: string | null;
  ownerUserId: string;
  metadata: Metadata;
  documentCount: number;
  createdAt: string;
  updatedAt: string;
}
export interface DocumentPreview {
  url: string;
  contentType: string;
  filename: string;
}
export interface SearchFilters {
  query?: string;
  status?: string;
  mimeType?: string;
  source?: string;
  limit?: number;
  offset?: number;
  sort?: string;
}
