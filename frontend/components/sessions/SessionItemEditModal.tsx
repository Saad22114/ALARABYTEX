'use client';

import { useEffect, useState } from 'react';
import Modal from '@/components/ui/Modal';
import Button from '@/components/ui/Button';
import Select from '@/components/ui/Select';
import Input from '@/components/ui/Input';
import {
  Fabric, SaleSession, SessionSaleType, SessionPaymentMethod, SessionSaleItem,
} from '@/types';
import { updateSessionItem } from '@/services/sessions';
import { formatCurrency, formatNumber } from '@/lib/format';
import { useToast } from '@/components/ui/Toast';
import { useSettings } from '@/components/providers/SettingsProvider';

const PAYMENT_OPTIONS = [
  { value: 'cash', label: 'كاش' },
  { value: 'transfer', label: 'تحويل' },
  { value: 'card', label: 'ماكينة' },
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
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (open && item) {
      setFabric(item.fabric);
      setSaleType(item.sale_type);
      setQuantity(String(item.quantity));
      setUnitPrice(String(item.unit_price));
      setDiscount(item.discount_amount > 0 ? String(item.discount_amount) : '');
      setPaymentMethod(item.payment_method);
    }
  }, [open, item]);

  const selectedFabric = fabrics.find((f) => f.id === fabric);
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
    setFabric(next.fabric);
    setSaleType(next.sale_type ?? saleType);
    const candidate = fabrics.find((f) => f.id === next.fabric);
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
        toast('error', `القماش «${fabricObj.name}» لا توجد له ياردات اللفة`);
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
            options={fabrics.map((f) => ({ value: f.id, label: `${f.name} — ي: ${formatNumber(f.sale_price_yard)}${f.sale_price_roll_display ? ` / ل: ${formatNumber(f.sale_price_roll_display)}` : ''}` }))}
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
                className={`flex-1 py-2.5 text-sm font-medium transition-colors ${saleType === 'roll' ? 'bg-brand-600 text-white' : 'bg-surface text-neutral-600 hover:bg-sand-100'}`}
              >
                لفة (بالطاقة)
              </button>
            </div>
          </div>
          <Input
            label={saleType === 'roll' ? 'عدد اللفات' : 'الكمية (ياردات)'}
            type="number"
            min="0"
            step={saleType === 'roll' ? '1' : '0.25'}
            value={quantity}
            onChange={(e) => setQuantity(e.target.value)}
            placeholder=""
          />
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
          <Select
            label="طريقة الدفع"
            value={paymentMethod}
            onChange={(e) => setPaymentMethod(e.target.value as SessionPaymentMethod)}
            options={PAYMENT_OPTIONS}
          />
        </div>

        <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl bg-sand-50 border border-sand-200 px-4 py-3">
          <span className="text-sm text-neutral-600">
            الإجمالي ({saleType === 'roll' ? `${quantity || '0'} لفة` : `${quantity || '0'} ياردة`} × {formatCurrency(priceNum)})
            {discountNum > 0 ? ` - خصم ${formatCurrency(discountNum)}` : ''}:
          </span>
          <span className="text-xl font-bold tabular-nums text-brand-700">
            {netTotal != null ? formatCurrency(netTotal) : '—'}
          </span>
        </div>

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