'use client';

import { useState, useEffect } from 'react';
import Input from '@/components/ui/Input';
import Select from '@/components/ui/Select';
import Textarea from '@/components/ui/Textarea';
import Button from '@/components/ui/Button';
import { Expense, Branch, ExpenseCategory, PaymentMethod } from '@/types';
import { PAYMENT_METHODS } from '@/lib/constants';

interface ExpenseFormProps {
  initial?: Partial<Expense>;
  branches: Branch[];
  categories: ExpenseCategory[];
  onSubmit: (data: Partial<Expense>) => Promise<void>;
  onCancel: () => void;
}

export default function ExpenseForm({ initial, branches, categories, onSubmit, onCancel }: ExpenseFormProps) {
  const [form, setForm] = useState({
    date: initial?.date || new Date().toISOString().slice(0, 10),
    branch: initial?.branch ? String(initial.branch) : '',
    category: initial?.category ? String(initial.category) : '',
    amount: initial?.amount ? String(initial.amount) : '',
    payment_method: (initial?.payment_method || 'cash') as PaymentMethod,
    description: initial?.description || '',
    notes: initial?.notes || '',
  });
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (initial) {
      setForm({
        date: initial.date || new Date().toISOString().slice(0, 10),
        branch: initial.branch ? String(initial.branch) : '',
        category: initial.category ? String(initial.category) : '',
        amount: initial.amount ? String(initial.amount) : '',
        payment_method: (initial.payment_method || 'cash') as PaymentMethod,
        description: initial.description || '',
        notes: initial.notes || '',
      });
    }
  }, [initial]);

  const validate = () => {
    const e: Record<string, string> = {};
    if (!form.branch) e.branch = 'الفرع مطلوب';
    if (!form.category) e.category = 'نوع المصروف مطلوب';
    if (!form.amount || parseFloat(form.amount) <= 0) e.amount = 'المبلغ مطلوب ويجب أن يكون أكبر من صفر';
    setErrors(e);
    return Object.keys(e).length === 0;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!validate()) return;
    setLoading(true);
    try {
      await onSubmit({
        date: form.date,
        branch: Number(form.branch),
        category: Number(form.category),
        amount: parseFloat(form.amount),
        payment_method: form.payment_method,
        description: form.description,
        notes: form.notes,
      });
    } finally {
      setLoading(false);
    }
  };

  const set = (key: string, val: string) => setForm((f) => ({ ...f, [key]: val }));

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
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
      </div>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <Select
          label="نوع المصروف"
          value={form.category}
          onChange={(e) => set('category', e.target.value)}
          options={categories.map((c) => ({ value: c.id, label: c.name }))}
          placeholder="اختر النوع"
          error={errors.category}
        />
        <Select
          label="طريقة الدفع"
          value={form.payment_method}
          onChange={(e) => set('payment_method', e.target.value as PaymentMethod)}
          options={PAYMENT_METHODS.map((m) => ({ value: m.value, label: m.label }))}
        />
      </div>
      <Input
        label="المبلغ"
        type="number"
        value={form.amount}
        onChange={(e) => set('amount', e.target.value)}
        error={errors.amount}
        placeholder=""
        min="0"
        step="0.01"
      />
      <Input
        label="الوصف"
        value={form.description}
        onChange={(e) => set('description', e.target.value)}
        placeholder="وصف المصروف"
      />
      <Textarea
        label="ملاحظات"
        value={form.notes}
        onChange={(e) => set('notes', e.target.value)}
        placeholder="ملاحظات إضافية..."
        rows={2}
      />
      <div className="flex justify-start gap-3 pt-2">
        <Button type="submit" loading={loading}>
          {initial?.id ? 'تحديث' : 'تسجيل'}
        </Button>
        <Button type="button" variant="secondary" onClick={onCancel}>
          إلغاء
        </Button>
      </div>
    </form>
  );
}
