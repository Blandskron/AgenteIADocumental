import {
  hasTenantPermission,
  isTenantAdmin,
} from "@/entities/auth/model/auth.user";
import { LoginPage } from "@/pages/LoginPage/LoginPage.tsx";
import { ErrorBoundary } from "@/shared/components/ErrorBoundary.tsx";
import { PageState } from "@/shared/components/PageState.tsx";
import { CommandPalette } from "@/widgets/CommandPalette/CommandPalette.tsx";
import { lazy, Suspense, useEffect } from "react";
import { useAuthContext } from "./providers/AuthProvider";
import { appRoutes } from "./router/routes";
import { useAppRouter } from "./router/useAppRouter.ts";
const ApplicationsPage = lazy(() =>
  import("@/pages/ApplicationsPage/ApplicationsPage.tsx").then((module) => ({
    default: module.ApplicationsPage,
  })),
);
const AdminPage = lazy(() =>
  import("@/pages/AdminPage/AdminPage.tsx").then((module) => ({
    default: module.AdminPage,
  })),
);
const ChatPage = lazy(() =>
  import("@/pages/ChatPage/ChatPage.tsx").then((module) => ({
    default: module.ChatPage,
  })),
);
const DocumentSearchPage = lazy(() =>
  import("@/pages/DocumentSearchPage/DocumentSearchPage.tsx").then(
    (module) => ({ default: module.DocumentSearchPage }),
  ),
);
const ProfilePage = lazy(() =>
  import("@/pages/ProfilePage/ProfilePage.tsx").then((module) => ({
    default: module.ProfilePage,
  })),
);
const SettingsAIPage = lazy(() =>
  import("@/pages/SettingsAIPage/SettingsAIPage.tsx").then((module) => ({
    default: module.SettingsAIPage,
  })),
);
const StudioPage = lazy(() =>
  import("@/pages/StudioPage/StudioPage.tsx").then((module) => ({
    default: module.StudioPage,
  })),
);
const AuditLogsPage = lazy(() =>
  import("@/pages/AuditLogsPage/AuditLogsPage.tsx").then((module) => ({
    default: module.AuditLogsPage,
  })),
);

export function App() {
  return (
    <Suspense fallback={<PageState title="Cargando página…" loading />}>
      <AppContent />
    </Suspense>
  );
}

function AppContent() {
  const { currentUser, isAuthenticated } = useAuthContext();
  const { route, navigate } = useAppRouter();
  const canUseChat =
    currentUser?.isSuperuser || hasTenantPermission(currentUser, "use_chat");
  const canUseIntegrations =
    currentUser?.isSuperuser ||
    hasTenantPermission(currentUser, "use_google_drive") ||
    hasTenantPermission(currentUser, "use_sharepoint");
  const canAdmin = isTenantAdmin(currentUser);
  const canManageAiSettings =
    currentUser?.isSuperuser ||
    hasTenantPermission(currentUser, "manage_ai_settings");
  const denied =
    (route === appRoutes.chat && !canUseChat) ||
    ((route === appRoutes.applications ||
      route === appRoutes.googleDriveApplication) &&
      !canUseIntegrations) ||
    (route === appRoutes.admin && !canAdmin) ||
    (route === appRoutes.auditLogs && !canAdmin) ||
    (route === appRoutes.settingsAi && !canManageAiSettings);

  useEffect(() => {
    if (isAuthenticated && denied) {
      navigate(appRoutes.documents, true);
    }
  }, [isAuthenticated, denied, navigate]);

  useEffect(() => {
    if (isAuthenticated && route === appRoutes.login) {
      navigate(appRoutes.chat, true);
    } else if (!isAuthenticated && route !== appRoutes.login) {
      navigate(appRoutes.login, true);
    }
  }, [isAuthenticated, route, navigate]);

  if (!isAuthenticated) return <LoginPage />;

  if (denied) return null;

  let pageNode = <ChatPage onNavigate={navigate} />;

  if (
    route === appRoutes.documents ||
    route === appRoutes.documentAssignments ||
    route === appRoutes.documentManaged ||
    route === appRoutes.documentNotifications ||
    route === appRoutes.documentFolders ||
    route === appRoutes.documentFavorites
  ) {
    pageNode = <DocumentSearchPage activeView={route} onNavigate={navigate} />;
  } else if (
    route === appRoutes.applications ||
    route === appRoutes.googleDriveApplication
  ) {
    pageNode = <ApplicationsPage activeView={route} onNavigate={navigate} />;
  } else if (route === appRoutes.profile) {
    pageNode = <ProfilePage onNavigate={navigate} />;
  } else if (route === appRoutes.admin) {
    pageNode = <AdminPage onNavigate={navigate} />;
  } else if (route === appRoutes.settingsAi) {
    pageNode = <SettingsAIPage onNavigate={navigate} />;
  } else if (route === appRoutes.studio) {
    pageNode = <StudioPage onNavigate={navigate} />;
  } else if (route === appRoutes.auditLogs) {
    pageNode = <AuditLogsPage onNavigate={navigate} />;
  }

  return (
    <ErrorBoundary resetKey={route}>
      {pageNode}
      <CommandPalette
        onNavigate={navigate}
        canUseChat={Boolean(canUseChat)}
        canUseIntegrations={Boolean(canUseIntegrations)}
        canAdmin={Boolean(canAdmin)}
        canManageAiSettings={Boolean(canManageAiSettings)}
      />
    </ErrorBoundary>
  );
}
