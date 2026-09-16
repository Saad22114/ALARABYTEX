'use client';

import { useState, useEffect } from 'react';
import Input from '@/components/ui/Input';
import Select from '@/components/ui/Select';
import Textarea from '@/components/ui/Textarea';
import Button from '@/components/ui/Button';
import { Plus, X } from 'lucide-react';
import { DailySale, Branch, Fabric, SaleStockResult, SaleWritePayload, Employee } from '@/types';
import { formatCurrency, formatNumber } from '@/lib/format';
import { listFabrics } from '@/services/fabrics';
import { listEmployees } from '@/services/employees';
import { getSaleStock } from '@/services/sales';

interface SalesFormProps {
  initial?: Partial<DailySale>;
  branches: Branch[];
  allowNegative?: boolean;
  onSubmit: (data: SaleWritePayload) => Promise<void>;
  onCancel: () => void;
}

interface ItemLine {
  fabric: string;
  yards: string;
  unit_price: string;
}

export default function SalesForm({ initial, branches, allowNegative = false, onSubmit, onCancel }: SalesFormProps) {
  const [form, setForm] = useState({
    date: initial?.date || new Date().toISOString().slice(0, 10),
    branch: initial?.branch ? String(initial.branch) : '',
    employee: initial?.employee ? String(initial.employee) : '',
    total_sales: initial?.total_sales ? String(initial.total_sales) : '',
    cash_amount: initial?.cash_amount ? String(initial.cash_amount) : '',
    transfer_amount: initial?.transfer_amount ? String(initial.transfer_amount) : '',
    card_amount: initial?.card_amount ? String(initial.card_amount) : '',
    other_amount: initial?.other_amount ? String(initial.other_amount) : '',
    notes: initial?.notes || '',
  });
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(false);
  const [fabrics, setFabrics] = useState<Fabric[]>([]);
  const [employees, setEmployees] = useState<Employee[]>([]);
  const [stock, setStock] = useState<SaleStockResult | null>(null);
  const [items, setItems] = useState<ItemLine[]>(
    initial?.items?.map((it) => ({
      fabric: String(it.fabric),
      yards: String(it.yards),
      unit_price: it.unit_price != null ? String(it.unit_price) : '',
    })) || []
  );
  const [itemsError, setItemsError] = useState('');

  const isEdit = !!initial?.id;

  useEffect(() => {
    listFabrics({ page_size: 200 })
      .then((res) => setFabrics(res.results.filter((f) => f.is_active)))
      .catch(() => {});
  }, []);

  useEffect(() => {
    if (!isEdit && form.branch) {
      let cancelled = false;
      getSaleStock(Number(form.branch))
        .then((res) => { if (!cancelled) setStock(res); })
        .catch(() => { if (!cancelled) setStock(null); });
      return () => { cancelled = true; };
    }
    setStock(null);
  }, [form.branch, isEdit]);

  useEffect(() => {
    if (!form.branch) {
      setEmployees([]);
      setForm((f) => ({ ...f, employee: '' }));
      return;
    }
    let cancelled = false;
    listEmployees({ branch: Number(form.branch), page_size: 100 })
      .then((res) => { if (!cancelled) setEmployees(res.results.filter((e) => e.is_active)); })
      .catch(() => { if (!cancelled) setEmployees([]); });
    return () => { cancelled = true; };
  }, [form.branch]);

  useEffect(() => {
    if (initial) {
      setForm({
        date: initial.date || new Date().toISOString().slice(0, 10),
        branch: initial.branch ? String(initial.branch) : '',
        employee: initial.employee ? String(initial.employee) : '',
        total_sales: initial.total_sales ? String(initial.total_sales) : '',
        cash_amount: initial.cash_amount ? String(initial.cash_amount) : '',
        transfer_amount: initial.transfer_amount ? String(initial.transfer_amount) : '',
        card_amount: initial.card_amount ? String(initial.card_amount) : '',
        other_amount: initial.other_amount ? String(initial.other_amount) : '',
        notes: initial.notes || '',
      });
      setItems(
        initial.items?.map((it) => ({
          fabric: String(it.fabric),
          yards: String(it.yards),
          unit_price: it.unit_price != null ? String(it.unit_price) : '',
        })) || []
      );
    }
  }, [initial]);

  const availableYards = (fabricId: number): number | undefined => {
    return stock?.items.find((i) => i.fabric === fabricId)?.yards;
  };

  const num = (v: string) => parseFloat(v) || 0;
  const totalSales = num(form.total_sales);
  const paymentTotal = num(form.cash_amount) + num(form.transfer_amount) + num(form.card_amount) + num(form.other_amount);
  const mismatch = totalSales > 0 && Math.abs(totalSales - paymentTotal) > 0.01;

  const validateItems = (): boolean => {
    setItemsError('');
    if (items.length === 0) return true;
    const seen = new Set<number>();
    for (let i = 0; i < items.length; i++) {
      const line = items[i];
      if (!line.fabric) {
        setItemsError('اختر القماش لكل سطر من أصناف المبيعات');
        return false;
      }
      const fid = Number(line.fabric);
      const yards = num(line.yards);
      if (yards <= 0) {
        setItemsError('ياردات المبيعات يجب أن تكون أكبر من صفر');
        return false;
      }
      if (seen.has(fid)) {
        setItemsError('يوجد قماش مكرر في أصناف المبيعات');
        return false;
      }
      seen.add(fid);
      const available = availableYards(fid);
      if (!allowNegative && available !== undefined && available < yards) {
        setItemsError(`المتوفر من «${fabrics.find((f) => f.id === fid)?.name || ''}» في مخزون الفرع ${formatNumber(available)} فقط`);
        return false;
      }
    }
    return true;
  };

  const validate = () => {
    const e: Record<string, string> = {};
    if (!form.branch) e.branch = 'الفرع مطلوب';
    if (!form.total_sales || totalSales <= 0) e.total_sales = 'إجمالي المبيعات مطلوب ويجب أن يكون أكبر من صفر';
    if (totalSales > 0 && mismatch) e.total_sales = 'إجمالي طرق الدفع لا يساوي إجمالي المبيعات';
    setErrors(e);
    return Object.keys(e).length === 0 && validateItems();
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!validate()) return;
    setLoading(true);
    try {
      const parts = items.filter((i) => i.fabric && num(i.yards) > 0);
      const payload: SaleWritePayload = {
        date: form.date,
        branch: Number(form.branch),
        employee: form.employee ? Number(form.employee) : null,
        total_sales: totalSales,
        cash_amount: num(form.cash_amount),
        transfer_amount: num(form.transfer_amount),
        card_amount: num(form.card_amount),
        other_amount: num(form.other_amount),
        notes: form.notes,
      };
      if (isEdit || parts.length > 0) {
        payload.items = parts.map((i) => ({ fabric: Number(i.fabric), yards: num(i.yards), unit_price: num(i.unit_price) }));
      }
      await onSubmit(payload);
    } finally {
      setLoading(false);
    }
  };

  const set = (key: string, val: string) => setForm((f) => ({ ...f, [key]: val }));
  const setLine = (idx: number, patch: Partial<ItemLine>) =>
    setItems((prev) => prev.map((l, i) => (i === idx ? { ...l, ...patch } : l)));
  const addLine = () => setItems((prev) => [...prev, { fabric: '', yards: '3.5', unit_price: '' }]);
  const removeLine = (idx: number) => setItems((prev) => prev.filter((_, i) => i !== idx));

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        <Input
          label="التاريخ"
          type="date"
          value={form.date}
          onChange={(e) => set('date', e.target.value)}
        />
        <Select
          label="الفرع"
          value={form.branch}
          onChange={(e) => set('branch', e.target.value)}
          options={branches.map((b) => ({ value: b.id, label: b.name }))}
          placeholder="اختر الفرع"
          error={errors.branch}
        />
        <Select
          label="الموظف"
          value={form.employee}
          onChange={(e) => set('employee', e.target.value)}
          options={employees.map((emp) => ({ value: emp.id, label: emp.name }))}
          placeholder="اختر الموظف (اختياري)"
        />
      </div>
      <Input
        label="إجمالي المبيعات"
        type="number"
        value={form.total_sales}
        onChange={(e) => set('total_sales', e.target.value)}
        error={errors.total_sales}
        placeholder=""
        min="0"
        step="0.01"
      />
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <Input
          label="المبلغ النقدي"
          type="number"
          value={form.cash_amount}
          onChange={(e) => set('cash_amount', e.target.value)}
          placeholder=""
          min="0"
          step="0.01"
        />
        <Input
          label="التحويل البنكي"
          type="number"
          value={form.transfer_amount}
          onChange={(e) => set('transfer_amount', e.target.value)}
          placeholder=""
          min="0"
          step="0.01"
        />
      </div>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <Input
          label="البطاقة"
          type="number"
          value={form.card_amount}
          onChange={(e) => set('card_amount', e.target.value)}
          placeholder=""
          min="0"
          step="0.01"
        />
        <Input
          label="أخرى"
          type="number"
          value={form.other_amount}
          onChange={(e) => set('other_amount', e.target.value)}
          placeholder=""
          min="0"
          step="0.01"
        />
      </div>

      <div className="rounded-xl bg-sand-50 border border-sand-200 p-4 space-y-2">
        <div className="flex justify-between text-sm">
          <span className="text-neutral-500">إجمالي طرق الدفع:</span>
          <span className="font-semibold text-neutral-700 tabular-nums">{formatCurrency(paymentTotal)}</span>
        </div>
        {mismatch && (
          <p className="text-xs text-red-500 font-medium">
            إجمالي طرق الدفع ({formatCurrency(paymentTotal)}) لا يساوي إجمالي المبيعات ({formatCurrency(totalSales)})
          </p>
        )}
      </div>

      <div className="rounded-xl border border-sand-200 overflow-hidden">
        <div className="px-4 py-3 bg-sand-50 border-b border-sand-100 flex items-center justify-between">
          <div>
            <h3 className="text-sm font-semibold text-neutral-800">أصناف المبيعات (اختياري)</h3>
            <p className="text-xs text-neutral-500 mt-0.5">
              {isEdit
                ? 'عند التحديث يُعاد خصم المخزون تلقائياً وفق الأصناف المعدلة'
                : `يُخصم المخزون تلقائياً من مخزون الفرع عند التسجيل${stock?.warehouse_name ? ` — مخزون الفرع: ${stock.warehouse_name}` : ''}`}
            </p>
          </div>
          <Button type="button" variant="secondary" size="sm" onClick={addLine}>
              <Plus size={14} />
              إضافة صنف
            </Button>
        </div>

        {items.length > 0 && (
          <div className="p-4 space-y-3">
            {items.map((line, idx) => {
              const fid = line.fabric ? Number(line.fabric) : null;
              const available = fid != null ? availableYards(fid) : undefined;
              const low = available !== undefined && num(line.yards) > available;
              return (
                <div key={idx} className="grid grid-cols-[1fr_130px_130px_36px] gap-2 items-end">
                  <Select
                    value={line.fabric}
                        onChange={(e) => {
                          const v = e.target.value;
                          const fid = Number(v);
                          const price = fabrics.find((f) => f.id === fid)?.sale_price_yard;
                          const patch: Partial<ItemLine> = { fabric: v };
                          if (price) patch.unit_price = String(price);
                          setLine(idx, patch);
                        }}
                        options={fabrics.map((f) => ({ value: f.id, label: `${f.name} (${f.code})` }))}
                        placeholder="اختر القماش"
                      />
                  <Input
                    label="الياردات"
                    type="number"
                    min="0"
                    step="0.01"
                    value={line.yards}
                    onChange={(e) => setLine(idx, { yards: e.target.value })}
                    className={low ? 'border-red-400 ring-2 ring-red-200' : ''}
                  />
                  <Input
                    label="سعر البيع للياردة"
                    type="number"
                    min="0"
                    step="0.01"
                    value={line.unit_price}
                    onChange={(e) => setLine(idx, { unit_price: e.target.value })}
                  />
                  <button
                    type="button"
                    onClick={() => removeLine(idx)}
                    className="mb-1 p-2 rounded-lg text-neutral-400 hover:bg-red-50 hover:text-red-600"
                    title="حذف السطر"
                  >
                    <X size={16} />
                  </button>
                  {available !== undefined && (
                    <p className={`col-span-4 -mt-1 text-xs ${low ? 'text-red-500 font-medium' : 'text-neutral-400'}`}>
                      المتوفر في مخزون الفرع: {formatNumber(available)} ياردة{low ? ' — الكمية تتجاوز المتوفر' : ''}
                    </p>
                  )}
                </div>
              );
            })}
            {itemsError && <p className="text-xs text-red-500 font-medium">{itemsError}</p>}
            <p className="text-xs text-neutral-400">
              {allowNegative
                ? 'مسموح بخصم المخزون حتى لو كان سالباً (الإعداد مفعّل في الإعدادات).'
                : 'لا يمكن تجاوز الكمية المتوفرة في مخزون الفرع.'}
            </p>
          </div>
        )}
      </div>

      <Textarea
        label="ملاحظات"
        value={form.notes}
        onChange={(e) => set('notes', e.target.value)}
        placeholder="ملاحظات إضافية..."
        rows={2}
      />
      <div className="flex justify-start gap-3 pt-2">
        <Button type="submit" loading={loading}>
          {isEdit ? 'تحديث' : 'تسجيل'}
        </Button>
        <Button type="button" variant="secondary" onClick={onCancel}>
          إلغاء
        </Button>
      </div>
    </form>
  );
}