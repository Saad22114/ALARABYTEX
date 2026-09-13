'use client';

import { useState, useEffect, useRef } from 'react';
import AppShell from '@/components/layout/AppShell';
import StatCard from '@/components/ui/StatCard';
import Card from '@/components/ui/Card';
import Button from '@/components/ui/Button';
import Select from '@/components/ui/Select';
import DateRangePicker from '@/components/ui/DateRangePicker';
import SalesChart from '@/components/dashboard/SalesChart';
import Spinner from '@/components/ui/Spinner';
import { Banknote, ReceiptText, TrendingUp, Store, Truck } from 'lucide-react';
import { DashboardSummary } from '@/types';
import { getDashboardSummary } from '@/services/dashboard';
import { listBranches } from '@/services/branches';
import { Branch } from '@/types';
import { formatCurrency } from '@/lib/format';
import { DATE_PERIODS } from '@/lib/constants';
import { useToast } from '@/components/ui/Toast';
import { useSettings } from '@/components/providers/SettingsProvider';

export default function DashboardPage() {
  const { toast } = useToast();
  const { settings } = useSettings();
  const [period, setPeriod] = useState('today');
  const userPicked = useRef(false);
  const [branch, setBranch] = useState('');
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');
  const [data, setData] = useState<DashboardSummary | null>(null);
  const [branches, setBranches] = useState<Branch[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (settings && !userPicked.current) {
      setPeriod(settings.default_period);
    }
  }, [settings, settings?.default_period]);

  useEffect(() => {
    let cancelled = false;
    listBranches({ page_size: 100 }).then((res) => {
      if (!cancelled) setBranches(res.results);
    });
    return () => { cancelled = true; };
  }, []);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    const params: Record<string, string | number | undefined> = { period };
    if (branch) params.branch = branch;
    if (period === 'custom') {
      params.date_from = dateFrom;
      params.date_to = dateTo;
    }
    getDashboardSummary(params)
      .then((res) => { if (!cancelled) setData(res); })
      .catch((err) => { if (!cancelled) toast('error', err.message); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [period, branch, dateFrom, dateTo]);

  return (
    <AppShell>
      <div className="space-y-6">
        {/* Period + Branch Filter */}
        <div className="flex flex-wrap items-center gap-4">
<div className="flex flex-wrap gap-2">
            {DATE_PERIODS.map((p) => (
              <button
                key={p.value}
                onClick={() => setPeriod(p.value)}
                className={`px-3 sm:px-4 py-2 rounded-xl text-sm font-medium transition-all duration-150 ${
                  period === p.value
                    ? 'bg-brand-600 text-white shadow-sm'
                    : 'bg-surface text-neutral-600 border border-sand-200 hover:bg-sand-50'
                }`}
              >
                {p.label}
              </button>
            ))}
          </div>
          {period === 'custom' && (
            <DateRangePicker
              from={dateFrom}
              to={dateTo}
              onChangeFrom={setDateFrom}
              onChangeTo={setDateTo}
            />
          )}
          <Select
            value={branch}
            onChange={(e) => setBranch(e.target.value)}
            options={[{ value: '', label: 'كل الفروع' }, ...branches.map((b) => ({ value: b.id, label: b.name }))]}
            className="w-full sm:w-48"
          />
        </div>

        {loading ? (
          <div className="flex items-center justify-center py-20">
            <Spinner size={40} />
          </div>
        ) : data ? (
          <>
            {/* Stat Cards */}
            <div className="grid grid-cols-1 md:grid-cols-3 lg:grid-cols-5 gap-4">
              <StatCard
                icon={<Banknote size={22} />}
                iconBg="bg-brand-50 text-brand-600 dark:bg-brand-500/15 dark:text-brand-400"
                label="إجمالي المبيعات"
                value={formatCurrency(data.total_sales)}
              />
              <StatCard
                icon={<ReceiptText size={22} />}
                iconBg="bg-red-50 text-red-600 dark:bg-red-500/15 dark:text-red-400"
                label="إجمالي المصاريف"
                value={formatCurrency(data.total_expenses)}
              />
              <StatCard
                icon={<TrendingUp size={22} />}
                iconBg={data.net >= 0 ? 'bg-gold-400/20 text-gold-700 dark:text-gold-400' : 'bg-red-50 text-red-600 dark:bg-red-500/15 dark:text-red-400'}
                label="صافي الفترة"
                value={formatCurrency(data.net)}
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

            {/* Chart */}
            <Card title="المبيعات والمصاريف" subtitle="نظرة عامة على الأداء المالي">
              <SalesChart data={data.chart_data} />
            </Card>
          </>
        ) : (
          <div className="text-center py-20 text-neutral-400">
            <p>حدث خطأ أثناء تحميل البيانات</p>
            <Button variant="secondary" className="mt-4" onClick={() => setPeriod(period)}>
              إعادة المحاولة
            </Button>
          </div>
        )}
      </div>
    </AppShell>
  );
}
