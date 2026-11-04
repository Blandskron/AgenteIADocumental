import "./ConfirmModal.css";

export function ConfirmModal({ isOpen, title, message, confirmText = "Eliminar", cancelText = "Cancelar", onConfirm, onCancel }) {
  if (!isOpen) return null;
  return (
    <div className="modal-overlay" role="presentation" onClick={onCancel}>
      <div className="modal-content confirm-modal" role="dialog" aria-modal="true" onClick={(event) => event.stopPropagation()}>
        <h3>{title}</h3>
        <p>{message}</p>
        <div className="modal-actions">
          <button className="modal-cancel" onClick={onCancel}>{cancelText}</button>
          <button className="modal-confirm danger" onClick={onConfirm}>{confirmText}</button>
        </div>
      </div>
    </div>
  );
}
