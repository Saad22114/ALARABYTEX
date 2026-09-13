'use client';

import { useState, useEffect } from 'react';
import Input from '@/components/ui/Input';
import Textarea from '@/components/ui/Textarea';
import Button from '@/components/ui/Button';
import { Supplier } from '@/types';

interface SupplierFormProps {
  initial?: Partial<Supplier>;
  onSubmit: (data: Partial<Supplier>) => Promise<void>;
  onCancel: () => void;
}

export default function SupplierForm({ initial, onSubmit, onCancel }: SupplierFormProps) {
  const [form, setForm] = useState({
    name: initial?.name || '',
    company_name: initial?.company_name || '',
    phone: initial?.phone || '',
    email: initial?.email || '',
    address: initial?.address || '',
    city: initial?.city || '',
    country: initial?.country || '',
    tax_number: initial?.tax_number || '',
    notes: initial?.notes || '',
  });
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (initial) {
      setForm({
        name: initial.name || '',
        company_name: initial.company_name || '',
        phone: initial.phone || '',
        email: initial.email || '',
        address: initial.address || '',
        city: initial.city || '',
        country: initial.country || '',
        tax_number: initial.tax_number || '',
        notes: initial.notes || '',
      });
    }
  }, [initial]);

  const validate = () => {
    const e: Record<string, string> = {};
    if (!form.name.trim()) e.name = 'اسم المورد مطلوب';
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

  const set = (key: string, val: string) => setForm((f) => ({ ...f, [key]: val }));

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <Input
          label="اسم المورد"
          value={form.name}
          onChange={(e) => set('name', e.target.value)}
          error={errors.name}
          placeholder="اسم المورد"
        />
        <Input
          label="اسم الشركة"
          value={form.company_name}
          onChange={(e) => set('company_name', e.target.value)}
          placeholder="اسم الشركة"
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
          label="البريد الإلكتروني"
          value={form.email}
          onChange={(e) => set('email', e.target.value)}
          placeholder="البريد الإلكتروني"
          type="email"
        />
      </div>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <Input
          label="المدينة"
          value={form.city}
          onChange={(e) => set('city', e.target.value)}
          placeholder="المدينة"
        />
        <Input
          label="الدولة"
          value={form.country}
          onChange={(e) => set('country', e.target.value)}
          placeholder="الدولة"
        />
      </div>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <Input
          label="العنوان"
          value={form.address}
          onChange={(e) => set('address', e.target.value)}
          placeholder="العنوان التفصيلي"
        />
        <Input
          label="الرقم الضريبي"
          value={form.tax_number}
          onChange={(e) => set('tax_number', e.target.value)}
          placeholder="الرقم الضريبي"
        />
      </div>
      <Textarea
        label="ملاحظات"
        value={form.notes}
        onChange={(e) => set('notes', e.target.value)}
        placeholder="ملاحظات إضافية..."
        rows={3}
      />
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
