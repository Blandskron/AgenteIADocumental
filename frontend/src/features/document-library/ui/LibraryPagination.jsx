export function LibraryPagination({ page, onLoadMore, label = "documentos" }) {
  return <div className="workflow-pagination" aria-live="polite">
    <span>{page.items.length} {label} cargados</span>
    {page.hasMore && <button type="button" className="action-button-secondary" disabled={page.loading} onClick={onLoadMore}>
      {page.loading ? "Cargando…" : "Cargar más"}
    </button>}
    {page.loading && !page.hasMore && <span> Cargando…</span>}
    {page.error && <p role="alert">{page.error}</p>}
  </div>;
}
