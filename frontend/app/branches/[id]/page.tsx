'use client';

import { useState, useEffect } from 'react';
import { useParams, useRouter } from 'next/navigation';
import AppShell from '@/components/layout/AppShell';
import Card from '@/components/ui/Card';
import Button from '@/components/ui/Button';
import Table, { Th, Td, Tr } from '@/components/ui/Table';
import Modal from '@/components/ui/Modal';
import ConfirmDialog from '@/components/ui/ConfirmDialog';
import BranchForm from '@/components/forms/BranchForm';
import Spinner from '@/components/ui/Spinner';
import Badge from '@/components/ui/Badge';
import Switch from '@/components/ui/Switch';
import EmptyState from '@/components/ui/EmptyState';
import StatCard from '@/components/ui/StatCard';
import SalesChart from '@/components/dashboard/SalesChart';
import DateRangeToolbar, { currentMonthRange, toISODate } from '@/components/ui/DateRangeToolbar';
import BranchPricingPanel from '@/components/branches/BranchPricingPanel';
import {
  ArrowRight, Pencil, Store, Power, PowerOff, LayoutDashboard, Boxes, Users,
  Receipt, CalendarDays, BarChart3, AlertTriangle, Download, Printer, TrendingUp,
  TrendingDown, CalendarCheck, CalendarX2, Sparkles, ArrowUpDown, ArrowDownToLine, ArrowUpFromLine, Tags,
} from 'lucide-react';
import { Branch, DailySale, Expense, Employee, SaleStockResult, DashboardSummary, SalesReportData, InventoryReportRow, StockBalanceResult, InventoryMovementReportRow, SalesByEmployeeResult } from '@/types';
import { getBranch, updateBranch } from '@/services/branches';
import { listSales } from '@/services/sales';
import { listExpenses } from '@/services/expenses';
import { listEmployees } from '@/services/employees';
import { getSaleStock } from '@/services/sales';
import { getSalesByEmployee } from '@/services/sales';
import { getDashboardSummary } from '@/services/dashboard';
import { getSalesReport, getInventoryReport, getInventoryMovementsReport } from '@/services/reports';
import { getStockBalances } from '@/services/warehouses';
import { API_URL } from '@/services/api';
import { formatCurrency, formatDate, formatNumber } from '@/lib/format';
import { PAYMENT_METHODS_MAP } from '@/lib/constants';
import { useToast } from '@/components/ui/Toast';

type Tab = 'dashboard' | 'stock' | 'employees' | 'expenses' | 'sales' | 'sales-employees' | 'movements' | 'reports' | 'pricing';

const tabs: { value: Tab; label: string; icon: React.ReactNode }[] = [
  { value: 'dashboard', label: 'نظرة عامة', icon: <LayoutDashboard size={16} /> },
  { value: 'stock', label: 'المخزون', icon: <Boxes size={16} /> },
  { value: 'pricing', label: 'أسعار الفرع', icon: <Tags size={16} /> },
  { value: 'employees', label: 'الموظفون', icon: <Users size={16} /> },
  { value: 'expenses', label: 'المصاريف', icon: <Receipt size={16} /> },
  { value: 'sales', label: 'المبيعات باليوم', icon: <CalendarDays size={16} /> },
  { value: 'sales-employees', label: 'مبيعات الموظفين', icon: <Users size={16} /> },
  { value: 'movements', label: 'حركة المخزون', icon: <ArrowUpDown size={16} /> },
  { value: 'reports', label: 'التقارير', icon: <BarChart3 size={16} /> },
];

const UNIT_LABEL: Record<string, string> = {
  yard: 'ياردة',
  roll: 'طاقة',
};

function previousRange(from: string, to: string): { from: string; to: string } {
  const toDate = new Date(`${from}T00:00:00`);
  const days = Math.round((new Date(`${to}T00:00:00`).getTime() - toDate.getTime()) / 86400000) + 1;
  const prevTo = new Date(toDate.getTime() - 86400000);
  const prevFrom = new Date(prevTo.getTime() - (days - 1) * 86400000);
  return { from: toISODate(prevFrom), to: toISODate(prevTo) };
}

export default function BranchDetailPage() {
  const { toast } = useToast();
  const params = useParams();
  const router = useRouter();
  const id = Number(params.id);

  const [branch, setBranch] = useState<Branch | null>(null);
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState<Tab>('dashboard');
  const [editOpen, setEditOpen] = useState(false);
  const [stopOpen, setStopOpen] = useState(false);
  const [toggleLoading, setToggleLoading] = useState(false);

  // dashboard
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [prevSummary, setPrevSummary] = useState<DashboardSummary | null>(null);
  const [summaryLoading, setSummaryLoading] = useState(false);
  const [inventoryForAlerts, setInventoryForAlerts] = useState<InventoryReportRow[] | null>(null);

  // shared date range (defaults to current month)
  const [dateFrom, setDateFrom] = useState(() => currentMonthRange().from);
  const [dateTo, setDateTo] = useState(() => currentMonthRange().to);

  // stock
  const [saleStock, setSaleStock] = useState<SaleStockResult | null>(null);
  const [stockData, setStockData] = useState<StockBalanceResult | null>(null);
  const [stockLoading, setStockLoading] = useState(false);

  // employees / expenses / sales
  const [employees, setEmployees] = useState<Employee[] | null>(null);
  const [employeesLoading, setEmployeesLoading] = useState(false);
  const [expenses, setExpenses] = useState<Expense[] | null>(null);
  const [expensesLoading, setExpensesLoading] = useState(false);
  const [sales, setSales] = useState<DailySale[] | null>(null);
  const [salesLoading, setSalesLoading] = useState(false);
  const [selectedSale, setSelectedSale] = useState<DailySale | null>(null);

  // sales by employee
  const [byEmployee, setByEmployee] = useState<SalesByEmployeeResult | null>(null);
  const [byEmployeeLoading, setByEmployeeLoading] = useState(false);

  // movements
  const [movements, setMovements] = useState<InventoryMovementReportRow[] | null>(null);
  const [movementsTotals, setMovementsTotals] = useState<{ in: number; out: number; count: number } | null>(null);
  const [movementsLoading, setMovementsLoading] = useState(false);
  // inventory load - used by alerts
  const loadInventoryRows = async (warehouse?: number | null): Promise<InventoryReportRow[]> => {
    if (warehouse == null) return [];
    const res = await getInventoryReport({ warehouse });
    return res.items || [];
  };
  const [reportsData, setReportsData] = useState<SalesReportData[] | null>(null);
  const [inventoryData, setInventoryData] = useState<InventoryReportRow[] | null>(null);
  const [reportsLoading, setReportsLoading] = useState(false);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    getBranch(id)
      .then((b) => { if (!cancelled) setBranch(b); })
      .catch((err) => { if (!cancelled) toast('error', err.message); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [id]);

  const loadDashboard = () => {
    let cancelled = false;
    setSummaryLoading(true);
    const prev = previousRange(dateFrom, dateTo);
    Promise.all([
      getDashboardSummary({ branch: id, period: 'custom', date_from: dateFrom, date_to: dateTo }),
      getDashboardSummary({ branch: id, period: 'custom', date_from: prev.from, date_to: prev.to }),
      getSaleStock(id),
    ])
      .then(async ([cur, p, sr]) => {
        if (cancelled) return;
        const inv = await loadInventoryRows(sr.warehouse);
        if (!cancelled) {
          setSummary(cur);
          setPrevSummary(p);
          setSaleStock(sr);
          setInventoryForAlerts(inv);
        }
      })
      .catch((err: any) => { if (!cancelled) toast('error', err.message); })
      .finally(() => { if (!cancelled) setSummaryLoading(false); });
    return () => { cancelled = true; };
  };

  const loadStock = () => {
    let cancelled = false;
    setStockLoading(true);
    getSaleStock(id)
      .then(async (sr) => {
        if (cancelled) return;
        setSaleStock(sr);
        if (sr.warehouse) {
          const bal = await getStockBalances({ warehouse: sr.warehouse });
          if (!cancelled) setStockData(bal);
        }
      })
      .catch((err: any) => { if (!cancelled) toast('error', err.message); })
      .finally(() => { if (!cancelled) setStockLoading(false); });
    return () => { cancelled = true; };
  };

  const loadMovements = () => {
    let cancelled = false;
    setMovementsLoading(true);
    const ensureWarehouse = saleStock?.warehouse != null
      ? Promise.resolve(saleStock)
      : getSaleStock(id);
    ensureWarehouse
      .then((sr) => {
        setSaleStock(sr);
        if (sr.warehouse == null) return { movements: [], totals: { in: 0, out: 0, count: 0 } };
        return getInventoryMovementsReport({ warehouse: sr.warehouse, date_from: dateFrom, date_to: dateTo });
      })
      .then((res) => {
        if (!cancelled) {
          setMovements(res.movements || []);
          setMovementsTotals(res.totals || { in: 0, out: 0, count: 0 });
        }
      })
      .catch((err: any) => { if (!cancelled) toast('error', err.message); })
      .finally(() => { if (!cancelled) setMovementsLoading(false); });
    return () => { cancelled = true; };
  };

  const loadEmployees = () => {
    let cancelled = false;
    setEmployeesLoading(true);
    listEmployees({ branch: id, page_size: 100 })
      .then((res) => { if (!cancelled) setEmployees(res.results); })
      .catch((err: any) => { if (!cancelled) toast('error', err.message); })
      .finally(() => { if (!cancelled) setEmployeesLoading(false); });
    return () => { cancelled = true; };
  };

  const loadExpenses = () => {
    let cancelled = false;
    setExpensesLoading(true);
    listExpenses({ branch: id, date_from: dateFrom, date_to: dateTo, page_size: 100 })
      .then((res) => { if (!cancelled) setExpenses(res.results); })
      .catch((err: any) => { if (!cancelled) toast('error', err.message); })
      .finally(() => { if (!cancelled) setExpensesLoading(false); });
    return () => { cancelled = true; };
  };

  const loadSales = () => {
    let cancelled = false;
    setSalesLoading(true);
    listSales({ branch: id, date_from: dateFrom, date_to: dateTo, page_size: 200 })
      .then((res) => { if (!cancelled) setSales(res.results); })
      .catch((err: any) => { if (!cancelled) toast('error', err.message); })
      .finally(() => { if (!cancelled) setSalesLoading(false); });
    return () => { cancelled = true; };
  };

  const loadByEmployee = () => {
    let cancelled = false;
    setByEmployeeLoading(true);
    getSalesByEmployee({ branch: id, date_from: dateFrom, date_to: dateTo })
      .then((res) => { if (!cancelled) setByEmployee(res); })
      .catch((err: any) => { if (!cancelled) toast('error', err.message); })
      .finally(() => { if (!cancelled) setByEmployeeLoading(false); });
    return () => { cancelled = true; };
  };

  const loadReports = () => {
    let cancelled = false;
    setReportsLoading(true);
    const ensureWarehouse = saleStock?.warehouse != null
      ? Promise.resolve(saleStock)
      : getSaleStock(id);
    ensureWarehouse
      .then((sr) => {
        const invParams: Record<string, string | number | undefined | null> = {
          warehouse: sr.warehouse || undefined,
        };
        return Promise.all([
          getSalesReport({ branch: id, date_from: dateFrom, date_to: dateTo }),
          getInventoryReport(invParams),
        ]);
      })
      .then(([salesRes, inv]) => {
        if (!cancelled) {
          setSaleStock((prev) => prev || saleStock || null);
          setReportsData(salesRes.sales || []);
          setInventoryData(inv.items || []);
        }
      })
      .catch((err: any) => { if (!cancelled) toast('error', err.message); })
      .finally(() => { if (!cancelled) setReportsLoading(false); });
    return () => { cancelled = true; };
  };

  useEffect(() => {
    if (tab === 'dashboard') return loadDashboard();
  }, [tab, dateFrom, dateTo, id]);

  useEffect(() => {
    if (tab === 'stock') return loadStock();
  }, [tab, id]);

  useEffect(() => {
    if (tab === 'movements') return loadMovements();
  }, [tab, dateFrom, dateTo, id]);

  useEffect(() => {
    if (tab === 'employees' && employees === null) return loadEmployees();
  }, [tab, id]);

  useEffect(() => {
    if (tab === 'expenses') return loadExpenses();
  }, [tab, dateFrom, dateTo, id]);

  useEffect(() => {
    if (tab === 'sales') return loadSales();
  }, [tab, dateFrom, dateTo, id]);

  useEffect(() => {
    if (tab === 'sales-employees') return loadByEmployee();
  }, [tab, dateFrom, dateTo, id]);

  useEffect(() => {
    if (tab === 'reports') return loadReports();
  }, [tab, dateFrom, dateTo, id]);

  const handleUpdate = async (d: Partial<Branch>) => {
    await updateBranch(id, d);
    toast('success', 'تم تحديث الفرع بنجاح');
    setEditOpen(false);
    const updated = await getBranch(id);
    setBranch(updated);
  };

  const handleToggle = async (next: boolean) => {
    setToggleLoading(true);
    try {
      const updated = await updateBranch(id, { is_active: next });
      setBranch(updated);
      toast('success', next ? 'تم تشغيل الفرع' : 'تم إيقاف الفرع');
    } catch (err: any) {
      toast('error', err.message);
    } finally {
      setToggleLoading(false);
      setStopOpen(false);
    }
  };

  if (loading) return <AppShell><div className="flex justify-center py-20"><Spinner size={40} /></div></AppShell>;
  if (!branch) return <AppShell><div className="text-center py-20 text-neutral-400">الفرع غير موجود</div></AppShell>;

  const salesTotal = sales?.reduce((s, x) => s + x.total_sales, 0) ?? 0;
  const expensesTotal = expenses?.reduce((s, x) => s + x.amount, 0) ?? 0;
  const assignedTotal = byEmployee?.items.reduce((s, r) => s + r.total_sales, 0) ?? 0;

  return (
    <AppShell>
      <div className="space-y-6">
        <div className="flex items-center justify-between no-print">
          <Button variant="ghost" onClick={() => router.push('/branches')}>
            <ArrowRight size={18} />
            عودة إلى الفروع
          </Button>
          <div className="flex items-center gap-3">
            {branch.is_active ? (
              <Button variant="secondary" onClick={() => setStopOpen(true)}>
                <PowerOff size={16} />
                إيقاف الفرع
              </Button>
            ) : (
              <Button onClick={() => handleToggle(true)} loading={toggleLoading}>
                <Power size={16} />
                تشغيل الفرع
              </Button>
            )}
            <Button variant="secondary" onClick={() => setEditOpen(true)}>
              <Pencil size={16} />
              تعديل
            </Button>
          </div>
        </div>

        {/* Branch Info */}
        <Card>
          <div className="flex items-start justify-between flex-wrap gap-4">
            <div className="flex items-center gap-4">
              <span className="p-3 rounded-2xl bg-brand-50 text-brand-600">
                <Store size={26} />
              </span>
              <div>
                <h1 className="text-xl font-bold text-neutral-800">{branch.name}</h1>
                <p className="text-sm text-neutral-500">
                  <span className="font-mono bg-sand-100 px-2 py-0.5 rounded">{branch.code}</span>
                  {branch.city && <> · {branch.city}</>}
                </p>
              </div>
            </div>
            <Badge variant={branch.is_active ? 'success' : 'danger'}>
              {branch.is_active ? 'يعمل' : 'موقوف'}
            </Badge>
          </div>
          {branch.notes && <p className="mt-3 text-sm text-neutral-500">{branch.notes}</p>}
        </Card>

        {/* Tabs */}
        <div className="flex flex-wrap gap-2">
          {tabs.map((t) => (
            <button
              key={t.value}
              onClick={() => setTab(t.value)}
              className={`inline-flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-medium transition-all duration-150 ${
                tab === t.value
                  ? 'bg-brand-600 text-white shadow-sm'
                  : 'bg-surface text-neutral-600 border border-sand-200 hover:bg-sand-50'
              }`}
            >
              {t.icon}
              {t.label}
            </button>
          ))}
        </div>

        {tab === 'dashboard' && (
          <>
            <Card className="!p-4">
              <DateRangeToolbar from={dateFrom} to={dateTo} onChange={(f, t) => { setDateFrom(f); setDateTo(t); }} />
            </Card>
            {summaryLoading && !summary ? (
              <Card><div className="flex justify-center py-12"><Spinner size={32} /></div></Card>
            ) : summary ? (() => {
              const chart = summary.chart_data || [];
              const days = chart.length;
              const activeDays = chart.filter((d) => d.sales > 0);
              const avgDaily = days ? summary.total_sales / days : 0;
              const best = activeDays.length ? activeDays.reduce((a, b) => (b.sales > a.sales ? b : a)) : null;
              const worst = activeDays.length ? activeDays.reduce((a, b) => (b.sales < a.sales ? b : a)) : null;
              const growth = prevSummary && prevSummary.total_sales > 0
                ? ((summary.total_sales - prevSummary.total_sales) / prevSummary.total_sales) * 100
                : null;
              const todayPoint = chart.find((d) => d.date === toISODate(new Date()));
              const lowStockItems = (inventoryForAlerts || []).filter((i) => i.low_stock);
              const deficitDays = chart.filter((d) => d.expenses > d.sales);
              const alertsEnabled = branch.is_active;
              const alerts = [
                ...(alertsEnabled && todayPoint && todayPoint.sales === 0
                  ? [{ type: 'danger' as const, icon: <CalendarX2 size={15} />, text: 'لا توجد مبيعات مسجلة لليوم الحالي' }]
                  : []),
                ...(!alertsEnabled
                  ? [{ type: 'danger' as const, icon: <PowerOff size={15} />, text: 'الفرع موقوف حاليًا — لا يمكن تسجيل مبيعات أو مصاريف جديدة' }]
                  : []),
                ...(summary.total_sales === 0
                  ? [{ type: 'warning' as const, icon: <AlertTriangle size={15} />, text: 'لا توجد مبيعات في الفترة المحددة' }]
                  : []),
                ...(deficitDays.length > 0
                  ? [{ type: 'warning' as const, icon: <AlertTriangle size={15} />, text: `${deficitDays.length} يوم بها مصاريف تتجاوز المبيعات (عجز صافي)` }]
                  : []),
                ...(lowStockItems.length > 0
                  ? [{ type: 'warning' as const, icon: <AlertTriangle size={15} />, text: `${lowStockItems.length} ${lowStockItems.length === 1 ? 'صنف تحت' : 'أصناف تحت'} الحد الأدنى في مخزون الفرع` }]
                  : []),
              ];
              return (
                <>
                  <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
                    <StatCard icon={<BarChart3 size={20} />} label="المبيعات" value={formatCurrency(summary.total_sales)} sub="إجمالي الفترة" />
                    <StatCard icon={<Receipt size={20} />} iconBg="bg-amber-50 text-amber-600" label="المصاريف" value={formatCurrency(summary.total_expenses)} sub="إجمالي الفترة" />
                    <StatCard
                      icon={<AlertTriangle size={20} />}
                      iconBg={summary.net < 0 ? 'bg-red-50 text-red-600' : 'bg-emerald-50 text-emerald-600'}
                      label="الصافي"
                      value={formatCurrency(summary.net)}
                      sub="مبيعات − مصاريف"
                    />
                  </div>
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                    <StatCard icon={<Sparkles size={20} />} iconBg="bg-sky-50 text-sky-600" label="متوسط المبيعات اليومي" value={formatCurrency(avgDaily)} sub={`على ${days} يوم`} />
                    <StatCard icon={<CalendarCheck size={20} />} iconBg="bg-emerald-50 text-emerald-600" label="أفضل يوم" value={best ? formatCurrency(best.sales) : '-'} sub={best ? formatDate(best.date) : 'لا توجد مبيعات'} />
                    <StatCard icon={<CalendarX2 size={20} />} iconBg="bg-red-50 text-red-600" label="أضعف يوم" value={worst ? formatCurrency(worst.sales) : '-'} sub={worst ? formatDate(worst.date) : 'لا توجد مبيعات'} />
                    <StatCard
                      icon={growth != null && growth < 0 ? <TrendingDown size={20} /> : <TrendingUp size={20} />}
                      iconBg={growth != null && growth < 0 ? 'bg-red-50 text-red-600' : 'bg-emerald-50 text-emerald-600'}
                      label="النمو مقارنة بالفترة السابقة"
                      value={growth == null ? '-' : `${growth >= 0 ? '+' : ''}${growth.toFixed(1)}%`}
                      sub={prevSummary ? `السابقة: ${formatCurrency(prevSummary.total_sales)}` : 'لا توجد بيانات سابقة'}
                    />
                  </div>
                  {alerts.length > 0 && (
                    <Card title="تنبيهات ذكية">
                      <div className="space-y-2">
                        {alerts.map((a, i) => (
                          <div
                            key={i}
                            className={`flex items-center gap-3 text-sm rounded-xl p-3 ${
                              a.type === 'danger' ? 'bg-red-50 text-red-700' : 'bg-amber-50 text-amber-700'
                            }`}
                          >
                            {a.icon}
                            {a.text}
                          </div>
                        ))}
                      </div>
                    </Card>
                  )}
                  {branch.monthly_sales_target > 0 && (() => {
                    const pct = branch.target_progress_pct ?? 0;
                    const remaining = branch.monthly_sales_target - branch.monthly_sales;
                    return (
                      <Card title="الهدف الشهري للمبيعات" subtitle="الكوتة المحددة لهذا الفرع">
                        <div className="flex items-center gap-4 flex-wrap">
                          <div className="flex-1 min-w-[220px]">
                            <div className="flex items-center justify-between text-sm mb-2">
                              <span className="text-neutral-500">التحصيل هذا الشهر</span>
                              <span className="font-semibold tabular-nums">
                                {formatCurrency(branch.monthly_sales)} / {formatCurrency(branch.monthly_sales_target)}
                              </span>
                            </div>
                            <div className="h-2.5 rounded-full bg-sand-100 overflow-hidden">
                              <div
                                className={`h-full rounded-full transition-all ${pct >= 100 ? 'bg-emerald-500' : 'bg-brand-500'}`}
                                style={{ width: `${Math.min(100, pct)}%` }}
                              />
                            </div>
                            <p className="text-xs text-neutral-400 mt-2">
                              {pct >= 100
                                ? `تم تجاوز الهدف بـ ${formatCurrency(-remaining)}`
                                : `المتبقي لتحقيق الهدف: ${formatCurrency(remaining)}`}
                            </p>
                          </div>
                          <div className="text-center px-4 shrink-0">
                            <p className={`text-2xl font-bold tabular-nums ${pct >= 100 ? 'text-emerald-600' : 'text-neutral-800'}`}>
                              {pct.toFixed(1)}%
                            </p>
                            <p className="text-xs text-neutral-400">من الهدف</p>
                          </div>
                        </div>
                      </Card>
                    );
                  })()}
                  <Card title="المبيعات والمصاريف اليومية">
                    <SalesChart data={summary.chart_data} />
                  </Card>
                </>
              );
            })() : null}
          </>
        )}

        {tab === 'stock' && (
          <Card title={saleStock?.warehouse_name ? `مخزون فرع «${branch.name}» — ${saleStock.warehouse_name}` : `مخزون فرع «${branch.name}»`}>
            {stockLoading ? (
              <div className="flex justify-center py-12"><Spinner size={32} /></div>
            ) : !stockData || stockData.items.length === 0 ? (
              <EmptyState title="لا يوجد مخزون" description="لا توجد أرصدة أقمشة مرتبطة بمخزن هذا الفرع" />
            ) : (
              <Table>
                <thead>
                  <tr>
                    <Th>القماش</Th>
                    <Th>الكود</Th>
                    <Th>الوحدة</Th>
                    <Th>الطاقات</Th>
                    <Th>الكمية</Th>
                    <Th>الحد الأدنى</Th>
                    <Th>الحالة</Th>
                  </tr>
                </thead>
                <tbody>
                  {stockData.items.map((item) => (
                    <Tr key={item.fabric}>
                      <Td className="font-medium">{item.fabric_name}</Td>
                      <Td><span className="font-mono text-xs bg-sand-100 px-2 py-1 rounded">{item.fabric_code}</span></Td>
                      <Td>{UNIT_LABEL[item.unit] || item.unit}</Td>
                      <Td className="tabular-nums">{formatNumber(item.rolls_available)}</Td>
                      <Td className="tabular-nums font-bold">{formatNumber(item.total_yards)}</Td>
                      <Td className="tabular-nums">{formatNumber(item.min_stock)}</Td>
                      <Td>
                        {item.low_stock ? (
                          <Badge variant="danger"><AlertTriangle size={12} /> تحت الحد الأدنى</Badge>
                        ) : (
                          <Badge variant="success">مناسب</Badge>
                        )}
                      </Td>
                    </Tr>
                  ))}
                </tbody>
              </Table>
            )}
          </Card>
        )}

        {tab === 'employees' && (
          <Card title={`الموظفون (${employees?.length ?? 0})`}>
            {employeesLoading && employees === null ? (
              <div className="flex justify-center py-12"><Spinner size={32} /></div>
            ) : !employees || employees.length === 0 ? (
              <EmptyState title="لا يوجد موظفون" description="لم يتم إضافة موظفين لهذا الفرع بعد" />
            ) : (
              <Table>
                <thead>
                  <tr>
                    <Th>الاسم</Th>
                    <Th>الهاتف</Th>
                    <Th>ملاحظات</Th>
                    <Th>الحالة</Th>
                  </tr>
                </thead>
                <tbody>
                  {employees.map((e) => (
                    <Tr key={e.id}>
                      <Td className="font-medium">{e.name}</Td>
                      <Td dir="ltr" className="text-left">{e.phone || '-'}</Td>
                      <Td className="text-xs text-neutral-500 max-w-[200px] truncate">{e.notes || '-'}</Td>
                      <Td>
                        <Badge variant={e.is_active ? 'success' : 'neutral'}>
                          {e.is_active ? 'نشط' : 'موقوف'}
                        </Badge>
                      </Td>
                    </Tr>
                  ))}
                </tbody>
              </Table>
            )}
          </Card>
        )}

        {tab === 'expenses' && (
          <div className="space-y-4">
            <Card className="!p-4">
              <DateRangeToolbar from={dateFrom} to={dateTo} onChange={(f, t) => { setDateFrom(f); setDateTo(t); }} />
            </Card>
            <Card title={`المصاريف (${expenses?.length ?? 0})`}>
            {expensesLoading && expenses === null ? (
              <div className="flex justify-center py-12"><Spinner size={32} /></div>
            ) : !expenses || expenses.length === 0 ? (
              <EmptyState title="لا توجد مصاريف" description="لا توجد مصاريف مسجلة لهذا الفرع" />
            ) : (
              <>
                <div className="p-3 border-b border-sand-100 flex items-center justify-between">
                  <span />
                  <span className="text-sm text-neutral-500">
                    الإجمالي: <span className="font-bold text-neutral-800 tabular-nums">{formatCurrency(expensesTotal)}</span>
                  </span>
                </div>
                <Table>
                  <thead>
                    <tr>
                      <Th>التاريخ</Th>
                      <Th>نوع المصروف</Th>
                      <Th>المبلغ</Th>
                      <Th>طريقة الدفع</Th>
                      <Th>الوصف</Th>
                    </tr>
                  </thead>
                  <tbody>
                    {expenses.map((e) => (
                      <Tr key={e.id}>
                        <Td>{formatDate(e.date)}</Td>
                        <Td>{e.category_name}</Td>
                        <Td className="tabular-nums font-medium">{formatCurrency(e.amount)}</Td>
                        <Td>{PAYMENT_METHODS_MAP[e.payment_method] || e.payment_method}</Td>
                        <Td className="text-xs text-neutral-500 max-w-[220px] truncate">{e.description || '-'}</Td>
                      </Tr>
                    ))}
                  </tbody>
                </Table>
              </>
            )}
          </Card>
          </div>
        )}

        {tab === 'sales' && (
          <div className="space-y-4">
            <Card className="!p-4">
              <DateRangeToolbar from={dateFrom} to={dateTo} onChange={(f, t) => { setDateFrom(f); setDateTo(t); }} />
            </Card>
            <Card title={`المبيعات باليوم — الإجمالي ${formatCurrency(salesTotal)}`}>
              {salesLoading && sales === null ? (
              <div className="flex justify-center py-12"><Spinner size={32} /></div>
            ) : !sales || sales.length === 0 ? (
              <EmptyState title="لا توجد مبيعات" description="لا توجد مبيعات مسجلة لهذا الفرع" />
            ) : (
              <Table>
                <thead>
                  <tr>
                    <Th>التاريخ</Th>
                    <Th>الموظف</Th>
                    <Th>إجمالي المبيعات</Th>
                    <Th>نقدي</Th>
                    <Th>تحويل</Th>
                    <Th>بطاقة</Th>
                    <Th>أخرى</Th>
                    <Th>التوازن</Th>
                  </tr>
                </thead>
                <tbody>
                  {sales.map((s) => (
                    <Tr key={s.id} onClick={() => setSelectedSale(s)} className="cursor-pointer">
                      <Td><Button variant="ghost" size="sm" className="!px-1">{formatDate(s.date)}</Button></Td>
                      <Td>{s.employee_name || <span className="text-neutral-400">—</span>}</Td>
                      <Td className="tabular-nums font-medium">{formatCurrency(s.total_sales)}</Td>
                      <Td className="tabular-nums">{formatCurrency(s.cash_amount)}</Td>
                      <Td className="tabular-nums">{formatCurrency(s.transfer_amount)}</Td>
                      <Td className="tabular-nums">{formatCurrency(s.card_amount)}</Td>
                      <Td className="tabular-nums">{formatCurrency(s.other_amount)}</Td>
                      <Td>
                        {s.mismatch ? (
                          <Badge variant="danger">غير متوازن</Badge>
                        ) : (
                          <Badge variant="success">متوازن</Badge>
                        )}
                      </Td>
                    </Tr>
                  ))}
                </tbody>
              </Table>
            )}
            </Card>
          </div>
        )}

        {tab === 'sales-employees' && (
          <div className="space-y-4">
            <Card className="!p-4">
              <DateRangeToolbar from={dateFrom} to={dateTo} onChange={(f, t) => { setDateFrom(f); setDateTo(t); }} />
            </Card>
            {byEmployee && (
              <div className="grid grid-cols-3 gap-4">
                <StatCard icon={<BarChart3 size={20} />} label="إجمالي مبيعات الموظفين" value={formatCurrency(assignedTotal)} />
                <StatCard icon={<Receipt size={20} />} iconBg="bg-sand-100 text-neutral-500" label="دون موظف" value={formatCurrency(byEmployee.unassigned_total)} />
                <StatCard icon={<Sparkles size={20} />} iconBg="bg-emerald-50 text-emerald-600" label="الإجمالي" value={formatCurrency(byEmployee.grand_total)} />
              </div>
            )}
            <Card title={`مبيعات الموظفين (${byEmployee?.items.length ?? 0})`}>
              {byEmployeeLoading && byEmployee === null ? (
                <div className="flex justify-center py-12"><Spinner size={32} /></div>
              ) : !byEmployee || byEmployee.items.length === 0 ? (
                <EmptyState title="لا توجد بيانات" description="لا توجد مبيعات مسندة لموظفين في الفترة المحددة" />
              ) : (
                <Table>
                  <thead>
                    <tr>
                      <Th>#</Th>
                      <Th>الموظف</Th>
                      <Th>عدد السجلات</Th>
                      <Th>نقدي</Th>
                      <Th>تحويل</Th>
                      <Th>بطاقة</Th>
                      <Th>أخرى</Th>
                      <Th>الإجمالي</Th>
                      <Th>النسبة</Th>
                    </tr>
                  </thead>
                  <tbody>
                    {byEmployee.items.map((row, idx) => (
                      <Tr key={row.employee}>
                        <Td className="text-neutral-400">{idx + 1}</Td>
                        <Td className="font-medium">{row.employee_name}</Td>
                        <Td className="tabular-nums">{row.sales_count}</Td>
                        <Td className="tabular-nums">{formatCurrency(row.cash_total)}</Td>
                        <Td className="tabular-nums">{formatCurrency(row.transfer_total)}</Td>
                        <Td className="tabular-nums">{formatCurrency(row.card_total)}</Td>
                        <Td className="tabular-nums">{formatCurrency(row.other_total)}</Td>
                        <Td className="tabular-nums font-bold">{formatCurrency(row.total_sales)}</Td>
                        <Td className="tabular-nums text-neutral-500">
                          {byEmployee.grand_total > 0 ? `${((row.total_sales / byEmployee.grand_total) * 100).toFixed(1)}%` : '-'}
                        </Td>
                      </Tr>
                    ))}
                  </tbody>
                  <tfoot>
                    <tr className="bg-sand-100 font-semibold">
                      <Td colSpan={2}>الإجمالي</Td>
                      <Td className="tabular-nums">{byEmployee.items.reduce((s, r) => s + r.sales_count, 0)}</Td>
                      <Td className="tabular-nums">{formatCurrency(byEmployee.items.reduce((s, r) => s + r.cash_total, 0))}</Td>
                      <Td className="tabular-nums">{formatCurrency(byEmployee.items.reduce((s, r) => s + r.transfer_total, 0))}</Td>
                      <Td className="tabular-nums">{formatCurrency(byEmployee.items.reduce((s, r) => s + r.card_total, 0))}</Td>
                      <Td className="tabular-nums">{formatCurrency(byEmployee.items.reduce((s, r) => s + r.other_total, 0))}</Td>
                      <Td className="tabular-nums">{formatCurrency(assignedTotal)}</Td>
                      <Td className="tabular-nums">{byEmployee.grand_total > 0 ? `${((assignedTotal / byEmployee.grand_total) * 100).toFixed(1)}%` : '-'}</Td>
                    </tr>
                  </tfoot>
                </Table>
              )}
            </Card>
          </div>
        )}

        {tab === 'movements' && (
          <div className="space-y-4">
            <Card className="!p-4">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <DateRangeToolbar from={dateFrom} to={dateTo} onChange={(f, t) => { setDateFrom(f); setDateTo(t); }} />
                <div className="flex gap-2">
                  <a
                    href={`${API_URL}/reports/inventory-movements/?${new URLSearchParams({
                      warehouse: String(saleStock?.warehouse || ''),
                      date_from: dateFrom,
                      date_to: dateTo,
                      export: 'xlsx',
                    }).toString()}`}
                    target="_blank"
                    rel="noreferrer"
                  >
                    <Button variant="secondary" size="sm" type="button"><Download size={16} /> تصدير Excel</Button>
                  </a>
                  <Button variant="secondary" size="sm" type="button" onClick={() => window.print()}><Printer size={16} /> طباعة PDF</Button>
                </div>
              </div>
            </Card>
            {movementsTotals && (
              <div className="grid grid-cols-3 gap-4">
                <StatCard icon={<ArrowDownToLine size={20} />} iconBg="bg-emerald-50 text-emerald-600" label="ياردةد" value={formatNumber(movementsTotals.in)} />
                <StatCard icon={<ArrowUpFromLine size={20} />} iconBg="bg-red-50 text-red-600" label="صادر" value={formatNumber(movementsTotals.out)} />
                <StatCard icon={<ArrowUpDown size={20} />} label="عدد الحركات" value={movementsTotals.count} />
              </div>
            )}
            <Card title={`حركة مخزون فرع «${branch.name}»`}>
              {movementsLoading && movements === null ? (
                <div className="flex justify-center py-12"><Spinner size={32} /></div>
              ) : !movements || movements.length === 0 ? (
                <EmptyState title="لا توجد حركات" description="لا توجد حركات مخزون في الفترة المحددة لمخزن هذا الفرع" />
              ) : (
                <Table>
                  <thead>
                    <tr>
                      <Th>التاريخ</Th>
                      <Th>القماش</Th>
                      <Th>الحركة</Th>
                      <Th>الكمية</Th>
                      <Th>الرصيد قبل</Th>
                      <Th>الرصيد بعد</Th>
                      <Th>المرجع</Th>
                    </tr>
                  </thead>
                  <tbody>
                    {movements.map((m, i) => (
                      <Tr key={i}>
                        <Td>{formatDate(m.date)}</Td>
                        <Td className="font-medium">{m.fabric_name}</Td>
                        <Td>
                          <Badge variant={m.quantity > 0 ? 'success' : 'danger'}>{m.movement_type_label}</Badge>
                        </Td>
                        <Td className={`tabular-nums font-bold ${m.quantity > 0 ? 'text-emerald-600' : 'text-red-600'}`}>
                          {m.quantity > 0 ? `+${formatNumber(m.quantity)}` : formatNumber(m.quantity)}
                        </Td>
                        <Td className="tabular-nums">{m.balance_before != null ? formatNumber(m.balance_before) : '-'}</Td>
                        <Td className="tabular-nums">{m.balance_after != null ? formatNumber(m.balance_after) : '-'}</Td>
                        <Td className="font-mono text-xs">{m.reference_no || '-'}</Td>
                      </Tr>
                    ))}
                  </tbody>
                </Table>
              )}
            </Card>
          </div>
        )}

        {tab === 'pricing' && (
          <BranchPricingPanel branchId={id} />
        )}

        {tab === 'reports' && (
          <div className="space-y-6">
            <Card className="!p-4">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <DateRangeToolbar from={dateFrom} to={dateTo} onChange={(f, t) => { setDateFrom(f); setDateTo(t); }} />
                <div className="flex gap-2">
                  <a
                    href={`${API_URL}/reports/sales/?${new URLSearchParams({
                      branch: String(id),
                      date_from: dateFrom,
                      date_to: dateTo,
                      export: 'xlsx',
                    }).toString()}`}
                    target="_blank"
                    rel="noreferrer"
                  >
                    <Button variant="secondary" size="sm" type="button"><Download size={16} /> مبيعات Excel</Button>
                  </a>
                  <a
                    href={`${API_URL}/reports/expenses/?${new URLSearchParams({
                      branch: String(id),
                      date_from: dateFrom,
                      date_to: dateTo,
                      export: 'xlsx',
                    }).toString()}`}
                    target="_blank"
                    rel="noreferrer"
                  >
                    <Button variant="secondary" size="sm" type="button"><Download size={16} /> مصاريف Excel</Button>
                  </a>
                  {saleStock?.warehouse != null && (
                    <a
                      href={`${API_URL}/reports/inventory/?${new URLSearchParams({
                        warehouse: String(saleStock.warehouse),
                        export: 'xlsx',
                      }).toString()}`}
                      target="_blank"
                      rel="noreferrer"
                    >
                      <Button variant="secondary" size="sm" type="button"><Download size={16} /> مخزون Excel</Button>
                    </a>
                  )}
                  <Button variant="secondary" size="sm" type="button" onClick={() => window.print()}><Printer size={16} /> طباعة PDF</Button>
                </div>
              </div>
            </Card>
            <Card title="تقرير المبيعات">
              {reportsLoading || (reportsData === null && inventoryData === null) ? (
                <div className="flex justify-center py-12"><Spinner size={32} /></div>
              ) : !reportsData || reportsData.length === 0 ? (
                <EmptyState title="لا توجد بيانات" description="لا توجد مبيعات في الفترة المحددة" />
              ) : (
                <Table>
                  <thead>
                    <tr>
                      <Th>التاريخ</Th>
                      <Th>إجمالي المبيعات</Th>
                      <Th>نقدي</Th>
                      <Th>بطاقة</Th>
                      <Th>تحويل</Th>
                      <Th>أخرى</Th>
                    </tr>
                  </thead>
                  <tbody>
                    {reportsData.map((r, i) => (
                      <Tr key={i}>
                        <Td>{formatDate(r.date)}</Td>
                        <Td className="tabular-nums font-medium">{formatCurrency(r.total_sales)}</Td>
                        <Td className="tabular-nums">{formatCurrency(r.cash_amount)}</Td>
                        <Td className="tabular-nums">{formatCurrency(r.card_amount)}</Td>
                        <Td className="tabular-nums">{formatCurrency(r.transfer_amount)}</Td>
                        <Td className="tabular-nums">{formatCurrency(r.other_amount)}</Td>
                      </Tr>
                    ))}
                  </tbody>
                  <tfoot>
                    <tr className="bg-sand-100 font-semibold">
                      <Td>الإجمالي</Td>
                      <Td className="tabular-nums">{formatCurrency(reportsData.reduce((s, r) => s + r.total_sales, 0))}</Td>
                      <Td className="tabular-nums">{formatCurrency(reportsData.reduce((s, r) => s + r.cash_amount, 0))}</Td>
                      <Td className="tabular-nums">{formatCurrency(reportsData.reduce((s, r) => s + r.card_amount, 0))}</Td>
                      <Td className="tabular-nums">{formatCurrency(reportsData.reduce((s, r) => s + r.transfer_amount, 0))}</Td>
                      <Td className="tabular-nums">{formatCurrency(reportsData.reduce((s, r) => s + r.other_amount, 0))}</Td>
                    </tr>
                  </tfoot>
                </Table>
              )}
            </Card>
            <Card title="تقرير المخزون">
              {reportsLoading ? (
                <div className="flex justify-center py-12"><Spinner size={32} /></div>
              ) : !inventoryData || inventoryData.length === 0 ? (
                <EmptyState title="لا يوجد مخزون" description="لا توجد أرصدة أقمشة لمخزن هذا الفرع" />
              ) : (
                <Table>
                  <thead>
                    <tr>
                      <Th>القماش</Th>
                      <Th>الكود</Th>
                      <Th>الوحدة</Th>
                      <Th>الطاقات</Th>
                      <Th>الكمية</Th>
                      <Th>الحد الأدنى</Th>
                      <Th>الحالة</Th>
                    </tr>
                  </thead>
                  <tbody>
                    {inventoryData.map((r) => (
                      <Tr key={r.fabric}>
                        <Td className="font-medium">{r.fabric_name}</Td>
                        <Td><span className="font-mono text-xs bg-sand-100 px-2 py-1 rounded">{r.fabric_code}</span></Td>
                        <Td>{UNIT_LABEL[r.unit] || r.unit}</Td>
                        <Td className="tabular-nums">{formatNumber(r.rolls_available)}</Td>
                        <Td className="tabular-nums font-bold">{formatNumber(r.total_yards)}</Td>
                        <Td className="tabular-nums">{formatNumber(r.min_stock)}</Td>
                        <Td>
                          {r.low_stock ? (
                            <Badge variant="danger"><AlertTriangle size={12} /> تحت الحد الأدنى</Badge>
                          ) : (
                            <Badge variant="success">مناسب</Badge>
                          )}
                        </Td>
                      </Tr>
                    ))}
                  </tbody>
                </Table>
              )}
            </Card>
          </div>
        )}

        {/* Sale Day Details */}
        <Modal open={selectedSale !== null} onClose={() => setSelectedSale(null)} title={selectedSale ? `تفاصيل بيع يوم ${formatDate(selectedSale.date)}` : ''} maxWidth="max-w-2xl">
          {selectedSale && (
            <div className="space-y-4">
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                <div className="rounded-xl bg-sand-50 p-4">
                  <p className="text-xs text-neutral-500 mb-1">إجمالي المبيعات</p>
                  <p className="text-lg font-bold tabular-nums">{formatCurrency(selectedSale.total_sales)}</p>
                </div>
                <div className="rounded-xl bg-sand-50 p-4">
                  <p className="text-xs text-neutral-500 mb-1">نقدي</p>
                  <p className="text-lg font-bold tabular-nums">{formatCurrency(selectedSale.cash_amount)}</p>
                </div>
                <div className="rounded-xl bg-sand-50 p-4">
                  <p className="text-xs text-neutral-500 mb-1">تحويل</p>
                  <p className="text-lg font-bold tabular-nums">{formatCurrency(selectedSale.transfer_amount)}</p>
                </div>
                <div className="rounded-xl bg-sand-50 p-4">
                  <p className="text-xs text-neutral-500 mb-1">بطاقة</p>
                  <p className="text-lg font-bold tabular-nums">{formatCurrency(selectedSale.card_amount)}</p>
                </div>
              </div>
              {selectedSale.mismatch && (
                <div className="flex items-center gap-2 text-sm text-red-600 bg-red-50 rounded-xl p-3">
                  <AlertTriangle size={16} />
                  إجمالي المدفوعات لا يطابق إجمالي المبيعات ({formatCurrency(selectedSale.payment_total)})
                </div>
              )}
              {selectedSale.employee_name && (
                <p className="text-sm text-neutral-600 bg-sand-50 rounded-xl p-3">الموظف: <span className="font-medium">{selectedSale.employee_name}</span></p>
              )}
              <div>
                <p className="text-sm font-semibold text-neutral-700 mb-2">أصناف البيع</p>
                {selectedSale.items.length === 0 ? (
                  <p className="text-sm text-neutral-400">لا توجد أصناف مسجلة لهذا البيع</p>
                ) : (
                  <Table>
                    <thead>
                      <tr>
                        <Th>القماش</Th>
                        <Th>الوحدة</Th>
                        <Th>الكمية</Th>
                      </tr>
                    </thead>
                    <tbody>
                      {selectedSale.items.map((it) => (
                        <Tr key={it.id}>
                          <Td className="font-medium">{it.fabric_name}</Td>
                          <Td>{it.fabric_unit}</Td>
                          <Td className="tabular-nums">{it.yards}</Td>
                        </Tr>
                      ))}
                    </tbody>
                  </Table>
                )}
              </div>
              {selectedSale.notes && (
                <p className="text-sm text-neutral-500 bg-sand-50 rounded-xl p-3">ملاحظات: {selectedSale.notes}</p>
              )}
            </div>
          )}
        </Modal>

        <Modal open={editOpen} onClose={() => setEditOpen(false)} title="تعديل الفرع">
          <BranchForm initial={branch} onSubmit={handleUpdate} onCancel={() => setEditOpen(false)} />
        </Modal>

        <ConfirmDialog
          open={stopOpen}
          onClose={() => setStopOpen(false)}
          onConfirm={() => handleToggle(false)}
          loading={toggleLoading}
          message={`هل أنت متأكد من إيقاف فرع "${branch.name}"؟ لن يتمكن من تسجيل مبيعات أو مصاريف جديدة، مع بقاء السجلات السابقة.`}
        />
      </div>
    </AppShell>
  );
}