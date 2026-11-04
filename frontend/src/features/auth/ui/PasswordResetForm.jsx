import { useState } from "react";
import { Brand } from "../../../shared/components/Brand/Brand";

export function PasswordResetForm({ error, isSubmitting, onSubmit }) {
  const [form, setForm] = useState({ email: "" });

  async function handleSubmit(event) {
    event.preventDefault();
    await onSubmit(form);
  }

  function updateField(field, value) {
    setForm((current) => ({ ...current, [field]: value }));
  }

  return (
    <form className="login-card" onSubmit={handleSubmit}>
      <Brand subtitle="Recuperar contraseña" className="login-brand" />
      <label>
        Email
        <input type="email" value={form.email} onChange={e => updateField("email", e.target.value)} required />
      </label>
      {error && <div className="login-error">{error}</div>}
      <button className="login-button" disabled={isSubmitting}>
        {isSubmitting ? "Enviando..." : "Enviar enlace"}
      </button>
    </form>
  );
}
