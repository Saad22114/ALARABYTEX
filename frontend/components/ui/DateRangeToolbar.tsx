'use client';

import React, { useState } from 'react';
import DateRangePicker from './DateRangePicker';

export type DateRangeKey = 'today' | 'week' | 'month' | 'last_month';

const RANGE_LABELS: { key: DateRangeKey; label: string }[] = [
  { key: 'today', label: 'اليوم' },
  { key: 'week', label: 'الأسبوع' },
  { key: 'month', label: 'الشهر' },
  { key: 'last_month', label: 'الشهر الماضي' },
];

export function toISODate(d: Date): string {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
}

export function getRangeForKey(key: DateRangeKey): { from: string; to: string } {
  const now = new Date();
  const y = now.getFullYear();
  const m = now.getMonth();
  const today = toISODate(now);

  if (key === 'today') return { from: today, to: today };

  if (key === 'week') {
    const start = new Date(y, m, now.getDate() - 6);
    return { from: toISODate(start), to: today };
  }

  if (key === 'month') {
    return { from: toISODate(new Date(y, m, 1)), to: today };
  }

  // last month
  const start = new Date(y, m - 1, 1);
  const end = new Date(y, m, 0);
  return { from: toISODate(start), to: toISODate(end) };
}

export function currentMonthRange(): { from: string; to: string } {
  return getRangeForKey('month');
}

export function getActivePreset(from: string, to: string): DateRangeKey | null {
  const keys: DateRangeKey[] = ['today', 'week', 'month', 'last_month'];
  for (const k of keys) {
    const r = getRangeForKey(k);
    if (r.from === from && r.to === to) return k;
  }
  return null;
}

interface DateRangeToolbarProps {
  from: string;
  to: string;
  onChange: (from: string, to: string) => void;
  className?: string;
}

export default function DateRangeToolbar({ from, to, onChange, className = '' }: DateRangeToolbarProps) {
  const [selected, setSelected] = useState<DateRangeKey | null>(null);
  const active = selected ?? getActivePreset(from, to);
  const [customOpen, setCustomOpen] = useState(false);
  const showPicker = customOpen || active === null;

  return (
    <div className={`flex flex-wrap items-center gap-2 ${className}`}>
      {RANGE_LABELS.map((r) => (
        <button
          key={r.key}
          onClick={() => {
            setSelected(r.key);
            setCustomOpen(false);
            const range = getRangeForKey(r.key);
            onChange(range.from, range.to);
          }}
          className={`px-3 py-2 rounded-xl text-sm font-medium transition-all duration-150 ${
            active === r.key && !customOpen
              ? 'bg-brand-600 text-white shadow-sm'
              : 'bg-surface text-neutral-600 border border-sand-200 hover:bg-sand-50'
          }`}
        >
          {r.label}
        </button>
      ))}
      <button
        onClick={() => setCustomOpen(true)}
        className={`px-3 py-2 rounded-xl text-sm font-medium transition-all duration-150 ${
          showPicker
            ? 'bg-brand-600 text-white shadow-sm'
            : 'bg-surface text-neutral-600 border border-sand-200 hover:bg-sand-50'
        }`}
      >
        من-إلى
      </button>
      {showPicker && (
        <div className="lg:ms-2">
          <DateRangePicker from={from} to={to} onChangeFrom={(v) => onChange(v, to)} onChangeTo={(v) => onChange(from, v)} />
        </div>
      )}
    </div>
  );
}
