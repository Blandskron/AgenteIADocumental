import type { Source } from "@/entities/conversation/model/types.ts";

export function SourceList({
  sources,
  activeSourceIndex = null,
  onSelectSource,
  onOpenSource,
}: {
  sources?: Source[];
  activeSourceIndex?: number | null;
  onSelectSource?: (index: number | null) => void;
  onOpenSource?: (source: Source) => void;
}) {
  if (!sources?.length) return null;

  return (
    <div className="sources">
      <div className="sources-title">Fuentes</div>
      {sources.map((source, index) => {
        const isActive = activeSourceIndex === index;
        const page = source.page ?? source.pageNumber ?? source.page_number;
        return (
          <details
            className={`source-card ${isActive ? "active-source" : ""}`.trim()}
            key={`${source.chunkId || source.chunk_id}-${index}`}
            open={isActive ? true : undefined}
            onToggle={(event) => {
              if (!onSelectSource) return;
              const target = event.currentTarget;
              if (target.open) {
                onSelectSource(index);
              } else if (isActive) {
                onSelectSource(null);
              }
            }}
          >
            <summary>
              <span>
                [{index + 1}]{" "}
                {source.filename || source.documentId || source.document_id}
                {page ? ` · Pág. ${page}` : ""}
                {source.section ? ` · ${source.section}` : ""}
              </span>
              <strong>{Number(source.score).toFixed(3)}</strong>
            </summary>
            <p>{source.content}</p>
            {onOpenSource ? (
              <button
                type="button"
                className="source-open-button"
                onClick={() => onOpenSource(source)}
              >
                {page ? `Abrir en página ${page}` : "Ver documento"}
              </button>
            ) : null}
          </details>
        );
      })}
    </div>
  );
}
