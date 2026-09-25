'use client';

/** الكميات السريعة (بالياردة) لبيع الأقمشة — الضغط يستبدل قيمة حقل الكمية. */
export const YARD_QUICK_PICKS = ['3.5', '4', '7', '10.5', '14'];

interface Props {
  value: string;
  onPick: (value: string) => void;
  options?: string[];
}

export default function QuantityQuickPicks({ value, onPick, options = YARD_QUICK_PICKS }: Props) {
  const current = parseFloat(value);
  return (
    <div className="flex flex-wrap gap-1.5 mt-1.5" role="group" aria-label="كميات سريعة">
      {options.map((opt) => {
        const active = !isNaN(current) && current === parseFloat(opt);
        return (
          <button
            key={opt}
            type="button"
            onClick={() => onPick(opt)}
            aria-pressed={active}
            className={`px-3 py-1 rounded-lg border text-xs font-semibold tabular-nums transition-colors ${
              active
                ? 'bg-brand-600 border-brand-600 text-white'
                : 'bg-surface border-sand-300 text-neutral-600 hover:bg-sand-100'
            }`}
          >
            {opt}
          </button>
        );
      })}
    </div>
  );
}
