'use client';

import { useState } from 'react';
import Input from '@/components/ui/Input';
import { formatCurrencyOneDecimal as formatCurrency } from '@/lib/format';

interface Props {
  /** إجمالي الصنف قبل الخصم (كمية × سعر)، أو null إن لم تُكمَل البيانات */
  subtotal: number | null;
  /** قيمة الخصم الحالية كنص (كما في حقل الخصم) */
  discount: string;
  /** يُستدعى لتحديث حقل الخصم عند كتابة المبلغ النهائي */
  onDiscountChange: (discount: string) => void;
  /** الكمية — لازمة لإعادة حساب سعر الوحدة من المبلغ النهائي */
  quantity?: number | null;
  /** يُستدعى لتحديث سعر الوحدة عند كتابة المبلغ النهائي */
  onUnitPriceChange?: (unitPrice: string) => void;
}

const round1 = (v: number) => Math.round(v * 10) / 10;
const round2 = (v: number) => Math.round(v * 100) / 100;
const round3 = (v: number) => Math.round(v * 1000) / 1000;

/**
 * حقل «المبلغ النهائي»: يكتب البائع المبلغ المتفق عليه مع الزبون
 * فيُعاد حساب سعر الوحدة تلقائياً = المبلغ النهائي ÷ الكمية، ويُصفّر الخصم
 * حتى يطابق إجمالي الصنف المبلغ الذي أدخله البائع.
 */
export default function FinalAmountInput({
  subtotal, discount, onDiscountChange, quantity, onUnitPriceChange,
}: Props) {
  const [draft, setDraft] = useState<string | null>(null);
  const [raised, setRaised] = useState(false);

  const discountNum = discount.trim() !== '' && !isNaN(parseFloat(discount)) ? parseFloat(discount) : 0;
  const derived = subtotal != null ? round1(Math.max(0, subtotal - discountNum)) : null;
  const shown = draft !== null ? draft : derived != null ? derived.toFixed(1) : '';

  const canUpdateUnitPrice = !!onUnitPriceChange && quantity != null && quantity > 0;
  const draftNum = draft !== null && draft.trim() !== '' ? parseFloat(draft) : NaN;
  const exceeds = !canUpdateUnitPrice && subtotal != null && !isNaN(draftNum) && draftNum > subtotal + 1e-9;

  const handleChange = (raw: string) => {
    setDraft(raw);
    setRaised(false);
    if (subtotal == null) return;
    const amount = raw.trim() === '' ? NaN : parseFloat(raw);
    if (isNaN(amount) || amount < 0) {
      onDiscountChange('');
      return;
    }
    const finalAmount = round1(amount);
    if (canUpdateUnitPrice && quantity) {
      onUnitPriceChange!(String(round3(finalAmount / quantity)));
      onDiscountChange('');
      setRaised(true);
      return;
    }
    onDiscountChange(finalAmount <= subtotal ? String(round2(subtotal - finalAmount)) : '');
  };

  return (
    <div>
      <Input
        label="المبلغ النهائي (بعد الخصم)"
        type="number"
        min="0"
        step="0.1"
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
        <p className="mt-1 text-xs text-amber-600">تحدّث سعر الوحدة تلقائيًا وأُلغي الخصم ليطابق الإجمالي المبلغ النهائي</p>
      ) : !exceeds && (
        <p className="mt-1 text-xs text-neutral-400">اكتب المبلغ النهائي لتحديث سعر الوحدة تلقائياً وإلغاء الخصم</p>
      )}
    </div>
  );
}
