import type { Credentials } from "@/entities/auth/model/types.ts";
import { Button } from "@/shared/components/Button/Button.tsx";
import { LockKeyhole, UserRound } from "lucide-react";
import type { FormEvent } from "react";
import { useState } from "react";

import { Brand } from "@/shared/components/Brand/Brand.tsx";

export function LoginForm({
  error,
  isSubmitting,
  onSubmit,
}: {
  error: string;
  isSubmitting: boolean;
  onSubmit: (credentials: Credentials) => Promise<boolean>;
}) {
  const [credentials, setCredentials] = useState({
    username: "",
    password: "",
  });

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const success = await onSubmit(credentials);

    if (success) {
      setCredentials({ username: "", password: "" });
    }
  }

  function updateField(field: keyof Credentials, value: string) {
    setCredentials((current) => ({ ...current, [field]: value }));
  }

  return (
    <form
      aria-busy={isSubmitting}
      className="login-card"
      onSubmit={handleSubmit}
    >
      <Brand subtitle="Tu conocimiento, conectado" className="login-brand" />
      <div className="login-heading">
        <p className="eyebrow">ESPACIO DOCUMENTAL</p>
        <h1>Bienvenido de nuevo</h1>
        <p>Accede a tus documentos y encuentra respuestas con fuentes.</p>
      </div>

      <label>
        Usuario
        <span className="login-input-wrap">
          <UserRound size={17} />
          <input
            name="username"
            autoCapitalize="none"
            spellCheck={false}
            value={credentials.username}
            onChange={(event) => updateField("username", event.target.value)}
            autoComplete="username"
            required
          />
        </span>
      </label>

      <label>
        Contraseña
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

      {error && (
        <div className="login-error" role="alert">
          {error}
        </div>
      )}

      <Button
        type="submit"
        variant="primary"
        className="login-button"
        busy={isSubmitting}
      >
        {isSubmitting ? "Ingresando..." : "Ingresar"}
      </Button>
    </form>
  );
}
