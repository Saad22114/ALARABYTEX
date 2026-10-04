'use client';

import { useCallback, useEffect, useState } from 'react';
import Card from '@/components/ui/Card';
import StatCard from '@/components/ui/StatCard';
import Spinner from '@/components/ui/Spinner';
import Badge from '@/components/ui/Badge';
import ExportButton from '@/components/ui/ExportButton';
import DateRangeToolbar from '@/components/ui/DateRangeToolbar';
import { useToast } from '@/components/ui/Toast';
import {
  CalendarDays, CalendarCheck, CalendarX2, Clock4, Flame, Timer,
} from 'lucide-react';
import { getAttendancePolicy, getAttendanceSummary } from '@/services/attendance';
import { formatNumber } from '@/lib/format';
import { counted } from '@/lib/arabic';
import { attainmentPercent, minutesLabel } from '@/lib/attendance';
import type { AttendancePolicy, AttendanceSummary } from '@/types';

/**
 * ملخّص المدى: الأرقام لا الأسطر.
 *
 * شاشةُ الملخّص تُجيب عن «كيف كان الشهر» لا «من كان غائباً ومتى» —
 * فالأولى لهذا والثانية لورقة اليوم وللسجلات. وللذلك لا جدول هنا:
 * جدولٌ هنا يُعاد جدولُ الملخّص سطراً سطراً، والمرء يقفز إلى «من»
 * فيبحث في عددٍ من الصفوف بدل أن يفتح السجلات.
 */
interface SummaryTabProps {
  from: string;
  to: string;
  onRangeChange: (from: string, to: string) => void;
}

export default function SummaryTab({ from, to, onRangeChange }: SummaryTabProps) {
  const { toast } = useToast();
  const [summary, setSummary] = useState<AttendanceSummary | null>(null);
  const [policy, setPolicy] = useState<AttendancePolicy | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(() => {
    setLoading(true);
    Promise.all([getAttendanceSummary({ start: from, end: to }), getAttendancePolicy()])
      .then(([data, policyData]) => {
        setSummary(data.summary);
        setPolicy(policyData);
      })
      .catch((err) => toast('error', err.message))
      .finally(() => setLoading(false));
  }, [from, to, toast]);

  useEffect(() => {
    load();
  }, [load]);

  if (loading) {
    return (
      <div className="flex justify-center py-20">
        <Spinner size={32} />
      </div>
    );
  }

  const s = summary;
  const attainment = attainmentPercent(s?.worked_minutes ?? 0, s?.expected_minutes ?? 0);
  // الغياب نسبةً من الأيام المحسوبة لا عدداً مجرّداً: «12 غياباً» لا
  // تُقارن بأحد، و«12 من 130 يوماً» تُقارن.
  const measurableDays = (s?.present ?? 0) + (s?.absent ?? 0);
  const absenceRate = measurableDays ? Math.round(((s?.absent ?? 0) / measurableDays) * 100) : 0;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-lg font-bold text-neutral-800">ملخّص الحضور</h2>
          <p className="text-sm text-neutral-500">
            {from} إلى {to} — {formatNumber(s?.days ?? 0)} يوماً فيه سجلات
          </p>
        </div>
        <ExportButton
          path="/attendance/records/export/"
          params={{ start: from, end: to }}
          filename="ملخص-الحضور.xlsx"
          label="تصدير الملخّص"
        />
      </div>

      <DateRangeToolbar from={from} to={to} onChange={onRangeChange} />

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          icon={<CalendarCheck size={22} />}
          iconBg="bg-emerald-50 text-emerald-600"
          label="أيام الحضور"
          value={formatNumber(s?.present ?? 0)}
          sub={`${attainment}% من زمن العمل المُتوقَّع`}
        />
        <StatCard
          icon={<CalendarX2 size={22} />}
          iconBg="bg-red-50 text-red-600"
          label="أيام الغياب"
          value={formatNumber(s?.absent ?? 0)}
          sub={`${absenceRate}% من ${counted(measurableDays, 'يوم', 'يومان', 'أيام')}`}
        />
        <StatCard
          icon={<Clock4 size={22} />}
          iconBg="bg-amber-50 text-amber-600"
          label="التأخير"
          value={minutesLabel(s?.late_minutes ?? 0)}
          sub={`${counted(s?.late_count ?? 0, 'يوم', 'يومان', 'أيام')} تأخّر فيها`}
        />
        <StatCard
          icon={<Timer size={22} />}
          iconBg="bg-violet-50 text-violet-600"
          label="الخروج المبكر"
          value={minutesLabel(s?.early_minutes ?? 0)}
          sub={`${counted(s?.early_count ?? 0, 'مرة', 'مرتان', 'مرات')} خرج فيها مبكراً`}
        />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <StatCard
          icon={<CalendarDays size={22} />}
          label="ساعات العمل"
          value={formatNumber(Math.round((s?.worked_minutes ?? 0) / 60))}
          sub={`المُتوقَّع ${counted(Math.round((s?.expected_minutes ?? 0) / 60), 'ساعة', 'ساعتان', 'ساعات')}`}
        />
        <StatCard
          icon={<Flame size={22} />}
          iconBg="bg-emerald-50 text-emerald-600"
          label="ساعات إضافية"
          value={formatNumber(Math.round((s?.overtime_minutes ?? 0) / 60))}
          sub={`${minutesLabel(s?.overtime_minutes ?? 0)} فوق يوم العمل`}
        />
        <StatCard
          icon={<CalendarDays size={22} />}
          iconBg="bg-sand-100 text-neutral-600"
          label="داخل الدوام الآن"
          value={formatNumber(s?.open_sessions ?? 0)}
          sub="دخلوا ولم يخرجوا بعد"
        />
      </div>

      <Card title="كيف تُقرأ هذه الأرقام">
        <div className="space-y-3 text-sm text-neutral-600">
          <p>
            «المُتوقَّع» = يوم العمل في السياسة × عدد أيام العمل في المدى. فليست
            الأيام العطلة ولا الأسبوعية ناقصةً على أحد: يومُ العطلة ليس يوماً
            قُلِّص، بل ليس يومَ عمل أصلاً.
          </p>
          <p>
            «أيام الحضور» تجمع من حضر كاملاً ومن تأخّر ومن خرج مبكراً: من جاء
            فهو جاء، والساعةُ الأولى لا تُلغي اليوم. والانصراف المبكر يُحسب
            عليه وحده.
          </p>
          {s && s.excused > 0 && (
            <p>
              <Badge variant="neutral">{counted(s.excused, 'يوم', 'يومان', 'أيام')} مبرَّراً</Badge>{' '}
              الغياب المُبرَّر لا يُحسب نقصاً، وهو مُستبعَد من نسبة الغياب أعلاه
              حتى لا يُقارَن غيابٌ باختيارٍ بغيابٍ دون تبرير.
            </p>
          )}
          {policy && !policy.enabled && (
            <p>
              <Badge variant="warning">تسجيل الحضور معطّل</Badge> السجلات
              الموجودة تاريخٌ سابق للإيقاف؛ لا يُفتح سطرٌ جديد حتى يُعاد تفعيله
              من «سياسة الحضور».
            </p>
          )}
        </div>
      </Card>
    </div>
  );
}