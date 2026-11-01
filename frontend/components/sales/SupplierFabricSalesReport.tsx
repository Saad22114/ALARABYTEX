'use client';

import { useEffect, useState } from 'react';
import Card from '@/components/ui/Card';
import Spinner from '@/components/ui/Spinner';
import Table, { Td, Th, Tr } from '@/components/ui/Table';
import DateRangeToolbar, { getRangeForKey } from '@/components/ui/DateRangeToolbar';
import Select from '@/components/ui/Select';
import { formatCurrency } from '@/lib/format';
import { useToast } from '@/components/ui/Toast';
import { getSalesBySupplierFabric, SupplierFabricSalesResult } from '@/services/sales';
import { Branch } from '@/types';
import { ChevronLeft, ChevronRight, CalendarDays } from 'lucide-react';

function currentMonthAndDay() {
  const now = new Date();
  return {
    month: `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`,
    day: now.getDate(),
  };
}

function daysInMonth(month: string) {
  const [year, monthNumber] = month.split('-').map(Number);
  return new Date(year, monthNumber, 0).getDate();
}

function isoDay(month: string, day: number) {
  const [year, monthNumber] = month.split('-');
  return `${year}-${monthNumber}-${String(day).padStart(2, '0')}`;
}

export default function SupplierFabricSalesReport({ branches, initialBranch = '' }: { branches: Branch[]; initialBranch?: string }) {
  const { toast } = useToast();
  const [from, setFrom] = useState(getRangeForKey('today').from);
  const [to, setTo] = useState(getRangeForKey('today').to);
  const [branch, setBranch] = useState(initialBranch);
  const initialDay = currentMonthAndDay();
  const [dayMonth, setDayMonth] = useState(initialDay.month);
  const [dayNumber, setDayNumber] = useState(initialDay.day);
  const [report, setReport] = useState<SupplierFabricSalesResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [schemaError, setSchemaError] = useState(false);
  const invalidRange = Boolean(from && to && from > to);
  const monthDayCount = daysInMonth(dayMonth);

  function applySingleDay(month: string, day: number) {
    const boundedDay = Math.max(1, Math.min(day, daysInMonth(month)));
    setDayMonth(month);
    setDayNumber(boundedDay);
    const selectedDate = isoDay(month, boundedDay);
    setFrom(selectedDate);
    setTo(selectedDate);
  }

  useEffect(() => {
    let cancelled = false;
    if (invalidRange) {
      setReport(null);
      setLoading(false);
      return () => { cancelled = true; };
    }
    setLoading(true);
    setSchemaError(false);
    getSalesBySupplierFabric({ date_from: from, date_to: to, branch: branch || undefined })
      .then((result) => {
        if (cancelled) return;
        const compatible = result.results.every((row) =>
          Number.isFinite(Number(row.yards_total)) && Number.isFinite(Number(row.supplier_due)),
        );
        setSchemaError(!compatible);
        setReport(compatible ? result : null);
      })
      .catch((error: any) => { if (!cancelled) toast('error', error?.message || 'تعذر تحميل مبيعات الأقمشة حسب المورد'); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [from, to, branch, toast, invalidRange]);

  return (
    <div className="space-y-4">
      <Card className="space-y-4">
        <div>
          <h2 className="text-lg font-bold text-neutral-900">تكلفة الأقمشة المباعة حسب المورد</h2>
          <p className="mt-1 text-sm text-neutral-500">سعر شراء الياردة × الياردات المباعة، ويشمل بنود الورديات المفتوحة والمغلقة.</p>
        </div>
        <Select
          aria-label="فرع التقرير"
          value={branch}
          onChange={(event) => setBranch(event.target.value)}
          options={[
            { value: '', label: 'كل الفروع المسموحة' },
            ...branches.map((item) => ({ value: String(item.id), label: item.name })),
          ]}
          className="w-full sm:max-w-xs"
        />
        <div className="flex flex-wrap items-center gap-2 rounded-xl border border-sand-200 bg-sand-50/70 px-3 py-2">
          <span className="inline-flex items-center gap-1.5 text-sm font-medium text-neutral-600"><CalendarDays size={16} />يوم واحد</span>
          <input
            aria-label="شهر التقرير اليومي"
            type="month"
            value={dayMonth}
            onChange={(event) => event.target.value && applySingleDay(event.target.value, dayNumber)}
            className="rounded-lg border border-sand-300 bg-surface px-2.5 py-1.5 text-sm text-neutral-700"
          />
          <button
            type="button"
            aria-label="اليوم السابق من الشهر"
            disabled={dayNumber <= 1}
            onClick={() => applySingleDay(dayMonth, dayNumber - 1)}
            className="rounded-lg border border-sand-300 bg-surface p-1.5 text-neutral-600 transition hover:bg-sand-100 disabled:cursor-not-allowed disabled:opacity-40"
          ><ChevronRight size={17} /></button>
          <label className="flex items-center gap-1 text-sm text-neutral-600">
            <input
              aria-label="رقم اليوم"
              type="number"
              min={1}
              max={monthDayCount}
              value={dayNumber}
              onChange={(event) => {
                const value = Number(event.target.value);
                if (Number.isInteger(value) && value >= 1 && value <= monthDayCount) applySingleDay(dayMonth, value);
              }}
              className="w-16 rounded-lg border border-sand-300 bg-surface px-2 py-1.5 text-center font-bold tabular-nums"
            />
            <span>من {monthDayCount}</span>
          </label>
          <button
            type="button"
            aria-label="اليوم التالي من الشهر"
            disabled={dayNumber >= monthDayCount}
            onClick={() => applySingleDay(dayMonth, dayNumber + 1)}
            className="rounded-lg border border-sand-300 bg-surface p-1.5 text-neutral-600 transition hover:bg-sand-100 disabled:cursor-not-allowed disabled:opacity-40"
          ><ChevronLeft size={17} /></button>
        </div>
        <DateRangeToolbar from={from} to={to} onChange={(start, end) => { setFrom(start); setTo(end); }} />
        {invalidRange && <p className="text-sm font-medium text-red-600">تاريخ البداية يجب أن يكون قبل تاريخ النهاية أو مساويًا له.</p>}
      </Card>

      <Card className="!p-0 overflow-hidden">
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-sand-200 bg-gradient-to-l from-brand-50/70 to-surface px-4 py-4">
          <span className="font-semibold text-neutral-700">إجمالي تكلفة الأقمشة المستحقة حسب المباع</span>
          <strong className="text-xl tabular-nums text-brand-700">{report ? formatCurrency(report.grand_total) : '—'}</strong>
        </div>
        {loading ? <div className="flex justify-center py-12"><Spinner size={28} /></div> : !report?.results.length ? (
          <p className={`py-10 text-center text-sm ${schemaError ? 'text-amber-700' : 'text-neutral-500'}`}>
            {schemaError ? 'استجابة الخادم لا تطابق نسخة التقرير. أعد تشغيل أو نشر تحديث الخادم ثم حدّث الصفحة.' : 'لا توجد مبيعات أقمشة في الفترة المحددة.'}
          </p>
        ) : (
          <Table>
            <thead><tr><Th>المورد</Th><Th>عدد البنود</Th><Th>الياردات المباعة</Th><Th>تكلفة الشراء المستحقة</Th></tr></thead>
            <tbody>{report.results.map((row) => (
              <Tr key={row.supplier ?? 'unassigned'}>
                <Td className="font-semibold">{row.supplier_name}</Td>
                <Td className="tabular-nums">{row.items_count}</Td>
                <Td className="tabular-nums">{Number(row.yards_total ?? 0).toLocaleString('en-US', { maximumFractionDigits: 2 })}</Td>
                <Td className="font-bold tabular-nums text-brand-700">{formatCurrency(Number(row.supplier_due ?? 0))}</Td>
              </Tr>
            ))}</tbody>
          </Table>
        )}
      </Card>
      <p className="px-1 text-xs text-neutral-500">المعادلة: سعر الشراء المسجل حاليًا للياردة × الياردات المباعة. بيع الطاقة يُحوّل إلى ياردات وفق إعداد القماش، والمرتجعات مستبعدة. يتغير الإجمالي مع إضافة البنود أو حذفها من الوردية.</p>
    </div>
  );
}
