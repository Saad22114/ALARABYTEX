'use client';

import { useState, useEffect, useRef } from 'react';
import AppShell from '@/components/layout/AppShell';
import StatCard from '@/components/ui/StatCard';
import Card from '@/components/ui/Card';
import Button from '@/components/ui/Button';
import Select from '@/components/ui/Select';
import DateRangeToolbar, { getRangeForKey, DateRangeKey } from '@/components/ui/DateRangeToolbar';
import SalesChart from '@/components/dashboard/SalesChart';
import ProfitChart from '@/components/dashboard/ProfitChart';
import ComparisonChart from '@/components/dashboard/ComparisonChart';
import MonthCompareChart from '@/components/dashboard/MonthCompareChart';
import AlertsPanel from '@/components/dashboard/AlertsPanel';
import RecentActivity from '@/components/dashboard/RecentActivity';
import Spinner from '@/components/ui/Spinner';
import Badge from '@/components/ui/Badge';
import { Banknote, ReceiptText, TrendingUp, Percent, Store, Truck, GitCompareArrows } from 'lucide-react';
import { DashboardActivityItem, DashboardAlertsResult, DashboardSummary } from '@/types';
import { getDashboardActivity, getDashboardAlerts, getDashboardSummary } from '@/services/dashboard';
import { listBranches } from '@/services/branches';
import { Branch } from '@/types';
import { formatCurrency, formatNumber } from '@/lib/format';
import { useToast } from '@/components/ui/Toast';
import { useSettings } from '@/components/providers/SettingsProvider';
import { useAuth } from '@/components/providers/AuthProvider';
import { useUrlState } from '@/lib/useUrlState';

function deltaText(pct: number | null | undefined): string {
  if (pct === null || pct === undefined) return '';
  const sign = pct >= 0 ? '+' : '−';
  return `${sign}${Math.abs(pct)}% عن الفترة السابقة`;
}

function currentMonthKey(): string {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`;
}

function monthRange(ym: string): { from: string; to: string } {
  const [y, m] = ym.split('-').map(Number);
  const lastDay = new Date(y, m, 0).getDate();
  return { from: `${ym}-01`, to: `${ym}-${String(lastDay).padStart(2, '0')}` };
}

function monthLabel(ym: string): string {
  const [y, m] = ym.split('-').map(Number);
  const months = ['يناير', 'فبراير', 'مارس', 'أبريل', 'مايو', 'يونيو', 'يوليو', 'أغسطس', 'سبتمبر', 'أكتوبر', 'نوفمبر', 'ديسمبر'];
  return `${months[(m || 1) - 1]} ${y}`;
}

function compareLabel(a: number, b: number): string {
  if (!a) return 'لا بيانات في الشهر الأول';
  const pct = ((b - a) / a) * 100;
  const sign = pct >= 0 ? '+' : '−';
  return `${sign}${Math.abs(pct).toFixed(1)}% مقارنة بالشهر الأول`;
}

export default function DashboardPage() {
  const { toast } = useToast();
  const { settings } = useSettings();
  const { session } = useAuth();
  const me = session?.employee;
  const isScoped = Boolean(me && me.role !== 'admin' && me.role !== 'supervisor');
  const [branch, setBranch] = useUrlState('branch', '');
  const [dateFrom, setDateFrom] = useUrlState('from', getRangeForKey('today').from);
  const [dateTo, setDateTo] = useUrlState('to', getRangeForKey('today').to);
  const appliedDefaultPeriod = useRef<string | null>(null);
  const [data, setData] = useState<DashboardSummary | null>(null);
  const [branches, setBranches] = useState<Branch[]>([]);
  const [alerts, setAlerts] = useState<DashboardAlertsResult | null>(null);
  const [activities, setActivities] = useState<DashboardActivityItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [reloadKey, setReloadKey] = useState(0);

  const [monthA, setMonthA] = useState<string>(currentMonthKey());
  const [monthB, setMonthB] = useState<string>(() => {
    const now = new Date();
    const prev = new Date(now.getFullYear(), now.getMonth() - 1, 1);
    return `${prev.getFullYear()}-${String(prev.getMonth() + 1).padStart(2, '0')}`;
  });
  const [monthDataA, setMonthDataA] = useState<DashboardSummary | null>(null);
  const [monthDataB, setMonthDataB] = useState<DashboardSummary | null>(null);
  const [monthLoading, setMonthLoading] = useState(false);

  useEffect(() => {
    if (!settings) return;
    if (typeof window !== 'undefined' && (new URLSearchParams(window.location.search).has('from') || new URLSearchParams(window.location.search).has('to'))) return;
    if (appliedDefaultPeriod.current === settings.default_period) return;
    appliedDefaultPeriod.current = settings.default_period;
    const range = getRangeForKey(settings.default_period as DateRangeKey);
    setDateFrom(range.from);
    setDateTo(range.to);
  }, [settings, settings?.default_period]);

  useEffect(() => {
    let cancelled = false;
    listBranches({ page_size: 100 }).then((res) => {
      if (!cancelled) setBranches(res.results);
    });
    getDashboardAlerts().then((res) => {
      if (!cancelled) setAlerts(res);
    }).catch(() => undefined);
    getDashboardActivity().then((res) => {
      if (!cancelled) setActivities(res.activities);
    }).catch(() => undefined);
    return () => { cancelled = true; };
  }, []);

  useEffect(() => {
    if (isScoped && me?.branch && !branch) {
      setBranch(String(me.branch));
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isScoped, me?.branch, branches]);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    const params: Record<string, string | number | undefined> = {};
    if (branch) params.branch = branch;
    if (dateFrom) params.date_from = dateFrom;
    if (dateTo) params.date_to = dateTo;
    getDashboardSummary(params)
      .then((res) => { if (!cancelled) setData(res); })
      .catch((err) => { if (!cancelled) toast('error', err.message); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [branch, dateFrom, dateTo, reloadKey]);

  useEffect(() => {
    if (!monthA || !monthB) return;
    let cancelled = false;
    setMonthLoading(true);
    const a = monthRange(monthA);
    const b = monthRange(monthB);
    const paramsA: Record<string, string | number | undefined> = { date_from: a.from, date_to: a.to };
    const paramsB: Record<string, string | number | undefined> = { date_from: b.from, date_to: b.to };
    if (branch) { paramsA.branch = branch; paramsB.branch = branch; }
    Promise.all([getDashboardSummary(paramsA), getDashboardSummary(paramsB)])
      .then(([ra, rb]) => {
        if (cancelled) return;
        setMonthDataA(ra);
        setMonthDataB(rb);
      })
      .catch((err) => { if (!cancelled) toast('error', err.message); })
      .finally(() => { if (!cancelled) setMonthLoading(false); });
    return () => { cancelled = true; };
  }, [monthA, monthB, branch]);

  return (
    <AppShell>
      <div className="space-y-6">
        {/* Period + Branch Filter */}
        <div className="flex flex-wrap items-center gap-4">
          <DateRangeToolbar
            from={dateFrom}
            to={dateTo}
            onChange={(f, t) => { setDateFrom(f); setDateTo(t); }}
          />
          <Select
            value={branch}
            onChange={(e) => setBranch(e.target.value)}
            options={branches.length > 1
              ? [{ value: '', label: 'كل الفروع' }, ...branches.map((b) => ({ value: b.id, label: b.name }))]
              : branches.map((b) => ({ value: b.id, label: b.name }))}
            className="w-full sm:w-48"
          />
        </div>

        {alerts && <AlertsPanel alerts={alerts} />}

        {loading ? (
          <div className="flex items-center justify-center py-20">
            <Spinner size={40} />
          </div>
        ) : data ? (
          <>
            {/* Stat Cards */}
            <div className="grid grid-cols-1 md:grid-cols-3 lg:grid-cols-6 gap-4">
              <StatCard
                icon={<Banknote size={22} />}
                iconBg="bg-brand-50 text-brand-600 dark:bg-brand-500/15 dark:text-brand-400"
                label="إجمالي المبيعات"
                value={formatCurrency(data.total_sales)}
                sub={deltaText(data.sales_delta_pct)}
              />
              <StatCard
                icon={<ReceiptText size={22} />}
                iconBg="bg-red-50 text-red-600 dark:bg-red-500/15 dark:text-red-400"
                label="إجمالي المصاريف"
                value={formatCurrency(data.total_expenses)}
                sub={deltaText(data.expenses_delta_pct)}
              />
              <StatCard
                icon={<TrendingUp size={22} />}
                iconBg={data.net >= 0 ? 'bg-gold-400/20 text-gold-700 dark:text-gold-400' : 'bg-red-50 text-red-600 dark:bg-red-500/15 dark:text-red-400'}
                label="صافي الفترة"
                value={formatCurrency(data.net)}
                sub={deltaText(data.net_delta_pct)}
              />
              <StatCard
                icon={<TrendingUp size={22} />}
                iconBg={data.gross_profit >= 0 ? 'bg-emerald-50 text-emerald-600 dark:bg-emerald-500/15 dark:text-emerald-400' : 'bg-red-50 text-red-600 dark:bg-red-500/15 dark:text-red-400'}
                label="الربح الإجمالي"
                value={formatCurrency(data.gross_profit)}
              />
              <StatCard
                icon={<Percent size={22} />}
                iconBg="bg-blue-50 text-blue-600 dark:bg-blue-500/15 dark:text-blue-400"
                label="هامش الربح"
                value={`${data.margin_pct}%`}
              />
              <StatCard
                icon={<Store size={22} />}
                iconBg="bg-emerald-50 text-emerald-600 dark:bg-emerald-500/15 dark:text-emerald-400"
                label="عدد الفروع"
                value={data.branches_count}
              />
              <StatCard
                icon={<Truck size={22} />}
                iconBg="bg-blue-50 text-blue-600 dark:bg-blue-500/15 dark:text-blue-400"
                label="عدد الموردين"
                value={data.suppliers_count}
              />
            </div>

            {/* Charts */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              <Card title="المبيعات والمصاريف" subtitle="نظرة عامة على الأداء المالي">
                <SalesChart data={data.chart_data} />
              </Card>
              <Card title="الربح والتكلفة" subtitle="إجمالي الربح مقابل تكلفة البضاعة المباعة">
                <ProfitChart data={data.chart_data} />
              </Card>
            </div>

            {/* Comparison + Recent Activity */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              <Card title="المبيعات مقارنة بالفترة السابقة" subtitle="نفس أيام الفترة السابقة مقابل الحالية">
                <ComparisonChart current={data.chart_data} previous={data.chart_previous} />
              </Card>
              <RecentActivity activities={activities} />
            </div>

            {/* Month-to-Month Comparison */}
            <Card
              title="مقارنة بين شهرين"
              subtitle="اختر شهرين لتقارن بين مبيعاتهما ومصاريفهما وربحهما يوماً بيوم"
              action={
                <div className="flex flex-wrap items-center gap-2">
                  <input
                    type="month"
                    value={monthA}
                    onChange={(e) => e.target.value && setMonthA(e.target.value)}
                    className="rounded-xl border border-sand-300 bg-surface px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500/40"
                  />
                  <GitCompareArrows size={18} className="text-neutral-400" />
                  <input
                    type="month"
                    value={monthB}
                    onChange={(e) => e.target.value && setMonthB(e.target.value)}
                    className="rounded-xl border border-sand-300 bg-surface px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500/40"
                  />
                </div>
              }
            >
              {monthLoading ? (
                <div className="flex items-center justify-center py-16">
                  <Spinner size={36} />
                </div>
              ) : monthDataA && monthDataB ? (
                <>
                  <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-6">
                    <div className="p-4 rounded-2xl border border-emerald-200 bg-emerald-50/50">
                      <div className="flex items-center justify-between mb-1">
                        <p className="text-sm text-emerald-700">إجمالي المبيعات</p>
                        <Badge variant={monthDataB.total_sales >= monthDataA.total_sales ? 'success' : 'neutral'}>
                          {compareLabel(monthDataA.total_sales, monthDataB.total_sales)}
                        </Badge>
                      </div>
                      <div className="flex items-end justify-between gap-2">
                        <div>
                          <p className="text-[11px] text-neutral-400">{monthLabel(monthA)}</p>
                          <p className="text-xl font-bold text-emerald-700">{formatCurrency(monthDataA.total_sales)}</p>
                        </div>
                        <div className="text-left">
                          <p className="text-[11px] text-neutral-400">{monthLabel(monthB)}</p>
                          <p className="text-xl font-bold text-neutral-800">{formatCurrency(monthDataB.total_sales)}</p>
                        </div>
                      </div>
                    </div>

                    <div className="p-4 rounded-2xl border border-red-200 bg-red-50/50">
                      <div className="flex items-center justify-between mb-1">
                        <p className="text-sm text-red-700">إجمالي المصاريف</p>
                        <Badge variant={monthDataB.total_expenses <= monthDataA.total_expenses ? 'success' : 'neutral'}>
                          {compareLabel(monthDataA.total_expenses, monthDataB.total_expenses)}
                        </Badge>
                      </div>
                      <div className="flex items-end justify-between gap-2">
                        <div>
                          <p className="text-[11px] text-neutral-400">{monthLabel(monthA)}</p>
                          <p className="text-xl font-bold text-red-700">{formatCurrency(monthDataA.total_expenses)}</p>
                        </div>
                        <div className="text-left">
                          <p className="text-[11px] text-neutral-400">{monthLabel(monthB)}</p>
                          <p className="text-xl font-bold text-neutral-800">{formatCurrency(monthDataB.total_expenses)}</p>
                        </div>
                      </div>
                    </div>

                    <div className="p-4 rounded-2xl border border-brand-200 bg-brand-50/50">
                      <div className="flex items-center justify-between mb-1">
                        <p className="text-sm text-brand-700">صافي الفترة</p>
                        <Badge variant={monthDataB.net >= monthDataA.net ? 'success' : 'neutral'}>
                          {compareLabel(monthDataA.net, monthDataB.net)}
                        </Badge>
                      </div>
                      <div className="flex items-end justify-between gap-2">
                        <div>
                          <p className="text-[11px] text-neutral-400">{monthLabel(monthA)}</p>
                          <p className="text-xl font-bold text-brand-700">{formatCurrency(monthDataA.net)}</p>
                        </div>
                        <div className="text-left">
                          <p className="text-[11px] text-neutral-400">{monthLabel(monthB)}</p>
                          <p className="text-xl font-bold text-neutral-800">{formatCurrency(monthDataB.net)}</p>
                        </div>
                      </div>
                    </div>
                  </div>

                  <div className="flex items-center justify-between mb-3">
                    <p className="text-sm font-medium text-neutral-600">المبيعات اليومية خلال الشهرين</p>
                  </div>
                  <MonthCompareChart monthA={monthA} monthB={monthB} seriesA={monthDataA.chart_data} seriesB={monthDataB.chart_data} />
                </>
              ) : (
                <div className="text-center py-12 text-neutral-400">
                  <p>اختر شهرين لعرض المقارنة</p>
                </div>
              )}
            </Card>

            {data.top_fabrics.length > 0 && (
              <Card title="أفضل الأصناف ربحية" subtitle="أعلى 5 أصناف حسب الربح في الفترة">
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="text-right text-neutral-500 border-b border-sand-200">
                        <th className="py-2 px-3 font-medium">القماش</th>
                        <th className="py-2 px-3 font-medium">الكود</th>
                        <th className="py-2 px-3 font-medium">المباع (يارة)</th>
                        <th className="py-2 px-3 font-medium">الإيراد</th>
                        <th className="py-2 px-3 font-medium">التكلفة</th>
                        <th className="py-2 px-3 font-medium">الربح</th>
                      </tr>
                    </thead>
                    <tbody>
                      {data.top_fabrics.map((f) => (
                        <tr key={f.fabric} className="border-b border-sand-100 last:border-0">
                          <td className="py-2 px-3 text-neutral-800">{f.fabric_name}</td>
                          <td className="py-2 px-3 text-neutral-500">{f.fabric_code}</td>
                          <td className="py-2 px-3 text-neutral-600">{formatNumber(f.yards_sold)}</td>
                          <td className="py-2 px-3 text-neutral-800">{formatCurrency(f.revenue)}</td>
                          <td className="py-2 px-3 text-neutral-800">{formatCurrency(f.cogs)}</td>
                          <td className={`py-2 px-3 font-medium ${f.profit >= 0 ? 'text-emerald-600' : 'text-red-600'}`}>
                            {formatCurrency(f.profit)}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </Card>
            )}
          </>
        ) : (
          <div className="text-center py-20 text-neutral-400">
            <p>حدث خطأ أثناء تحميل البيانات</p>
            <Button variant="secondary" className="mt-4" onClick={() => setReloadKey((k) => k + 1)}>
              إعادة المحاولة
            </Button>
          </div>
        )}
      </div>
    </AppShell>
  );
}
