'use client';

import { useState, useEffect, useMemo } from 'react';
import Modal from '@/components/ui/Modal';
import Button from '@/components/ui/Button';
import Select from '@/components/ui/Select';
import Input from '@/components/ui/Input';
import Textarea from '@/components/ui/Textarea';
import { createManualSession } from '@/services/sessions';
import { useToast } from '@/components/ui/Toast';
import { formatCurrency } from '@/lib/format';
import { SaleSession, Employee } from '@/types';

interface Props {
  open: boolean;
  employees: Employee[];
  onClose: () => void;
  onSaved: (session: SaleSession) => void;
}

function todayStr() {
  const d = new Date();
  const m = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  return `${d.getFullYear()}-${m}-${day}`;
}

export default function ManualSessionModal({ open, employees, onClose, onSaved }: Props) {
  const { toast } = useToast();
  const [employee, setEmployee] = useState<number | ''>('');
  const [date, setDate] = useState(todayStr);
  const [cash, setCash] = useState('');
  const [transfer, setTransfer] = useState('');
  const [card, setCard] = useState('');
  const [notes, setNotes] = useState('');
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (open) {
      setEmployee('');
      setDate(todayStr());
      setCash('');
      setTransfer('');
      setCard('');
      setNotes('');
    }
  }, [open]);

  const selected = useMemo(
    () => employees.find((e) => e.id === employee) || null,
    [employees, employee]
  );

  const total =
    (parseFloat(cash) || 0) + (parseFloat(transfer) || 0) + (parseFloat(card) || 0);

  const handleSave = async () => {
    if (!employee) {
      toast('error', 'اختر الموظف');
      return;
    }
    if (!date) {
      toast('error', 'حدّد التاريخ');
      return;
    }
    if (total <= 0) {
      toast('error', 'أدخل مبلغاً واحداً على الأقل');
      return;
    }
    setSaving(true);
    try {
      const session = await createManualSession({
        employee: employee as number,
        date,
        cash: parseFloat(cash) || 0,
        transfer: parseFloat(transfer) || 0,
        card: parseFloat(card) || 0,
        notes,
      });
      toast('success', 'تم تسجيل الوردية الكاملة بنجاح');
      onClose();
      onSaved(session);
    } catch (err: any) {
      toast('error', err.message);
    } finally {
      setSaving(false);
    }
  };

  return (
    <Modal open={open} onClose={onClose} title="إضافة وردية كاملة (مجموع)" maxWidth="max-w-xl">
      <div className="space-y-4">
        <div className="flex items-start gap-3 rounded-xl border border-amber-200 bg-amber-50 p-3 text-sm text-amber-800">
          إدخال سريع بإجمالي الوردية فقط — بدون تفاصيل أصناف ولا خصم من المخزون.
        </div>

        <Select
          label="الموظف"
          value={employee}
          onChange={(e) => setEmployee(e.target.value ? Number(e.target.value) : '')}
          options={employees.map((emp) => ({ value: emp.id, label: `${emp.name} — ${emp.branch_name}` }))}
          placeholder="اختر الموظف"
        />

        <div className="flex items-center justify-between rounded-xl border border-sand-200 bg-sand-50/60 px-4 py-2.5 text-sm">
          <span className="text-neutral-500">الفرع</span>
          <span className="font-medium text-neutral-800">{selected?.branch_name || '—'}</span>
        </div>

        <Input label="التاريخ" type="date" value={date} onChange={(e) => setDate(e.target.value)} />

        <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
          <Input label="نقدي" type="number" inputMode="decimal" value={cash} onChange={(e) => setCash(e.target.value)} placeholder="0" />
          <Input label="تحويل" type="number" inputMode="decimal" value={transfer} onChange={(e) => setTransfer(e.target.value)} placeholder="0" />
          <Input label="ماكينة" type="number" inputMode="decimal" value={card} onChange={(e) => setCard(e.target.value)} placeholder="0" />
        </div>

        <div className="flex items-center justify-between rounded-xl border border-brand-200 bg-brand-50 px-4 py-2.5">
          <span className="text-sm font-medium text-brand-700">الإجمالي</span>
          <span className="text-lg font-bold tabular-nums text-brand-700">{formatCurrency(total)}</span>
        </div>

        <Textarea label="ملاحظات" value={notes} onChange={(e) => setNotes(e.target.value)} placeholder="ملاحظات عن الوردية..." rows={2} />

        <div className="flex items-center justify-end gap-3 pt-2">
          <Button variant="secondary" onClick={onClose}>إلغاء</Button>
          <Button loading={saving} onClick={handleSave}>تسجيل الوردية</Button>
        </div>
      </div>
    </Modal>
  );
}
