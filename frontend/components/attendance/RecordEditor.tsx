'use client';

import { useEffect, useState } from 'react';
import Modal from '@/components/ui/Modal';
import Input from '@/components/ui/Input';
import Select from '@/components/ui/Select';
import Textarea from '@/components/ui/Textarea';
import Button from '@/components/ui/Button';
import { useToast } from '@/components/ui/Toast';
import { updateAttendance } from '@/services/attendance';
import type { AttendanceExcuse, AttendanceRecord } from '@/types';
import { EXCUSE_OPTIONS, fromDateTimeLocal, minutesLabel, toDateTimeLocal } from '@/lib/attendance';

interface RecordEditorProps {
  record: AttendanceRecord | null;
  onClose: () => void;
  onSaved: () => void;
}

/**
 * تعديل سطر حضور واحد.
 *
 * أربعةُ حقول فقط: الدخول، الخروج، التبرير، ملاحظة. والبقية مُشتقّة ولا
 * تُكتب —Minutes العمل والتأخير والانصراف المبكر والإضافي والحالة.
 * لو فُتحت لغير المُبرَّر لظهر له ما يكتبه، فيصير الحقلُ يُكتب مرّتين:
 * مرّةً بحسب السياسة، ومرّةً بحسب من يكتب، وتضيع الحقيقةُ في المرّتين.
 *
 * والحقولُ الأربعة تُرسَل كلُّها عند الحفظ لا المتغيّر منها فقط: تفريغُ
 * وقت الخروج تغييرٌ حقيقي، وإرساله «فارغاً» يُبقيه على حاله فيتحرّك
 * الموظف في الجدول ولا يتغيّر شيءٌ عند الخادم.
 */
export default function RecordEditor({ record, onClose, onSaved }: RecordEditorProps) {
  const { toast } = useToast();
  const [login, setLogin] = useState('');
  const [logout, setLogout] = useState('');
  const [excuse, setExcuse] = useState<AttendanceExcuse>('none');
  const [note, setNote] = useState('');
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!record) return;
    setLogin(toDateTimeLocal(record.login_at));
    setLogout(toDateTimeLocal(record.logout_at));
    setExcuse(record.excuse || 'none');
    setNote(record.note || '');
  }, [record]);

  const save = async () => {
    if (!record) return;
    setSaving(true);
    try {
      await updateAttendance(record.id, {
        login_at: fromDateTimeLocal(login),
        logout_at: fromDateTimeLocal(logout),
        excuse,
        note,
      });
      toast('success', 'حُفظ السجل وأُعيد احتسابه');
      onSaved();
      onClose();
    } catch (err: any) {
      toast('error', err.message);
    } finally {
      setSaving(false);
    }
  };

  return (
    <Modal
      open={Boolean(record)}
      onClose={onClose}
      title={record ? `سجل ${record.employee.name} — ${record.date}` : ''}
      footer={
        <div className="flex gap-2 justify-end">
          <Button variant="secondary" onClick={onClose} disabled={saving}>
            إلغاء
          </Button>
          <Button onClick={save} loading={saving}>
            حفظ
          </Button>
        </div>
      }
    >
      {record && (
        <div className="space-y-4">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <Input
              label="الدخول"
              type="datetime-local"
              value={login}
              onChange={(e) => setLogin(e.target.value)}
            />
            <Input
              label="الخروج"
              type="datetime-local"
              value={logout}
              onChange={(e) => setLogout(e.target.value)}
            />
          </div>

          <Select
            label="التبرير"
            value={excuse}
            onChange={(e) => setExcuse(e.target.value as AttendanceExcuse)}
            options={EXCUSE_OPTIONS}
          />

          <Textarea
            label="ملاحظة"
            rows={3}
            value={note}
            onChange={(e) => setNote(e.target.value)}
            placeholder="ما جرى لهذا اليوم، أو لماذا عُدّل السجل"
          />

          {record.worked_minutes !== null && (
            <p className="text-xs text-neutral-500 tabular-nums">
              العمل المحسوب: {minutesLabel(record.worked_minutes)} — يُعاد احتسابه بعد
              الحفظ من الوقتين والسياسة، لا من هذه الشاشة.
            </p>
          )}
        </div>
      )}
    </Modal>
  );
}