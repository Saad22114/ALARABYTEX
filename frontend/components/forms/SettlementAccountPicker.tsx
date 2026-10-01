'use client';

import { PaymentSettlementSource } from '@/types';

export const SETTLEMENT_LABELS: Record<PaymentSettlementSource, string> = {
  machine: 'حساب الماكينة',
  bank: 'الحساب البنكي',
  none: 'لا يخصم من الماكينة ولا البنك',
};

export const SETTLEMENT_OPTIONS: {
  value: PaymentSettlementSource;
  label: string;
  hint: string;
}[] = [
  {
    value: 'machine',
    label: 'حساب الماكينة',
    hint: 'ما سدّدنا به مال شركة البطاقة — ينقص رصيد حساب الماكينة ويظهر في قسمه.',
  },
  {
    value: 'bank',
    label: 'الحساب البنكي',
    hint: 'خُصم من حسابنا في البنك — ينقص رصيد الحساب البنكي ويظهر في قسمه.',
  },
  {
    value: 'none',
    label: 'لا يخصم من الماكينة ولا البنك',
    hint: 'سداد من الخزنة أو من غيرهما — يُسدَّد للمورد ولا يمسّ حسابَي التسوية.',
  },
];

/**
 * اختيار إلزامي: من أي حساب خرجت الدفعة.
 *
 * لا يبدأ على أي خيار، لأن خياراً محدداً مسبقاً يُقرأ إجابةً موافَقاً عليها
 * وهي إجابةٌ لم ينظر فيها المستخدم. والخادم يرفض القيد بلا اختيار، لأن
 * الرصيد الذي يُخصم لا يُعرف أي حسابين قبل أن يُقال.
 */
export default function SettlementAccountPicker({
  value,
  onChange,
  error,
}: {
  value: PaymentSettlementSource | '';
  onChange: (value: PaymentSettlementSource) => void;
  error?: string;
}) {
  return (
    <div>
      <p className="text-xs font-medium text-neutral-500 mb-2">
        من أي حساب خُصم المبلغ؟ <span className="text-red-500">*</span>
      </p>
      <div className="space-y-2">
        {SETTLEMENT_OPTIONS.map((opt) => (
          <button
            key={opt.value}
            type="button"
            onClick={() => onChange(opt.value)}
            className={`w-full text-right rounded-xl border p-3 transition-colors ${
              value === opt.value
                ? 'border-brand-500 bg-brand-50 ring-1 ring-brand-500/30'
                : 'border-sand-300 bg-surface hover:bg-sand-50'
            }`}
          >
            <span className="block text-sm font-medium text-neutral-800">
              {opt.label}
            </span>
            <span className="block text-xs text-neutral-500 mt-0.5">
              {opt.hint}
            </span>
          </button>
        ))}
      </div>
      {error ? (
        <p className="mt-2 text-xs text-red-600">{error}</p>
      ) : !value ? (
        <p className="mt-2 text-xs text-amber-600">
          لا يُحفظ الدفعة قبل اختيار الحساب — فبلاختياره لا يُعرف أي حساب
          تسوية يُخصم.
        </p>
      ) : null}
    </div>
  );
}
