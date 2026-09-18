'use client';

import { useState, useEffect } from 'react';
import Input from '@/components/ui/Input';
import Textarea from '@/components/ui/Textarea';
import Select from '@/components/ui/Select';
import Button from '@/components/ui/Button';
import { Branch, Customer } from '@/types';
import { listBranches } from '@/services/branches';

interface CustomerFormProps {
  initial?: Partial<Customer>;
  defaultBranch?: number | null;
  onSubmit: (data: Partial<Customer>) => Promise<void>;
  onCancel: () => void;
}

export default function CustomerForm({ initial, defaultBranch, onSubmit, onCancel }: CustomerFormProps) {
  const [form, setForm] = useState({
    name: initial?.name || '',
    phone: initial?.phone || '',
    email: initial?.email || '',
    address: initial?.address || '',
    notes: initial?.notes || '',
    branch: initial?.branch ?? defaultBranch ?? '',
  });
  const [branches, setBranches] = useState<Branch[]>([]);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    let cancelled = false;
    listBranches({ page_size: 200 })
      .then((res) => { if (!cancelled) setBranches(res.results); })
      .catch(() => {});
    return () => { cancelled = true; };
  }, []);

  useEffect(() => {
    if (initial?.id) {
      setForm({
        name: initial.name || '',
        phone: initial.phone || '',
        email: initial.email || '',
        address: initial.address || '',
        notes: initial.notes || '',
        branch: initial.branch ?? '',
      });
    }
  }, [initial?.id]);

  const validate = () => {
    const e: Record<string, string> = {};
    if (!form.name.trim()) e.name = 'اسم الزبون مطلوب';
    setErrors(e);
    return Object.keys(e).length === 0;
  };

  const submit = async (ev: React.FormEvent) => {
    ev.preventDefault();
    if (!validate()) return;
    setLoading(true);
    try {
      await onSubmit({
        name: form.name.trim(),
        phone: form.phone.trim() || null,
        email: form.email.trim(),
        address: form.address.trim(),
        notes: form.notes,
        branch: form.branch ? Number(form.branch) : null,
      });
    } finally {
      setLoading(false);
    }
  };

  return (
    <form onSubmit={submit} className="space-y-4">
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <Input
          label="اسم الزبون"
          value={form.name}
          onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
          error={errors.name}
          placeholder="اسم الزبون"
        />
        <Input
          label="رقم الهاتف"
          value={form.phone}
          onChange={(e) => setForm((f) => ({ ...f, phone: e.target.value }))}
          placeholder="رقم الهاتف"
          dir="ltr"
        />
      </div>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <Input
          label="البريد الإلكتروني"
          value={form.email}
          onChange={(e) => setForm((f) => ({ ...f, email: e.target.value }))}
          placeholder="البريد الإلكتروني"
          type="email"
        />
        <Select
          label="الفرع"
          value={form.branch}
          onChange={(e) => setForm((f) => ({ ...f, branch: e.target.value }))}
          placeholder="بدون فرع"
          options={branches.map((b) => ({ value: b.id, label: b.name }))}
        />
      </div>
      <Input
        label="العنوان"
        value={form.address}
        onChange={(e) => setForm((f) => ({ ...f, address: e.target.value }))}
        placeholder="العنوان"
      />
      <Textarea
        label="ملاحظات"
        value={form.notes}
        onChange={(e) => setForm((f) => ({ ...f, notes: e.target.value }))}
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