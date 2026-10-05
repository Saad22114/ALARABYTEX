import React from 'react';

interface StatCardProps {
  icon: React.ReactNode;
  iconBg?: string;
  label: string;
  value: string | number;
  sub?: React.ReactNode;
}

export default function StatCard({ icon, iconBg = 'bg-brand-50 text-brand-600', label, value, sub }: StatCardProps) {
  return (
    <div className="min-w-0 rounded-2xl bg-surface border border-sand-200 shadow-sm p-4 sm:p-5 card-hover">
      <div className="flex min-w-0 items-center gap-2.5 mb-3">
        <div className={`shrink-0 p-2 rounded-xl ${iconBg}`}>{icon}</div>
        <p className="min-w-0 text-xs sm:text-sm leading-snug text-neutral-500 line-clamp-2">{label}</p>
      </div>
      <p className="text-xl sm:text-2xl font-bold leading-tight text-neutral-800 tabular-nums break-words">{value}</p>
      {sub && <p className="text-xs text-neutral-400 mt-1.5 leading-snug line-clamp-2">{sub}</p>}
    </div>
  );
}
