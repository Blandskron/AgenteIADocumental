import { useEffect, useState } from "react";

import { searchDocuments } from "../api/document-search.api";

export function useDocumentSearch(apiClient) {
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState("PROCESSED");
  const [documents, setDocuments] = useState([]);
  const [total, setTotal] = useState(0);
  const [error, setError] = useState("");
  const [isLoading, setIsLoading] = useState(false);

  async function runSearch(next = {}) {
    setIsLoading(true);
    setError("");

    try {
      const response = await searchDocuments(apiClient, {
        query,
        status,
        ...next,
      });
      setDocuments(response.items);
      setTotal(response.total);
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setIsLoading(false);
    }
  }

  useEffect(() => {
    runSearch();
  }, []);

  return {
    query,
    setQuery,
    status,
    setStatus,
    documents,
    total,
    error,
    isLoading,
    runSearch,
  };
}
