import type { MaybeClient } from "@/shared/api/types.ts";
import { requireClient } from "@/shared/api/types.ts";
interface SourceDto {
  document_id?: string;
  chunk_id?: string;
  content?: string;
  score?: number;
  filename?: string;
}
interface ChatAskResponseDto {
  answer?: string;
  sources?: SourceDto[];
}
function normalizeSource(source: SourceDto = {}) {
  return {
    documentId: source.document_id || "",
    chunkId: source.chunk_id,
    content: source.content || "",
    score: Number(source.score || 0),
    filename: source.filename || null,
  };
}

function normalizeChatAskResponse(payload: ChatAskResponseDto = {}) {
  return {
    answer: payload.answer || "",
    sources: Array.isArray(payload.sources)
      ? payload.sources.map(normalizeSource)
      : [],
  };
}

export function askExistingDocuments(
  apiClient: MaybeClient,
  {
    question,
    sessionId,
    documentIds = [],
  }: { question: string; sessionId: string; documentIds?: string[] },
) {
  return requireClient(apiClient)<
    Parameters<typeof normalizeChatAskResponse>[0]
  >("/api/v1/chat/ask", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      question,
      session_id: sessionId,
      document_ids: documentIds,
    }),
  }).then(normalizeChatAskResponse);
}
