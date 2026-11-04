import { useState } from "react";
import { LockKeyhole, UserRound } from "lucide-react";

import { Brand } from "../../../shared/components/Brand/Brand";

export function LoginForm({ error, isSubmitting, onSubmit }) {
  const [credentials, setCredentials] = useState({ username: "", password: "" });

  async function handleSubmit(event) {
    event.preventDefault();
    const success = await onSubmit(credentials);

    if (success) {
      setCredentials({ username: "", password: "" });
    }
  }

  function updateField(field, value) {
    setCredentials((current) => ({ ...current, [field]: value }));
  }

  return (
    <form className="login-card" onSubmit={handleSubmit}>
      <Brand subtitle="Acceso seguro" className="login-brand" />

      <label>
        Usuario
        <span className="login-input-wrap">
          <UserRound size={17} />
          <input
            value={credentials.username}
            onChange={(event) => updateField("username", event.target.value)}
            autoComplete="username"
            required
          />
        </span>
      </label>

      <label>
        Password
        <span className="login-input-wrap">
          <LockKeyhole size={17} />
          <input
            value={credentials.password}
            onChange={(event) => updateField("password", event.target.value)}
            type="password"
            autoComplete="current-password"
            required
          />
        </span>
      </label>

      {error && <div className="login-error">{error}</div>}

      <button className="login-button" disabled={isSubmitting}>
        {isSubmitting ? "Ingresando..." : "Ingresar"}
      </button>

      {/* Frase eliminada por requerimiento */}
    </form>
  );
}
