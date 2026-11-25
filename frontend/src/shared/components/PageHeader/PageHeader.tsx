import type { ReactNode } from "react";

export interface PageHeaderProps {
  eyebrow?: string;
  title: string;
  description?: string;
  icon?: ReactNode;
  badges?: ReactNode;
  actions?: ReactNode;
  className?: string;
}

export function PageHeader({
  eyebrow,
  title,
  description,
  icon,
  badges,
  actions,
  className = "",
}: PageHeaderProps) {
  return (
    <header className={`kd-page-header ${className}`.trim()}>
      <div className="kd-page-header-main">
        {icon ? (
          <div className="kd-page-header-icon" aria-hidden="true">
            {icon}
          </div>
        ) : null}
        <div className="kd-page-header-copy">
          {eyebrow ? (
            <p className="kd-eyebrow">
              <span className="kd-eyebrow-dot" aria-hidden="true" />
              <span>{eyebrow}</span>
            </p>
          ) : null}
          <div className="kd-page-header-title-row">
            <h1>{title}</h1>
            {badges ? (
              <div className="kd-page-header-badges">{badges}</div>
            ) : null}
          </div>
          {description ? (
            <p className="kd-page-header-desc">{description}</p>
          ) : null}
        </div>
      </div>
      {actions ? <div className="kd-page-header-actions">{actions}</div> : null}
    </header>
  );
}
