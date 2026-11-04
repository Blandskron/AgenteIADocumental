import { useAuthContext } from "../../app/providers/AuthProvider";
import { LoginForm } from "../../features/auth/ui/LoginForm";

export function LoginPage() {
  const { login, loginError, isAuthenticating } = useAuthContext();

  return (
    <div className="login-shell">
      <LoginForm error={loginError} isSubmitting={isAuthenticating} onSubmit={login} />
    </div>
  );
}
