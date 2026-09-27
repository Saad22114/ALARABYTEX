'use client';

import { useState } from 'react';
import Input from '@/components/ui/Input';
import { formatCurrency } from '@/lib/format';

interface Props {
  /** إجمالي الصنف قبل الخصم (كمية × سعر)، أو null إن لم تُكمَل البيانات */
  subtotal: number | null;
  /** قيمة الخصم الحالية كنص (كما في حقل الخصم) */
  discount: string;
  /** يُستدعى لتحديث حقل الخصم عند كتابة المبلغ النهائي */
  onDiscountChange: (discount: string) => void;
  /** الكمية — لازمة لرفع سعر الوحدة تلقائياً عند كتابة مبلغ أكبر من الإجمالي */
  quantity?: number | null;
  /** يُستدعى لرفع سعر الوحدة عند كتابة مبلغ نهائي أكبر من الإجمالي */
  onUnitPriceChange?: (unitPrice: string) => void;
}

const round2 = (v: number) => Math.round(v * 100) / 100;
const round3 = (v: number) => Math.round(v * 1000) / 1000;

/**
 * حقل «المبلغ النهائي»: يكتب البائع المبلغ المتفق عليه مع الزبون
 * فيُحسب الخصم تلقائياً = الإجمالي − المبلغ النهائي.
 * مترابط مع حقل الخصم بالاتجاهين.
 * إن كان المبلغ أكبر من الإجمالي يُرفع سعر الوحدة تلقائياً (مبلغ ÷ كمية) ويُصفَّر الخصم.
 */
export default function FinalAmountInput({
  subtotal, discount, onDiscountChange, quantity, onUnitPriceChange,
}: Props) {
  const [draft, setDraft] = useState<string | null>(null);
  const [raised, setRaised] = useState(false);

  const discountNum = discount.trim() !== '' && !isNaN(parseFloat(discount)) ? parseFloat(discount) : 0;
  const derived = subtotal != null ? round2(Math.max(0, subtotal - discountNum)) : null;
  const shown = draft !== null ? draft : derived != null ? String(derived) : '';

  const canRaisePrice = !!onUnitPriceChange && quantity != null && quantity > 0;
  const draftNum = draft !== null && draft.trim() !== '' ? parseFloat(draft) : NaN;
  const exceeds = !canRaisePrice && subtotal != null && !isNaN(draftNum) && draftNum > subtotal + 1e-9;

  const handleChange = (raw: string) => {
    setDraft(raw);
    setRaised(false);
    if (subtotal == null) return;
    const amount = raw.trim() === '' ? NaN : parseFloat(raw);
    if (isNaN(amount) || amount < 0) {
      onDiscountChange('');
      return;
    }
    if (amount > subtotal + 1e-9) {
      if (canRaisePrice && quantity) {
        // مبلغ أكبر من الإجمالي → يُرفع سعر الوحدة ليطابق المبلغ ويُصفَّر الخصم
        onUnitPriceChange!(String(round3(amount / quantity)));
        onDiscountChange('');
        setRaised(true);
        return;
      }
      onDiscountChange('');
      return;
    }
    const d = round2(subtotal - amount);
    onDiscountChange(d > 0 ? String(d) : '');
  };

  return (
    <div>
      <Input
        label="المبلغ النهائي (بعد الخصم)"
        type="number"
        min="0"
        step="0.01"
        value={shown}
        disabled={subtotal == null}
        onChange={(e) => handleChange(e.target.value)}
        onFocus={(e) => {
          // صفر → خانة فارغة؛ غير ذلك → تحديد النص كله ليُستبدل بالكتابة مباشرة
          if (parseFloat(shown) === 0) {
            setDraft('');
          } else {
            setDraft(shown);
            e.target.select();
          }
        }}
        onBlur={() => { setDraft(null); setRaised(false); }}
        placeholder={subtotal == null ? 'أكمل الكمية والسعر أولاً' : ''}
        className={subtotal == null ? 'opacity-60 cursor-not-allowed' : ''}
        error={exceeds && subtotal != null ? `المبلغ أكبر من الإجمالي (${formatCurrency(subtotal)}) — الخصم لا يكون سالباً` : undefined}
      />
      {raised ? (
        <p className="mt-1 text-xs text-amber-600">المبلغ أكبر من الإجمالي — رُفع سعر الوحدة تلقائياً ليطابقه</p>
      ) : !exceeds && (
        <p className="mt-1 text-xs text-neutral-400">اكتب المبلغ المتفق عليه مع الزبون ليُحسب الخصم تلقائياً</p>
      )}
    </div>
  );
}
