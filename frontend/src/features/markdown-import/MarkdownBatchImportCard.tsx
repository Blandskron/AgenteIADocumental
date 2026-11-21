import type { MaybeClient } from "@/shared/api/types.ts";
import { requireClient } from "@/shared/api/types.ts";
import { FileArchive, Upload } from "lucide-react";
import { useState } from "react";

export interface MarkdownBatchItem {
  path_rel: string;
  status: "created" | "reused" | "rejected" | string;
  document_id?: string | null;
  reason?: string | null;
}

export interface MarkdownBatchSummary {
  batch_id: string;
  created: number;
  reused: number;
  rejected: number;
  items: MarkdownBatchItem[];
}

export function importMarkdownBatchFiles(
  documentClient: MaybeClient,
  files: File[],
) {
  const formData = new FormData();
  for (const file of files) {
    formData.append("files", file);
  }
  formData.append("process", "true");
  return requireClient(documentClient)<MarkdownBatchSummary>(
    "/api/v1/documents/import-batch",
    {
      method: "POST",
      body: formData,
    },
  );
}

export function MarkdownBatchImportCard({
  documentClient,
}: {
  documentClient: MaybeClient;
}) {
  const [files, setFiles] = useState<File[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [summary, setSummary] = useState<MarkdownBatchSummary | null>(null);

  async function handleImport(event: React.FormEvent) {
    event.preventDefault();
    if (!files.length || busy) return;
    setBusy(true);
    setError(null);
    try {
      const result = await importMarkdownBatchFiles(documentClient, files);
      setSummary(result);
      setFiles([]);
    } catch (caught) {
      setError(
        caught instanceof Error
          ? caught.message
          : "No se pudo completar la importación por lote.",
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <section
      className="application-row"
      aria-labelledby="markdown-batch-heading"
      style={{
        flexDirection: "column",
        alignItems: "stretch",
        cursor: "default",
        gap: "0.75rem",
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: "0.75rem" }}>
        <FileArchive size={22} aria-hidden="true" />
        <span>
          <strong id="markdown-batch-heading">Importar Markdown / ZIP</strong>
          <small>
            Importa colecciones `.md` o archivos `.zip` (Obsidian, Logseq, repos
            de documentación) con deduplicación por SHA-256 y protección anti
            zip-bomb.
          </small>
        </span>
      </div>

      <form
        onSubmit={handleImport}
        style={{ display: "flex", flexWrap: "wrap", gap: "0.5rem" }}
      >
        <input
          type="file"
          accept=".zip,.md,.markdown,.txt"
          multiple
          aria-label="Seleccionar archivo ZIP o notas Markdown"
          onChange={(event) => {
            setFiles(Array.from(event.target.files || []));
            setError(null);
          }}
          disabled={busy}
        />
        <button
          type="submit"
          className="btn-primary"
          disabled={busy || files.length === 0}
        >
          <Upload size={15} aria-hidden="true" />
          {busy ? "Importando…" : "Importar lote"}
        </button>
      </form>

      {error && (
        <p role="alert" style={{ margin: 0, color: "#b91c1c" }}>
          {error}
        </p>
      )}

      {summary && (
        <div role="status" style={{ fontSize: "0.88rem" }}>
          <strong>Lote {summary.batch_id}:</strong> {summary.created} creados ·{" "}
          {summary.reused} reutilizados · {summary.rejected} rechazados
        </div>
      )}
    </section>
  );
}
