import type { DocumentItem } from "@/entities/document/model/types.ts";
export interface Source {
  documentId?: string;
  chunkId?: string;
  filename?: string | null;
  content: string;
  score: number;
  document_id?: string;
  chunk_id?: string;
  page?: number | null;
  pageNumber?: number;
  page_number?: number;
  snippet?: string;
}
export interface Message {
  id?: string;
  role: string;
  content: string;
  sources?: Source[];
}
export interface Conversation {
  id: string;
  title: string;
  updatedAt: number;
  selectedDocuments: DocumentItem[];
  messages: Message[];
  historyBefore?: string | null;
}
