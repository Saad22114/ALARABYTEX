'use client';

import { useState, useEffect } from 'react';
import Input from '@/components/ui/Input';
import Textarea from '@/components/ui/Textarea';
import Button from '@/components/ui/Button';
import { Branch } from '@/types';

interface BranchFormProps {
  initial?: Partial<Branch>;
  onSubmit: (data: Partial<Branch>) => Promise<void>;
  onCancel: () => void;
}

export default function BranchForm({ initial, onSubmit, onCancel }: BranchFormProps) {
  const [form, setForm] = useState({
    name: initial?.name || '',
    code: initial?.code || '',
    phone: initial?.phone || '',
    address: initial?.address || '',
    city: initial?.city || '',
    notes: initial?.notes || '',
    is_active: initial?.is_active ?? true,
  });
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (initial) {
      setForm({
        name: initial.name || '',
        code: initial.code || '',
        phone: initial.phone || '',
        address: initial.address || '',
        city: initial.city || '',
        notes: initial.notes || '',
        is_active: initial.is_active ?? true,
      });
    }
  }, [initial]);

  const validate = () => {
    const e: Record<string, string> = {};
    if (!form.name.trim()) e.name = 'اسم الفرع مطلوب';
    if (!form.code.trim()) e.code = 'كود الفرع مطلوب';
    setErrors(e);
    return Object.keys(e).length === 0;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!validate()) return;
    setLoading(true);
    try {
      await onSubmit(form);
    } finally {
      setLoading(false);
    }
  };

  const set = (key: string, val: string | boolean) => setForm((f) => ({ ...f, [key]: val }));

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <Input
          label="اسم الفرع"
          value={form.name}
          onChange={(e) => set('name', e.target.value)}
          error={errors.name}
          placeholder="اسم الفرع"
        />
        <Input
          label="كود الفرع"
          value={form.code}
          onChange={(e) => set('code', e.target.value)}
          error={errors.code}
          placeholder="مثال: BR-001"
        />
      </div>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <Input
          label="الهاتف"
          value={form.phone}
          onChange={(e) => set('phone', e.target.value)}
          placeholder="رقم الهاتف"
        />
        <Input
          label="المدينة"
          value={form.city}
          onChange={(e) => set('city', e.target.value)}
          placeholder="المدينة"
        />
      </div>
      <Input
        label="العنوان"
        value={form.address}
        onChange={(e) => set('address', e.target.value)}
        placeholder="العنوان التفصيلي"
      />
      <Textarea
        label="ملاحظات"
        value={form.notes}
        onChange={(e) => set('notes', e.target.value)}
        placeholder="ملاحظات إضافية..."
        rows={3}
      />
      <label className="flex items-center gap-3 cursor-pointer">
        <input
          type="checkbox"
          checked={form.is_active}
          onChange={(e) => set('is_active', e.target.checked)}
          className="w-4 h-4 accent-brand-600"
        />
        <span className="text-sm font-medium text-neutral-700">نشط (يعمل)</span>
      </label>
      <div className="flex justify-start gap-3 pt-2">
        <Button type="submit" loading={loading}>
          {initial?.id ? 'تحديث' : 'إضافة'}
        </Button>
        <Button type="button" variant="secondary" onClick={onCancel}>
          إلغاء
        </Button>
      </div>
    </form>
  );
}
