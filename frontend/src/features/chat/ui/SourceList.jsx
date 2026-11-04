export function SourceList({ sources }) {
  if (!sources?.length) return null;

  return (
    <div className="sources">
      <div className="sources-title">Fuentes</div>
      {sources.map((source, index) => (
        <details className="source-card" key={`${source.chunkId || source.chunk_id}-${index}`}>
          <summary>
            <span>{source.filename || source.documentId || source.document_id}</span>
            <strong>{Number(source.score).toFixed(3)}</strong>
          </summary>
          <p>{source.content}</p>
        </details>
      ))}
    </div>
  );
}
