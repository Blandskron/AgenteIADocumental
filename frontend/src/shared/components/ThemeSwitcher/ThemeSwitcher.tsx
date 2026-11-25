import { Monitor, Moon, Sun } from "lucide-react";

import type { ThemePreference } from "@/app/providers/ThemeProvider.tsx";

const THEME_OPTIONS: Array<{
  id: ThemePreference;
  label: string;
  icon: typeof Moon;
}> = [
  { id: "dark", label: "Oscuro", icon: Moon },
  { id: "light", label: "Claro", icon: Sun },
  { id: "system", label: "Sistema", icon: Monitor },
];

export function ThemeSwitcher({
  preference,
  resolvedTheme,
  collapsed = false,
  onChange,
  onToggle,
}: {
  preference: ThemePreference;
  resolvedTheme: "light" | "dark";
  collapsed?: boolean;
  onChange: (next: ThemePreference) => void;
  onToggle: () => void;
}) {
  if (collapsed) {
    return (
      <button
        className="sidebar-theme-toggle"
        onClick={onToggle}
        title={
          resolvedTheme === "dark"
            ? "Cambiar a modo claro"
            : "Cambiar a modo oscuro"
        }
        aria-label={
          resolvedTheme === "dark"
            ? "Cambiar a modo claro"
            : "Cambiar a modo oscuro"
        }
        type="button"
      >
        {resolvedTheme === "dark" ? (
          <Sun size={16} aria-hidden="true" />
        ) : (
          <Moon size={16} aria-hidden="true" />
        )}
        <span>{resolvedTheme === "dark" ? "Modo claro" : "Modo oscuro"}</span>
      </button>
    );
  }

  return (
    <div
      className="theme-switcher"
      role="group"
      aria-label="Preferencia de tema"
    >
      {THEME_OPTIONS.map((option) => {
        const Icon = option.icon;
        const active = preference === option.id;
        return (
          <button
            key={option.id}
            type="button"
            className={`theme-switcher-btn ${active ? "is-active" : ""}`.trim()}
            aria-pressed={active}
            onClick={() => onChange(option.id)}
            title={`Tema: ${option.label}`}
          >
            <Icon size={14} aria-hidden="true" />
            <span>{option.label}</span>
          </button>
        );
      })}
    </div>
  );
}
