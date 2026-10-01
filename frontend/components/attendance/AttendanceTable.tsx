'use client';

import Table, { Th, Td, Tr } from '@/components/ui/Table';
import Badge from '@/components/ui/Badge';
import EmptyState from '@/components/ui/EmptyState';
import { Pencil } from 'lucide-react';
import type { AttendancePolicy, AttendanceRecord } from '@/types';
import {
  clockLabel,
  EXCUSE_LABEL,
  isOpen,
  minutesLabel,
  minutesToClock,
  shortfall,
  statusLabel,
  statusVariant,
  workedText,
} from '@/lib/attendance';

interface AttendanceTableProps {
  rows: AttendanceRecord[];
  policy: AttendancePolicy | null;
  /** عمود التاريخ: يظهر في السجلات، ويكفيه اليوم في ورقة اليوم. */
  showDate?: boolean;
  onEdit?: (record: AttendanceRecord) => void;
  emptyTitle: string;
  emptyDescription?: string;
}

/** خليةٌ واحدة بحدٍّّين: الرقم، وتفسيره underneath لمن أراده. */
function Measure({
  minutes,
  hint,
  tone,
}: {
  minutes: number;
  hint: string;
  tone?: 'warn' | 'good';
}) {
  if (!minutes) return <span className="text-neutral-400">—</span>;
  const color =
    tone === 'warn' ? 'text-amber-700' : tone === 'good' ? 'text-emerald-700' : 'text-neutral-700';
  return (
    <span>
      <span className={`tabular-nums ${color}`}>{minutesToClock(minutes)}</span>
      <span className="block text-[11px] text-neutral-400 tabular-nums">{hint}</span>
    </span>
  );
}

/**
 * جدول الحضور — واحدٌ لورقة اليوم وللسجلات.
 *
 * لُبّه واحدٌ لا يتكرّر: عمودُ العمل يقرأ «لم يخرج بعد» لا «0:00»، لأن
 * الصفرَ يعني أنه عمل صفرَ دقيقة، والفارغُ يعني أنه لم يُقَس بعد. ومن
 * يعرضهما سواءً يُظهر موظفاً حاضراً في الدوام منذ الفجر على أنه غائب —
 * وهي قسوةٌ تخصم من راتبه ولا يصحّحها أحد.
 */
export default function AttendanceTable({
  rows,
  policy,
  showDate = false,
  onEdit,
  emptyTitle,
  emptyDescription,
}: AttendanceTableProps) {
  if (rows.length === 0) {
    return <EmptyState title={emptyTitle} description={emptyDescription} />;
  }

  const workdayMinutes = policy?.workday_minutes ?? 480;

  return (
    <Table>
      <thead>
        <tr>
          <Th>الموظف</Th>
          {showDate && <Th>التاريخ</Th>}
          <Th>الدخول</Th>
          <Th>الخروج</Th>
          <Th>مدة العمل</Th>
          <Th>التأخير</Th>
          <Th>الخروج المبكر</Th>
          <Th>الإضافي</Th>
          <Th>الحالة</Th>
          <Th>التبرير</Th>
          {onEdit && (
            <Th>
              <span className="sr-only">تعديل</span>
            </Th>
          )}
        </tr>
      </thead>
      <tbody>
        {rows.map((row) => {
          const open = isOpen(row);
          const missing = shortfall(row.worked_minutes, workdayMinutes);
          return (
            <Tr key={row.id ?? `day-${row.employee.id}`} className={open ? 'bg-emerald-50/40' : ''}>
              <Td>
                <span className="font-medium text-neutral-800">{row.employee.name}</span>
                {row.employee.branch_name && (
                  <span className="block text-[11px] text-neutral-400">{row.employee.branch_name}</span>
                )}
              </Td>
              {showDate && <Td className="tabular-nums">{row.date}</Td>}
              <Td className="tabular-nums">{clockLabel(row.login_at) || <span className="text-neutral-400">—</span>}</Td>
              <Td className="tabular-nums">
                {clockLabel(row.logout_at) || (
                  <span className="text-emerald-700">{open ? 'لم يخرج' : '—'}</span>
                )}
              </Td>
              <Td>
                {row.worked_minutes === null ? (
                  <span className="text-emerald-700">{open ? workedText(null) : '—'}</span>
                ) : (
                  <>
                    <span className="tabular-nums">{minutesToClock(row.worked_minutes)}</span>
                    {missing > 0 && (
                      <span className="block text-[11px] text-neutral-400">
                        ناقص {minutesLabel(missing)}
                      </span>
                    )}
                  </>
                )}
              </Td>
              <Td>
                <Measure minutes={row.late_minutes} hint="بعد نهاية نافذة الدخول" tone="warn" />
              </Td>
              <Td>
                <Measure minutes={row.early_leave_minutes} hint="قبل بداية نافذة الخروج" tone="warn" />
              </Td>
              <Td>
                <Measure minutes={row.overtime_minutes} hint="بعد نهاية نافذة الخروج" tone="good" />
              </Td>
              <Td>
                <Badge variant={statusVariant(row.status)}>{statusLabel(row.status)}</Badge>
                {row.source === 'manual' && (
                  <span className="block text-[11px] text-neutral-400">تسجيل يدوي</span>
                )}
              </Td>
              <Td>
                <span className="text-xs text-neutral-500">
                  {EXCUSE_LABEL[row.excuse] || 'لا شيء'}
                </span>
                {row.note && (
                  <span className="block text-[11px] text-neutral-400">{row.note}</span>
                )}
              </Td>
              {onEdit && (
                <Td>
                  <button
                    onClick={() => onEdit(row)}
                    className="p-2 rounded-lg text-brand-600 hover:bg-brand-50"
                    title="تعديل السجل"
                  >
                    <Pencil size={16} />
                  </button>
                </Td>
              )}
            </Tr>
          );
        })}
      </tbody>
    </Table>
  );
}