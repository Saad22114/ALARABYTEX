'use client';

import React, { useState } from 'react';
import DateRangePicker from './DateRangePicker';

/**
 * ``all`` ليست فترةً بل غيابُها: نطاقٌ بلا حدَّين. تحتفظ بها في النوع
 * نفسه لأنها تُكتشف من `getActivePreset` كما تُكتشف الفترات، ولأن زرّها
 * يُرسم على قدمِ ما سواها لا في موضعٍ خاص.
 */
export type DateRangeKey = 'today' | 'week' | 'month' | 'last_month' | 'all';

const RANGE_LABELS: { key: Exclude<DateRangeKey, 'all'>; label: string }[] = [
  { key: 'today', label: 'اليوم' },
  { key: 'week', label: 'الأسبوع' },
  { key: 'month', label: 'الشهر' },
  { key: 'last_month', label: 'الشهر الماضي' },
];

export function toISODate(d: Date): string {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
}

export function getRangeForKey(key: DateRangeKey): { from: string; to: string } {
  // نطاق «الكل» فراغٌ متعمَّد: لا حدَ أدنى ولا حدَ أقصى، فيشمل ما
  // وُثّّق قبل أن يبدأ أحدٌ بإثبات تاريخ السجلّ أصلاً.
  if (key === 'all') return { from: '', to: '' };

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
  // حدٌّ واحد دون الآخر ليس «الكل» بل اختيارٌ ناقص، فيُترك للشاشة
  // تُظهر منتقيَها بدل أن يدّعي المشهدُ ما ليس فيه.
  if (from === '' && to === '') return 'all';
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
  /**
   * يُرسم زرّ «الكل» حين تُمرّره الشاشة. وهو مخرجٌ من كل فترةٍ اختيرت،
   * والشاشاتُ التي تحفظ نطاقها بنفسها تمرّر `allActive` و`onSelectAll`
   * لأن تفريغَ الحدَّين لا يكفي: حدٌّ بلا حدٍّ لا يعود كما كان عند
   * تحديث الصفحة.
   */
  allowAll?: boolean;
  allActive?: boolean;
  onSelectAll?: () => void;
  className?: string;
}

export default function DateRangeToolbar({
  from, to, onChange, allowAll = false, allActive, onSelectAll, className = '',
}: DateRangeToolbarProps) {
  const [selected, setSelected] = useState<DateRangeKey | null>(null);
  const detected = getActivePreset(from, to);
  const active = selected ?? detected;
  const showingAll = allActive ?? detected === 'all';
  const [customOpen, setCustomOpen] = useState(false);
  const showPicker = customOpen || (active === null && !showingAll);

  // منتقي التواريخ لا يقبل فراغاً: فنمرّر له شهراً افتراضياً يُستبدل
  // فور نقره. بلا هذا لفتحُ «من-إلى» وهو على «الكل» يترك حقلَي التاريخ فارغين.
  const fallback = getRangeForKey('month');
  const pickerFrom = from || fallback.from;
  const pickerTo = to || fallback.to;

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
            active === r.key && !customOpen && !showingAll
              ? 'bg-brand-600 text-white shadow-sm'
              : 'bg-surface text-neutral-600 border border-sand-200 hover:bg-sand-50'
          }`}
        >
          {r.label}
        </button>
      ))}
      {allowAll && (
        <button
          onClick={() => {
            setSelected(null);
            setCustomOpen(false);
            if (onSelectAll) onSelectAll();
            else onChange('', '');
          }}
          className={`px-3 py-2 rounded-xl text-sm font-medium transition-all duration-150 ${
            showingAll
              ? 'bg-brand-600 text-white shadow-sm'
              : 'bg-surface text-neutral-600 border border-sand-200 hover:bg-sand-50'
          }`}
        >
          الكل
        </button>
      )}
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
          <DateRangePicker
            from={pickerFrom}
            to={pickerTo}
            onChangeFrom={(v) => onChange(v, pickerTo)}
            onChangeTo={(v) => onChange(pickerFrom, v)}
          />
        </div>
      )}
    </div>
  );
}
