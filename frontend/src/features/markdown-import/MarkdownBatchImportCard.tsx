import type { MaybeClient } from "@/shared/api/types.ts";
import { requireClient } from "@/shared/api/types.ts";
import { Button } from "@/shared/components/Button/Button.tsx";
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
      className="application-row ui-batch-card"
      aria-labelledby="markdown-batch-heading"
    >
      <div className="ui-batch-card-header">
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

      <form onSubmit={handleImport} className="ui-toolbar-row">
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
        <Button
          type="submit"
          variant="primary"
          disabled={busy || files.length === 0}
        >
          <Upload size={15} aria-hidden="true" />
          {busy ? "Importando…" : "Importar lote"}
        </Button>
      </form>

      {error && (
        <p role="alert" className="settings-ai-alert settings-ai-alert-error">
          {error}
        </p>
      )}

      {summary && (
        <div role="status" className="settings-ai-meta">
          <strong>Lote {summary.batch_id}:</strong> {summary.created} creados ·{" "}
          {summary.reused} reutilizados · {summary.rejected} rechazados
        </div>
      )}
    </section>
  );
}
