import "./ConfirmModal.css";
import { useId } from "react";
import { ModalDialog } from "../ModalDialog";

export function ConfirmModal({ isOpen, title, message, confirmText = "Eliminar", cancelText = "Cancelar", onConfirm, onCancel }) {
  const titleId = useId();
  if (!isOpen) return null;
  return (
    <div className="modal-overlay" role="presentation" onClick={onCancel}>
      <ModalDialog className="modal-content confirm-modal" aria-labelledby={titleId} onClose={onCancel} onClick={(event) => event.stopPropagation()}>
        <h3 id={titleId}>{title}</h3>
        <p>{message}</p>
        <div className="modal-actions">
          <button className="modal-cancel" autoFocus onClick={onCancel}>{cancelText}</button>
          <button className="modal-confirm danger" onClick={onConfirm}>{confirmText}</button>
        </div>
      </ModalDialog>
    </div>
  );
}
