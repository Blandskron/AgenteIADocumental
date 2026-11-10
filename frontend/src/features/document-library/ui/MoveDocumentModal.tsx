import type {
  DocumentItem,
  Folder as FolderItem,
} from "@/entities/document/model/types.ts";
import { ModalDialog } from "@/shared/components/ModalDialog.tsx";
import { Folder, X } from "lucide-react";
import type { LibraryPage } from "../library-controller.ts";
import { LibraryPagination } from "./LibraryPagination.tsx";
export function MoveDocumentModal({
  document,
  folders,
  page,
  error,
  onLoadMore,
  isOpen,
  onClose,
  onMove,
}: {
  document: DocumentItem | null;
  folders: FolderItem[];
  page: LibraryPage<FolderItem>;
  error: string;
  onLoadMore: () => void;
  isOpen: boolean;
  onClose: () => void;
  onMove: (folderId: string | null) => void;
}) {
  if (!isOpen) return null;

  return (
    <div
      className="move-document-backdrop"
      role="presentation"
      onClick={onClose}
    >
      <ModalDialog
        onClose={onClose}
        className="move-document-modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="move-document-title"
        onClick={(event) => event.stopPropagation()}
      >
        <header>
          <div>
            <p>Mover documento</p>
            <h3 id="move-document-title">
              {document?.filename || "Documento"}
            </h3>
          </div>
          <button
            className="icon-action-button"
            type="button"
            onClick={onClose}
            aria-label="Cerrar"
          >
            <X size={17} />
          </button>
        </header>
        <div className="move-folder-list">
          {error && <p role="alert">{error}</p>}
          {folders.map((folder) => (
            <button
              key={folder.folderId}
              type="button"
              onClick={() => onMove(folder.folderId)}
            >
              <Folder size={18} />
              <span>{folder.name}</span>
              <small>{formatFolderCount(folder)} archivos</small>
            </button>
          ))}
          {!folders.length && !page.loading && (
            <p>No tienes carpetas raíz creadas.</p>
          )}
          <LibraryPagination
            page={page}
            label="carpetas raíz"
            onLoadMore={onLoadMore}
          />
        </div>
        <footer>
          <button type="button" onClick={() => onMove(null)}>
            Sacar de carpetas
          </button>
          <button type="button" onClick={onClose}>
            Cancelar
          </button>
        </footer>
      </ModalDialog>
    </div>
  );
}

export function formatFolderCount(folder: FolderItem) {
  return Number(folder.documentCount || 0);
}
