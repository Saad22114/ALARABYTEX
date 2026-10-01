'use client';

import { useCallback, useEffect, useState } from 'react';
import Card from '@/components/ui/Card';
import Button from '@/components/ui/Button';
import Input from '@/components/ui/Input';
import Textarea from '@/components/ui/Textarea';
import Switch from '@/components/ui/Switch';
import Spinner from '@/components/ui/Spinner';
import Badge from '@/components/ui/Badge';
import { useToast } from '@/components/ui/Toast';
import { getAttendancePolicy, saveAttendancePolicy } from '@/services/attendance';
import { ALL_WEEKDAYS, WEEKDAY_NAME } from '@/lib/attendance';
import type { AttendancePolicy } from '@/types';

/**
 * سياسة الحضور: متى يُسمح بالدخول، ومتى يجب أن يخرج، وكم يوم العمل.
 *
 * سياسةٌ واحدة للنظام كله، لا واحدة لكل موظف. والسبب أن الأرقام
 * المشتقّة (التأخير، الانصراف المبكر، الإضافي) تُحسَب على أساسها:
 * سياستان تعنيان رقمين لكل موظف لا يُعرف أيّهما عُرض، فيصير التقرير
 * حشداً من النسب بلا معنى.
 *
 * وكل تعديل هنا يُعيد احتساب **كل** السجلات المحفوظة، لأنها بُنيت على
 * نافذةٍ قد تغيّرت. بلا ذلك يبقى رقمٌ مكتوبٌ تحت سياسةٍ لم تعد له
 * صالحة — وهو أسوأ من رقمٍ خاطئ، لأن صاحبه لا يعرف أنه خاطئ.
 */
export default function PolicyTab({ onSaved }: { onSaved?: () => void }) {
  const { toast } = useToast();
  const [policy, setPolicy] = useState<AttendancePolicy | null>(null);
  const [draft, setDraft] = useState<AttendancePolicy | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  const load = useCallback(() => {
    setLoading(true);
    getAttendancePolicy()
      .then((data) => {
        setPolicy(data);
        setDraft(data);
      })
      .catch((err) => toast('error', err.message))
      .finally(() => setLoading(false));
  }, [toast]);

  useEffect(() => {
    load();
  }, [load]);

  if (loading || !draft) {
    return (
      <div className="flex justify-center py-20">
        <Spinner size={32} />
      </div>
    );
  }

  const set = <K extends keyof AttendancePolicy>(key: K, value: AttendancePolicy[K]) =>
    setDraft((d) => (d ? { ...d, [key]: value } : d));

  const toggleWeekend = (day: number) => {
    setDraft((d) => {
      if (!d) return d;
      const has = d.weekend_days.includes(day);
      return {
        ...d,
        weekend_days: has
          ? d.weekend_days.filter((x) => x !== day)
          : [...d.weekend_days, day].sort((a, b) => a - b),
      };
    });
  };

  const dirty = Boolean(policy && draft && JSON.stringify(policy) !== JSON.stringify(draft));

  const save = async () => {
    setSaving(true);
    try {
      const data = await saveAttendancePolicy(draft);
      setPolicy(data);
      setDraft(data);
      // الشاشة الأمّ تحتفظ بنسخةٍ سياستها أقدم من هذه، فلا بدّ من إخبارها:
      // لولا ذلك لبقي التحذيرُ «معطّل» معروضاً بعد إعادة التفعيل.
      onSaved?.();
      toast('success', 'حُفظت السياسة وأُعيد احتساب كل السجلات على أساسها');
    } catch (err: any) {
      toast('error', err.message);
    } finally {
      setSaving(false);
    }
  };

  const windows: Array<{ start: keyof AttendancePolicy; end: keyof AttendancePolicy; label: string; hint: string }> = [
    {
      start: 'login_window_start',
      end: 'login_window_end',
      label: 'نافذة الدخول',
      hint: 'قبل بدايتها دخولٌ مبكر لا يُحسب تأخيراً، وبعد نهايتها يُحسب.',
    },
    {
      start: 'logout_window_start',
      end: 'logout_window_end',
      label: 'نافذة الخروج',
      hint: 'قبل بدايتها خروجٌ مبكر يُحسب، وبعد نهايتها يُحتسب وقتٌ إضافي.',
    },
  ];

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-lg font-bold text-neutral-800">سياسة الحضور</h2>
          <p className="text-sm text-neutral-500">
            سياسةٌ واحدة تُقاس بها كل السجلات؛ وتغييرُها يعيد احتساب ما سبق
          </p>
        </div>
        <div className="flex gap-2">
          <Button variant="secondary" onClick={load} disabled={saving}>
            إعادة
          </Button>
          <Button onClick={save} loading={saving} disabled={!dirty}>
            حفظ
          </Button>
        </div>
      </div>

      <Card>
        <div className="flex items-start justify-between gap-4">
          <div>
            <p className="font-medium text-neutral-800">تسجيل الحضور تلقائياً</p>
            <p className="text-sm text-neutral-500 mt-1">
              عند التفعيل يُفتح سجلّ الحضور مع كل دخول ويغلق مع كل خروج. عند
              الإيقاف لا تُفتح سجلات جديدة، وتبقى القديمة كما هي — الإيقاف لا
              يمحو تاريخاً.
            </p>
          </div>
          <Switch checked={draft.enabled} onChange={(v) => set('enabled', v)} />
        </div>
      </Card>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {windows.map((w) => (
          <Card key={String(w.start)} title={w.label} subtitle={w.hint}>
            <div className="grid grid-cols-2 gap-3">
              <Input
                label="من"
                type="time"
                value={String(draft[w.start])}
                onChange={(e) => set(w.start, e.target.value as never)}
              />
              <Input
                label="إلى"
                type="time"
                value={String(draft[w.end])}
                onChange={(e) => set(w.end, e.target.value as never)}
              />
            </div>
          </Card>
        ))}
      </div>

      <Card title="يوم العمل" subtitle="أساسُ كل حساب: به تُقاس الإضافية والنقص">
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          <Input
            label="دقائق يوم العمل"
            type="number"
            numeric="int"
            min={1}
            max={1440}
            value={draft.workday_minutes}
            onChange={(e) => set('workday_minutes', Number(e.target.value) || 0)}
          />
          <Input
            label="سماح التأخير (دقائق)"
            type="number"
            numeric="int"
            min={0}
            max={240}
            value={draft.grace_minutes}
            onChange={(e) => set('grace_minutes', Number(e.target.value) || 0)}
          />
          <Input
            label="ساعة فاصل اليوم"
            type="number"
            numeric="int"
            min={0}
            max={23}
            value={draft.day_cutoff_hour}
            onChange={(e) => set('day_cutoff_hour', Number(e.target.value) || 0)}
          />
        </div>
        <p className="text-xs text-neutral-500 mt-3">
          ساعةُ الفاصل هي التي يُنسب إليها الدخولُ المتأخر: من دخل بعد فاصل
          الليل بساعة، نُسب إلى يومه بالأمس لا اليوم. والسماحُ يُطرح من
          التأخير قبل حسابه، فلا يُحسب تأخيرُ أوله داخله.
        </p>
      </Card>

      <Card
        title="أيام العطلة الأسبوعية"
        subtitle="تُحسب على ترتيب date.weekday(): الاثنين ٠ … الجمعة ٤ … الأحد ٦"
      >
        <div className="flex flex-wrap gap-2">
          {ALL_WEEKDAYS.map((day) => {
            const on = draft.weekend_days.includes(day);
            return (
              <button
                key={day}
                onClick={() => toggleWeekend(day)}
                className={`px-3 py-2 rounded-xl text-sm font-medium transition-colors ${
                  on ? 'bg-brand-600 text-white' : 'bg-surface text-neutral-600 border border-sand-200 hover:bg-sand-50'
                }`}
              >
                {WEEKDAY_NAME[day]}
              </button>
            );
          })}
        </div>
        <p className="text-xs text-neutral-500 mt-3">
          {draft.weekend_days.length === 0 ? (
            <>
              <Badge variant="warning">بلا عطلة أسبوعية</Badge> كل الأيام أيام
              عمل، فلا يُفترض يومٌ لا يُقاس. وهذا مقصود: من أراد عطلةً
              فعّلها، ومن ترك القائمة فارغة فقد اختار «العمل كل يوم».
            </>
          ) : (
            <>العطلة: {draft.weekend_days.map((d) => WEEKDAY_NAME[d]).join('، ')}. وما
              فيها لا يُحتسب غياباً ولا نقصاً — اليوم الذي لا يُعمل فيه لا
              يُحاسَب عليه أحد.</>
          )}
        </p>
      </Card>

      <Card title="ملاحظات" subtitle="تظهر في السياسة نفسها، لا في السجلات">
        <Textarea
          rows={3}
          value={draft.notes}
          onChange={(e) => set('notes', e.target.value)}
          placeholder="اتفاقٌ مع الموظفين: دوامٌ مرن، استثناءٌ في الجمعة، إجازةٌ أسبوعية…"
        />
      </Card>
    </div>
  );
}