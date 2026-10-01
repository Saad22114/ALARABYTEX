'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import Card from '@/components/ui/Card';
import StatCard from '@/components/ui/StatCard';
import Spinner from '@/components/ui/Spinner';
import Badge from '@/components/ui/Badge';
import Input from '@/components/ui/Input';
import Button from '@/components/ui/Button';
import { useToast } from '@/components/ui/Toast';
import { CalendarCheck, Clock, DoorOpen, DoorClosed, UserCheck } from 'lucide-react';
import { getAttendancePolicy, getDaySheet } from '@/services/attendance';
import { todayISO } from '@/lib/date';
import { formatNumber } from '@/lib/format';
import { attainmentPercent, clockLabel, minutesLabel } from '@/lib/attendance';
import type { AttendanceDaySheet, AttendancePolicy, AttendanceRecord } from '@/types';
import AttendanceTable from './AttendanceTable';
import RecordEditor from './RecordEditor';

interface DailyTabProps {
  day: string;
  onDayChange: (day: string) => void;
}

/**
 * ورقة اليوم: صفٌّ لكل موظف نشط، حاضراً كان أو غائباً.
 *
 * الغياب حالةٌ في الجدول لا سطرٌ ناقص. ولو اقتصرت الورقة على «من له
 * سطر» لاختفى نصفُ الغائبين — والغيابُ هو ما Comes أولاً إلى هذه
 * الشاشة. فالورقة تُبنى من الموظفين النشطين، ويأتي السطرُ من سجلّه أو
 * يُصنع فارغاً معنوناً «غائب».
 */
export default function DailyTab({ day, onDayChange }: DailyTabProps) {
  const { toast } = useToast();
  const [sheet, setSheet] = useState<AttendanceDaySheet | null>(null);
  const [policy, setPolicy] = useState<AttendancePolicy | null>(null);
  const [loading, setLoading] = useState(true);
  const [editing, setEditing] = useState<AttendanceRecord | null>(null);
  const [reloadKey, setReloadKey] = useState(0);

  const load = useCallback(() => {
    setLoading(true);
    Promise.all([getDaySheet(day), getAttendancePolicy()])
      .then(([sheetData, policyData]) => {
        setSheet(sheetData);
        setPolicy(policyData);
      })
      .catch((err) => toast('error', err.message))
      .finally(() => setLoading(false));
  }, [day, toast]);

  useEffect(() => {
    load();
  }, [load, reloadKey]);

  const open = useMemo(
    () => (sheet?.rows || []).filter((r) => r.login_at && !r.logout_at),
    [sheet],
  );

  if (loading) {
    return (
      <div className="flex justify-center py-20">
        <Spinner size={32} />
      </div>
    );
  }

  const summary = sheet?.summary;
  const attainment = attainmentPercent(summary?.worked_minutes ?? 0, summary?.expected_minutes ?? 0);

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 className="text-lg font-bold text-neutral-800">ورقة اليوم</h2>
          <p className="text-sm text-neutral-500">
            كل موظفٍ نشط في سطرٍ واحد — الحاضر والمنسحب على حدّ سواء
          </p>
        </div>
        <div className="flex flex-wrap items-end gap-2">
          <Input
            label="اليوم"
            type="date"
            value={day}
            max={todayISO()}
            onChange={(e) => onDayChange(e.target.value || todayISO())}
          />
          <Button variant="secondary" size="md" onClick={() => onDayChange(todayISO())}>
            اليوم
          </Button>
        </div>
      </div>

      {sheet && !sheet.working_day && (
        <Card>
          <div className="flex items-start gap-3">
            <Badge variant="neutral">عطلة</Badge>
            <p className="text-sm text-neutral-600">
              هذا اليوم عطلةٌ في سياسة الحضور، فما فيه من سجلات لا يُحتسب غياباً ولا
              نقصاً في يوم العمل. من يعمل فيه يُسجَّل، ويظهر في الجدول.
            </p>
          </div>
        </Card>
      )}

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          icon={<UserCheck size={22} />}
          label="حضور"
          value={formatNumber(summary?.present ?? 0)}
          sub={`${formatNumber(summary?.absent ?? 0)} غائب من ${formatNumber(sheet?.rows.length ?? 0)}`}
        />
        <StatCard
          icon={<Clock size={22} />}
          iconBg="bg-amber-50 text-amber-600"
          label="داخل الدوام الآن"
          value={formatNumber(open.length)}
          sub={
            open.length
              ? `أقدمهم ${clockLabel(open[0].login_at)} — ${open[0].employee.name}`
              : 'لا أحد داخل الدوام'
          }
        />
        <StatCard
          icon={<CalendarCheck size={22} />}
          iconBg="bg-emerald-50 text-emerald-600"
          label="ساعات العمل"
          value={formatNumber(Math.round((summary?.worked_minutes ?? 0) / 60))}
          sub={`${attainment}% من المُتوقَّع`}
        />
        <StatCard
          icon={<DoorClosed size={22} />}
          iconBg="bg-red-50 text-red-600"
          label="تأخير وانصراف مبكر"
          value={`${formatNumber(summary?.late_count ?? 0)} / ${formatNumber(summary?.early_count ?? 0)}`}
          sub={`${minutesLabel(summary?.late_minutes ?? 0)} · ${minutesLabel(summary?.early_minutes ?? 0)}`}
        />
      </div>

      <Card
        title="سجل اليوم"
        action={
          open.length ? (
            <Badge variant="success">
              <span className="inline-flex items-center gap-1">
                <DoorOpen size={14} />
                {formatNumber(open.length)} لم يخرجوا بعد
              </span>
            </Badge>
          ) : null
        }
      >
        <AttendanceTable
          rows={sheet?.rows || []}
          policy={policy}
          onEdit={setEditing}
          emptyTitle="لا موظفين في هذا اليوم"
          emptyDescription="الورقة تُبنى من الموظفين النشطين، فخواءُها يعني لا موظفاً نشطاً"
        />
      </Card>

      <RecordEditor
        record={editing}
        onClose={() => setEditing(null)}
        onSaved={() => setReloadKey((k) => k + 1)}
      />
    </div>
  );
}