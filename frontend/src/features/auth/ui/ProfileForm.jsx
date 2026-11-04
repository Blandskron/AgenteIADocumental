import { useState } from "react";
import { Brand } from "../../../shared/components/Brand/Brand";

export function ProfileForm({ user, error, isSubmitting, onSubmit }) {
  const [form, setForm] = useState({
    username: user?.username || "",
    email: user?.email || "",
    displayName: user?.displayName || "",
  });

  async function handleSubmit(event) {
    event.preventDefault();
    await onSubmit(form);
  }

  function updateField(field, value) {
    setForm((current) => ({ ...current, [field]: value }));
  }

  return (
    <form className="login-card" onSubmit={handleSubmit}>
      <Brand subtitle="Perfil de usuario" className="login-brand" />
      <label>
        Usuario
        <input value={form.username} onChange={e => updateField("username", e.target.value)} required />
      </label>
      <label>
        Email
        <input type="email" value={form.email} onChange={e => updateField("email", e.target.value)} required />
      </label>
      <label>
        Nombre para mostrar
        <input value={form.displayName} onChange={e => updateField("displayName", e.target.value)} />
      </label>
      {error && <div className="login-error">{error}</div>}
      <button className="login-button" disabled={isSubmitting}>
        {isSubmitting ? "Guardando..." : "Guardar cambios"}
      </button>
    </form>
  );
}
