export function TransferWarning({ warning, onDismiss }) {
  if (!warning) return null;
  return <p role="status" className="transfer-state error">{warning} <button type="button" onClick={onDismiss}>Cerrar aviso</button></p>;
}
