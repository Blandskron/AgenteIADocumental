import { X } from "lucide-react";

export function SelectedDocumentsPanel({ selectedDocuments, onRemove }) {
  if (!selectedDocuments?.length) return null;
  return (
    <aside className="selected-documents-panel">
      <h4>Documentos activos en el chat</h4>
      <ul>
        {selectedDocuments.map((doc) => (
          <li key={doc.documentId}>
            <span>{doc.filename}</span>
            <button
              className="remove-selected-doc"
              onClick={() => onRemove(doc.documentId)}
              aria-label={`Quitar ${doc.filename}`}
            >
              <X size={14} />
            </button>
          </li>
        ))}
      </ul>
    </aside>
  );
}
