import { pendingImportAttempt } from "./import-attempt.js";

export function ImportAttemptNotice({ scope, isBusy, onRetry }) {
  const pending = scope ? pendingImportAttempt(scope) : null;
  if (!pending) return null;
  return (
    <div role="status">
      <p>Hay una importación sin resultado confirmado. Consulta la operación anterior antes de cambiar la selección.</p>
      <button className="action-button-secondary" type="button" disabled={isBusy} onClick={(event) => onRetry(event, pending)}>
        Consultar importación pendiente
      </button>
    </div>
  );
}
