import type { Navigate } from "@/app/router/useAppRouter.ts";
import type { AuthUser } from "@/entities/auth/model/types.ts";
import type { Conversation } from "@/entities/conversation/model/types.ts";
import {
  AppWindow,
  Building2,
  FileSearch,
  LogOut,
  MessageSquare,
  Moon,
  PanelLeftClose,
  PanelLeftOpen,
  Plus,
  ShieldCheck,
  Sun,
  Trash2,
  UserRound,
  UsersRound,
} from "lucide-react";
import { useEffect, useRef, useState } from "react";
interface SidebarProps {
  activeConversation?: Conversation;
  activeRoute?: string;
  collapsed?: boolean;
  conversations?: Conversation[];
  onClose: () => void;
  onOpen: () => void;
  onCreateConversation?: () => void;
  onDeleteConversation?: (id: string) => void;
  onLogout?: () => void;
  onNavigate?: Navigate;
  onSelectConversation?: (id: string) => void;
  user: AuthUser | null;
}

import { useAuthContext } from "@/app/providers/AuthProvider.tsx";
import { useTheme } from "@/app/providers/ThemeProvider.tsx";
import { appRoutes } from "@/app/router/routes.ts";
import {
  hasTenantPermission,
  isTenantAdmin,
} from "@/entities/auth/model/auth.user";
import { usePrivateAvatar } from "@/features/profile/hooks/usePrivateAvatar.ts";
import { Brand } from "@/shared/components/Brand/Brand.tsx";
import { IconButton } from "@/shared/components/IconButton/IconButton.tsx";

export function Sidebar({
  activeConversation,
  activeRoute = appRoutes.chat,
  collapsed = false,
  conversations = [],
  onClose,
  onCreateConversation,
  onDeleteConversation,
  onLogout,
  onNavigate,
  onOpen,
  onSelectConversation,
  user,
}: SidebarProps) {
  const [profileMenuOpen, setProfileMenuOpen] = useState(false);
  const profileMenuRef = useRef<HTMLDivElement>(null);
  const { theme, toggleTheme } = useTheme();
  function navigate(route: string) {
    onNavigate?.(route);
    if (window.matchMedia("(max-width: 760px)").matches) onClose();
  }
  const initials = (user?.displayName || user?.username || "U")
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0])
    .join("")
    .toUpperCase();

  const { profile, profileClient } = useAuthContext();
  const avatar = usePrivateAvatar(profileClient, profile?.profile_picture_url);
  const isSuperuser = Boolean(user?.isSuperuser || profile?.is_superuser);
  const isAdmin = isTenantAdmin(user);
  const canUseChat = isSuperuser || hasTenantPermission(user, "use_chat");
  const canUseIntegrations =
    isSuperuser ||
    hasTenantPermission(user, "use_google_drive") ||
    hasTenantPermission(user, "use_sharepoint");
  const navItems = [
    ...(canUseChat
      ? [
          {
            route: appRoutes.chat,
            label: "Nuevo chat",
            icon: Plus,
            isNewChat: true,
          },
        ]
      : []),
    { route: appRoutes.documents, label: "Documentos", icon: FileSearch },
    ...(canUseIntegrations
      ? [
          {
            route: appRoutes.applications,
            label: "Aplicaciones",
            icon: AppWindow,
          },
        ]
      : []),
    ...(isAdmin
      ? [{ route: appRoutes.admin, label: "Administracion", icon: Building2 }]
      : []),
  ];

  useEffect(() => {
    function handleOutsideClick(event: MouseEvent) {
      if (!profileMenuRef.current?.contains(event.target as Node)) {
        setProfileMenuOpen(false);
      }
    }

    if (profileMenuOpen) {
      document.addEventListener("mousedown", handleOutsideClick);
    }

    return () => document.removeEventListener("mousedown", handleOutsideClick);
  }, [profileMenuOpen]);

  const renderAvatar = () => {
    if (avatar.src) {
      return (
        <div
          className="account-avatar"
          style={{ padding: 0, overflow: "hidden" }}
        >
          <img
            src={avatar.src}
            alt="Avatar"
            style={{ width: "100%", height: "100%", objectFit: "cover" }}
            onError={avatar.onError}
          />
        </div>
      );
    }
    return <div className="account-avatar">{initials}</div>;
  };

  return (
    <aside
      aria-label="Barra lateral"
      className={`sidebar blandskron-sidebar ${collapsed ? "collapsed" : ""}`}
    >
      <div className="sidebar-top">
        <Brand />
        <IconButton
          onClick={collapsed ? onOpen : onClose}
          aria-label={collapsed ? "Abrir menu" : "Cerrar menu"}
        >
          {collapsed ? (
            <PanelLeftOpen size={19} />
          ) : (
            <PanelLeftClose size={19} />
          )}
        </IconButton>
      </div>

      <nav className="sidebar-nav" aria-label="Navegacion principal">
        {navItems.map((item) => (
          <button
            aria-current={activeRoute === item.route ? "page" : undefined}
            className={`sidebar-nav-item ${activeRoute === item.route && !item.isNewChat ? "active" : ""}`}
            key={`${item.route}-${item.label}`}
            onClick={() => {
              if (item.isNewChat) onCreateConversation?.();
              navigate(item.route);
            }}
            title={item.label}
            type="button"
          >
            <item.icon size={18} />
            <span>{item.label}</span>
          </button>
        ))}
      </nav>

      <div className="history-label">Recientes</div>
      <nav
        className="history-list chat-history-list"
        aria-label="Historial de conversaciones"
      >
        {conversations.map((conversation) => (
          <div
            className={`history-row ${conversation.id === activeConversation?.id ? "active" : ""}`}
            key={conversation.id}
          >
            <button
              className="history-item"
              aria-current={
                conversation.id === activeConversation?.id ? "true" : undefined
              }
              onClick={() => {
                onSelectConversation?.(conversation.id);
                navigate(appRoutes.chat);
              }}
              title={conversation.title}
              type="button"
            >
              <MessageSquare size={16} />
              <span>{conversation.title}</span>
            </button>
            <button
              className="delete-chat"
              type="button"
              onClick={() => onDeleteConversation?.(conversation.id)}
              aria-label={`Eliminar chat ${conversation.title}`}
            >
              <Trash2 size={14} />
            </button>
          </div>
        ))}
        {conversations.length === 0 && (
          <p className="history-empty">Sin conversaciones todavia.</p>
        )}
      </nav>

      <div className="sidebar-footer-container">
        <button
          className="sidebar-theme-toggle"
          onClick={toggleTheme}
          title={
            theme === "dark" ? "Cambiar a modo claro" : "Cambiar a modo oscuro"
          }
          type="button"
        >
          {theme === "dark" ? <Sun size={16} /> : <Moon size={16} />}
          <span>{theme === "dark" ? "Modo claro" : "Modo oscuro"}</span>
        </button>
        <div
          className="sidebar-profile-menu-wrap"
          ref={profileMenuRef}
          onKeyDown={(event) => {
            if (event.key === "Escape") {
              setProfileMenuOpen(false);
              profileMenuRef.current
                ?.querySelector<HTMLButtonElement>(".sidebar-account")
                ?.focus();
            }
          }}
        >
          {profileMenuOpen && (
            <div id="account-actions" className="sidebar-profile-menu">
              <button
                type="button"
                onClick={() => {
                  sessionStorage.setItem("blandskron:profile-tab", "personal");
                  setProfileMenuOpen(false);
                  navigate(appRoutes.profile);
                }}
              >
                <UserRound size={16} />
                Editar perfil
              </button>
              {isAdmin && (
                <button
                  type="button"
                  onClick={() => {
                    sessionStorage.setItem(
                      "blandskron:profile-tab",
                      "permissions",
                    );
                    setProfileMenuOpen(false);
                    onNavigate?.(appRoutes.profile);
                  }}
                >
                  {isSuperuser ? (
                    <ShieldCheck size={16} />
                  ) : (
                    <UsersRound size={16} />
                  )}
                  Crear grupos, usuarios y permisos
                </button>
              )}
              <button
                type="button"
                onClick={() => {
                  setProfileMenuOpen(false);
                  onLogout?.();
                }}
              >
                <LogOut size={16} />
                Cerrar sesion
              </button>
            </div>
          )}
          <button
            aria-expanded={profileMenuOpen}
            aria-controls="account-actions"
            className={`sidebar-account interactive ${activeRoute === appRoutes.profile ? "active" : ""}`}
            onClick={() => setProfileMenuOpen((current) => !current)}
            title={user?.displayName || user?.username}
            type="button"
          >
            {renderAvatar()}
            <div className="account-copy">
              <strong>{user?.displayName || user?.username}</strong>
              <span>{profile?.email || user?.email || "Sin correo"}</span>
            </div>
          </button>
        </div>
      </div>
    </aside>
  );
}
