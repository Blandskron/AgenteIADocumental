import { useCallback, useEffect, useState } from "react";
import { appRoutes } from "./routes.ts";

const routes = new Set<string>(Object.values(appRoutes));

export type AppRoute = (typeof appRoutes)[keyof typeof appRoutes];
export type Navigate = (route: string, replace?: boolean) => void;

export interface PageProps {
  onNavigate: Navigate;
}

export const routeTitles: Record<AppRoute, string> = {
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
  [appRoutes.settingsAi]: "Configuración de IA",
  [appRoutes.studio]: "Knowledge Studio",
  [appRoutes.auditLogs]: "Auditoría de seguridad",
};

export function splitRouteAndSearch(rawPath: string): {
  route: AppRoute;
  search: string;
} {
  const input = (rawPath || "").trim();
  const qIndex = input.indexOf("?");
  const pathname = qIndex >= 0 ? input.slice(0, qIndex) : input;
  const rawSearch = qIndex >= 0 ? input.slice(qIndex) : "";
  if (routes.has(pathname)) {
    return {
      route: pathname as AppRoute,
      search: rawSearch.length > 1 ? rawSearch : "",
    };
  }
  return { route: appRoutes.chat, search: "" };
}

export function normalizeRoute(path: string): AppRoute {
  return splitRouteAndSearch(path).route;
}

export function getRouteDocumentTitle(route: AppRoute): string {
  return `${routeTitles[route]} · KronDocs`;
}

export function useAppRouter() {
  const [route, setRoute] = useState<AppRoute>(() =>
    normalizeRoute(window.location.pathname),
  );
  const [search, setSearch] = useState<string>(
    () => window.location.search || "",
  );

  useEffect(() => {
    document.title = getRouteDocumentTitle(route);
  }, [route]);

  const navigate = useCallback((rawPath: string, replace = false) => {
    const { route: nextRoute, search: nextSearch } =
      splitRouteAndSearch(rawPath);
    const targetUrl = `${nextRoute}${nextSearch}`;
    const currentUrl = `${window.location.pathname}${window.location.search}`;
    if (targetUrl !== currentUrl) {
      window.history[replace ? "replaceState" : "pushState"](
        null,
        "",
        targetUrl,
      );
    }
    setRoute(nextRoute);
    setSearch(nextSearch);
  }, []);

  useEffect(() => {
    const sync = () =>
      navigate(`${window.location.pathname}${window.location.search}`, true);
    sync();
    window.addEventListener("popstate", sync);
    return () => window.removeEventListener("popstate", sync);
  }, [navigate]);

  return { route, search, navigate };
}
