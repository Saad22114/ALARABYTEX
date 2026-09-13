'use client';

import React from 'react';

interface DateRangePickerProps {
  from: string;
  to: string;
  onChangeFrom: (v: string) => void;
  onChangeTo: (v: string) => void;
}

export default function DateRangePicker({ from, to, onChangeFrom, onChangeTo }: DateRangePickerProps) {
  return (
    <div className="flex flex-wrap items-center gap-3">
      <div className="space-y-1">
        <label className="block text-xs text-neutral-500">من</label>
        <input
          type="date"
          value={from}
          onChange={(e) => onChangeFrom(e.target.value)}
          className="rounded-xl border border-sand-300 px-3 py-2 text-sm focus:border-brand-500 focus:ring-2 focus:ring-brand-100 outline-none"
        />
      </div>
      <div className="space-y-1">
        <label className="block text-xs text-neutral-500">إلى</label>
        <input
          type="date"
          value={to}
          onChange={(e) => onChangeTo(e.target.value)}
          className="rounded-xl border border-sand-300 px-3 py-2 text-sm focus:border-brand-500 focus:ring-2 focus:ring-brand-100 outline-none"
        />
      </div>
    </div>
  );
}
