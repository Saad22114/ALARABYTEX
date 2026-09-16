'use client';

import { useState } from 'react';
import Input from '@/components/ui/Input';
import Select from '@/components/ui/Select';
import Button from '@/components/ui/Button';
import { CreateLedgerEntry, SupplierPayMethod } from '@/types';
import { todayISO } from '@/lib/date';

const PAYMENT_METHOD_OPTIONS = [
  { value: 'cash', label: 'كاش' },
  { value: 'bank_transfer', label: 'تحويل بنكي' },
];

interface PaymentFormProps {
  onSubmit: (data: CreateLedgerEntry) => Promise<void>;
  onCancel: () => void;
}

export default function PaymentForm({ onSubmit, onCancel }: PaymentFormProps) {
  const [form, setForm] = useState({ date: todayISO(), amount: '', notes: '' });
  const [method, setMethod] = useState<SupplierPayMethod>('cash');
  const [bankReference, setBankReference] = useState('');
  const [receiverName, setReceiverName] = useState('');
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(false);

  const validate = () => {
    const e: Record<string, string> = {};
    if (!form.date) e.date = 'التاريخ مطلوب';
    if (!form.amount || Number(form.amount) <= 0) e.amount = 'أدخل مبلغًا صحيحًا';
    if (method === 'bank_transfer' && !bankReference.trim()) e.bank_reference = 'رقم الحوالة مطلوب';
    setErrors(e);
    return Object.keys(e).length === 0;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!validate()) return;
    const payload: CreateLedgerEntry = {
      entry_type: 'payment',
      date: form.date,
      amount: Number(form.amount),
      payment_method: method,
      notes: form.notes.trim() || undefined,
    };
    if (method === 'bank_transfer') payload.bank_reference = bankReference.trim() || undefined;
    if (method === 'cash' && receiverName.trim()) payload.receiver_name = receiverName.trim();
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
      <Select
        label="طريقة الدفع"
        value={method}
        onChange={(e) => setMethod(e.target.value as SupplierPayMethod)}
        options={PAYMENT_METHOD_OPTIONS}
      />
      {method === 'bank_transfer' && (
        <Input
          label="رقم الحوالة"
          value={bankReference}
          onChange={(e) => setBankReference(e.target.value)}
          error={errors.bank_reference}
          placeholder="رقم الحوالة البنكية"
        />
      )}
      {method === 'cash' && (
        <Input
          label="اسم المستلم"
          value={receiverName}
          onChange={(e) => setReceiverName(e.target.value)}
          placeholder="اسم من يستلم المبلغ"
        />
      )}
      <Input
        label="ملاحظات"
        value={form.notes}
        onChange={(e) => setForm({ ...form, notes: e.target.value })}
        placeholder="ملاحظات إضافية..."
      />
      <div className="flex justify-start gap-3 pt-2">
        <Button type="submit" loading={loading}>تسجيل الدفعة</Button>
        <Button type="button" variant="secondary" onClick={onCancel}>إلغاء</Button>
      </div>
    </form>
  );
}