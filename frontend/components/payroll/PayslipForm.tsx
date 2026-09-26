'use client';

import { useMemo, useState } from 'react';
import Input from '@/components/ui/Input';
import Textarea from '@/components/ui/Textarea';
import Button from '@/components/ui/Button';
import { Payslip } from '@/types';
import { formatCurrency } from '@/lib/format';

interface PayslipFormProps {
  payslip: Payslip;
  onSubmit: (data: Record<string, unknown>) => Promise<void>;
  onCancel: () => void;
}

const str = (v: number) => (v ? String(v) : '');

export default function PayslipForm({ payslip, onSubmit, onCancel }: PayslipFormProps) {
  const [form, setForm] = useState({
    overtime_hours: str(payslip.overtime_hours),
    bonus: str(payslip.bonus),
    commission_amount: str(payslip.commission_amount),
    absence_days: str(payslip.absence_days),
    late_deduction: str(payslip.late_deduction),
    other_deduction: str(payslip.other_deduction),
    advance_deduction: str(payslip.advance_deduction),
    notes: payslip.notes || '',
  });
  const [loading, setLoading] = useState(false);

  const set = (key: string, value: string) => setForm((f) => ({ ...f, [key]: value }));
  const num = (v: string) => (v === '' ? 0 : Number(v) || 0);

  const computed = useMemo(() => {
    const overtimeAmount = Math.round(num(form.overtime_hours) * payslip.overtime_hour_rate * 100) / 100;
    const absenceDeduction = Math.round(num(form.absence_days) * payslip.daily_rate * 100) / 100;
    const overtime = payslip.overtime_amount || overtimeAmount;
    const absence = payslip.absence_deduction || absenceDeduction;
    const deductions =
      absence + num(form.late_deduction) + num(form.other_deduction) + num(form.advance_deduction);
    const gross = payslip.total_allowances + overtime + num(form.bonus) + num(form.commission_amount);
    return {
      overtime,
      absence,
      gross,
      deductions: Math.round(deductions * 100) / 100,
      net: Math.round((gross - deductions) * 100) / 100,
    };
  }, [form, payslip.overtime_amount, payslip.absence_deduction, payslip.total_allowances, payslip.overtime_hour_rate, payslip.daily_rate]);

  const handleSubmit = async (ev: React.FormEvent) => {
    ev.preventDefault();
    setLoading(true);
    try {
      await onSubmit({
        overtime_hours: num(form.overtime_hours),
        overtime_amount: computed.overtime,
        bonus: num(form.bonus),
        commission_amount: num(form.commission_amount),
        absence_days: num(form.absence_days),
        absence_deduction: computed.absence,
        late_deduction: num(form.late_deduction),
        other_deduction: num(form.other_deduction),
        advance_deduction: num(form.advance_deduction),
        notes: form.notes,
      });
    } finally {
      setLoading(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div className="rounded-xl bg-sand-100 px-4 py-3 text-sm text-neutral-600 grid grid-cols-2 sm:grid-cols-3 gap-2">
        <div>
          <span className="block text-xs text-neutral-500">الراتب الأساسي</span>
          <span className="tabular-nums font-medium">{formatCurrency(payslip.base_salary)}</span>
        </div>
        <div>
          <span className="block text-xs text-neutral-500">إجمالي البدلات</span>
          <span className="tabular-nums font-medium">{formatCurrency(payslip.total_allowances)}</span>
        </div>
        <div>
          <span className="block text-xs text-neutral-500">معدل اليوم / الساعة</span>
          <span className="tabular-nums font-medium">
            {formatCurrency(payslip.daily_rate)} / {formatCurrency(payslip.overtime_hour_rate)}
          </span>
        </div>
        <div>
          <span className="block text-xs text-neutral-500">أيام العمل</span>
          <span className="tabular-nums font-medium">{payslip.working_days}</span>
        </div>
        <div>
          <span className="block text-xs text-neutral-500">خصم السلفة المحدّد</span>
          <span className="tabular-nums font-medium">{formatCurrency(payslip.advance_deduction)}</span>
        </div>
        <div>
          <span className="block text-xs text-neutral-500">العمولة المحسوبة</span>
          <span className="tabular-nums font-medium">{formatCurrency(payslip.commission_amount)}</span>
        </div>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <Input
          label="ساعات العمل الإضافي"
          type="number"
          step="0.5"
          min="0"
          value={form.overtime_hours}
          onChange={(e) => set('overtime_hours', e.target.value)}
        />
        <Input
          label="أيام الغياب"
          type="number"
          step="0.5"
          min="0"
          value={form.absence_days}
          onChange={(e) => set('absence_days', e.target.value)}
        />
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <Input
          label="مبلغ العمل الإضافي"
          type="number"
          step="0.01"
          readOnly
          value={form.overtime_hours ? String(computed.overtime) : '0'}
          error="مُحتسب تلقائياً: الساعات × سعر الساعة"
        />
        <Input
          label="بدل الغياب"
          type="number"
          step="0.01"
          readOnly
          value={form.absence_days ? String(computed.absence) : '0'}
          error="مُحتسب تلقائياً: الأيام × معدل اليوم"
        />
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <Input
          label="مكافأة"
          type="number"
          step="0.01"
          min="0"
          value={form.bonus}
          onChange={(e) => set('bonus', e.target.value)}
        />
        <Input
          label="عمولة"
          type="number"
          step="0.01"
          min="0"
          value={form.commission_amount}
          onChange={(e) => set('commission_amount', e.target.value)}
        />
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <Input
          label="خصم التأخير"
          type="number"
          step="0.01"
          min="0"
          value={form.late_deduction}
          onChange={(e) => set('late_deduction', e.target.value)}
        />
        <Input
          label="خصومات أخرى"
          type="number"
          step="0.01"
          min="0"
          value={form.other_deduction}
          onChange={(e) => set('other_deduction', e.target.value)}
        />
        <Input
          label="خصم السلفة"
          type="number"
          step="0.01"
          min="0"
          value={form.advance_deduction}
          onChange={(e) => set('advance_deduction', e.target.value)}
        />
      </div>

      <Textarea
        label="ملاحظات"
        value={form.notes}
        onChange={(e) => set('notes', e.target.value)}
        rows={2}
      />

      <div className="rounded-xl bg-brand-50 dark:bg-brand-500/10 px-4 py-3 text-sm space-y-1">
        <div className="flex justify-between text-neutral-600">
          <span>الإجمالي بعد التعديل</span>
          <span className="tabular-nums font-medium">{formatCurrency(computed.gross)}</span>
        </div>
        <div className="flex justify-between text-neutral-600">
          <span>إجمالي الخصومات</span>
          <span className="tabular-nums font-medium">{formatCurrency(computed.deductions)}</span>
        </div>
        <div className="flex justify-between text-brand-700 dark:text-brand-300 font-semibold">
          <span>الصافي</span>
          <span className="tabular-nums">{formatCurrency(computed.net)}</span>
        </div>
      </div>

      <div className="flex justify-start gap-3 pt-2">
        <Button type="submit" loading={loading}>
          حفظ التعديلات
        </Button>
        <Button type="button" variant="secondary" onClick={onCancel}>
          إلغاء
        </Button>
      </div>
    </form>
  );
}
