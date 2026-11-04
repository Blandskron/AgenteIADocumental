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

import { appRoutes } from "../../app/router/routes";
import { hasTenantPermission, isTenantAdmin } from "../../entities/auth/model/auth.user";
import { Brand } from "../../shared/components/Brand/Brand";
import { IconButton } from "../../shared/components/IconButton/IconButton";
import { useAuthContext } from "../../app/providers/AuthProvider";
import { useTheme } from "../../app/providers/ThemeProvider";

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
}) {
  const [profileMenuOpen, setProfileMenuOpen] = useState(false);
  const profileMenuRef = useRef(null);
  const { theme, toggleTheme } = useTheme();
  const initials = (user?.displayName || user?.username || "U")
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0])
    .join("")
    .toUpperCase();

  const { profile } = useAuthContext();
  const roles = (user?.roles || profile?.roles || []).map((item) => String(item).toLowerCase());
  const groups = (user?.groups || profile?.groups || []).map((item) => String(item).toLowerCase());
  const isSuperuser = Boolean(user?.isSuperuser || user?.is_superuser || profile?.is_superuser);
  const isAdmin = Boolean(
    isSuperuser ||
      user?.isStaff ||
      user?.is_staff ||
      profile?.is_staff ||
      isTenantAdmin(user) ||
      roles.includes("admin") ||
      groups.includes("admin"),
  );
  const canUseChat = isSuperuser || hasTenantPermission(user, "use_chat");
  const canUseIntegrations = isSuperuser || hasTenantPermission(user, "use_google_drive") || hasTenantPermission(user, "use_sharepoint");
  const navItems = [
    ...(canUseChat ? [{ route: appRoutes.chat, label: "Nuevo chat", icon: Plus, isNewChat: true }] : []),
    { route: appRoutes.documents, label: "Documentos", icon: FileSearch },
    ...(canUseIntegrations ? [{ route: appRoutes.applications, label: "Aplicaciones", icon: AppWindow }] : []),
    ...(isAdmin ? [{ route: appRoutes.admin, label: "Administracion", icon: Building2 }] : []),
  ];

  useEffect(() => {
    function handleOutsideClick(event) {
      if (!profileMenuRef.current?.contains(event.target)) {
        setProfileMenuOpen(false);
      }
    }

    if (profileMenuOpen) {
      document.addEventListener("mousedown", handleOutsideClick);
    }

    return () => document.removeEventListener("mousedown", handleOutsideClick);
  }, [profileMenuOpen]);

  const renderAvatar = () => {
    if (profile?.profile_picture_url) {
      return (
        <div className="account-avatar" style={{ padding: 0, overflow: "hidden" }}>
          <img
            src={profile.profile_picture_url}
            alt="Avatar"
            style={{ width: "100%", height: "100%", objectFit: "cover" }}
            onError={(event) => {
              event.currentTarget.style.display = "none";
            }}
          />
        </div>
      );
    }
    return <div className="account-avatar">{initials}</div>;
  };

  return (
    <aside className={`sidebar blandskron-sidebar ${collapsed ? "collapsed" : ""}`}>
      <div className="sidebar-top">
        <Brand />
        <IconButton onClick={collapsed ? onOpen : onClose} aria-label={collapsed ? "Abrir menu" : "Cerrar menu"}>
          {collapsed ? <PanelLeftOpen size={19} /> : <PanelLeftClose size={19} />}
        </IconButton>
      </div>

      <nav className="sidebar-nav" aria-label="Navegacion principal">
        {navItems.map((item) => (
          <button
            className={`sidebar-nav-item ${activeRoute === item.route && !item.isNewChat ? "active" : ""}`}
            key={`${item.route}-${item.label}`}
            onClick={() => {
              if (item.isNewChat) onCreateConversation?.();
              onNavigate?.(item.route);
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
      <nav className="history-list chat-history-list" aria-label="Historial de conversaciones">
        {conversations.map((conversation) => (
          <button
            className={`history-item ${conversation.id === activeConversation?.id ? "active" : ""}`}
            key={conversation.id}
            onClick={() => {
              onSelectConversation?.(conversation.id);
              onNavigate?.(appRoutes.chat);
            }}
            title={conversation.title}
            type="button"
          >
            <MessageSquare size={16} />
            <span>{conversation.title}</span>
            <span
              className="delete-chat"
              role="button"
              tabIndex={0}
              onClick={(event) => {
                event.stopPropagation();
                onDeleteConversation?.(conversation.id);
              }}
              onKeyDown={(event) => {
                if (event.key === "Enter" || event.key === " ") {
                  event.preventDefault();
                  event.stopPropagation();
                  onDeleteConversation?.(conversation.id);
                }
              }}
              aria-label="Eliminar chat"
            >
              <Trash2 size={14} />
            </span>
          </button>
        ))}
        {conversations.length === 0 && <p className="history-empty">Sin conversaciones todavia.</p>}
      </nav>

      <div className="sidebar-footer-container">
        <button
          className="sidebar-theme-toggle"
          onClick={toggleTheme}
          title={theme === "dark" ? "Cambiar a modo claro" : "Cambiar a modo oscuro"}
          type="button"
        >
          {theme === "dark" ? <Sun size={16} /> : <Moon size={16} />}
          <span>{theme === "dark" ? "Modo claro" : "Modo oscuro"}</span>
        </button>
        <div className="sidebar-profile-menu-wrap" ref={profileMenuRef}>
          {profileMenuOpen && (
            <div className="sidebar-profile-menu" role="menu">
              <button
                type="button"
                role="menuitem"
                onClick={() => {
                  sessionStorage.setItem("blandskron:profile-tab", "personal");
                  setProfileMenuOpen(false);
                  onNavigate?.(appRoutes.profile);
                }}
              >
                <UserRound size={16} />
                Editar perfil
              </button>
              {isAdmin && (
                <button
                  type="button"
                  role="menuitem"
                  onClick={() => {
                    sessionStorage.setItem("blandskron:profile-tab", "permissions");
                    setProfileMenuOpen(false);
                    onNavigate?.(appRoutes.profile);
                  }}
                >
                  {isSuperuser ? <ShieldCheck size={16} /> : <UsersRound size={16} />}
                  Crear grupos, usuarios y permisos
                </button>
              )}
              <button
                type="button"
                role="menuitem"
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
