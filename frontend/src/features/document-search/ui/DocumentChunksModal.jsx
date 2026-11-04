import { useEffect } from "react";

export function DocumentChunksModal({ isOpen, onClose, document, apiClient, useChunksHook }) {
  const { chunks, isLoading, error, fetchChunks } = useChunksHook(apiClient, document?.documentId);

  useEffect(() => {
    if (isOpen && document?.documentId) {
      fetchChunks();
    }
    // eslint-disable-next-line
  }, [isOpen, document?.documentId]);

  if (!isOpen) return null;

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={e => e.stopPropagation()}>
        <h3>Fragmentos de {document?.filename}</h3>
        {isLoading && <p>Cargando fragmentos...</p>}
        {error && <div className="login-error">{error}</div>}
        <ul className="document-chunks-list">
          {chunks.map(chunk => (
            <li key={chunk.chunk_id}>
              <pre>{chunk.content}</pre>
              <small>#{chunk.chunk_index} - {chunk.created_at}</small>
            </li>
          ))}
        </ul>
        <button onClick={onClose}>Cerrar</button>
      </div>
    </div>
  );
}
