'use client';

import { useState } from 'react';
import Input from '@/components/ui/Input';
import Select from '@/components/ui/Select';
import Button from '@/components/ui/Button';
import { CreateLedgerEntry, SupplierEntryType } from '@/types';
import { todayISO } from '@/lib/date';

const TYPE_OPTIONS = [
  { value: 'adjustment', label: 'تسوية' },
  { value: 'opening', label: 'رصيد افتتاحي' },
];

const DIRECTION_OPTIONS = [
  { value: 'increase', label: 'زيادة' },
  { value: 'decrease', label: 'نقصان' },
];

interface AdjustmentFormProps {
  onSubmit: (data: CreateLedgerEntry) => Promise<void>;
  onCancel: () => void;
  defaultType?: SupplierEntryType;
}

export default function AdjustmentForm({ onSubmit, onCancel, defaultType = 'adjustment' }: AdjustmentFormProps) {
  const [type, setType] = useState<SupplierEntryType>(defaultType === 'opening' ? 'opening' : 'adjustment');
  const [direction, setDirection] = useState<'increase' | 'decrease'>('increase');
  const [form, setForm] = useState({ date: todayISO(), amount: '', description: '' });
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(false);

  const validate = () => {
    const e: Record<string, string> = {};
    if (!form.date) e.date = 'التاريخ مطلوب';
    if (!form.amount || Number(form.amount) <= 0) e.amount = 'أدخل مبلغًا صحيحًا';
    setErrors(e);
    return Object.keys(e).length === 0;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!validate()) return;
    const signed = direction === 'decrease' ? -Number(form.amount) : Number(form.amount);
    const payload: CreateLedgerEntry = {
      entry_type: type,
      date: form.date,
      amount: signed,
      description: form.description.trim() || undefined,
    };
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
        <Select
          label="النوع"
          value={type}
          onChange={(e) => setType(e.target.value as SupplierEntryType)}
          options={TYPE_OPTIONS}
        />
        <Select
          label="الجهة"
          value={direction}
          onChange={(e) => setDirection(e.target.value as 'increase' | 'decrease')}
          options={DIRECTION_OPTIONS}
        />
      </div>
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
      <Input
        label="البيان"
        value={form.description}
        onChange={(e) => setForm({ ...form, description: e.target.value })}
        placeholder="سبب التسوية"
      />
      <div className="flex justify-start gap-3 pt-2">
        <Button type="submit" loading={loading}>
          {type === 'opening' ? 'حفظ الرصيد الافتتاحي' : 'حفظ التسوية'}
        </Button>
        <Button type="button" variant="secondary" onClick={onCancel}>إلغاء</Button>
      </div>
    </form>
  );
}