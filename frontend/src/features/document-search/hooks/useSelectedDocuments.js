import { useState } from "react";

export function useSelectedDocuments(initial = []) {
  const [selectedDocuments, setSelectedDocuments] = useState(initial);

  function addDocument(doc) {
    setSelectedDocuments((docs) =>
      docs.some((d) => d.documentId === doc.documentId) ? docs : [...docs, doc]
    );
  }

  function removeDocument(documentId) {
    setSelectedDocuments((docs) => docs.filter((d) => d.documentId !== documentId));
  }

  function clearDocuments() {
    setSelectedDocuments([]);
  }

  return {
    selectedDocuments,
    addDocument,
    removeDocument,
    clearDocuments,
  };
}
