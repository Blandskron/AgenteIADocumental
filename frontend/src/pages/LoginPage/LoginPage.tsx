import { useAuthContext } from "@/app/providers/AuthProvider.tsx";
import {
  passwordResetRequest,
  setupStatusRequest,
  type SetupStatusPayload,
} from "@/features/auth/api/auth.api.ts";
import { LoginForm } from "@/features/auth/ui/LoginForm.tsx";
import { Brand } from "@/shared/components/Brand/Brand.tsx";
import { Button } from "@/shared/components/Button/Button.tsx";
import { toError } from "@/shared/lib/errors.ts";
import { FileText, Layers3, Search } from "lucide-react";
import type { FormEvent } from "react";
import { useEffect, useState } from "react";

type AuthScreenMode = "login" | "register" | "reset";

export function LoginPage() {
  const { login, register, loginError, isAuthenticating } = useAuthContext();
  const [mode, setMode] = useState<AuthScreenMode>("login");
  const [setupStatus, setSetupStatus] = useState<SetupStatusPayload | null>(
    null,
  );
  const [regEmail, setRegEmail] = useState("");
  const [regUsername, setRegUsername] = useState("");
  const [regPassword, setRegPassword] = useState("");
  const [workspaceName, setWorkspaceName] = useState("Espacio principal");
  const [resetEmail, setResetEmail] = useState("");
  const [resetFeedback, setResetFeedback] = useState<string | null>(null);
  const [resetBusy, setResetBusy] = useState(false);

  useEffect(() => {
    let active = true;
    setupStatusRequest()
      .then((data) => {
        if (!active) return;
        setSetupStatus(data);
        if (data.needs_setup) {
          setMode("register");
        }
      })
      .catch(() => {
        // Conserva el formulario de inicio de sesión si setup-status no está disponible.
      });
    return () => {
      active = false;
    };
  }, []);

  async function handleRegisterSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    await register({
      email: regEmail.trim(),
      username: regUsername.trim() || undefined,
      password: regPassword,
      workspace_name: setupStatus?.needs_setup
        ? workspaceName.trim() || "Espacio principal"
        : undefined,
    });
  }

  async function handleResetSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setResetBusy(true);
    setResetFeedback(null);
    try {
      const resp = await passwordResetRequest(resetEmail.trim());
      setResetFeedback(resp.detail);
    } catch (caught) {
      setResetFeedback(toError(caught).message);
    } finally {
      setResetBusy(false);
    }
  }

  return (
    <main className="login-shell" id="main-content">
      <div className="login-window">
        <div className="login-identity">
          <Brand className="login-brand" showDescriptor />
          <div className="login-art" aria-hidden="true">
            <div className="login-art-layer login-art-layer--rear">
              <Layers3 size={30} />
            </div>
            <div className="login-art-layer login-art-layer--front">
              <FileText size={48} strokeWidth={1.5} />
            </div>
            <div className="login-art-layer login-art-layer--detail">
              <Search size={26} />
            </div>
          </div>
          <div className="login-product">
            <p className="login-product-slogan">
              Turn Documents into Intelligence.
            </p>
            <p className="login-product-sub">
              Organiza conocimiento, consulta con RAG híbrido y verifica cada
              respuesta con citas trazables.
            </p>
            <p className="login-signature">Open Source · By BLANDSKRON</p>
          </div>
        </div>

        <div className="login-form-column">
          {mode === "login" && (
            <LoginForm
              error={loginError}
              isSubmitting={isAuthenticating}
              onSubmit={login}
            />
          )}

          {mode === "register" && (
            <form
              className="login-card"
              aria-busy={isAuthenticating}
              onSubmit={handleRegisterSubmit}
            >
              <div className="login-heading">
                <h1>
                  {setupStatus?.needs_setup
                    ? "Configuración inicial"
                    : "Crear cuenta"}
                </h1>
                <p>
                  {setupStatus?.needs_setup
                    ? "Crea la primera cuenta para administrar tu espacio documental."
                    : "Registra una cuenta estándar con correo y contraseña."}
                </p>
              </div>
              <label>
                Correo electrónico
                <input
                  type="email"
                  required
                  value={regEmail}
                  onChange={(e) => setRegEmail(e.target.value)}
                  autoComplete="email"
                />
              </label>
              <label>
                Usuario (opcional)
                <input
                  type="text"
                  value={regUsername}
                  onChange={(e) => setRegUsername(e.target.value)}
                  autoComplete="username"
                />
              </label>
              {setupStatus?.needs_setup && (
                <label>
                  Nombre del espacio
                  <input
                    type="text"
                    value={workspaceName}
                    onChange={(e) => setWorkspaceName(e.target.value)}
                  />
                </label>
              )}
              <label>
                Contraseña (mínimo 8 caracteres)
                <input
                  type="password"
                  required
                  minLength={8}
                  value={regPassword}
                  onChange={(e) => setRegPassword(e.target.value)}
                  autoComplete="new-password"
                />
              </label>
              {loginError && (
                <div className="login-error" role="alert">
                  {loginError}
                </div>
              )}
              <Button
                type="submit"
                variant="primary"
                className="login-button"
                busy={isAuthenticating}
              >
                {setupStatus?.needs_setup
                  ? "Crear cuenta administradora"
                  : "Registrarme"}
              </Button>
            </form>
          )}

          {mode === "reset" && (
            <form className="login-card" onSubmit={handleResetSubmit}>
              <div className="login-heading">
                <h1>Recuperar acceso</h1>
                <p>
                  {setupStatus?.smtp_configured
                    ? "Ingresa tu correo para solicitar instrucciones."
                    : "Esta instalación no tiene servidor SMTP configurado; un administrador puede restablecer tu acceso de forma segura."}
                </p>
              </div>
              <label>
                Correo electrónico
                <input
                  type="email"
                  required
                  value={resetEmail}
                  onChange={(e) => setResetEmail(e.target.value)}
                />
              </label>
              {resetFeedback && (
                <div className="login-error" role="status">
                  {resetFeedback}
                </div>
              )}
              <Button
                type="submit"
                variant="primary"
                className="login-button"
                busy={resetBusy}
              >
                Solicitar recuperación
              </Button>
            </form>
          )}

          <div className="login-mode-actions">
            {mode !== "login" && (
              <Button
                type="button"
                variant="ghost"
                onClick={() => setMode("login")}
              >
                Ya tengo cuenta
              </Button>
            )}
            {mode !== "register" && (
              <Button
                type="button"
                variant="ghost"
                onClick={() => setMode("register")}
              >
                Crear cuenta
              </Button>
            )}
            {mode !== "reset" && (
              <Button
                type="button"
                variant="ghost"
                onClick={() => {
                  setResetFeedback(null);
                  setMode("reset");
                }}
              >
                ¿Olvidaste tu contraseña?
              </Button>
            )}
          </div>

          {setupStatus?.google_login_enabled && (
            <p className="login-oidc-note">
              Inicio de sesión con Google OIDC habilitado (cliente configurado).
            </p>
          )}
        </div>
      </div>
    </main>
  );
}
