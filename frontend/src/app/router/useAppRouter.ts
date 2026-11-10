import { useCallback, useEffect, useState } from "react";
import { appRoutes } from "./routes.ts";
const routes = new Set<string>(Object.values(appRoutes));
const titles: Record<string, string> = {
  [appRoutes.login]: "Iniciar sesión",
  [appRoutes.chat]: "Chat documental",
  [appRoutes.admin]: "Administración",
  [appRoutes.applications]: "Aplicaciones",
  [appRoutes.googleDriveApplication]: "Google Drive",
  [appRoutes.documents]: "Documentos",
  [appRoutes.documentAssignments]: "Asignaciones",
  [appRoutes.documentManaged]: "Documentos gestionados",
  [appRoutes.documentNotifications]: "Notificaciones",
  [appRoutes.documentFolders]: "Carpetas",
  [appRoutes.documentFavorites]: "Favoritos",
  [appRoutes.profile]: "Mi perfil",
};
export type AppRoute = (typeof appRoutes)[keyof typeof appRoutes];
export type Navigate = (route: string) => void;
export interface PageProps {
  onNavigate: Navigate;
}
export function normalizeRoute(path: string): AppRoute {
  return routes.has(path) ? (path as AppRoute) : appRoutes.chat;
}
export function useAppRouter() {
  const [route, setRoute] = useState(() =>
    normalizeRoute(window.location.pathname),
  );
  useEffect(() => {
    document.title = `${titles[route]} · Blandskron Documental`;
  }, [route]);
  const navigate = useCallback((path: string, replace = false) => {
    const next = normalizeRoute(path);
    if (next !== window.location.pathname)
      window.history[replace ? "replaceState" : "pushState"](null, "", next);
    setRoute(next);
  }, []);
  useEffect(() => {
    const sync = () => navigate(window.location.pathname, true);
    sync();
    window.addEventListener("popstate", sync);
    return () => window.removeEventListener("popstate", sync);
  }, [navigate]);
  return { route, navigate };
}
