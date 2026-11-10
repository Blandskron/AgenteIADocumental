import { IconButton } from "@/shared/components/IconButton/IconButton.tsx";
import { ModalDialog } from "@/shared/components/ModalDialog.tsx";
import { useMediaQuery } from "@/shared/hooks/useMediaQuery.ts";
import { Menu } from "lucide-react";
import type { PropsWithChildren, ReactNode } from "react";
import { useEffect } from "react";

export function AppShell({
  sidebarOpen,
  sidebar,
  children,
  onSidebarChange,
}: PropsWithChildren<{
  sidebarOpen: boolean;
  sidebar: ReactNode;
  onSidebarChange: (open: boolean) => void;
}>) {
  const mobile = useMediaQuery("(max-width: 760px)");
  useEffect(() => {
    const main = document.getElementById("main-content");
    main?.focus({ preventScroll: true });
  }, []);
  return (
    <div className={`app-shell ${sidebarOpen ? "" : "sidebar-collapsed"}`}>
      <a className="skip-link" href="#main-content">
        Saltar al contenido
      </a>
      {mobile ? (
        <>
          <IconButton
            className="workspace-menu"
            aria-label="Abrir navegación"
            aria-expanded={sidebarOpen}
            aria-controls={sidebarOpen ? "mobile-navigation" : undefined}
            onClick={() => onSidebarChange(true)}
          >
            <Menu size={20} />
          </IconButton>
          {sidebarOpen && (
            <ModalDialog
              className="navigation-drawer"
              id="mobile-navigation"
              aria-label="Navegación principal"
              onClose={() => onSidebarChange(false)}
            >
              {sidebar}
            </ModalDialog>
          )}
        </>
      ) : (
        sidebar
      )}
      {children}
    </div>
  );
}
