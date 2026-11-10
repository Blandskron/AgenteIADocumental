import type { DocumentItem } from "@/entities/document/model/types.ts";
import type { listUsers } from "@/features/auth/api/user-management.api.ts";
import { ModalDialog } from "@/shared/components/ModalDialog.tsx";
import { formatDate } from "@/shared/utils/format.ts";
import { X } from "lucide-react";
import type { FormEvent } from "react";
import type { Assignment } from "../api/document-access.api.ts";
interface AssignmentForm {
  userId: string;
  allowDownload: boolean;
  dueAt: string;
}

interface WorkflowPage {
  loading: boolean;
  error: string;
  hasMore: boolean;
  reload: () => void;
  loadMore: () => void;
}

export function AssignmentWorkflowList({
  assignments,
  mode,
  onAction,
  onDownload,
  pagination,
}: {
  assignments: Assignment[];
  mode: "assigned" | "managed";
  onAction: (assignment: Assignment, action: string) => void;
  onDownload: (assignment: Assignment) => void;
  pagination: WorkflowPage;
}) {
  const isAssigned = mode === "assigned";
  const STATUS_LABELS: Record<string, string> = {
    PENDING: "Pendiente",
    SIGNED: "Firmado",
    APPROVED: "Aprobado",
    ACCEPTED: "Aprobado",
    REJECTED: "Rechazado",
    VIEWED: "Visto",
    CANCELLED: "Cancelado",
  };

  return (
    <section className="documents-list-section">
      <div className="section-header-row">
        <h3>
          {isAssigned ? "Documentos asignados a mi" : "Documentos que gestiono"}
        </h3>
        <span className="section-header-badge">
          {assignments.length} asignaciones cargadas
        </span>
      </div>
      <div className="workflow-list">
        {assignments.map((assignment) => (
          <article className="workflow-card" key={assignment.assignmentId}>
            <div>
              <strong>Documento {assignment.documentId.slice(0, 8)}</strong>
              <p
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: "6px",
                  flexWrap: "wrap",
                  margin: "4px 0",
                }}
              >
                <span>Estado:</span>
                <span
                  className={`status-badge status-${assignment.status.toLowerCase()}`}
                >
                  {STATUS_LABELS[assignment.status] || assignment.status}
                </span>
                {assignment.dueAt
                  ? ` · vence ${formatDate(assignment.dueAt)}`
                  : ""}
              </p>
              <span>
                {isAssigned
                  ? `Asignado por ${assignment.assignedByUserId}`
                  : `Asignado a ${assignment.assignedToUserId}`}
              </span>
            </div>
            <div className="workflow-actions">
              {assignment.allowDownload && (
                <button
                  className="action-button-secondary"
                  type="button"
                  onClick={() => onDownload(assignment)}
                >
                  Descargar
                </button>
              )}
              {isAssigned && assignment.status === "PENDING" && (
                <>
                  <button
                    className="action-button-secondary"
                    type="button"
                    onClick={() => onAction(assignment, "reject")}
                  >
                    Rechazar
                  </button>
                  <button
                    className="action-button-secondary"
                    type="button"
                    onClick={() => onAction(assignment, "sign")}
                  >
                    Firmar
                  </button>
                  <button
                    className="action-button-primary"
                    type="button"
                    onClick={() => onAction(assignment, "accept")}
                  >
                    Aprobar
                  </button>
                </>
              )}
              {!isAssigned && assignment.status === "PENDING" && (
                <button
                  className="action-button-secondary"
                  type="button"
                  onClick={() => onAction(assignment, "cancel")}
                >
                  Cancelar
                </button>
              )}
            </div>
          </article>
        ))}
        {!assignments.length && !pagination.loading && (
          <div className="empty-documents">
            {isAssigned
              ? "No tienes documentos asignados."
              : "Aun no gestionas asignaciones."}
          </div>
        )}
      </div>
      <WorkflowPagination page={pagination} />
    </section>
  );
}

export function WorkflowPagination({ page }: { page: WorkflowPage }) {
  if (page.loading) return <p role="status">Cargando…</p>;
  return (
    <div className="workflow-actions">
      {page.error && (
        <button
          type="button"
          className="action-button-secondary"
          onClick={page.reload}
        >
          Reintentar
        </button>
      )}
      {page.hasMore && (
        <button
          type="button"
          className="action-button-secondary"
          onClick={page.loadMore}
        >
          Cargar más
        </button>
      )}
    </div>
  );
}

export function AssignDocumentModal({
  document,
  form,
  isOpen,
  users,
  onChange,
  onClose,
  onSubmit,
}: {
  document: DocumentItem | null;
  form: AssignmentForm;
  isOpen: boolean;
  users: Awaited<ReturnType<typeof listUsers>>;
  onChange: (form: AssignmentForm) => void;
  onClose: () => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
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
        aria-labelledby="assign-document-title"
        onClick={(event) => event.stopPropagation()}
      >
        <header>
          <div>
            <p>Asignar documento</p>
            <h3 id="assign-document-title">
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
        <form className="assign-document-form" onSubmit={onSubmit}>
          <label>
            Usuario destino
            <select
              value={form.userId}
              onChange={(event) =>
                onChange({ ...form, userId: event.target.value })
              }
              required
            >
              <option value="">Selecciona usuario</option>
              {users.map((user) => (
                <option key={user.id} value={user.id}>
                  {user.username} {user.email ? `- ${user.email}` : ""}
                </option>
              ))}
            </select>
          </label>
          <label>
            Vencimiento
            <input
              type="datetime-local"
              value={form.dueAt}
              onChange={(event) =>
                onChange({ ...form, dueAt: event.target.value })
              }
            />
          </label>
          <label className="assign-checkbox">
            <input
              type="checkbox"
              checked={form.allowDownload}
              onChange={(event) =>
                onChange({ ...form, allowDownload: event.target.checked })
              }
            />
            Permitir descarga
          </label>
          <footer>
            <button type="button" onClick={onClose}>
              Cancelar
            </button>
            <button type="submit">Asignar</button>
          </footer>
        </form>
      </ModalDialog>
    </div>
  );
}
