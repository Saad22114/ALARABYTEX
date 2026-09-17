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
import AlertsPanel from '@/components/dashboard/AlertsPanel';
import RecentActivity from '@/components/dashboard/RecentActivity';
import Spinner from '@/components/ui/Spinner';
import { Banknote, ReceiptText, TrendingUp, Percent, Store, Truck } from 'lucide-react';
import { DashboardActivityItem, DashboardAlertsResult, DashboardSummary } from '@/types';
import { getDashboardActivity, getDashboardAlerts, getDashboardSummary } from '@/services/dashboard';
import { listBranches } from '@/services/branches';
import { Branch } from '@/types';
import { formatCurrency, formatNumber } from '@/lib/format';
import { useToast } from '@/components/ui/Toast';
import { useSettings } from '@/components/providers/SettingsProvider';
import { useUrlState } from '@/lib/useUrlState';

function deltaText(pct: number | null | undefined): string {
  if (pct === null || pct === undefined) return '';
  const sign = pct >= 0 ? '+' : '−';
  return `${sign}${Math.abs(pct)}% عن الفترة السابقة`;
}

export default function DashboardPage() {
  const { toast } = useToast();
  const { settings } = useSettings();
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
            options={[{ value: '', label: 'كل الفروع' }, ...branches.map((b) => ({ value: b.id, label: b.name }))]}
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
