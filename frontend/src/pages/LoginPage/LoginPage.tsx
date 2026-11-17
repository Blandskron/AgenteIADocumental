import { useAuthContext } from "@/app/providers/AuthProvider.tsx";
import { LoginForm } from "@/features/auth/ui/LoginForm.tsx";
import { Brand } from "@/shared/components/Brand/Brand.tsx";
import { FileText, Layers3, Search } from "lucide-react";

export function LoginPage() {
  const { login, loginError, isAuthenticating } = useAuthContext();

  return (
    <main className="login-shell" id="main-content">
      <div className="login-window">
        <div className="login-identity">
          <Brand className="login-brand" />
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
            <p>Espacio documental</p>
            <p>Organiza tus archivos y consulta su contenido con fuentes.</p>
          </div>
        </div>
        <LoginForm
          error={loginError}
          isSubmitting={isAuthenticating}
          onSubmit={login}
        />
      </div>
    </main>
  );
}
