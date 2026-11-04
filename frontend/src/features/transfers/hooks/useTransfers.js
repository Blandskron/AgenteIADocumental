import { useCallback, useEffect, useState } from "react";

import { clearTransferHistory, createTransfer, listTransfers, updateTransfer } from "../api/transfers.api";

export function useTransfers(apiClient, { autoLoad = true } = {}) {
  const [transfers, setTransfers] = useState([]);
  const [error, setError] = useState("");
  const [isLoading, setIsLoading] = useState(false);

  const refreshTransfers = useCallback(async () => {
    if (!apiClient) return;

    setIsLoading(true);
    setError("");

    try {
      setTransfers(await listTransfers(apiClient));
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setIsLoading(false);
    }
  }, [apiClient]);

  useEffect(() => {
    if (autoLoad) refreshTransfers();
  }, [autoLoad, refreshTransfers]);

  async function recordTransfer(payload) {
    if (!apiClient) return null;
    const transfer = await createTransfer(apiClient, payload);
    setTransfers((current) => [transfer, ...current.filter((item) => item.transferId !== transfer.transferId)]);
    return transfer;
  }

  async function patchTransfer(transferId, payload) {
    if (!apiClient || !transferId) return null;
    const transfer = await updateTransfer(apiClient, transferId, payload);
    setTransfers((current) => current.map((item) => (item.transferId === transfer.transferId ? transfer : item)));
    return transfer;
  }

  async function clearHistory() {
    if (!apiClient) return;
    await clearTransferHistory(apiClient);
    setTransfers([]);
  }

  return {
    transfers,
    error,
    isLoading,
    refreshTransfers,
    recordTransfer,
    patchTransfer,
    clearHistory,
  };
}
