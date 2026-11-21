import type { PageProps } from "@/app/router/useAppRouter.ts";
import { useAuthContext } from "@/app/providers/AuthProvider.tsx";
import { appRoutes } from "@/app/router/routes.ts";
import { SafeMarkdown } from "@/features/chat/ui/SafeMarkdown.tsx";
import { useSidebarState } from "@/shared/hooks/useSidebarState.ts";
import { AppShell } from "@/shared/layouts/AppShell.tsx";
import { Sidebar } from "@/widgets/Sidebar/Sidebar.tsx";
import {
  BookOpenCheck,
  FileText,
  Sparkles,
  Table2,
  ListChecks,
} from "lucide-react";
import { useState } from "react";

const P0_TEMPLATE_GROUPS = [
  {
    id: "summary.executive",
    label: "Resumen ejecutivo",
    family: "Resúmenes",
    description: "Síntesis ejecutiva con citas verificadas [Fuente N].",
    icon: Sparkles,
  },
  {
    id: "report.technical",
    label: "Informe técnico / Minuta / FAQ",
    family: "Reportes plantillados",
    description:
      "Documento estructurado con secciones, decisiones y vacíos explícitos.",
    icon: FileText,
  },
  {
    id: "evidence_table",
    label: "Tabla de evidencia (+ CSV)",
    family: "Evidencia estructurada",
    description:
      "Comparativa de métricas con procedencia por celda y exportación CSV segura.",
    icon: Table2,
  },
  {
    id: "proposed_tasks",
    label: "Tareas propuestas",
    family: "Acciones (revisión humana)",
    description:
      "Lista de tareas extraídas con estado proposed/accepted/rejected/done; sin auto-ejecución.",
    icon: ListChecks,
  },
] as const;

export function StudioPage({ onNavigate }: PageProps) {
  const { currentUser, logout } = useAuthContext();
  const [sidebarOpen, setSidebarOpen] = useSidebarState();
  const [activeTab, setActiveTab] = useState<"generate" | "artifacts">(
    "generate",
  );
  const [selectedTemplate, setSelectedTemplate] =
    useState<string>("summary.executive");
  const [draftMarkdown, setDraftMarkdown] = useState<string>(
    "# Vista previa de Knowledge Studio\n\nSelecciona una colección autorizada y una plantilla P0 para generar un artefacto con citas verificables `[Fuente N]`.",
  );
  const [citationsDetached, setCitationsDetached] = useState(false);

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
            <h1>Knowledge Studio (P0)</h1>
            <p>
              Genera artefactos reutilizables, versionados y auditables con
              citas ancladas al texto real de tus documentos autorizados.
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
              Mis artefactos
            </button>
          </div>
        </header>

        {activeTab === "generate" ? (
          <div className="settings-ai-grid">
            <section
              className="settings-ai-card"
              aria-labelledby="studio-templates-heading"
            >
              <div className="settings-ai-card-title">
                <BookOpenCheck size={18} aria-hidden="true" />
                <h2 id="studio-templates-heading">Plantillas P0</h2>
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
                <h2 id="studio-editor-heading">
                  Previsualización y editor ligero
                </h2>
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
                rows={6}
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
              <div
                style={{
                  padding: "0.75rem",
                  borderRadius: "8px",
                  border: "1px solid var(--border-subtle, #cbd5e1)",
                }}
              >
                <SafeMarkdown content={draftMarkdown} />
              </div>
            </section>
          </div>
        ) : (
          <section className="settings-ai-card">
            <h2>Mis artefactos</h2>
            <p className="settings-ai-meta">
              Los artefactos generados se versionan automáticamente en{" "}
              <code>studio.artifacts</code> y se marcan <code>STALE</code> si
              cambia o se elimina una fuente.
            </p>
          </section>
        )}
      </main>
    </AppShell>
  );
}
