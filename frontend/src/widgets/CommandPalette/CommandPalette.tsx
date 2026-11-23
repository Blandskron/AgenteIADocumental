import { appRoutes } from "@/app/router/routes.ts";
import { ModalDialog } from "@/shared/components/ModalDialog.tsx";
import { Search } from "lucide-react";
import { useDeferredValue, useEffect, useMemo, useState } from "react";

export interface CommandItem {
  id: string;
  label: string;
  description: string;
  route: string;
  keywords: string;
}

export function buildCommandItems(permissions: {
  canUseChat: boolean;
  canUseIntegrations: boolean;
  canAdmin: boolean;
  canManageAiSettings: boolean;
}): CommandItem[] {
  const items: CommandItem[] = [];
  if (permissions.canUseChat) {
    items.push({
      id: "chat",
      label: "Chat documental y Agente IA",
      description: "Consultar documentos con RAG híbrido, Agente y Code Mode",
      route: appRoutes.chat,
      keywords: "chat rag agente code mode preguntas citas",
    });
  }
  items.push(
    {
      id: "documents",
      label: "Biblioteca de documentos",
      description: "Subir, buscar, organizar carpetas y previsualizar archivos",
      route: appRoutes.documents,
      keywords: "documentos biblioteca subir pdf docx xlsx pptx buscar",
    },
    {
      id: "assignments",
      label: "Asignaciones y firmas",
      description: "Revisar y aprobar documentos asignados",
      route: appRoutes.documentAssignments,
      keywords: "asignaciones firmas aprobaciones revision",
    },
    {
      id: "studio",
      label: "Knowledge Studio",
      description:
        "Informes citados, tablas de evidencia, tarjetas SM-2 y quiz",
      route: appRoutes.studio,
      keywords: "studio informes resumenes flashcards quiz grafos",
    },
    {
      id: "profile",
      label: "Mi perfil",
      description: "Datos de cuenta, avatar y seguridad",
      route: appRoutes.profile,
      keywords: "perfil cuenta avatar contraseña",
    },
  );
  if (permissions.canUseIntegrations) {
    items.push({
      id: "applications",
      label: "Aplicaciones e importación",
      description: "Google Drive OAuth PKCE y lotes ZIP/Markdown",
      route: appRoutes.applications,
      keywords: "aplicaciones drive importacion zip markdown",
    });
  }
  if (permissions.canManageAiSettings) {
    items.push({
      id: "settings-ai",
      label: "Configuración de IA",
      description: "Elegir entre Ollama local CPU o Groq cifrado",
      route: appRoutes.settingsAi,
      keywords: "ia ollama groq modelos api key proveedor",
    });
  }
  if (permissions.canAdmin) {
    items.push(
      {
        id: "admin",
        label: "Administración multiempresa",
        description: "Empresas, áreas, usuarios, grupos y permisos RBAC",
        route: appRoutes.admin,
        keywords: "admin empresas tenants usuarios grupos rbac",
      },
      {
        id: "audit",
        label: "Auditoría de seguridad",
        description: "Bitácora inmutable de cambios críticos y exportación CSV",
        route: appRoutes.auditLogs,
        keywords: "auditoria logs seguridad csv eventos",
      },
    );
  }
  return items;
}

export function CommandPalette({
  onNavigate,
  canUseChat,
  canUseIntegrations,
  canAdmin,
  canManageAiSettings,
}: {
  onNavigate: (route: string) => void;
  canUseChat: boolean;
  canUseIntegrations: boolean;
  canAdmin: boolean;
  canManageAiSettings: boolean;
}) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const deferredQuery = useDeferredValue(query);
  const [selectedIndex, setSelectedIndex] = useState(0);

  const allItems = useMemo(
    () =>
      buildCommandItems({
        canUseChat,
        canUseIntegrations,
        canAdmin,
        canManageAiSettings,
      }),
    [canUseChat, canUseIntegrations, canAdmin, canManageAiSettings],
  );

  const filtered = useMemo(() => {
    const q = deferredQuery.trim().toLowerCase();
    if (!q) return allItems;
    return allItems.filter(
      (item) =>
        item.label.toLowerCase().includes(q) ||
        item.description.toLowerCase().includes(q) ||
        item.keywords.includes(q),
    );
  }, [allItems, deferredQuery]);

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        setOpen((prev) => !prev);
        setQuery("");
        setSelectedIndex(0);
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, []);

  if (!open) return null;

  const activeIdx = Math.min(selectedIndex, Math.max(0, filtered.length - 1));

  const choose = (item: CommandItem) => {
    setOpen(false);
    setQuery("");
    onNavigate(item.route);
  };

  return (
    <div className="document-preview-backdrop" role="presentation">
      <ModalDialog
        className="command-palette-modal"
        aria-label="Paleta de comandos rápidos"
        onClose={() => setOpen(false)}
      >
        <div className="command-palette-search">
          <Search size={16} aria-hidden="true" />
          <input
            type="search"
            autoFocus
            placeholder="Ir a vista o acción… (Ctrl+K)"
            aria-label="Buscar vista o comando"
            value={query}
            onChange={(event) => {
              setQuery(event.target.value);
              setSelectedIndex(0);
            }}
            onKeyDown={(event) => {
              if (event.key === "ArrowDown") {
                event.preventDefault();
                setSelectedIndex((prev) =>
                  filtered.length ? (prev + 1) % filtered.length : 0,
                );
              } else if (event.key === "ArrowUp") {
                event.preventDefault();
                setSelectedIndex((prev) =>
                  filtered.length
                    ? (prev - 1 + filtered.length) % filtered.length
                    : 0,
                );
              } else if (event.key === "Enter" && filtered[activeIdx]) {
                event.preventDefault();
                choose(filtered[activeIdx]);
              }
            }}
          />
        </div>
        <ul className="command-palette-list" role="listbox">
          {filtered.length === 0 ? (
            <li className="command-palette-empty">
              Sin resultados para &ldquo;{query}&rdquo;.
            </li>
          ) : (
            filtered.map((item, idx) => (
              <li key={item.id} role="option" aria-selected={idx === activeIdx}>
                <button
                  type="button"
                  className={`command-palette-item ${idx === activeIdx ? "is-active" : ""}`.trim()}
                  onClick={() => choose(item)}
                >
                  <strong>{item.label}</strong>
                  <span>{item.description}</span>
                </button>
              </li>
            ))
          )}
        </ul>
      </ModalDialog>
    </div>
  );
}
