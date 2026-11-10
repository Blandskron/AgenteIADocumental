import { useAuthContext } from "@/app/providers/AuthProvider.tsx";
import { LoginForm } from "@/features/auth/ui/LoginForm.tsx";

export function LoginPage() {
  const { login, loginError, isAuthenticating } = useAuthContext();

  return (
    <main className="login-shell" id="main-content">
      <LoginForm
        error={loginError}
        isSubmitting={isAuthenticating}
        onSubmit={login}
      />
    </main>
  );
}
