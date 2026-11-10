import type { LucideIcon } from "lucide-react";
import type { ReactNode } from "react";
export function AdminPanel({
  children,
  featured = false,
  icon: Icon,
  title,
  subtitle,
}: {
  children: ReactNode;
  featured?: boolean;
  icon: LucideIcon;
  title: string;
  subtitle: string;
}) {
  return (
    <article className={`admin-panel ${featured ? "featured" : ""}`}>
      <header className="admin-panel-header">
        <span>
          <Icon size={18} />
        </span>
        <div>
          <h2>{title}</h2>
          <p>{subtitle}</p>
        </div>
      </header>
      {children}
    </article>
  );
}

export function CompactList({
  items,
  empty,
}: {
  items: { id: string; title: string; detail: string }[];
  empty: string;
}) {
  if (!items.length) return <p className="admin-empty">{empty}</p>;
  return (
    <div className="admin-compact-list">
      {items.slice(0, 8).map((item) => (
        <div key={item.id}>
          <strong>{item.title}</strong>
          <span>{item.detail}</span>
        </div>
      ))}
    </div>
  );
}
