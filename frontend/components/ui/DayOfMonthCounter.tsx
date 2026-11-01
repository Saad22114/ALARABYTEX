'use client';

import { CalendarDays, ChevronLeft, ChevronRight } from 'lucide-react';

interface DayOfMonthCounterProps {
  from: string;
  to: string;
  onChange: (from: string, to: string) => void;
}

function countDays(month: string): number {
  const [year, monthNumber] = month.split('-').map(Number);
  return new Date(year, monthNumber, 0).getDate();
}

function localDateString(date: Date): string {
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`;
}

export default function DayOfMonthCounter({ from, to, onChange }: DayOfMonthCounterProps) {
  const anchor = /^\d{4}-\d{2}-\d{2}$/.test(to)
    ? to
    : /^\d{4}-\d{2}-\d{2}$/.test(from)
      ? from
      : localDateString(new Date());
  const month = anchor.slice(0, 7);
  const day = Number(anchor.slice(8, 10));
  const maximum = countDays(month);

  function chooseDay(targetMonth: string, targetDay: number) {
    const [year, monthNumber] = targetMonth.split('-');
    const bounded = Math.max(1, Math.min(targetDay, countDays(targetMonth)));
    const date = `${year}-${monthNumber}-${String(bounded).padStart(2, '0')}`;
    onChange(date, date);
  }

  return (
    <div className="inline-flex items-center gap-1.5 rounded-xl border border-sand-200 bg-sand-50/70 px-2 py-1.5">
      <span className="inline-flex items-center gap-1 text-xs font-medium text-neutral-600"><CalendarDays size={14} />يوم</span>
      <input
        aria-label="شهر اليوم المحدد"
        type="month"
        value={month}
        onChange={(event) => event.target.value && chooseDay(event.target.value, day)}
        className="max-w-32 rounded-lg border border-sand-300 bg-surface px-1.5 py-1 text-xs text-neutral-700"
      />
      <button
        type="button"
        aria-label="اليوم السابق من الشهر"
        disabled={day <= 1}
        onClick={() => chooseDay(month, day - 1)}
        className="rounded-md border border-sand-300 bg-surface p-1 text-neutral-600 transition hover:bg-sand-100 disabled:cursor-not-allowed disabled:opacity-40"
      ><ChevronRight size={14} /></button>
      <span className="min-w-12 text-center text-xs font-bold tabular-nums text-neutral-700">{day} / {maximum}</span>
      <button
        type="button"
        aria-label="اليوم التالي من الشهر"
        disabled={day >= maximum}
        onClick={() => chooseDay(month, day + 1)}
        className="rounded-md border border-sand-300 bg-surface p-1 text-neutral-600 transition hover:bg-sand-100 disabled:cursor-not-allowed disabled:opacity-40"
      ><ChevronLeft size={14} /></button>
    </div>
  );
}
