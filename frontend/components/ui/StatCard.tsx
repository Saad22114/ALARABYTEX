import React from 'react';

interface StatCardProps {
  icon: React.ReactNode;
  iconBg?: string;
  label: string;
  value: string | number;
  sub?: string;
}

export default function StatCard({ icon, iconBg = 'bg-brand-50 text-brand-600', label, value, sub }: StatCardProps) {
  return (
    <div className="rounded-2xl bg-surface border border-sand-200 shadow-sm p-4 sm:p-5 card-hover">
      <div className="flex items-start gap-3 sm:gap-4">
        <div className={`p-2.5 sm:p-3 rounded-xl ${iconBg}`}>{icon}</div>
        <div className="flex-1 min-w-0">
          <p className="text-xs sm:text-sm text-neutral-500 mb-1">{label}</p>
          <p className="text-xl sm:text-2xl font-bold text-neutral-800 tabular-nums">{value}</p>
          {sub && <p className="text-xs text-neutral-400 mt-1">{sub}</p>}
        </div>
      </div>
    </div>
  );
}
