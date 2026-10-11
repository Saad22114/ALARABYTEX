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

const RECURRING_FREQUENCIES = [
  { value: 'monthly', label: 'شهري' },
  { value: 'weekly', label: 'أسبوعي' },
];

export default function ExpenseForm({ initial, branches, categories, onSubmit, onCancel }: ExpenseFormProps) {
  const [form, setForm] = useState({
    date: initial?.date || new Date().toISOString().slice(0, 10),
    branch: initial?.branch ? String(initial.branch) : '',
    category: initial?.category ? String(initial.category) : '',
    amount: initial?.amount ? String(initial.amount) : '',
    payment_method: (initial?.payment_method || 'cash') as PaymentMethod,
    description: initial?.description || '',
    notes: initial?.notes || '',
    is_recurring: initial?.id ? Boolean(initial.is_recurring) : false,
    recur_frequency: (initial?.recur_frequency || 'monthly') as string,
  });
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(false);
  const [receiptImage, setReceiptImage] = useState('');
  const [removeReceiptImage, setRemoveReceiptImage] = useState(false);
  const [receiptError, setReceiptError] = useState('');

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
        is_recurring: Boolean(initial.is_recurring),
        recur_frequency: (initial.recur_frequency || 'monthly') as string,
      });
      setReceiptImage('');
      setRemoveReceiptImage(false);
      setReceiptError('');
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
      const payload: Partial<Expense> = {
        date: form.date,
        branch: Number(form.branch),
        category: Number(form.category),
        amount: parseFloat(form.amount),
        payment_method: form.payment_method,
        description: form.description,
        notes: form.notes,
        is_recurring: form.is_recurring,
        recur_frequency: form.is_recurring ? form.recur_frequency : 'monthly',
      };
      if (receiptImage) payload.receipt_image = receiptImage;
      else if (removeReceiptImage) payload.receipt_image = '';
      await onSubmit(payload);
    } finally {
      setLoading(false);
    }
  };

  const set = (key: string, val: string) => setForm((f) => ({ ...f, [key]: val }));
  const toggleRecurring = () => setForm((f) => ({ ...f, is_recurring: !f.is_recurring }));

  const chooseReceipt = (file?: File) => {
    setReceiptError('');
    if (!file) return;
    if (!['image/jpeg', 'image/png', 'image/webp'].includes(file.type)) {
      setReceiptError('اختر صورة بصيغة JPG أو PNG أو WebP');
      return;
    }
    if (file.size > 5 * 1024 * 1024) {
      setReceiptError('حجم الصورة يجب ألا يتجاوز 5 ميجابايت');
      return;
    }
    const reader = new FileReader();
    reader.onload = () => {
      if (typeof reader.result === 'string') {
        setReceiptImage(reader.result);
        setRemoveReceiptImage(false);
      } else setReceiptError('تعذرت قراءة الصورة');
    };
    reader.onerror = () => setReceiptError('تعذرت قراءة الصورة');
    reader.readAsDataURL(file);
  };

  // النسخة المتولدة من مصروف متكرر (لقطة) — لا تعرض عناصر التكرار عند تعديلها.
  const isSnapshot = Boolean(initial?.origin);

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
      {!isSnapshot && (
        <div className="rounded-xl border border-sand-200 dark:border-neutral-800 p-3 space-y-3">
          <label className="flex items-center gap-2 cursor-pointer select-none">
            <input
              type="checkbox"
              checked={form.is_recurring}
              onChange={toggleRecurring}
              className="h-4 w-4 rounded border-sand-300 text-brand-600 accent-brand-600"
            />
            <span className="text-sm font-medium">مصروف ثابت — يتجدد تلقائياً في الشهور التالية</span>
          </label>
          {form.is_recurring && (
            <>
              <Select
                label="دورة التكرار"
                value={form.recur_frequency}
                onChange={(e) => set('recur_frequency', e.target.value)}
                options={RECURRING_FREQUENCIES}
              />
              <p className="text-xs text-neutral-500">تُنشأ نسخة تلقائية في كل موعد قادم (أول نفس اليوم من الشهر/الأسبوع التالي)</p>
            </>
          )}
        </div>
      )}
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
      <div className="rounded-xl border border-sand-200 p-3 space-y-3">
        <label className="block text-sm font-medium text-neutral-700">صورة فاتورة المصروف (اختياري)</label>
        <input
          type="file"
          accept="image/jpeg,image/png,image/webp"
          capture="environment"
          onChange={(event) => chooseReceipt(event.target.files?.[0])}
          className="block w-full text-sm text-neutral-600 file:ml-3 file:rounded-lg file:border-0 file:bg-brand-50 file:px-3 file:py-2 file:font-medium file:text-brand-700"
        />
        <p className="text-xs text-neutral-500">يمكنك فتح الكاميرا أو اختيار صورة من الجهاز. الحد الأقصى 5 ميجابايت.</p>
        {initial?.has_receipt_image && !removeReceiptImage && !receiptImage && (
          <div className="flex items-center justify-between gap-3 rounded-lg bg-sand-50 p-2 text-sm">
            <span className="text-neutral-600">توجد صورة فاتورة محفوظة لهذا المصروف.</span>
            <button type="button" onClick={() => setRemoveReceiptImage(true)} className="text-red-600 hover:underline">إزالة</button>
          </div>
        )}
        {receiptImage && (
          <div className="flex items-start gap-3">
            <img src={receiptImage} alt="معاينة صورة الفاتورة" className="max-h-40 max-w-48 rounded-lg border border-sand-200 object-contain" />
            <button type="button" onClick={() => setReceiptImage('')} className="text-sm text-red-600 hover:underline">إزالة الصورة المختارة</button>
          </div>
        )}
        {removeReceiptImage && <p className="text-xs text-amber-700">ستُحذف الصورة المحفوظة عند حفظ التعديل.</p>}
        {receiptError && <p className="text-xs text-red-600">{receiptError}</p>}
      </div>
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
