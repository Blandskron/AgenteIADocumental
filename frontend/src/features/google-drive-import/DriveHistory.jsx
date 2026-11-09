import { useEffect, useRef, useState } from "react";
import { getGoogleDriveImport, listGoogleDriveImports, listGoogleDriveImportFiles } from "./api/google-drive-import.api.js";

const initial = () => ({ items: [], nextCursor: null, files: [], filesCursor: null, selected: null, busy: false, error: "" });

export function DriveHistory({ client, scope }) {
  const [open, setOpen] = useState(false);
  return <>
    <button type="button" className="action-button-secondary" onClick={() => setOpen(true)}>Historial de Drive</button>
    {open && <HistoryDialog key={scope} client={client} onClose={() => setOpen(false)} />}
  </>;
}

function HistoryDialog({ client, onClose }) {
  const dialog = useRef(), request = useRef(), epoch = useRef(0), stateRef = useRef();
  const [state, setState] = useState(initial);
  stateRef.current = state;
  function stop() { epoch.current++; request.current?.abort(); request.current = null; }
  function close() { stop(); onClose(); }
  async function load(kind, more = false, record = null) {
    // Serialized reads avoid repeated paging clicks; selecting another row cancels its predecessor.
    if (request.current && more) return;
    stop();
    const generation = epoch.current, abort = new AbortController();
    request.current = abort;
    const previous = stateRef.current;
    setState((value) => ({ ...value, busy: true, error: "", ...(kind === "files" && !more ? { files: [], filesCursor: null, selected: record } : {}) }));
    try {
      if (kind === "imports") {
        const cursor = more ? previous.nextCursor : null;
        const page = await listGoogleDriveImports(client, { cursor, signal: abort.signal });
        if (generation !== epoch.current) return;
        if (page.nextCursor && page.nextCursor === cursor) throw new Error("El historial no avanzó. Actualiza para continuar.");
        const rows = more ? [...previous.items, ...page.items] : page.items;
        setState((value) => ({ ...value, items: [...new Map(rows.map((row) => [row.importId, row])).values()], nextCursor: page.nextCursor,
          ...(!more ? { files: [], filesCursor: null, selected: null } : {}) }));
      } else {
        const selected = more ? previous.selected : await getGoogleDriveImport(client, record.importId, abort.signal);
        if (generation !== epoch.current) return;
        const cursor = more ? previous.filesCursor : null;
        const page = await listGoogleDriveImportFiles(client, selected.importId, { cursor, signal: abort.signal });
        if (generation !== epoch.current) return;
        if (page.nextCursor && page.nextCursor === cursor) throw new Error("Los archivos no avanzaron. Actualiza para continuar.");
        const rows = more ? [...previous.files, ...page.items] : page.items;
        setState((value) => ({ ...value, selected, files: [...new Map(rows.map((row) => [row.importFileId, row])).values()], filesCursor: page.nextCursor,
          items: value.items.map((row) => row.importId === selected.importId ? selected : row) }));
      }
    } catch (error) { if (generation === epoch.current) setState((value) => ({ ...value, error: error.message })); }
    finally { if (generation === epoch.current) { request.current = null; setState((value) => ({ ...value, busy: false })); } }
  }
  useEffect(() => {
    const opener = document.activeElement, element = dialog.current;
    element.showModal();
    load("imports");
    return () => { stop(); element.close(); if (opener?.isConnected) opener.focus(); };
  }, [client]);
  return <dialog ref={dialog} aria-labelledby="drive-history-title" onCancel={(event) => { event.preventDefault(); event.stopPropagation(); close(); }}
    style={{ maxWidth: "min(850px, 90vw)", maxHeight: "85vh", overflow: "auto", padding: 24 }}>
    <h2 id="drive-history-title">Historial de Drive</h2>
    <p>Historial propio, compartido entre tus espacios de trabajo. Cerrar esta ventana solo detiene la consulta.</p>
    <button type="button" onClick={close} autoFocus>Cerrar historial</button>{" "}
    <button type="button" onClick={() => load("imports")} disabled={state.busy}>Actualizar historial</button>
    {state.error && <p role="alert">{state.error}</p>}
    <p role="status">{state.busy ? "Consultando historial…" : `${state.items.length} importaciones cargadas`}</p>
    <ul>{state.items.map((row) => <li key={row.importId}>
      <button type="button" onClick={() => load("files", false, row)} aria-pressed={state.selected?.importId === row.importId}>
        {row.createdAt ? new Date(row.createdAt).toLocaleString() : row.importId} · {row.status} · {row.processedFiles ?? 0}/{row.totalFiles ?? 0} archivos
      </button>
    </li>)}</ul>
    {state.nextCursor && <button type="button" disabled={state.busy} onClick={() => load("imports", true)}>Cargar más importaciones</button>}
    {state.selected && <section aria-label="Archivos de la importación">
      <h3>Archivos de la importación</h3>
      <p>Estado: {state.selected.status}. Operación: {state.selected.operationId || "anterior al diario"}.</p>
      {state.selected.status === "REVIEW_REQUIRED" && <p role="alert">Resultado incierto: revisa los documentos existentes. No repitas la carga hasta confirmar su resultado.</p>}
      {state.selected.status === "PURGED" && <p>Detalles compactados por retención. Se conservan los marcadores para evitar cargas repetidas.</p>}
      <p>{state.files.length} archivos cargados</p>
      <ul>{state.files.map((file) => <li key={file.importFileId}>
        <strong>{file.filename || file.googleFileId}</strong>: {file.status}
        {file.documentId && <span> · Documento: {file.documentId}</span>}
        {file.metadata.document_status && <span> · Procesamiento: {file.metadata.document_status}</span>}
        {file.metadata.folder_association?.status === "FAILED" && <p role="alert">El documento se conservó, pero no pudo asociarse a la carpeta.</p>}
        {file.errorMessage && <p>{file.errorMessage}</p>}
      </li>)}</ul>
      {state.filesCursor && <button type="button" disabled={state.busy} onClick={() => load("files", true)}>Cargar más archivos</button>}
    </section>}
  </dialog>;
}
