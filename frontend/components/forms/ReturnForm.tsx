'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link';
import Input from '@/components/ui/Input';
import Button from '@/components/ui/Button';
import EmptyState from '@/components/ui/EmptyState';
import LedgerItemsFields, { newLedgerItemRow, ledgerItemsTotal, LedgerItemRow } from './LedgerItemsFields';
import { Fabric, CreateLedgerEntry } from '@/types';
import { listFabrics } from '@/services/fabrics';
import { formatCurrency } from '@/lib/format';
import { todayISO } from '@/lib/date';

interface ReturnFormProps {
  onSubmit: (data: CreateLedgerEntry) => Promise<void>;
  onCancel: () => void;
}

export default function ReturnForm({ onSubmit, onCancel }: ReturnFormProps) {
  const [fabrics, setFabrics] = useState<Fabric[]>([]);
  const [fabricsLoading, setFabricsLoading] = useState(true);
  const [form, setForm] = useState({ date: todayISO(), amount: '', notes: '' });
  const [items, setItems] = useState<LedgerItemRow[]>([]);
  const [useItems, setUseItems] = useState(false);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    let cancelled = false;
    setFabricsLoading(true);
    listFabrics({ page_size: 200 })
      .then((res) => { if (!cancelled) setFabrics(res.results.filter((f) => f.is_active)); })
      .catch(() => { if (!cancelled) setFabrics([]); })
      .finally(() => { if (!cancelled) setFabricsLoading(false); });
    return () => { cancelled = true; };
  }, []);

  const total = ledgerItemsTotal(items);

  const validate = () => {
    const e: Record<string, string> = {};
    if (!form.date) e.date = 'التاريخ مطلوب';
    if (!useItems) {
      if (!form.amount || Number(form.amount) <= 0) e.amount = 'أدخل مبلغًا صحيحًا';
    } else {
      const validRows = items.filter((r) => r.fabric);
      if (validRows.length === 0) e.items = 'أضف صنفًا واحدًا على الأقل أو أدخل المبلغ مباشرة';
    }
    setErrors(e);
    return Object.keys(e).length === 0;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!validate()) return;
    const payload: CreateLedgerEntry = {
      entry_type: 'return',
      date: form.date,
      notes: form.notes.trim() || undefined,
    };
    if (useItems) {
      payload.items = items.filter((r) => r.fabric).map((r) => ({
        fabric: Number(r.fabric),
        quantity_yards: r.quantity_yards ? Number(r.quantity_yards) : undefined,
        rolls: r.rolls ? Number(r.rolls) : undefined,
        unit_price: r.unit_price ? Number(r.unit_price) : undefined,
      }));
      if (total) payload.amount = total;
    } else {
      payload.amount = Number(form.amount);
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
          label="المبلغ"
          type="number"
          step="0.01"
          min="0"
          value={form.amount}
          onChange={(e) => setForm({ ...form, amount: e.target.value })}
          error={errors.amount}
          placeholder=""
        />
      </div>

      <label className="flex items-center gap-3 cursor-pointer">
        <input
          type="checkbox"
          checked={useItems}
          onChange={(e) => setUseItems(e.target.checked)}
          className="w-4 h-4 accent-brand-600"
        />
        <span className="text-sm font-medium text-neutral-700">إدخال الأصناف بدلاً من المبلغ</span>
      </label>

      {useItems &&
        (fabricsLoading ? (
          <p className="text-sm text-neutral-400 py-3">جارٍ تحميل الأقمشة...</p>
        ) : fabrics.length === 0 ? (
          <div className="border border-sand-200 rounded-xl">
            <EmptyState
              title="لا توجد أقمشة"
              description="أضف الأقمشة أولاً لتتمكن من تسجيل مرتجع بأصناف"
              action={
                <Link href="/fabrics">
                  <Button type="button" size="sm">إضافة قماش</Button>
                </Link>
              }
            />
          </div>
        ) : (
          <div className="space-y-3">
            <LedgerItemsFields fabrics={fabrics} items={items} onChange={setItems} />
            {errors.items && <p className="text-xs text-red-500">{errors.items}</p>}
            <div className="flex items-center justify-between p-4 bg-sand-50 rounded-xl">
              <span className="text-sm font-medium text-neutral-600">إجمالي المرتجع</span>
              <span className="text-xl font-bold text-neutral-800 tabular-nums">{formatCurrency(total)}</span>
            </div>
          </div>
        ))}

      <Input
        label="ملاحظات"
        value={form.notes}
        onChange={(e) => setForm({ ...form, notes: e.target.value })}
        placeholder="ملاحظات إضافية..."
      />

      <div className="flex justify-start gap-3 pt-2">
        <Button type="submit" loading={loading}>تسجيل المرتجع</Button>
        <Button type="button" variant="secondary" onClick={onCancel}>إلغاء</Button>
      </div>
    </form>
  );
}