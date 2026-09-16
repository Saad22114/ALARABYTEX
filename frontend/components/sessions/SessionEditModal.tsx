'use client';

import { useState, useEffect } from 'react';
import Modal from '@/components/ui/Modal';
import Button from '@/components/ui/Button';
import Select from '@/components/ui/Select';
import Textarea from '@/components/ui/Textarea';
import Badge from '@/components/ui/Badge';
import { updateSaleSession } from '@/services/sessions';
import { useToast } from '@/components/ui/Toast';
import { SaleSession, Employee, Branch } from '@/types';

interface Props {
  open: boolean;
  session: SaleSession | null;
  employees: Employee[];
  branches: Branch[];
  onClose: () => void;
  onSaved: () => void;
}

export default function SessionEditModal({ open, session, employees, branches, onClose, onSaved }: Props) {
  const { toast } = useToast();
  const [employee, setEmployee] = useState<number | null>(null);
  const [branch, setBranch] = useState<number | null>(null);
  const [notes, setNotes] = useState('');
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (open && session) {
      setEmployee(session.employee);
      setBranch(session.branch);
      setNotes(session.notes || '');
    }
  }, [open, session]);

  const handleSave = async () => {
    if (!session) return;
    if (!employee) {
      toast('error', 'اختر الموظف');
      return;
    }
    setSaving(true);
    try {
      await updateSaleSession(session.id, { employee, notes });
      toast('success', 'تم تحديث الوردية بنجاح');
      onClose();
      onSaved();
    } catch (err: any) {
      toast('error', err.message);
    } finally {
      setSaving(false);
    }
  };

  const closed = session?.status === 'closed';

  return (
    <Modal open={open} onClose={onClose} title="تعديل الوردية" maxWidth="max-w-xl">
      {session && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="font-semibold text-neutral-800">{session.employee_name}</p>
              <p className="text-sm text-neutral-500">{session.branch_name}</p>
            </div>
            <Badge variant={closed ? 'neutral' : 'success'}>{session.status_label}</Badge>
          </div>

          <Select
            label="الموظف"
            value={employee ?? ''}
            onChange={(e) => setEmployee(Number(e.target.value))}
            options={employees.map((emp) => ({ value: emp.id, label: `${emp.name} — ${emp.branch_name}` }))}
            placeholder="اختر الموظف"
          />

          <Select
            label="الفرع"
            value={branch ?? ''}
            disabled={closed}
            onChange={(e) => setBranch(Number(e.target.value))}
            options={branches.map((b) => ({ value: b.id, label: b.name }))}
            placeholder="اختر الفرع"
          />
          {closed && (
            <p className="text-xs text-neutral-400 -mt-2 text-left">
              لا يمكن تغيير فرع وردية مغلقة لأن المبيعات سبق تسجيلها باسم هذا الفرع.
            </p>
          )}

          <Textarea
            label="ملاحظات"
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            placeholder="ملاحظات عن الوردية..."
            rows={3}
          />

          <div className="flex items-center justify-end gap-3 pt-2">
            <Button variant="secondary" onClick={onClose}>إلغاء</Button>
            <Button loading={saving} onClick={handleSave}>حفظ التعديلات</Button>
          </div>
        </div>
      )}
    </Modal>
  );
}