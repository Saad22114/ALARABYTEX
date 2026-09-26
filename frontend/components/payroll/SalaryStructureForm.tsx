'use client';

import { useState } from 'react';
import Input from '@/components/ui/Input';
import Select from '@/components/ui/Select';
import Textarea from '@/components/ui/Textarea';
import Button from '@/components/ui/Button';
import { SalaryStructure } from '@/types';

export interface StructureEmployeeOption {
  id: number;
  name: string;
  branch_name: string;
}

interface SalaryStructureFormProps {
  initial?: Partial<SalaryStructure> | null;
  employees: StructureEmployeeOption[];
  onSubmit: (data: Record<string, unknown>) => Promise<void>;
  onCancel: () => void;
}

const todayISO = () => new Date().toISOString().slice(0, 10);

export default function SalaryStructureForm({
  initial,
  employees,
  onSubmit,
  onCancel,
}: SalaryStructureFormProps) {
  const [form, setForm] = useState({
    employee: initial?.employee ? String(initial.employee) : '',
    base_salary: initial?.base_salary != null ? String(initial.base_salary) : '',
    housing_allowance: initial?.housing_allowance != null ? String(initial.housing_allowance) : '0',
    transport_allowance:
      initial?.transport_allowance != null ? String(initial.transport_allowance) : '0',
    other_allowance: initial?.other_allowance != null ? String(initial.other_allowance) : '0',
    overtime_hour_rate: initial?.overtime_hour_rate != null ? String(initial.overtime_hour_rate) : '0',
    working_days: initial?.working_days != null ? String(initial.working_days) : '26',
    effective_from: initial?.effective_from || todayISO(),
    effective_to: initial?.effective_to || '',
    notes: initial?.notes || '',
    is_active: initial?.is_active !== false,
  });
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(false);

  const set = (key: string, value: string | boolean) =>
    setForm((f) => ({ ...f, [key]: value }));

  const num = (v: string) => (v === '' ? 0 : Number(v) || 0);

  const allowances =
    num(form.housing_allowance) + num(form.transport_allowance) + num(form.other_allowance);
  const gross = num(form.base_salary) + allowances;
  const dailyRate = num(form.working_days) > 0 ? gross / num(form.working_days) : 0;

  const validate = () => {
    const e: Record<string, string> = {};
    if (!form.employee) e.employee = 'الموظف مطلوب';
    if (form.base_salary === '' || num(form.base_salary) <= 0)
      e.base_salary = 'الراتب الأساسي مطلوب ويجب أن يكون أكبر من صفر';
    if (form.working_days === '' || num(form.working_days) <= 0)
      e.working_days = 'عدد أيام العمل مطلوب';
    if (form.effective_to && form.effective_to <= form.effective_from)
      e.effective_to = 'تاريخ الانتهاء يجب أن يكون بعد تاريخ السريان';
    setErrors(e);
    return Object.keys(e).length === 0;
  };

  const handleSubmit = async (ev: React.FormEvent) => {
    ev.preventDefault();
    if (!validate()) return;
    setLoading(true);
    try {
      await onSubmit({
        employee: Number(form.employee),
        base_salary: num(form.base_salary),
        housing_allowance: num(form.housing_allowance),
        transport_allowance: num(form.transport_allowance),
        other_allowance: num(form.other_allowance),
        overtime_hour_rate: num(form.overtime_hour_rate),
        working_days: num(form.working_days),
        effective_from: form.effective_from,
        effective_to: form.effective_to || null,
        notes: form.notes,
        is_active: form.is_active,
      });
    } finally {
      setLoading(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <Select
        label="الموظف"
        value={form.employee}
        onChange={(e) => set('employee', e.target.value)}
        options={employees.map((emp) => ({
          value: emp.id,
          label: emp.branch_name ? `${emp.name} — ${emp.branch_name}` : emp.name,
        }))}
        placeholder="اختر الموظف"
        error={errors.employee}
        disabled={!!initial?.id}
      />

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <Input
          label="الراتب الأساسي"
          type="number"
          step="0.01"
          min="0"
          value={form.base_salary}
          onChange={(e) => set('base_salary', e.target.value)}
          error={errors.base_salary}
        />
        <Input
          label="عدد أيام العمل بالشهر"
          type="number"
          step="0.5"
          min="1"
          value={form.working_days}
          onChange={(e) => set('working_days', e.target.value)}
          error={errors.working_days}
        />
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <Input
          label="بدل سكن"
          type="number"
          step="0.01"
          min="0"
          value={form.housing_allowance}
          onChange={(e) => set('housing_allowance', e.target.value)}
        />
        <Input
          label="بدل نقل"
          type="number"
          step="0.01"
          min="0"
          value={form.transport_allowance}
          onChange={(e) => set('transport_allowance', e.target.value)}
        />
        <Input
          label="بدلات أخرى"
          type="number"
          step="0.01"
          min="0"
          value={form.other_allowance}
          onChange={(e) => set('other_allowance', e.target.value)}
        />
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <Input
          label="سعر ساعة العمل الإضافي"
          type="number"
          step="0.01"
          min="0"
          value={form.overtime_hour_rate}
          onChange={(e) => set('overtime_hour_rate', e.target.value)}
        />
        <Input
          label="سريان من"
          type="date"
          value={form.effective_from}
          onChange={(e) => set('effective_from', e.target.value)}
        />
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <Input
          label="سريان إلى (اختياري)"
          type="date"
          value={form.effective_to}
          onChange={(e) => set('effective_to', e.target.value)}
          error={errors.effective_to}
        />
        <label className="flex items-center gap-2 pt-6">
          <input
            type="checkbox"
            checked={form.is_active}
            onChange={(e) => set('is_active', e.target.checked)}
            className="w-4 h-4 rounded border-sand-300 text-brand-600"
          />
          <span className="text-sm text-neutral-700">هيكل فعّال</span>
        </label>
      </div>

      <Textarea
        label="ملاحظات"
        value={form.notes}
        onChange={(e) => set('notes', e.target.value)}
        rows={2}
        placeholder="ملاحظات إضافية..."
      />

      <div className="rounded-xl bg-sand-100 px-4 py-3 text-sm text-neutral-600 space-y-1">
        <div className="flex justify-between">
          <span>إجمالي البدلات</span>
          <span className="tabular-nums font-medium">{allowances.toFixed(2)}</span>
        </div>
        <div className="flex justify-between">
          <span>الإجمالي الشهري</span>
          <span className="tabular-nums font-medium">{gross.toFixed(2)}</span>
        </div>
        <div className="flex justify-between">
          <span>معدل اليوم</span>
          <span className="tabular-nums font-medium">{dailyRate.toFixed(2)}</span>
        </div>
      </div>

      <div className="flex justify-start gap-3 pt-2">
        <Button type="submit" loading={loading}>
          {initial?.id ? 'تحديث' : 'حفظ'}
        </Button>
        <Button type="button" variant="secondary" onClick={onCancel}>
          إلغاء
        </Button>
      </div>
    </form>
  );
}
