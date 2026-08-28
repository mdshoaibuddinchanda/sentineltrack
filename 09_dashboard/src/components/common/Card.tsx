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
    <div className={`bg-police-850 border border-police-750/80 rounded-lg shadow-lg overflow-hidden flex flex-col ${className}`}>
      {(title || icon || actions) && (
        <div className={`px-4 py-3 border-b border-police-750/60 flex items-center justify-between gap-3 bg-police-800/40 ${headerClassName}`}>
          <div className="flex items-center gap-2.5 min-w-0">
            {icon && <span className="text-accent-blue shrink-0">{icon}</span>}
            <div className="min-w-0">
              {title && <h3 className="text-sm font-semibold text-slate-100 tracking-wide truncate">{title}</h3>}
              {subtitle && <p className="text-xs text-slate-400 truncate">{subtitle}</p>}
            </div>
          </div>
          {actions && <div className="flex items-center gap-2 shrink-0">{actions}</div>}
        </div>
      )}
      <div className={`p-4 flex-1 ${bodyClassName}`}>{children}</div>
    </div>
  );
}
