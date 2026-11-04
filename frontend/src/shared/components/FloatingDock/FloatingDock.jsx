import { Bot, FileArchive, Folder, Plus, Star } from "lucide-react";

import { appRoutes } from "../../../app/router/routes";

export function FloatingDock({ active = "chat", onNavigate, onCreateConversation }) {
  const items = [
    {
      id: "library",
      label: "Biblioteca",
      icon: Folder,
      onClick: () => onNavigate?.(appRoutes.documents),
    },
    {
      id: "favorites",
      label: "Favoritos",
      icon: Star,
      onClick: () => onNavigate?.(appRoutes.documents),
    },
    {
      id: "new",
      label: "Nuevo",
      icon: Plus,
      onClick: onCreateConversation,
    },
    {
      id: "chat",
      label: "IA",
      icon: Bot,
      onClick: () => onNavigate?.(appRoutes.chat),
    },
  ];

  return (
    <nav className="floating-dock" aria-label="Navegacion principal">
      {items.map((item) => {
        const Icon = item.icon || FileArchive;
        return (
          <button
            className={`dock-item ${active === item.id ? "active" : ""}`}
            key={item.id}
            onClick={item.onClick}
            title={item.label}
            type="button"
          >
            <Icon size={22} />
          </button>
        );
      })}
    </nav>
  );
}
