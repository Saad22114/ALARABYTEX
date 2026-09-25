'use client';

import { useEffect, useState } from 'react';
import Modal from '@/components/ui/Modal';
import Button from '@/components/ui/Button';
import Select from '@/components/ui/Select';
import Input from '@/components/ui/Input';
import QuantityQuickPicks from '@/components/sessions/QuantityQuickPicks';
import FinalAmountInput from '@/components/sessions/FinalAmountInput';
import {
  Fabric, SaleSession, SessionCardType, SessionSaleType, SessionPaymentMethod, SessionSaleItem,
} from '@/types';
import { updateSessionItem } from '@/services/sessions';
import { formatCurrency, formatNumber } from '@/lib/format';
import { rollSaleAllowed } from '@/lib/fabrics';
import { useToast } from '@/components/ui/Toast';
import { useSettings } from '@/components/providers/SettingsProvider';

const PAYMENT_OPTIONS = [
  { value: 'cash', label: 'كاش' },
  { value: 'transfer', label: 'تحويل' },
  { value: 'card', label: 'ماكينة' },
];

const CARD_TYPE_OPTIONS: { value: SessionCardType; label: string }[] = [
  { value: 'credit', label: 'إئتماني / Credit' },
  { value: 'debit', label: 'خصم مباشر / Debit' },
];

interface Props {
  open: boolean;
  session: SaleSession | null;
  item: SessionSaleItem | null;
  fabrics: Fabric[];
  onClose: () => void;
  onSaved: () => void;
}

export default function SessionItemEditModal({ open, session, item, fabrics, onClose, onSaved }: Props) {
  const { toast } = useToast();
  const { settings } = useSettings();
  const [fabric, setFabric] = useState<number | null>(null);
  const [saleType, setSaleType] = useState<SessionSaleType>('yard');
  const [quantity, setQuantity] = useState('');
  const [unitPrice, setUnitPrice] = useState('');
  const [discount, setDiscount] = useState('');
  const [paymentMethod, setPaymentMethod] = useState<SessionPaymentMethod>(settings?.default_payment_method || 'cash');
  const [cardType, setCardType] = useState<SessionCardType | ''>('');
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (open && item) {
      setFabric(item.fabric);
      setSaleType(item.sale_type);
      setQuantity(String(item.quantity));
      setUnitPrice(String(item.unit_price));
      setDiscount(item.discount_amount > 0 ? String(item.discount_amount) : '');
      setPaymentMethod(item.payment_method);
      setCardType((item.card_type === 'credit' || item.card_type === 'debit' ? item.card_type : '') as SessionCardType | '');
    }
  }, [open, item]);

  const selectedFabric = fabrics.find((f) => f.id === fabric);
  const rollAllowed = rollSaleAllowed(selectedFabric, session?.branch);
  const autoPrice = () => {
    if (!selectedFabric) return 0;
    const base = Number(selectedFabric.sale_price_yard) || 0;
    if (saleType === 'roll') {
      if (selectedFabric.sale_price_roll != null) return Number(selectedFabric.sale_price_roll) || 0;
      return base * (Number(selectedFabric.yards_per_roll) || 0);
    }
    return base;
  };

  const handleFabricOrType = (patch: Partial<{ fabric: number | null; sale_type: SessionSaleType }>) => {
    const next = { fabric, saleType, ...patch };
    const candidate = fabrics.find((f) => f.id === next.fabric);
    if (candidate && !rollSaleAllowed(candidate, session?.branch) && next.sale_type === 'roll') {
      next.sale_type = 'yard';
    }
    setFabric(next.fabric);
    setSaleType(next.sale_type ?? saleType);
    if (candidate) {
      const base = Number(candidate.sale_price_yard) || 0;
      let price = base;
      if (next.sale_type === 'roll') {
        price = candidate.sale_price_roll != null ? (Number(candidate.sale_price_roll) || 0) : base * (Number(candidate.yards_per_roll) || 0);
      }
      setUnitPrice(String(price));
    }
  };

  const qtyNum = parseFloat(quantity);
  const priceNum = parseFloat(unitPrice);
  const discountNum = discount.trim() !== '' && !isNaN(parseFloat(discount)) ? parseFloat(discount) : 0;
  const subtotal = quantity.trim() !== '' && qtyNum > 0 && priceNum >= 0 ? qtyNum * priceNum : null;
  const netTotal = subtotal != null ? Math.max(0, subtotal - discountNum) : null;
  const feePercent =
    paymentMethod === 'card'
      ? cardType === 'debit'
        ? Number(settings?.card_debit_fee_percent ?? 0)
        : Number(settings?.card_credit_fee_percent ?? 0)
      : 0;
  const cardFee = netTotal != null && feePercent > 0 ? Math.round(netTotal * feePercent) / 100 : 0;
  const netAfterFee = netTotal != null ? netTotal - cardFee : null;

  const handleSave = async () => {
    if (!session || !item) return;
    if (!fabric) {
      toast('error', 'اختر القماش');
      return;
    }
    if (!qtyNum || qtyNum <= 0) {
      toast('error', 'أدخل كمية صحيحة أكبر من صفر');
      return;
    }
    if (isNaN(priceNum) || priceNum < 0) {
      toast('error', 'أدخل سعر وحدة صحيح');
      return;
    }
    if (saleType === 'roll') {
      const fabricObj = fabrics.find((f) => f.id === fabric);
      if (fabricObj && !fabricObj.yards_per_roll) {
        toast('error', `القماش «${fabricObj.name}» لا توجد له ياردات الطاقة`);
        return;
      }
    }
    setSaving(true);
    try {
      await updateSessionItem(session.id, item.id, {
        fabric,
        sale_type: saleType,
        quantity: qtyNum,
        unit_price: priceNum,
        discount_amount: discountNum,
        payment_method: paymentMethod,
        card_type: paymentMethod === 'card' ? (cardType || '') : '',
      });
      toast('success', 'تم تعديل البيع بنجاح');
      onClose();
      onSaved();
    } catch (err: any) {
      toast('error', err.message);
    } finally {
      setSaving(false);
    }
  };

  return (
    <Modal open={open} onClose={onClose} title="تعديل بيعة من الوردية" maxWidth="max-w-2xl">
      <div className="space-y-4">
        <div className="grid gap-4 sm:grid-cols-2">
          <Select
            label="القماش"
            value={fabric ?? ''}
            onChange={(e) => handleFabricOrType({ fabric: Number(e.target.value) })}
            options={fabrics.map((f) => ({ value: f.id, label: `${f.name} — ي: ${formatNumber(f.sale_price_yard)}${f.sale_price_roll_display ? ` / ط: ${formatNumber(f.sale_price_roll_display)}` : ''}` }))}
            placeholder="اختر القماش"
          />
          <div>
            <label className="block text-sm font-medium text-neutral-700 mb-1.5">نوع البيع</label>
            <div className="flex rounded-xl border border-sand-300 overflow-hidden">
              <button
                type="button"
                onClick={() => handleFabricOrType({ sale_type: 'yard' })}
                className={`flex-1 py-2.5 text-sm font-medium transition-colors ${saleType === 'yard' ? 'bg-brand-600 text-white' : 'bg-surface text-neutral-600 hover:bg-sand-100'}`}
              >
                ياردة
              </button>
              <button
                type="button"
                onClick={() => handleFabricOrType({ sale_type: 'roll' })}
                disabled={!selectedFabric || !rollAllowed}
                title={selectedFabric && !rollAllowed ? 'البيع بالطاقة غير مسموح لهذا القماش في هذا الفرع' : 'بيع بالطاقة'}
                className={`flex-1 py-2.5 text-sm font-medium transition-colors ${
                  !selectedFabric || !rollAllowed
                    ? 'bg-surface text-neutral-300 cursor-not-allowed'
                    : saleType === 'roll'
                      ? 'bg-brand-600 text-white'
                      : 'bg-surface text-neutral-600 hover:bg-sand-100'
                }`}
              >
                طاقة (بالطاقة)
              </button>
            </div>
          </div>
          <div>
            <Input
              label={saleType === 'roll' ? 'عدد الطاقات' : 'الكمية (ياردات)'}
              type="number"
              min="0"
              step={saleType === 'roll' ? '1' : '0.25'}
              value={quantity}
              onChange={(e) => setQuantity(e.target.value)}
              placeholder=""
            />
            {saleType === 'yard' && <QuantityQuickPicks value={quantity} onPick={setQuantity} />}
          </div>
          <Input
            label="سعر الوحدة"
            type="number"
            min="0"
            step="0.1"
            value={unitPrice}
            onChange={(e) => setUnitPrice(e.target.value)}
            placeholder={String(autoPrice())}
          />
          <Input
            label="قيمة الخصم"
            type="number"
            min="0"
            step="0.01"
            value={discount}
            onChange={(e) => setDiscount(e.target.value)}
            placeholder=""
          />
          <FinalAmountInput subtotal={subtotal} discount={discount} onDiscountChange={setDiscount} />
          <Select
            label="طريقة الدفع"
            value={paymentMethod}
            onChange={(e) => {
              const v = e.target.value as SessionPaymentMethod;
              setPaymentMethod(v);
              if (v === 'card' && !cardType) setCardType('credit');
            }}
            options={PAYMENT_OPTIONS}
          />
        </div>

        {paymentMethod === 'card' && (
          <div>
            <label className="block text-sm font-medium text-neutral-700 mb-1.5">نوع الماكينة</label>
            <div className="flex rounded-xl border border-sand-300 overflow-hidden">
              {CARD_TYPE_OPTIONS.map((opt) => (
                <button
                  key={opt.value}
                  type="button"
                  onClick={() => setCardType(opt.value)}
                  className={`flex-1 py-2.5 text-sm font-medium transition-colors ${cardType === opt.value ? 'bg-brand-600 text-white' : 'bg-surface text-neutral-600 hover:bg-sand-100'}`}
                >
                  {opt.label}
                </button>
              ))}
            </div>
            <p className="text-xs text-neutral-400 mt-1">عمولة الماكينة {feePercent}% — تُخصم من البيعة ويُسجَّل الصافي</p>
          </div>
        )}

        <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl bg-sand-50 border border-sand-200 px-4 py-3">
          <span className="text-sm text-neutral-600">
            الإجمالي ({saleType === 'roll' ? `${quantity || '0'} طاقة` : `${quantity || '0'} ياردة`} × {formatCurrency(priceNum)})
            {discountNum > 0 ? ` - خصم ${formatCurrency(discountNum)}` : ''}:
          </span>
          <span className="text-xl font-bold tabular-nums text-brand-700">
            {netTotal != null ? formatCurrency(netTotal) : '—'}
          </span>
        </div>
        {paymentMethod === 'card' && cardFee > 0 && netAfterFee != null && (
          <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl bg-amber-50 border border-amber-200 px-4 py-2">
            <span className="text-xs text-neutral-600">عمولة الماكينة {feePercent}% ({cardType === 'debit' ? 'خصم مباشر / Debit' : 'إئتماني / Credit'}):</span>
            <span className="text-xs font-semibold text-red-600 tabular-nums">- {formatCurrency(cardFee)}</span>
            <span className="text-sm font-bold text-brand-700 tabular-nums">الصافي: {formatCurrency(netAfterFee)}</span>
          </div>
        )}

        <p className="text-xs text-neutral-400">
          تعديل بيعة من وردية مغلقة يُحدّث السجل اليومي والمخزون تلقائياً — حتى بعد مرور أيام على الإغلاق.
        </p>

        <div className="flex items-center justify-end gap-3 pt-2">
          <Button variant="secondary" onClick={onClose}>
            إلغاء
          </Button>
          <Button onClick={handleSave} loading={saving}>
            حفظ التعديل
          </Button>
        </div>
      </div>
    </Modal>
  );
}