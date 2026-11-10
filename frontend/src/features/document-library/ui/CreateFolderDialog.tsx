import { Button } from "@/shared/components/Button/Button.tsx";
import { ModalDialog } from "@/shared/components/ModalDialog.tsx";
import { X } from "lucide-react";
import type { FormEvent } from "react";
import { useRef, useState } from "react";

export function CreateFolderDialog({
  onCreate,
  onClose,
  error,
}: {
  onCreate: (name: string) => Promise<boolean>;
  onClose: () => void;
  error: string;
}) {
  const [name, setName] = useState("");
  const [busy, setBusy] = useState(false);
  const input = useRef<HTMLInputElement>(null);
  const pending = useRef(false);
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (pending.current || !name.trim()) return;
    pending.current = true;
    setBusy(true);
    try {
      if (await onCreate(name.trim())) onClose();
    } finally {
      pending.current = false;
      setBusy(false);
    }
  }
  return (
    <ModalDialog
      className="move-document-modal"
      aria-labelledby="create-folder-title"
      onClose={onClose}
      initialFocusRef={input}
    >
      <header>
        <div>
          <p>Organiza tu biblioteca</p>
          <h2 id="create-folder-title">Nueva Carpeta</h2>
        </div>
        <Button variant="ghost" onClick={onClose} aria-label="Cerrar">
          <X size={18} />
        </Button>
      </header>
      <form onSubmit={submit} className="assign-document-form" aria-busy={busy}>
        {error && <p role="alert">{error}</p>}
        <label>
          Nombre de carpeta
          <input
            ref={input}
            value={name}
            onChange={(event) => setName(event.target.value)}
            maxLength={255}
            required
          />
        </label>
        <footer>
          <Button onClick={onClose}>Cancelar</Button>
          <Button
            type="submit"
            variant="primary"
            busy={busy}
            disabled={!name.trim()}
          >
            {busy ? "Creando…" : "Crear"}
          </Button>
        </footer>
      </form>
    </ModalDialog>
  );
}
