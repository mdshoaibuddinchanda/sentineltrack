import React from "react";

interface CardProps {
  title?: React.ReactNode;
  subtitle?: React.ReactNode;
  icon?: React.ReactNode;
  actions?: React.ReactNode;
  children: React.ReactNode;
  className?: string;
  bodyClassName?: string;
  headerClassName?: string;
}

export function Card({
  title,
  subtitle,
  icon,
  actions,
  children,
  className = "",
  bodyClassName = "",
  headerClassName = "",
}: CardProps) {
  return (
    <div className={`surface-card overflow-hidden flex flex-col ${className}`}>
      {(title || icon || actions) && (
        <div className={`surface-card__header px-4 py-3 flex items-center justify-between gap-3 ${headerClassName}`}>
          <div className="flex items-center gap-2.5 min-w-0">
            {icon && <span className="surface-card__icon shrink-0">{icon}</span>}
            <div className="min-w-0">
              {title && <h3 className="surface-card__title text-sm font-semibold tracking-wide truncate">{title}</h3>}
              {subtitle && <p className="surface-card__subtitle text-xs truncate">{subtitle}</p>}
            </div>
          </div>
          {actions && <div className="flex items-center gap-2 shrink-0">{actions}</div>}
        </div>
      )}
      <div className={`p-4 flex-1 ${bodyClassName}`}>{children}</div>
    </div>
  );
}
