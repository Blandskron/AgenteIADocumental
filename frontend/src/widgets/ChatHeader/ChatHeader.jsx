import { Bell, CircleUserRound, LogOut, Menu, X } from "lucide-react";

import { IconButton } from "../../shared/components/IconButton/IconButton";

export function ChatHeader({
  title,
  selectedDocuments = [],
  onClearSelectedDocuments,
  onOpenSidebar,
  onLogout,
}) {
  return (
    <header className="chat-header">
      <IconButton className="menu-button" onClick={onOpenSidebar} aria-label="Abrir menu">
        <Menu size={20} />
      </IconButton>
      <div className="chat-header-context">
        <p>Sesion activa</p>
        <h2>{title}</h2>
        {selectedDocuments.length > 0 && (
          <div className="selected-documents-chip">
            <span>{selectedDocuments.map((document) => document.filename).join(", ")}</span>
            <button onClick={onClearSelectedDocuments} aria-label="Quitar documentos seleccionados">
              <X size={13} />
            </button>
          </div>
        )}
      </div>
      <div className="header-actions">
        <IconButton aria-label="Notificaciones">
          <Bell size={16} />
        </IconButton>
        <IconButton onClick={onLogout} aria-label="Salir">
          <LogOut size={16} />
        </IconButton>
        <IconButton aria-label="Perfil">
          <CircleUserRound size={17} />
        </IconButton>
      </div>
    </header>
  );
}
