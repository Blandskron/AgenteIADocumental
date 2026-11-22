import type { PageProps } from "@/app/router/useAppRouter.ts";
import { useAuthContext } from "@/app/providers/AuthProvider.tsx";
import { appRoutes } from "@/app/router/routes.ts";
import {
  fetchAuditLogs,
  type AuditLogEntry,
} from "@/features/audit-logs/api/audit-logs.api.ts";
import { Button } from "@/shared/components/Button/Button.tsx";
import { PageState } from "@/shared/components/PageState.tsx";
import { useSidebarState } from "@/shared/hooks/useSidebarState.ts";
import { AppShell } from "@/shared/layouts/AppShell.tsx";
import { toError } from "@/shared/lib/errors.ts";
import { Sidebar } from "@/widgets/Sidebar/Sidebar.tsx";
import { RefreshCw, ShieldAlert } from "lucide-react";
import { useCallback, useEffect, useState } from "react";

export function AuditLogsPage({ onNavigate }: PageProps) {
  const { authClient, currentUser, logout } = useAuthContext();
  const [sidebarOpen, setSidebarOpen] = useSidebarState();
  const [items, setItems] = useState<AuditLogEntry[]>([]);
  const [total, setTotal] = useState(0);
  const [actionFilter, setActionFilter] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadLogs = useCallback(
    async (signal?: AbortSignal) => {
      setLoading(true);
      setError(null);
      try {
        const page = await fetchAuditLogs(authClient, {
          action: actionFilter.trim() || undefined,
          limit: 50,
          offset: 0,
          signal,
        });
        if (signal?.aborted) return;
        setItems(page.items);
        setTotal(page.total);
      } catch (caught) {
        if (
          signal?.aborted ||
          (caught instanceof Error && caught.name === "AbortError")
        ) {
          return;
        }
        setError(
          toError(caught).message ||
            "No se pudo cargar el historial de auditoría.",
        );
      } finally {
        if (!signal?.aborted) {
          setLoading(false);
        }
      }
    },
    [authClient, actionFilter],
  );

  useEffect(() => {
    const controller = new AbortController();
    void loadLogs(controller.signal);
    return () => controller.abort();
  }, [loadLogs]);

  return (
    <AppShell
      sidebarOpen={sidebarOpen}
      onSidebarChange={setSidebarOpen}
      sidebar={
        <Sidebar
          collapsed={!sidebarOpen}
          activeRoute={appRoutes.auditLogs}
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
            <h1>Auditoría de seguridad</h1>
            <p>
              Registro persistente de cambios administrativos (IA, permisos y
              operaciones críticas) sin exposición de secretos.
            </p>
          </div>
          <Button
            type="button"
            variant="secondary"
            onClick={() => void loadLogs()}
            disabled={loading}
          >
            <RefreshCw size={15} aria-hidden="true" />
            Actualizar ({total})
          </Button>
        </header>

        <div className="ui-toolbar-row">
          <label htmlFor="audit-action-filter">Filtrar acción:</label>
          <input
            id="audit-action-filter"
            placeholder="ej. ai_settings_write"
            value={actionFilter}
            onChange={(event) => setActionFilter(event.target.value)}
          />
        </div>

        {loading && <PageState title="Cargando auditoría…" loading />}
        {!loading && error && (
          <div
            className="settings-ai-alert settings-ai-alert-error"
            role="alert"
          >
            {error}
          </div>
        )}

        {!loading && !error && (
          <section className="settings-ai-card" aria-label="Tabla de auditoría">
            {items.length === 0 ? (
              <p className="settings-ai-meta">
                <ShieldAlert size={15} aria-hidden="true" /> Sin eventos
                registrados para el filtro actual.
              </p>
            ) : (
              <div className="ui-table-scroll">
                <table className="ui-data-table">
                  <thead>
                    <tr>
                      <th>Fecha UTC</th>
                      <th>Acción</th>
                      <th>Recurso</th>
                      <th>Actor</th>
                      <th>Detalle</th>
                    </tr>
                  </thead>
                  <tbody>
                    {items.map((row) => (
                      <tr key={row.audit_id}>
                        <td>{row.created_at}</td>
                        <td>
                          <code>{row.action}</code>
                        </td>
                        <td>{row.resource_type}</td>
                        <td>{row.actor_user_id || "-"}</td>
                        <td>
                          <code>{JSON.stringify(row.metadata)}</code>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>
        )}
      </main>
    </AppShell>
  );
}
