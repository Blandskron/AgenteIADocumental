import { useAuthContext } from "./providers/AuthProvider";
import { appRoutes } from "./router/routes";
import { ApplicationsPage } from "../pages/ApplicationsPage/ApplicationsPage";
import { AdminPage } from "../pages/AdminPage/AdminPage";
import { ChatPage } from "../pages/ChatPage/ChatPage";
import { DocumentSearchPage } from "../pages/DocumentSearchPage/DocumentSearchPage";
import { LoginPage } from "../pages/LoginPage/LoginPage";
import { ProfilePage } from "../pages/ProfilePage/ProfilePage";
import { hasTenantPermission, isTenantAdmin } from "../entities/auth/model/auth.user";
import { useEffect, useState } from "react";

const knownRoutes = new Set(Object.values(appRoutes));

function normalizeRoute(pathname) {
  return knownRoutes.has(pathname) ? pathname : appRoutes.chat;
}

export function App() {
  const { currentUser, isAuthenticated } = useAuthContext();
  const [route, setRoute] = useState(() => normalizeRoute(window.location.pathname || appRoutes.chat));

  useEffect(() => {
    function handlePopState() {
      setRoute(normalizeRoute(window.location.pathname || appRoutes.chat));
    }

    window.addEventListener("popstate", handlePopState);
    return () => window.removeEventListener("popstate", handlePopState);
  }, []);

  useEffect(() => {
    const normalizedRoute = normalizeRoute(window.location.pathname || appRoutes.chat);
    if (normalizedRoute !== window.location.pathname) {
      window.history.replaceState(null, "", normalizedRoute);
      setRoute(normalizedRoute);
    }
  }, []);

  useEffect(() => {
    if (isAuthenticated && route === appRoutes.login) {
      window.history.replaceState(null, "", appRoutes.chat);
      setRoute(appRoutes.chat);
    } else if (!isAuthenticated && route !== appRoutes.login) {
      window.history.replaceState(null, "", appRoutes.login);
      setRoute(appRoutes.login);
    }
  }, [isAuthenticated, route]);

  function navigate(nextRoute) {
    const normalizedRoute = normalizeRoute(nextRoute);
    window.history.pushState(null, "", normalizedRoute);
    setRoute(normalizedRoute);
  }

  if (!isAuthenticated) return <LoginPage />;

  const canUseChat = currentUser?.isSuperuser || hasTenantPermission(currentUser, "use_chat");
  const canUseIntegrations =
    currentUser?.isSuperuser ||
    hasTenantPermission(currentUser, "use_google_drive") ||
    hasTenantPermission(currentUser, "use_sharepoint");
  const canAdmin = isTenantAdmin(currentUser);

  if (route === appRoutes.chat && !canUseChat) {
    window.history.replaceState(null, "", appRoutes.documents);
    setRoute(appRoutes.documents);
    return null;
  }

  if ((route === appRoutes.applications || route === appRoutes.googleDriveApplication) && !canUseIntegrations) {
    window.history.replaceState(null, "", appRoutes.documents);
    setRoute(appRoutes.documents);
    return null;
  }

  if (route === appRoutes.admin && !canAdmin) {
    window.history.replaceState(null, "", appRoutes.documents);
    setRoute(appRoutes.documents);
    return null;
  }

  if (
    route === appRoutes.documents ||
    route === appRoutes.documentAssignments ||
    route === appRoutes.documentManaged ||
    route === appRoutes.documentNotifications ||
    route === appRoutes.documentFolders ||
    route === appRoutes.documentFavorites
  ) {
    return <DocumentSearchPage activeView={route} onNavigate={navigate} />;
  }

  if (route === appRoutes.applications || route === appRoutes.googleDriveApplication) {
    return <ApplicationsPage activeView={route} onNavigate={navigate} />;
  }

  if (route === appRoutes.profile) {
    return <ProfilePage onNavigate={navigate} />;
  }

  if (route === appRoutes.admin) {
    return <AdminPage onNavigate={navigate} />;
  }

  return <ChatPage onNavigate={navigate} />;
}
