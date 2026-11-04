import { useState } from "react";
import { getDocumentChunks } from "../api/document-chunks.api";

export function useDocumentChunks(apiClient, documentId) {
  const [chunks, setChunks] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState("");

  async function fetchChunks({ limit = 20, offset = 0, q = "" } = {}) {
    setIsLoading(true);
    setError("");
    try {
      const data = await getDocumentChunks(apiClient, documentId, { limit, offset, q });
      setChunks(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setIsLoading(false);
    }
  }

  return { chunks, isLoading, error, fetchChunks };
}
