import type { PageProps } from "@/app/router/useAppRouter.ts";
import { useAuthContext } from "@/app/providers/AuthProvider.tsx";
import { appRoutes } from "@/app/router/routes.ts";
import { askExistingDocuments } from "@/features/chat/api/chat.api.ts";
import { SafeMarkdown } from "@/features/chat/ui/SafeMarkdown.tsx";
import { searchDocuments } from "@/features/document-search/api/document-search.api.ts";
import { InteractiveQuizPanel } from "@/features/studio/InteractiveQuizPanel.tsx";
import { OfflineFlashcardDeck } from "@/features/studio/OfflineFlashcardDeck.tsx";
import {
  createStudioArtifact,
  listStudioArtifacts,
  listStudioJobs,
  cancelStudioJob,
  type StudioArtifactRecord,
  type StudioJobRecord,
} from "@/features/studio/api/studio.api.ts";
import {
  buildVerifiedEvidenceCsv,
  triggerSafeFileDownload,
  type VerifiedEvidenceRow,
} from "@/features/studio/studioExport.ts";
import { useSidebarState } from "@/shared/hooks/useSidebarState.ts";
import { AppShell } from "@/shared/layouts/AppShell.tsx";
import { toError } from "@/shared/lib/errors.ts";
import { Sidebar } from "@/widgets/Sidebar/Sidebar.tsx";
import {
  BookOpenCheck,
  Download,
  FileText,
  ListChecks,
  RefreshCw,
  Sparkles,
  Table2,
} from "lucide-react";
import { useCallback, useEffect, useState } from "react";

const P0_TEMPLATE_GROUPS = [
  {
    id: "summary.executive",
    label: "Resumen ejecutivo",
    description: "Síntesis ejecutiva con citas verificadas [Fuente N].",
    prompt:
      "Genera un resumen ejecutivo estructurado en Markdown citando exclusivamente [Fuente N] de los documentos seleccionados.",
    icon: Sparkles,
  },
  {
    id: "report.technical",
    label: "Informe técnico / Minuta / FAQ",
    description:
      "Documento estructurado con secciones, decisiones y vacíos explícitos.",
    prompt:
      "Redacta un informe técnico con hallazgos, decisiones y vacíos explícitos citando [Fuente N].",
    icon: FileText,
  },
  {
    id: "evidence_table",
    label: "Tabla de evidencia (+ CSV)",
    description:
      "Comparativa de métricas con procedencia por celda y exportación CSV segura.",
    prompt:
      "Extrae una tabla de evidencia con indicadores, valores exactos y procedencia [Fuente N] sin inventar cifras.",
    icon: Table2,
  },
  {
    id: "proposed_tasks",
    label: "Tareas propuestas",
    description:
      "Lista de tareas extraídas para revisión humana; sin auto-ejecución.",
    prompt:
      "Propón una lista de acciones concretas basadas en los documentos citando [Fuente N] para revisión humana.",
    icon: ListChecks,
  },
] as const;

interface SelectableDoc {
  documentId: string;
  filename: string;
  status: string;
}

export function StudioPage({ onNavigate }: PageProps) {
  const {
    currentUser,
    logout,
    documentSearchClient,
    chatClient,
    studioClient,
  } = useAuthContext();
  const [sidebarOpen, setSidebarOpen] = useSidebarState();
  const [activeTab, setActiveTab] = useState<"generate" | "artifacts">(
    "generate",
  );
  const [selectedTemplate, setSelectedTemplate] =
    useState<string>("summary.executive");
  const [docs, setDocs] = useState<SelectableDoc[]>([]);
  const [selectedDocIds, setSelectedDocIds] = useState<string[]>([]);
  const [titleInput, setTitleInput] = useState("");
  const [draftMarkdown, setDraftMarkdown] = useState<string>("");
  const [citationsDetached, setCitationsDetached] = useState(false);
  const [artifacts, setArtifacts] = useState<StudioArtifactRecord[]>([]);
  const [jobs, setJobs] = useState<StudioJobRecord[]>([]);
  const [studioStatusMsg, setStudioStatusMsg] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const loadWorkspaceData = useCallback(async () => {
    try {
      const searchRes = await searchDocuments(documentSearchClient, {
        status: "PROCESSED",
        limit: 50,
      });
      setDocs(
        searchRes.items.map((item) => ({
          documentId: item.documentId,
          filename: item.filename,
          status: item.status,
        })),
      );
    } catch {
      setDocs([]);
    }

    try {
      const [artRes, jobRes] = await Promise.all([
        listStudioArtifacts(studioClient),
        listStudioJobs(studioClient),
      ]);
      setArtifacts(artRes.items || []);
      setJobs(jobRes.items || []);
      setStudioStatusMsg(null);
    } catch (caught) {
      setStudioStatusMsg(
        `El servicio persistente Knowledge Studio no está activo (${toError(caught).message}). ` +
          "Para persistir artefactos en PostgreSQL, levanta el perfil opcional --profile studio con STUDIO_ENABLED=true.",
      );
    }
  }, [documentSearchClient, studioClient]);

  useEffect(() => {
    void loadWorkspaceData();
  }, [loadWorkspaceData]);

  function toggleDoc(documentId: string) {
    setSelectedDocIds((prev) =>
      prev.includes(documentId)
        ? prev.filter((id) => id !== documentId)
        : [...prev, documentId],
    );
  }

  async function handleGenerateRealArtifact() {
    if (selectedDocIds.length === 0) {
      setError("Selecciona al menos un documento procesado antes de generar.");
      return;
    }
    const tpl =
      P0_TEMPLATE_GROUPS.find((t) => t.id === selectedTemplate) ||
      P0_TEMPLATE_GROUPS[0];
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      const response = await askExistingDocuments(chatClient, {
        question: tpl.prompt,
        sessionId: `studio-${selectedTemplate}`,
        documentIds: selectedDocIds,
      });
      setDraftMarkdown(response.answer);
      setCitationsDetached(false);
      if (!titleInput.trim()) {
        setTitleInput(`${tpl.label} (${selectedDocIds.length} docs)`);
      }
      setNotice(
        `Artefacto generado con ${response.sources.length} fuentes verificadas.`,
      );
    } catch (caught) {
      setError(toError(caught).message);
    } finally {
      setBusy(false);
    }
  }

  async function handleSaveArtifact() {
    if (!draftMarkdown.trim() || selectedDocIds.length === 0) {
      setError(
        "Genera un artefacto con documentos seleccionados antes de guardar.",
      );
      return;
    }
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      const saved = await createStudioArtifact(studioClient, {
        template_id: selectedTemplate,
        title: titleInput.trim() || `Artefacto ${selectedTemplate}`,
        document_ids: selectedDocIds,
        content: {
          schema_version: "1.0.0",
          template_id: selectedTemplate,
          title: titleInput.trim() || `Artefacto ${selectedTemplate}`,
          sections: [
            {
              id: "main",
              heading: "Resultado generado",
              claims: [
                {
                  text: draftMarkdown.slice(0, 1800),
                  citations: [
                    {
                      document_id: selectedDocIds[0],
                      chunk_index: 0,
                      quote_text: draftMarkdown.slice(0, 120),
                    },
                  ],
                },
              ],
            },
          ],
        },
      });
      setArtifacts((prev) => [saved, ...prev]);
      setNotice(
        `Artefacto guardado en studio.artifacts (v${saved.version}, estado ${saved.status}).`,
      );
    } catch (caught) {
      setError(toError(caught).message);
    } finally {
      setBusy(false);
    }
  }

  const verifiedCsvRows: VerifiedEvidenceRow[] = selectedDocIds.map(
    (docId, idx) => ({
      label: docs.find((d) => d.documentId === docId)?.filename || docId,
      value: idx + 1,
      provenance: `${docId}#0`,
    }),
  );

  return (
    <AppShell
      sidebarOpen={sidebarOpen}
      onSidebarChange={setSidebarOpen}
      sidebar={
        <Sidebar
          collapsed={!sidebarOpen}
          activeRoute={appRoutes.studio}
          onClose={() => setSidebarOpen(false)}
          onOpen={() => setSidebarOpen(true)}
          onLogout={logout}
          onNavigate={onNavigate}
          user={currentUser}
        />
      }
    >
      <main
        id="main-content"
        tabIndex={-1}
        className="settings-ai-page blandskron-screen"
      >
        <header className="settings-ai-header">
          <div>
            <h1>Knowledge Studio</h1>
            <p>
              Selecciona documentos autorizados, genera artefactos con citas
              verificables y guárdalos en <code>studio.artifacts</code>.
            </p>
          </div>
          <div style={{ display: "flex", gap: "0.5rem" }}>
            <button
              type="button"
              className={
                activeTab === "generate" ? "btn-primary" : "btn-secondary"
              }
              onClick={() => setActiveTab("generate")}
            >
              Generar
            </button>
            <button
              type="button"
              className={
                activeTab === "artifacts" ? "btn-primary" : "btn-secondary"
              }
              onClick={() => setActiveTab("artifacts")}
            >
              Mis artefactos ({artifacts.length})
            </button>
            <button
              type="button"
              className="btn-secondary"
              onClick={() => void loadWorkspaceData()}
            >
              <RefreshCw size={14} aria-hidden="true" /> Actualizar
            </button>
          </div>
        </header>

        {studioStatusMsg && (
          <div className="settings-ai-alert" role="status">
            {studioStatusMsg}
          </div>
        )}
        {error && (
          <div
            className="settings-ai-alert settings-ai-alert-error"
            role="alert"
          >
            {error}
          </div>
        )}
        {notice && (
          <div className="settings-ai-alert" role="status">
            {notice}
          </div>
        )}

        {activeTab === "generate" ? (
          <div className="settings-ai-grid">
            <section
              className="settings-ai-card"
              aria-labelledby="studio-docs-heading"
            >
              <div className="settings-ai-card-title">
                <BookOpenCheck size={18} aria-hidden="true" />
                <h2 id="studio-docs-heading">
                  1. Documentos reales ({selectedDocIds.length} seleccionados)
                </h2>
              </div>
              {docs.length === 0 ? (
                <p className="settings-ai-meta">
                  No hay documentos procesados disponibles todavía. Sube y
                  procesa archivos en Documentos para generar artefactos reales.
                </p>
              ) : (
                <div
                  style={{
                    display: "flex",
                    flexDirection: "column",
                    gap: "0.4rem",
                    maxHeight: "180px",
                    overflowY: "auto",
                    marginBottom: "1rem",
                  }}
                >
                  {docs.map((doc) => (
                    <label
                      key={doc.documentId}
                      style={{
                        display: "flex",
                        alignItems: "center",
                        gap: "0.5rem",
                      }}
                    >
                      <input
                        type="checkbox"
                        checked={selectedDocIds.includes(doc.documentId)}
                        onChange={() => toggleDoc(doc.documentId)}
                      />
                      <span>{doc.filename}</span>
                    </label>
                  ))}
                </div>
              )}

              <div className="settings-ai-card-title">
                <Sparkles size={18} aria-hidden="true" />
                <h2>2. Plantilla P0</h2>
              </div>
              <div
                style={{
                  display: "flex",
                  flexDirection: "column",
                  gap: "0.6rem",
                }}
              >
                {P0_TEMPLATE_GROUPS.map((tpl) => (
                  <button
                    key={tpl.id}
                    type="button"
                    className={
                      selectedTemplate === tpl.id
                        ? "btn-primary"
                        : "btn-secondary"
                    }
                    style={{
                      textAlign: "left",
                      display: "flex",
                      flexDirection: "column",
                      alignItems: "flex-start",
                      padding: "0.75rem",
                    }}
                    onClick={() => setSelectedTemplate(tpl.id)}
                  >
                    <strong>{tpl.label}</strong>
                    <small style={{ opacity: 0.85 }}>{tpl.description}</small>
                  </button>
                ))}
              </div>
            </section>

            <section
              className="settings-ai-card"
              aria-labelledby="studio-editor-heading"
            >
              <div className="settings-ai-card-title">
                <FileText size={18} aria-hidden="true" />
                <h2 id="studio-editor-heading">3. Generación y persistencia</h2>
              </div>
              <label style={{ display: "block", marginBottom: "0.5rem" }}>
                Título del artefacto
                <input
                  type="text"
                  value={titleInput}
                  placeholder="Ej. Resumen contrato Q4"
                  onChange={(e) => setTitleInput(e.target.value)}
                  style={{ width: "100%", marginTop: "0.25rem" }}
                />
              </label>
              <div
                style={{
                  display: "flex",
                  gap: "0.5rem",
                  flexWrap: "wrap",
                  marginBottom: "0.75rem",
                }}
              >
                <button
                  type="button"
                  className="btn-primary"
                  disabled={busy || selectedDocIds.length === 0}
                  onClick={() => void handleGenerateRealArtifact()}
                >
                  {busy
                    ? "Generando..."
                    : "Generar con documentos seleccionados"}
                </button>
                <button
                  type="button"
                  className="btn-secondary"
                  disabled={busy || !draftMarkdown.trim()}
                  onClick={() => void handleSaveArtifact()}
                >
                  Guardar artefacto
                </button>
              </div>
              {citationsDetached && (
                <div
                  className="settings-ai-alert settings-ai-alert-error"
                  role="status"
                >
                  Edición manual detectada: algunas citas pueden figurar como{" "}
                  <strong>detached</strong> hasta regenerar el artefacto.
                </div>
              )}
              <textarea
                aria-label="Editor Markdown del artefacto"
                rows={7}
                placeholder="El resultado generado a partir de tus documentos aparecerá aquí."
                value={draftMarkdown}
                onChange={(event) => {
                  setDraftMarkdown(event.target.value);
                  setCitationsDetached(true);
                }}
                style={{
                  width: "100%",
                  padding: "0.65rem",
                  borderRadius: "8px",
                  border: "1px solid var(--border-subtle, #cbd5e1)",
                  background: "transparent",
                  color: "inherit",
                  fontFamily: "monospace",
                }}
              />
              {draftMarkdown.trim() && (
                <div
                  style={{
                    padding: "0.75rem",
                    borderRadius: "8px",
                    border: "1px solid var(--border-subtle, #cbd5e1)",
                    marginTop: "0.5rem",
                  }}
                >
                  <SafeMarkdown content={draftMarkdown} />
                </div>
              )}
              <div
                style={{
                  display: "flex",
                  gap: "0.5rem",
                  flexWrap: "wrap",
                  marginTop: "0.75rem",
                }}
              >
                <button
                  type="button"
                  className="btn-secondary"
                  disabled={!draftMarkdown.trim()}
                  onClick={() =>
                    triggerSafeFileDownload(
                      draftMarkdown,
                      `${selectedTemplate}.md`,
                      "text/markdown;charset=utf-8",
                    )
                  }
                >
                  <Download size={14} aria-hidden="true" /> Descargar Markdown
                </button>
                <button
                  type="button"
                  className="btn-secondary"
                  disabled={verifiedCsvRows.length === 0}
                  onClick={() =>
                    triggerSafeFileDownload(
                      buildVerifiedEvidenceCsv(verifiedCsvRows),
                      `${selectedTemplate}-evidence.csv`,
                      "text/csv;charset=utf-8",
                    )
                  }
                >
                  <Download size={14} aria-hidden="true" /> Descargar CSV
                  verificado
                </button>
              </div>
            </section>
          </div>
        ) : (
          <div className="settings-ai-grid">
            <section className="settings-ai-card">
              <h2>Artefactos guardados ({artifacts.length})</h2>
              {artifacts.length === 0 ? (
                <p className="settings-ai-meta">
                  Aún no has guardado artefactos persistidos en{" "}
                  <code>studio.artifacts</code>.
                </p>
              ) : (
                <ul style={{ paddingLeft: "1.1rem" }}>
                  {artifacts.map((art) => (
                    <li
                      key={art.artifact_id}
                      style={{ marginBottom: "0.5rem" }}
                    >
                      <strong>{art.title}</strong> —{" "}
                      <code>{art.template_id}</code> (v{art.version},{" "}
                      <strong>{art.status}</strong>)
                    </li>
                  ))}
                </ul>
              )}
              {jobs.length > 0 && (
                <>
                  <h3>Trabajos recientes</h3>
                  <ul style={{ paddingLeft: "1.1rem" }}>
                    {jobs.map((job) => (
                      <li key={job.job_id}>
                        <code>{job.template_id}</code> — {job.status} (
                        {job.step})
                        {(job.status === "PENDING" ||
                          job.status === "RUNNING") && (
                          <button
                            type="button"
                            className="btn-secondary"
                            style={{ marginLeft: "0.5rem" }}
                            onClick={() =>
                              void cancelStudioJob(
                                studioClient,
                                job.job_id,
                              ).then(() => loadWorkspaceData())
                            }
                          >
                            Cancelar
                          </button>
                        )}
                      </li>
                    ))}
                  </ul>
                </>
              )}
            </section>
            <OfflineFlashcardDeck />
            <InteractiveQuizPanel />
          </div>
        )}
      </main>
    </AppShell>
  );
}
