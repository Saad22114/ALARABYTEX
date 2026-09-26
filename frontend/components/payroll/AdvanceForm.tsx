'use client';

import { useState } from 'react';
import Input from '@/components/ui/Input';
import Select from '@/components/ui/Select';
import Textarea from '@/components/ui/Textarea';
import Button from '@/components/ui/Button';
import { SalaryAdvance } from '@/types';
import { ADVANCE_METHODS_LIST } from '@/lib/constants';
import type { StructureEmployeeOption } from './SalaryStructureForm';

interface AdvanceFormProps {
  initial?: Partial<SalaryAdvance> | null;
  employees: StructureEmployeeOption[];
  defaultDate?: string;
  onSubmit: (data: Record<string, unknown>) => Promise<void>;
  onCancel: () => void;
}

const todayISO = () => new Date().toISOString().slice(0, 10);

export default function AdvanceForm({
  initial,
  employees,
  defaultDate,
  onSubmit,
  onCancel,
}: AdvanceFormProps) {
  const [form, setForm] = useState({
    employee: initial?.employee ? String(initial.employee) : '',
    date: initial?.date || defaultDate || todayISO(),
    amount: initial?.amount != null ? String(initial.amount) : '',
    method: initial?.method || 'CASH',
    reason: initial?.reason || '',
    notes: initial?.notes || '',
    approve: !initial?.id,
  });
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(false);

  const set = (key: string, value: string | boolean) =>
    setForm((f) => ({ ...f, [key]: value }));

  const validate = () => {
    const e: Record<string, string> = {};
    if (!form.employee) e.employee = 'الموظف مطلوب';
    if (!form.date) e.date = 'التاريخ مطلوب';
    if (!form.amount || Number(form.amount) <= 0)
      e.amount = 'المبلغ مطلوب ويجب أن يكون أكبر من صفر';
    if (initial?.id && initial.employee !== Number(form.employee))
      e.employee = 'لا يمكن تغيير الموظف بعد إنشاء السلفة';
    setErrors(e);
    return Object.keys(e).length === 0;
  };

  const handleSubmit = async (ev: React.FormEvent) => {
    ev.preventDefault();
    if (!validate()) return;
    setLoading(true);
    try {
      const payload: Record<string, unknown> = {
        employee: Number(form.employee),
        date: form.date,
        amount: Number(form.amount),
        method: form.method,
        reason: form.reason,
        notes: form.notes,
      };
      if (form.approve) payload.approve = true;
      await onSubmit(payload);
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

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <Input
          label="التاريخ"
          type="date"
          value={form.date}
          onChange={(e) => set('date', e.target.value)}
          error={errors.date}
        />
        <Input
          label="المبلغ"
          type="number"
          step="0.01"
          min="0"
          value={form.amount}
          onChange={(e) => set('amount', e.target.value)}
          error={errors.amount}
        />
        <Select
          label="طريقة الصرف"
          value={form.method}
          onChange={(e) => set('method', e.target.value)}
          options={ADVANCE_METHODS_LIST.map((m) => ({ value: m.value, label: m.label }))}
        />
      </div>

      <Input
        label="السبب"
        value={form.reason}
        onChange={(e) => set('reason', e.target.value)}
        placeholder="سبب طلب السلفة"
      />

      <Textarea
        label="ملاحظات"
        value={form.notes}
        onChange={(e) => set('notes', e.target.value)}
        rows={2}
      />

      <label className="flex items-center gap-2">
        <input
          type="checkbox"
          checked={form.approve}
          onChange={(e) => set('approve', e.target.checked)}
          className="w-4 h-4 rounded border-sand-300 text-brand-600"
        />
        <span className="text-sm text-neutral-700">اعتماد السلفة مباشرة</span>
      </label>

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
