'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import Card from '@/components/ui/Card';
import Button from '@/components/ui/Button';
import Table, { Th, Td, Tr } from '@/components/ui/Table';
import Select from '@/components/ui/Select';
import Input from '@/components/ui/Input';
import Spinner from '@/components/ui/Spinner';
import EmptyState from '@/components/ui/EmptyState';
import { useToast } from '@/components/ui/Toast';
import { Download, TrendingUp, TrendingDown, Minus } from 'lucide-react';
import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import {
  AnalyticsReportDef,
  ReportEnvelope,
  ReportKpi,
  ReportValueType,
} from '@/types';
import { exportAnalyticsReport, getAnalyticsReport } from '@/services/reports';
import { formatCurrency, formatDate, formatNumber } from '@/lib/format';

interface AnalyticsReportViewProps {
  report: AnalyticsReportDef;
  dateFrom: string;
  dateTo: string;
  branch: string;
  compare: boolean;
  idleDays: string;
  onIdleDays: (v: string) => void;
  groupBy: string;
  onGroupBy: (v: string) => void;
  refreshKey: number;
}

function formatValue(value: unknown, type: ReportValueType): string {
  if (value === null || value === undefined || value === '') return '-';
  if (type === 'money') return formatCurrency(Number(value));
  if (type === 'number') return formatNumber(Number(value));
  if (type === 'percent') return `${Number(value).toFixed(1)}%`;
  return String(value);
}

function KpiCard({ kpi, showChange }: { kpi: ReportKpi; showChange: boolean }) {
  const up = (kpi.change_pct ?? 0) > 0;
  const flat = kpi.change_pct === null || kpi.change_pct === 0;
  const Icon = flat ? Minus : up ? TrendingUp : TrendingDown;
  const tone = flat
    ? 'text-neutral-500'
    : up
      ? 'text-emerald-600'
      : 'text-red-600';

  return (
    <div className="rounded-xl border border-sand-200 bg-surface px-4 py-3">
      <span className="block text-xs text-neutral-500">{kpi.label}</span>
      <span className="tabular-nums text-xl font-semibold text-neutral-800">
        {formatValue(kpi.value, kpi.type)}
      </span>
      {showChange && kpi.change_pct !== null && (
        <span className={`mt-1 flex items-center gap-1 text-xs ${tone}`}>
          <Icon size={13} />
          {Math.abs(kpi.change_pct).toFixed(1)}%
          {kpi.previous !== null && (
            <span className="text-neutral-400">
              (مقابل {formatValue(kpi.previous, kpi.type)})
            </span>
          )}
        </span>
      )}
    </div>
  );
}

export default function AnalyticsReportView({
  report,
  dateFrom,
  dateTo,
  branch,
  compare,
  idleDays,
  onIdleDays,
  groupBy,
  onGroupBy,
  refreshKey,
}: AnalyticsReportViewProps) {
  const { toast } = useToast();
  const [data, setData] = useState<ReportEnvelope | null>(null);
  const [loading, setLoading] = useState(true);
  const [exporting, setExporting] = useState(false);
  const [chartMode, setChartMode] = useState<'line' | 'bar'>('line');

  const params = useMemo(() => {
    const p: Record<string, string | number | boolean | undefined> = {
      date_from: dateFrom || undefined,
      date_to: dateTo || undefined,
      branch: branch || undefined,
    };
    if (report.supportsGroupBy) p.group_by = groupBy || undefined;
    if (report.supportsIdleDays) p.idle_days = idleDays || undefined;
    return p;
  }, [dateFrom, dateTo, branch, groupBy, idleDays, report.supportsGroupBy, report.supportsIdleDays]);

  const load = useCallback(() => {
    setLoading(true);
    getAnalyticsReport(report.key, params)
      .then(setData)
      .catch((err) => toast('error', err.message))
      .finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [report.key, JSON.stringify(params)]);

  useEffect(() => {
    load();
  }, [load, refreshKey]);

  const handleExport = async () => {
    setExporting(true);
    try {
      await exportAnalyticsReport(report.key, params, `تقرير_${report.key}`);
      toast('success', 'تم تنزيل التقرير');
    } catch (err: any) {
      toast('error', err.message);
    } finally {
      setExporting(false);
    }
  };

  const seriesData = useMemo(() => {
    const series = data?.series;
    if (!series || !series.labels?.length) return [];
    return series.labels.map((label, i) => ({
      label,
      current: series.current[i] ?? 0,
      previous: series.previous ? (series.previous[i] ?? 0) : undefined,
    }));
  }, [data]);

  const totalKeys = useMemo(
    () => (data?.columns || []).filter((c) => c.total && data?.totals?.[c.key] !== undefined),
    [data],
  );

  return (
    <div className="space-y-4">
      <Card className="!p-4">
        <div className="flex flex-wrap items-center gap-3">
          <div className="flex-1">
            <h3 className="text-base font-semibold text-neutral-800">{data?.title || report.label}</h3>
            <p className="text-xs text-neutral-500">
              {report.description}
              {data?.period && (
                <>
                  {' — '}
                  {formatDate(data.period.from)} إلى {formatDate(data.period.to)}
                </>
              )}
              {data?.previous && compare && (
                <>
                  {' — مقارنة بـ '}
                  {formatDate(data.previous.from)} إلى {formatDate(data.previous.to)}
                </>
              )}
            </p>
          </div>
          {report.supportsGroupBy && (
            <Select
              value={groupBy}
              onChange={(e) => onGroupBy(e.target.value)}
              options={[
                { value: '', label: 'تجميع تلقائي' },
                { value: 'day', label: 'يومي' },
                { value: 'week', label: 'أسبوعي' },
                { value: 'month', label: 'شهري' },
              ]}
              className="sm:w-36"
            />
          )}
          {report.supportsIdleDays && (
            <Input
              type="number"
              min="0"
              value={idleDays}
              onChange={(e) => onIdleDays(e.target.value)}
              className="sm:w-28"
              title="أيام الركود"
            />
          )}
          <Button type="button" variant="secondary" onClick={handleExport} loading={exporting}>
            <Download size={16} />
            Excel
          </Button>
        </div>
      </Card>

      {loading ? (
        <div className="flex justify-center py-16">
          <Spinner size={32} />
        </div>
      ) : !data ? (
        <EmptyState title="تعذّر تحميل التقرير" />
      ) : (
        <>
          {data.kpis.length > 0 && (
            <div
              className={`grid gap-3 ${
                data.kpis.length > 4
                  ? 'grid-cols-2 lg:grid-cols-5'
                  : 'grid-cols-2 lg:grid-cols-4'
              }`}
            >
              {data.kpis.map((k) => (
                <KpiCard key={k.key} kpi={k} showChange={compare} />
              ))}
            </div>
          )}

          {seriesData.length > 1 && (
            <Card
              title="المنحنى الزمني"
              action={
                <Select
                  value={chartMode}
                  onChange={(e) => setChartMode(e.target.value as 'line' | 'bar')}
                  options={[
                    { value: 'line', label: 'خطي' },
                    { value: 'bar', label: 'أعمدة' },
                  ]}
                  className="sm:w-32"
                />
              }
            >
              <div className="h-[300px]" dir="ltr">
                <ResponsiveContainer width="100%" height="100%">
                  {chartMode === 'line' ? (
                    <LineChart data={seriesData} margin={{ top: 10, right: 10, left: 10, bottom: 0 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#e8e4db" />
                      <XAxis dataKey="label" tick={{ fontSize: 12, fill: '#737373' }} />
                      <YAxis tick={{ fontSize: 12, fill: '#737373' }} />
                      <Tooltip
                        contentStyle={{ borderRadius: '12px', border: '1px solid #e8e4db', direction: 'rtl' }}
                        formatter={(value: number, name: string) => [
                          formatCurrency(value),
                          name === 'current' ? 'الفترة الحالية' : 'الفترة السابقة',
                        ]}
                      />
                      <Legend
                        wrapperStyle={{ fontSize: '13px' }}
                        formatter={(value) => (value === 'current' ? 'الفترة الحالية' : 'الفترة السابقة')}
                      />
                      <Line type="monotone" dataKey="current" stroke="#1e6b56" strokeWidth={2.5} dot={{ r: 3 }} />
                      {data.series?.previous && (
                        <Line
                          type="monotone"
                          dataKey="previous"
                          stroke="#a8a29e"
                          strokeWidth={2}
                          strokeDasharray="5 5"
                          dot={{ r: 2 }}
                        />
                      )}
                    </LineChart>
                  ) : (
                    <BarChart data={seriesData} margin={{ top: 10, right: 10, left: 10, bottom: 0 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#e8e4db" />
                      <XAxis dataKey="label" tick={{ fontSize: 12, fill: '#737373' }} />
                      <YAxis tick={{ fontSize: 12, fill: '#737373' }} />
                      <Tooltip
                        contentStyle={{ borderRadius: '12px', border: '1px solid #e8e4db', direction: 'rtl' }}
                        formatter={(value: number) => [formatCurrency(value), 'القيمة']}
                      />
                      <Bar dataKey="current" fill="#1e6b56" radius={[4, 4, 0, 0]} />
                    </BarChart>
                  )}
                </ResponsiveContainer>
              </div>
            </Card>
          )}

          <Card>
            {data.rows.length === 0 ? (
              <EmptyState
                title="لا توجد بيانات"
                description="لا توجد نتائج في الفترة المحددة"
              />
            ) : (
              <Table>
                <thead>
                  <tr>
                    {data.columns.map((col) => (
                      <Th key={col.key} className={col.type === 'text' ? '' : 'text-left'}>
                        {col.label}
                      </Th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {data.rows.map((row, i) => (
                    <Tr key={i}>
                      {data.columns.map((col) => (
                        <Td
                          key={col.key}
                          className={
                            col.type === 'text'
                              ? 'font-medium'
                              : 'tabular-nums text-left whitespace-nowrap'
                          }
                        >
                          {formatValue(row[col.key], col.type)}
                        </Td>
                      ))}
                    </Tr>
                  ))}
                </tbody>
                {totalKeys.length > 0 && (
                  <tfoot>
                    <tr className="bg-sand-100 font-semibold">
                      {data.columns.map((col) => (
                        <Td
                          key={col.key}
                          className={
                            col.type === 'text'
                              ? 'font-semibold text-neutral-700'
                              : 'tabular-nums text-left'
                          }
                        >
                          {totalKeys.some((t) => t.key === col.key)
                            ? formatValue(data.totals[col.key], col.type)
                            : ''}
                        </Td>
                      ))}
                    </tr>
                  </tfoot>
                )}
              </Table>
            )}
          </Card>
        </>
      )}
    </div>
  );
}
