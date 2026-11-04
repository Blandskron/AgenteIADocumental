import { useState } from "react";
import { Brand } from "../../../shared/components/Brand/Brand";

export function RegisterForm({ error, isSubmitting, onSubmit }) {
  const [form, setForm] = useState({ username: "", password: "", email: "" });

  async function handleSubmit(event) {
    event.preventDefault();
    await onSubmit(form);
  }

  function updateField(field, value) {
    setForm((current) => ({ ...current, [field]: value }));
  }

  return (
    <form className="login-card" onSubmit={handleSubmit}>
      <Brand subtitle="Registro de usuario" className="login-brand" />
      <label>
        Usuario
        <input value={form.username} onChange={e => updateField("username", e.target.value)} required />
      </label>
      <label>
        Email
        <input type="email" value={form.email} onChange={e => updateField("email", e.target.value)} required />
      </label>
      <label>
        Password
        <input type="password" value={form.password} onChange={e => updateField("password", e.target.value)} required />
      </label>
      {error && <div className="login-error">{error}</div>}
      <button className="login-button" disabled={isSubmitting}>
        {isSubmitting ? "Registrando..." : "Registrar"}
      </button>
    </form>
  );
}
