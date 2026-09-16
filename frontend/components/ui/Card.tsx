import React from 'react';

interface CardProps {
  title?: string;
  subtitle?: string;
  action?: React.ReactNode;
  className?: string;
  children: React.ReactNode;
}

export default function Card({ title, subtitle, action, className = '', children }: CardProps) {
  return (
    <div className={`rounded-2xl bg-surface border border-sand-200 shadow-sm card-hover ${className}`}>
      {(title || action) && (
        <div className="flex items-center justify-between gap-3 px-3 sm:px-6 py-3 sm:py-4 border-b border-sand-100">
          <div className="min-w-0">
            {title && <h3 className="text-lg font-semibold text-neutral-800 truncate">{title}</h3>}
            {subtitle && <p className="text-sm text-neutral-500 mt-0.5">{subtitle}</p>}
          </div>
          {action && <div className="shrink-0">{action}</div>}
        </div>
      )}
      <div className="p-3 sm:p-6">{children}</div>
    </div>
  );
}
