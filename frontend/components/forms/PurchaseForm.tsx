'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link';
import Input from '@/components/ui/Input';
import Select from '@/components/ui/Select';
import Button from '@/components/ui/Button';
import EmptyState from '@/components/ui/EmptyState';
import LedgerItemsFields, { newLedgerItemRow, ledgerItemsTotal, LedgerItemRow } from './LedgerItemsFields';
import { Fabric, CreateLedgerEntry, SupplierPayMethod, Warehouse, Branch } from '@/types';
import { listFabrics } from '@/services/fabrics';
import { listWarehouses } from '@/services/warehouses';
import { listBranches } from '@/services/branches';
import { formatCurrency } from '@/lib/format';
import { todayISO } from '@/lib/date';

const PAYMENT_METHOD_OPTIONS = [
  { value: 'cash', label: 'كاش' },
  { value: 'bank_transfer', label: 'تحويل بنكي' },
];

interface PurchaseFormProps {
  onSubmit: (data: CreateLedgerEntry) => Promise<void>;
  onCancel: () => void;
}

export default function PurchaseForm({ onSubmit, onCancel }: PurchaseFormProps) {
  const [fabrics, setFabrics] = useState<Fabric[]>([]);
  const [warehouses, setWarehouses] = useState<Warehouse[]>([]);
  const [branches, setBranches] = useState<Branch[]>([]);
  const [fabricsLoading, setFabricsLoading] = useState(true);
  const [form, setForm] = useState({ date: todayISO(), receipt_no: '', notes: '' });
  const [items, setItems] = useState<LedgerItemRow[]>([newLedgerItemRow(1)]);
  const [paid, setPaid] = useState(false);
  const [paymentMethod, setPaymentMethod] = useState<SupplierPayMethod>('cash');
  const [paymentAmount, setPaymentAmount] = useState('');
  const [bankReference, setBankReference] = useState('');
  const [receiverName, setReceiverName] = useState('');
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    let cancelled = false;
    setFabricsLoading(true);
    listFabrics({ page_size: 200 })
      .then((res) => { if (!cancelled) setFabrics(res.results.filter((f) => f.is_active)); })
      .catch(() => { if (!cancelled) setFabrics([]); })
      .finally(() => { if (!cancelled) setFabricsLoading(false); });
    listWarehouses({ page_size: 200 }).then((r) => { if (!cancelled) setWarehouses(r.results.filter((w) => !w.is_branch_stock)); }).catch(() => {});
    listBranches({ page_size: 200 }).then((r) => { if (!cancelled) setBranches(r.results); }).catch(() => {});
    return () => { cancelled = true; };
  }, []);

  const total = ledgerItemsTotal(items);

  const validate = () => {
    const e: Record<string, string> = {};
    if (!form.date) e.date = 'التاريخ مطلوب';
    const validRows = items.filter((r) => r.fabric);
    if (validRows.length === 0) e.items = 'أضف صنفًا واحدًا على الأقل';
    else if (validRows.some((r) => !Number(r.quantity_yards) || !Number(r.unit_price))) {
      e.items = 'أدخل الكمية وسعر الياردة للأصناف بشكل صحيح';
    }
    if (paid && !paymentMethod) e.payment_method = 'طريقة الدفع مطلوبة';
    if (paid && paymentMethod === 'bank_transfer' && !bankReference.trim()) e.bank_reference = 'رقم الحوالة مطلوب';
    setErrors(e);
    return Object.keys(e).length === 0;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!validate()) return;
    const payload: CreateLedgerEntry = {
      entry_type: 'purchase',
      date: form.date,
      receipt_no: form.receipt_no.trim() || undefined,
      notes: form.notes.trim() || undefined,
      items: items
        .filter((r) => r.fabric)
        .map((r) => ({
          fabric: Number(r.fabric),
          quantity_yards: r.quantity_yards ? Number(r.quantity_yards) : undefined,
          rolls: r.rolls ? Number(r.rolls) : undefined,
          unit_price: r.unit_price ? Number(r.unit_price) : undefined,
          warehouse: r.destType === 'warehouse' ? Number(r.destId) : undefined,
          branch: r.destType === 'branch' ? Number(r.destId) : undefined,
        })),
    };
    if (paid) {
      payload.payment_method = paymentMethod;
      payload.payment_amount = Number(paymentAmount) || total;
      if (paymentMethod === 'bank_transfer') payload.bank_reference = bankReference.trim() || undefined;
      if (paymentMethod === 'cash' && receiverName.trim()) payload.receiver_name = receiverName.trim();
    }
    setLoading(true);
    try {
      await onSubmit(payload);
    } finally {
      setLoading(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <Input
          label="التاريخ"
          type="date"
          dir="ltr"
          value={form.date}
          onChange={(e) => setForm({ ...form, date: e.target.value })}
          error={errors.date}
        />
        <Input
          label="رقم الفاتورة"
          value={form.receipt_no}
          onChange={(e) => setForm({ ...form, receipt_no: e.target.value })}
          placeholder="اختياري"
        />
      </div>

      {fabricsLoading ? (
        <p className="text-sm text-neutral-400 py-3">جارٍ تحميل الأقمشة...</p>
      ) : fabrics.length === 0 ? (
        <div className="border border-sand-200 rounded-xl">
          <EmptyState
            title="لا توجد أقمشة"
            description="أضف الأقمشة أولاً لتتمكن من تسجيل فاتورة شراء"
            action={
              <Link href="/fabrics">
                <Button type="button" size="sm">إضافة قماش</Button>
              </Link>
            }
          />
        </div>
      ) : (
        <div className="space-y-3">
          <LedgerItemsFields
            fabrics={fabrics}
            items={items}
            onChange={setItems}
            destinations={{ warehouses, branches }}
            destinationLabel="وجهة توريد البضاعة (اختياري)"
          />
          {errors.items && <p className="text-xs text-red-500">{errors.items}</p>}
          <div className="flex items-center justify-between p-4 bg-sand-50 rounded-xl">
            <span className="text-sm font-medium text-neutral-600">إجمالي الفاتورة</span>
            <span className="text-xl font-bold text-neutral-800 tabular-nums">{formatCurrency(total)}</span>
          </div>
        </div>
      )}

      <div className="border-t border-sand-100 pt-4 space-y-4">
        <label className="flex items-center gap-3 cursor-pointer">
          <input
            type="checkbox"
            checked={paid}
            onChange={(e) => setPaid(e.target.checked)}
            className="w-4 h-4 accent-brand-600"
          />
          <span className="text-sm font-medium text-neutral-700">تم السداد الآن</span>
        </label>

        {paid && (
          <div className="space-y-4 p-4 bg-sand-50 rounded-xl">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <Input
                label="المبلغ المسدد"
                type="number"
                step="0.01"
                min="0"
                value={paymentAmount}
                onChange={(e) => setPaymentAmount(e.target.value)}
                placeholder={String(total)}
              />
              <Select
                label="طريقة الدفع"
                value={paymentMethod}
                onChange={(e) => setPaymentMethod(e.target.value as SupplierPayMethod)}
                options={PAYMENT_METHOD_OPTIONS}
              />
            </div>
            {paymentMethod === 'bank_transfer' && (
              <Input
                label="رقم الحوالة"
                value={bankReference}
                onChange={(e) => setBankReference(e.target.value)}
                error={errors.bank_reference}
                placeholder="رقم الحوالة البنكية"
              />
            )}
            {paymentMethod === 'cash' && (
              <Input
                label="اسم المستلم"
                value={receiverName}
                onChange={(e) => setReceiverName(e.target.value)}
                placeholder="اسم من يستلم المبلغ"
              />
            )}
          </div>
        )}
      </div>

      <Input
        label="ملاحظات"
        value={form.notes}
        onChange={(e) => setForm({ ...form, notes: e.target.value })}
        placeholder="ملاحظات إضافية..."
      />

      <div className="flex justify-start gap-3 pt-2">
        <Button type="submit" loading={loading}>تسجيل الفاتورة</Button>
        <Button type="button" variant="secondary" onClick={onCancel}>إلغاء</Button>
      </div>
    </form>
  );
}