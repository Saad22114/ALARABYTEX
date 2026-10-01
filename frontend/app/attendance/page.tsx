'use client';

import { useCallback, useEffect, useState } from 'react';
import AppShell from '@/components/layout/AppShell';
import Spinner from '@/components/ui/Spinner';
import { useToast } from '@/components/ui/Toast';
import { useAuth } from '@/components/providers/AuthProvider';
import { useUrlState } from '@/lib/useUrlState';
import { hasWindow } from '@/lib/permissions';
import { toISODate } from '@/components/ui/DateRangeToolbar';
import { todayISO } from '@/lib/date';
import { getAttendancePolicy } from '@/services/attendance';
import DailyTab from '@/components/attendance/DailyTab';
import RecordsTab from '@/components/attendance/RecordsTab';
import SummaryTab from '@/components/attendance/SummaryTab';
import PolicyTab from '@/components/attendance/PolicyTab';
import type { AttendancePolicy } from '@/types';

type TabKey = 'daily' | 'records' | 'summary' | 'policy';

/**
 * ترتيبُ التبويبات ومسمياتُها مرآةٌ لقسم ``attendance`` في ``sections.py``.
 *
 * لا تُجلب من الخادم لأنّها لا تتغيّر بتغيّر الصلاحيات، لكنّها تُكتب
 * هنا مرّةً واحدة: لو جُلبت أو كُرّرت في كل تبويب لاختلفت النسختان
 * في يومٍ ما، فيبقى تبويبٌ يظهر لموظفٍ ويختفي عن آخر.
 *
 * المفتاحُ (``daily``/``records``/…) هو نفسه مفتاحُ النافذة في
 * الصلاحيات، فلذلك يصلح هنا ``hasWindow`` بلا ترجمةٍ بينهما.
 */
const TABS: Array<{ key: TabKey; label: string }> = [
  { key: 'daily', label: 'ورقة اليوم' },
  { key: 'records', label: 'السجلات' },
  { key: 'summary', label: 'الملخص' },
  { key: 'policy', label: 'سياسة الحضور' },
];

/** مدى السجلات والملخص: الشهر الجاري وحده افتراضاً. */
function thisMonth(): { from: string; to: string } {
  const now = new Date();
  const start = new Date(now.getFullYear(), now.getMonth(), 1);
  return { from: toISODate(start), to: toISODate(now) };
}

export default function AttendancePage() {
  const { toast } = useToast();
  const { session, loading: authLoading } = useAuth();
  const me = session?.employee;

  const [tab, setTab] = useUrlState<TabKey>('tab', 'daily');
  const [day, setDay] = useUrlState('day', todayISO());
  const [from, setFrom] = useUrlState('from', thisMonth().from);
  const [to, setTo] = useUrlState('to', thisMonth().to);
  const [policy, setPolicy] = useState<AttendancePolicy | null>(null);

  // السياسة تُقرأ هنا لثلاثة أسباب لا لتكرار في الجلب: تعطيلُ التسجيل
  // يجب أن يُقال في الشاشة لا أن يُكتشف بسطرٍ لا يُفتح، و«ورقة اليوم»
  // تحتاجها لعرض نقصِ يوم العمل، وتغييرُها في تبويب السياسة يجب أن
  // يصل إلى بقية التبويبات بلا إعادة تحميل للصفحة.
  const loadPolicy = useCallback(() => {
    getAttendancePolicy()
      .then(setPolicy)
      .catch((err) => toast('error', err.message));
  }, [toast]);

  useEffect(() => {
    if (authLoading) return;
    loadPolicy();
  }, [authLoading, loadPolicy]);

  const visible = TABS.filter((t) => hasWindow(me?.permissions, 'attendance', t.key));

  // حالتان لا ثالثة، وكلتاهما تُقالان بغيرها: القسم ممنوعٌ، أو القسم
  // مفتوحٌ ونوافذُه كلُّها مغلقة. في الثانية كان شرطُ الرفض القديم يمرّ
  // بها إلى «ورقة اليوم» بحكم الـ fallback — فيرى الموظفُ نفسَه بلا
  // تبويبٍ مضيء، فيقرأ ذلك خطأً في حسابه لا في صلاحياته.
  const denied = !me?.permissions?.attendance?.view;
  const noWindows = !denied && visible.length === 0;

  // التبويبُ المطلوب في الرابط قد لا يكون مرخّصاً لموظفٍ بعدُ أُضيف
  // القسم إلى حسابه. حينئذٍ نُظهر أوّل ما له حقّ فيه، لا شاشةً فارغة:
  // الشاشةُ الفارغةُ بلا سببٍ ظاهر تُقرأ عطلاً في النظام.
  const active: TabKey =
    visible.some((t) => t.key === tab) ? tab : visible[0]?.key ?? 'daily';

  useEffect(() => {
    if (tab !== active) setTab(active);
  }, [tab, active, setTab]);

  // «لا صلاحية» تُحسم بعد تحميل الجلسة لا قبله. فبينما `me` غيرُ معرَّف
  // بعد، لا نعرف أهو محرومٌ أم لم تُقرأ صلاحياتُه بعد — والحكمُ في تلك
  // اللحظة يمنعه ما ليس له، ويقول له «هذا القسم غير متاح لحسابك» ثم
  // يفتح له القسم في ثانيتين. فالرسالةُ قاطعةٌ، فلا يُحكم قبل أن
  // تكتمل الحقيقة.
  if (authLoading) {
    return (
      <AppShell>
        <div className="flex justify-center py-20">
          <Spinner size={32} />
        </div>
      </AppShell>
    );
  }

  if (denied || noWindows) {
    return (
      <AppShell>
        <div className="py-20 text-center">
          <p className="text-neutral-600">
            {denied
              ? 'هذا القسم غير متاح لحسابك'
              : 'لا نافذة مفتوحة لك في هذا القسم'}
          </p>
          <p className="text-sm text-neutral-400 mt-1">
            {denied
              ? 'راجع المسؤول عن تفعيل «الحضور» في صلاحياتك'
              : 'أُضيف القسم إلى حسابك بلا نافذة — راجع المسؤول عن منحك واحدة'}
          </p>
        </div>
      </AppShell>
    );
  }

  return (
    <AppShell>
      <div className="space-y-6">
        <div>
          <h1 className="text-xl font-bold text-neutral-800">الحضور والانصراف</h1>
          <p className="text-sm text-neutral-500">
            من سجّل دخوله، ومن تأخّر، ومن غاب — والدوام الذي يُقاس عليه
          </p>
        </div>

        {policy && !policy.enabled && (
          <div className="rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
            تسجيلُ الحضور <strong>معطّل</strong> في السياسة. لن تُفتح سجلات جديدة
            حتى يُعاد تفعيله من تبويب «سياسة الحضور»، وما هو مسجَّل باقٍ كما هو.
          </div>
        )}

        <div className="flex flex-wrap items-center gap-2 border-b border-sand-200 pb-2">
          {visible.map((t) => (
            <button
              key={t.key}
              onClick={() => setTab(t.key)}
              className={`px-4 py-2 rounded-xl text-sm font-medium transition-colors ${
                active === t.key
                  ? 'bg-brand-600 text-white'
                  : 'text-neutral-600 hover:bg-sand-100'
              }`}
            >
              {t.label}
            </button>
          ))}
        </div>

        {active === 'daily' ? (
          <DailyTab day={day} onDayChange={setDay} />
        ) : active === 'records' ? (
          <RecordsTab
            from={from}
            to={to}
            onRangeChange={(a, b) => {
              setFrom(a);
              setTo(b);
            }}
          />
        ) : active === 'summary' ? (
          <SummaryTab
            from={from}
            to={to}
            onRangeChange={(a, b) => {
              setFrom(a);
              setTo(b);
            }}
          />
        ) : (
          <PolicyTab onSaved={loadPolicy} />
        )}
      </div>
    </AppShell>
  );
}