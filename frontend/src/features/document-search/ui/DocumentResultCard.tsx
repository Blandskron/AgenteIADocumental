import { formatDate } from "@/shared/utils/format.ts";
import type { DocumentItem } from "@/entities/document/model/types.ts";
import {
  Download,
  Eye,
  FileArchive,
  FileSpreadsheet,
  FileText,
  FolderInput,
  MoreVertical,
  Send,
  Star,
  Trash2,
} from "lucide-react";
import { useEffect, useRef, useState } from "react";
type DocumentAction = (document: DocumentItem) => void;
interface DocumentResultCardProps {
  document: DocumentItem;
  isFavorite?: boolean;
  folderName?: string;
  onDelete: DocumentAction;
  onAssign: DocumentAction;
  onDownload: DocumentAction;
  onMoveToFolder: DocumentAction;
  onPreview: DocumentAction;
  onSendToChat: DocumentAction;
  onToggleFavorite: DocumentAction;
  permissions?: { download?: boolean; delete?: boolean; assign?: boolean };
}

export function DocumentResultCard({
  document,
  isFavorite,
  folderName,
  onDelete,
  onAssign,
  onDownload,
  onMoveToFolder,
  onPreview,
  onSendToChat,
  onToggleFavorite,
  permissions = {},
}: DocumentResultCardProps) {
  const [menuOpen, setMenuOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);

  const canSendToChat = document.status === "PROCESSED";
  const canDownload = permissions.download !== false;
  const canDelete = permissions.delete !== false;
  const canAssign = Boolean(permissions.assign);
  const { icon: FileIcon, badgeClass } = getFileTypeInfo(document.filename);

  // Cerrar el menú al hacer clic afuera
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (
        menuOpen &&
        menuRef.current &&
        !menuRef.current.contains(event.target as Node) &&
        !triggerRef.current?.contains(event.target as Node)
      ) {
        setMenuOpen(false);
      }
    }
    window.addEventListener("mousedown", handleClickOutside);
    return () => {
      window.removeEventListener("mousedown", handleClickOutside);
    };
  }, [menuOpen]);

  const handleAction = (callback: DocumentAction) => {
    callback(document);
    setMenuOpen(false);
  };

  const formattedSize = document.size_bytes
    ? formatBytes(document.size_bytes)
    : `${document.chunkCount || 1} fragmentos`;

  return (
    <article
      className={`document-result-card-v2 ${menuOpen ? "menu-active" : ""}`}
    >
      {/* Fila superior: Icono de archivo e íconos de acción principal */}
      <div className="card-top-row">
        <div className={`file-type-badge-circle ${badgeClass}`}>
          <FileIcon size={18} />
        </div>

        {/* Acciones principales visibles: Ver (ojo) y Acciones (3 puntos) */}
        <div className="card-main-actions">
          <button
            className="icon-action-button-v2"
            onClick={() => onPreview(document)}
            title="Vista rápida"
            aria-label={`Vista rápida de ${document.filename}`}
            type="button"
          >
            <Eye size={15} />
          </button>

          <div className="dropdown-trigger-container">
            <button
              ref={triggerRef}
              className={`icon-action-button-v2 3dots-btn ${menuOpen ? "active" : ""}`}
              onClick={() => setMenuOpen(!menuOpen)}
              title="Acciones"
              aria-label={`Acciones de ${document.filename}`}
              aria-expanded={menuOpen}
              type="button"
            >
              <MoreVertical size={15} />
            </button>

            {menuOpen && (
              <div
                ref={menuRef}
                className="document-dropdown-menu"
                onKeyDown={(event) => {
                  if (event.key === "Escape") {
                    setMenuOpen(false);
                    triggerRef.current?.focus();
                  }
                }}
              >
                <button
                  className="dropdown-item"
                  onClick={() => handleAction(() => onToggleFavorite(document))}
                  type="button"
                >
                  <Star
                    size={14}
                    className={isFavorite ? "favorite-active-star" : ""}
                    fill={isFavorite ? "currentColor" : "none"}
                  />
                  <span>{isFavorite ? "Quitar de favoritos" : "Favorito"}</span>
                </button>

                <button
                  className="dropdown-item"
                  disabled={!canDownload}
                  onClick={() => handleAction(onDownload)}
                  type="button"
                >
                  <Download size={14} />
                  <span>Descargar</span>
                </button>

                <button
                  className="dropdown-item"
                  onClick={() => handleAction(onMoveToFolder)}
                  type="button"
                >
                  <FolderInput size={14} />
                  <span>Mover a carpeta</span>
                </button>

                <button
                  className="dropdown-item"
                  disabled={!canAssign}
                  onClick={() => handleAction(onAssign)}
                  type="button"
                >
                  <Send size={14} />
                  <span>Asignar</span>
                </button>

                <button
                  className="dropdown-item"
                  disabled={!canSendToChat}
                  onClick={() => handleAction(onSendToChat)}
                  type="button"
                  title={
                    !canSendToChat ? "El archivo debe estar procesado" : ""
                  }
                >
                  <FileText size={14} />
                  <span>Enviar al chat</span>
                </button>

                <div className="dropdown-divider" />

                <button
                  className="dropdown-item danger"
                  disabled={!canDelete}
                  onClick={() => handleAction(onDelete)}
                  type="button"
                >
                  <Trash2 size={14} />
                  <span>Eliminar</span>
                </button>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Información del documento */}
      <div className="card-info-body">
        <h3
          className="document-filename-title"
          title={document.filename}
          style={{ display: "flex", alignItems: "center", gap: "6px" }}
        >
          {isFavorite && (
            <Star
              size={15}
              className="favorite-active-star"
              fill="#f59e0b"
              color="#f59e0b"
              style={{ flexShrink: 0 }}
            />
          )}
          <span>{document.filename}</span>
        </h3>

        {/* Nombre de la carpeta */}
        {folderName ? (
          <span className="document-folder-badge">
            <FolderInput size={11} style={{ marginRight: 4 }} />
            {folderName}
          </span>
        ) : (
          <span className="document-folder-badge unassigned">Sin carpeta</span>
        )}

        {/* Metadatos de tamaño y fecha */}
        <div className="document-meta-info">
          <span>{formattedSize}</span>
          <span className="meta-dot">•</span>
          <span>
            {document.updatedAt ? formatDate(document.updatedAt) : "Reciente"}
          </span>
        </div>
      </div>
    </article>
  );
}

function getFileTypeInfo(filename: string) {
  const name = filename.toLowerCase();
  if (name.endsWith(".pdf")) {
    return { icon: FileText, badgeClass: "file-badge-pdf" };
  }
  if (
    name.endsWith(".xlsx") ||
    name.endsWith(".xls") ||
    name.endsWith(".csv")
  ) {
    return { icon: FileSpreadsheet, badgeClass: "file-badge-spreadsheet" };
  }
  if (
    name.endsWith(".docx") ||
    name.endsWith(".doc") ||
    name.endsWith(".txt") ||
    name.endsWith(".md")
  ) {
    return { icon: FileText, badgeClass: "file-badge-doc" };
  }
  if (name.endsWith(".pptx") || name.endsWith(".ppt")) {
    return { icon: FileText, badgeClass: "file-badge-presentation" };
  }
  if (
    name.endsWith(".zip") ||
    name.endsWith(".rar") ||
    name.endsWith(".7z") ||
    name.endsWith(".tar") ||
    name.endsWith(".gz")
  ) {
    return { icon: FileArchive, badgeClass: "file-badge-archive" };
  }
  return { icon: FileText, badgeClass: "file-badge-default" };
}

function formatBytes(bytes: number, decimals = 1) {
  if (!bytes) return "0 Bytes";
  const k = 1024;
  const dm = decimals < 0 ? 0 : decimals;
  const sizes = ["Bytes", "KB", "MB", "GB"];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(dm)) + " " + sizes[i];
}
