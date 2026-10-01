'use client';

import { useState, useEffect, useCallback } from 'react';
import AppShell from '@/components/layout/AppShell';
import Card from '@/components/ui/Card';
import Button from '@/components/ui/Button';
import ExportButton from '@/components/ui/ExportButton';
import Table, { Th, Td, Tr } from '@/components/ui/Table';
import Select from '@/components/ui/Select';
import DateRangeToolbar, { currentMonthRange } from '@/components/ui/DateRangeToolbar';
import Spinner from '@/components/ui/Spinner';
import EmptyState from '@/components/ui/EmptyState';
import { Branch, SalesReportData, ExpensesReportData, ExpenseBudgetReportRow, CommissionReportRow, NetDailyReportData, BranchesReportData, SuppliersReportData, InventoryReportRow, InventoryMovementReportRow, Warehouse, CogsReportRow, ProfitLossReportResult, ProfitLossComparison, JournalReportRow } from '@/types';
import { listBranches } from '@/services/branches';
import { listWarehouses } from '@/services/warehouses';
import { getSalesReport, getExpensesReport, getExpensesBudgetReport, getCommissionsReport, getNetDailyReport, getSuppliersReport, getBranchesReport, getInventoryReport, getInventoryMovementsReport, getCogsReport, getProfitLossReport, getJournalReport } from '@/services/reports';
import { formatCurrency, formatDate, formatNumber } from '@/lib/format';
import { PAYMENT_METHODS_MAP, ANALYTICS_REPORTS, REPORT_GROUPS } from '@/lib/constants';
import { useToast } from '@/components/ui/Toast';
import { useUrlState } from '@/lib/useUrlState';
import { useAuth } from '@/components/providers/AuthProvider';
import { hasWindow } from '@/lib/permissions';
import AnalyticsReportView from '@/components/reports/AnalyticsReportView';

type Tab = 'analytics' | 'sales' | 'expenses' | 'budget' | 'commissions' | 'net' | 'suppliers' | 'branches' | 'inventory' | 'inventory-movements' | 'profit-loss' | 'cogs' | 'journal';

const tabs: { value: Tab; label: string }[] = [
  { value: 'analytics', label: 'التقارير التحليلية' },
  { value: 'sales', label: 'تقرير المبيعات' },
  { value: 'expenses', label: 'تقرير المصاريف' },
  { value: 'budget', label: 'المصاريف مقابل الميزانية' },
  { value: 'commissions', label: 'عمولات المبيعات' },
  { value: 'net', label: 'صافي النتيجة اليومي' },
  { value: 'profit-loss', label: 'الربح والخسارة' },
  { value: 'cogs', label: 'تكلفة البضاعة المباعة' },
  { value: 'journal', label: 'القيود اليومية' },
  { value: 'inventory', label: 'تقرير المخزون' },
  { value: 'inventory-movements', label: 'حركات المخزون' },
  { value: 'suppliers', label: 'قائمة الموردين' },
  { value: 'branches', label: 'قائمة الفروع' },
];

const MOVEMENT_TYPE_OPTIONS = [
  { value: 'receipt', label: 'استلام من مورد' },
  { value: 'transfer_out', label: 'تحويل صادر' },
  { value: 'transfer_in', label: 'تحويل ياردةد' },
  { value: 'adjustment_in', label: 'تسوية إضافة' },
  { value: 'adjustment_out', label: 'تسوية خصم' },
  { value: 'count', label: 'فارق جرد' },
  { value: 'opening', label: 'رصيد افتتاحي' },
  { value: 'sale', label: 'مبيعات' },
];

const UNIT_LABEL: Record<string, string> = {
  yard: 'ياردة',
  roll: 'طاقة',
};

/** سطر نسبة التغيّر عن الفترة السابقة. invert = بند ارتفاعه إيجابي (مبيعات/ربح). */
function PlChange({ pct, invert = false }: { pct?: number | null; invert?: boolean }) {
  if (pct == null) return null;
  const up = pct > 0;
  const good = invert ? up : !up;
  const color = pct === 0 ? 'text-neutral-400' : good ? 'text-emerald-600' : 'text-red-600';
  return (
    <div className={`text-xs font-medium mt-1 ${color}`}>
      {pct > 0 ? '▲' : pct < 0 ? '▼' : '■'} {formatNumber(Math.abs(pct))}% عن الفترة السابقة
    </div>
  );
}

/** بنود جدول المقارنة: [مفتاح، تسمية، هل ارتفاعه إيجابي؟] */
const PL_COMPARISON_ROWS: [keyof ProfitLossComparison['change_pct'], string, boolean][] = [
  ['total_sales', 'إجمالي المبيعات', true],
  ['cogs', 'تكلفة البضاعة المباعة', false],
  ['gross_profit', 'مجمل الربح', true],
  ['salaries', 'الرواتب', false],
  ['expenses', 'المصاريف', false],
  ['net_profit', 'صافي الربح', true],
];

export default function ReportsPage() {
  const { toast } = useToast();
  const { session } = useAuth();
  const me = session?.employee;
  const [activeTab, setActiveTab] = useUrlState<Tab>('report', 'analytics');
  const [dateFrom, setDateFrom] = useUrlState('from', currentMonthRange().from);
  const [dateTo, setDateTo] = useUrlState('to', currentMonthRange().to);
  const [filterBranch, setFilterBranch] = useUrlState('branch', '');
  const [branches, setBranches] = useState<Branch[]>([]);
  const [loading, setLoading] = useState(false);

  const [salesData, setSalesData] = useState<SalesReportData[]>([]);
  const [expensesData, setExpensesData] = useState<ExpensesReportData[]>([]);
  const [budgetData, setBudgetData] = useState<ExpenseBudgetReportRow[]>([]);
  const [budgetTotals, setBudgetTotals] = useState<{ budget: number; spent: number; remaining: number; rows: number } | null>(null);
  const [budgetMonth, setBudgetMonth] = useUrlState('budget_month', new Date().toISOString().slice(0, 7));
  const [commissionData, setCommissionData] = useState<CommissionReportRow[]>([]);
  const [commissionTotals, setCommissionTotals] = useState<{
    sessions: number;
    sales: number;
    commission: number;
    employees: number;
    pieces: number;
    yards: number;
  } | null>(null);
  const [commissionMonth, setCommissionMonth] = useUrlState('commission_month', new Date().toISOString().slice(0, 7));
  const [netData, setNetData] = useState<NetDailyReportData[]>([]);
  const [suppliersData, setSuppliersData] = useState<SuppliersReportData[]>([]);
  const [branchesData, setBranchesData] = useState<BranchesReportData[]>([]);
  const [inventoryData, setInventoryData] = useState<InventoryReportRow[]>([]);
  const [inventoryTotals, setInventoryTotals] = useState<{ total_yards: number; rolls_available: number; low_stock_count: number; fabrics: number } | null>(null);
  const [movementsData, setMovementsData] = useState<InventoryMovementReportRow[]>([]);
  const [movementsTotals, setMovementsTotals] = useState<{ in: number; out: number; count: number } | null>(null);
  const [cogsData, setCogsData] = useState<CogsReportRow[]>([]);
  const [cogsTotals, setCogsTotals] = useState<{ yards_sold: number; revenue: number; cogs: number; profit: number } | null>(null);
  const [plData, setPlData] = useState<ProfitLossReportResult | null>(null);
  const [journalData, setJournalData] = useState<JournalReportRow[]>([]);
  const [journalTotals, setJournalTotals] = useState<{ sales: number; purchases: number; expenses: number; support: number; withdraw: number; net: number } | null>(null);
  const [warehouses, setWarehouses] = useState<Warehouse[]>([]);
  const [filterWarehouse, setFilterWarehouse] = useUrlState('warehouse', '');
  const [filterMovementType, setFilterMovementType] = useUrlState('movement_type', '');
  const [filterSearch, setFilterSearch] = useUrlState('q', '');

  // Reports V2
  const [analyticsKey, setAnalyticsKey] = useUrlState('report_key', 'summary');
  const [analyticsGroup, setAnalyticsGroup] = useUrlState('report_group', 'overview');
  const [groupBy, setGroupBy] = useUrlState('group_by', '');
  const [idleDays, setIdleDays] = useUrlState('idle_days', '60');
  const [compare, setCompare] = useUrlState('compare', '1');
  const [refreshKey, setRefreshKey] = useState(0);

  const activeReport =
    ANALYTICS_REPORTS.find((r) => r.key === analyticsKey) || ANALYTICS_REPORTS[0];

  useEffect(() => {
    let cancelled = false;
    listBranches({ page_size: 100 }).then((res) => {
      if (!cancelled) setBranches(res.results);
    });
    listWarehouses({ page_size: 100 }).then((res) => {
      if (!cancelled) setWarehouses(res.results);
    });
    return () => { cancelled = true; };
  }, []);

  const buildParams = useCallback(() => {
    const p: Record<string, string | number | undefined | null> = {};
    if (dateFrom) p.date_from = dateFrom;
    if (dateTo) p.date_to = dateTo;
    if (filterBranch) p.branch = filterBranch;
    return p;
  }, [dateFrom, dateTo, filterBranch]);

  const loadTab = useCallback(async (tab: Tab) => {
    setLoading(true);
    try {
      const params = buildParams();
      switch (tab) {
        case 'sales':
          const salesRes = await getSalesReport(params);
          setSalesData(salesRes.sales || []);
          break;
        case 'expenses':
          const expRes = await getExpensesReport(params);
          setExpensesData(expRes.expenses || []);
          break;
        case 'budget':
          const budParams: Record<string, string | number | undefined | null> = {
            month: budgetMonth || undefined,
            branch: filterBranch || undefined,
          };
          const budRes = await getExpensesBudgetReport(budParams);
          setBudgetData(budRes.items || []);
          setBudgetTotals(budRes.totals || null);
          break;
        case 'commissions':
          const comParams: Record<string, string | number | undefined | null> = {
            month: commissionMonth || undefined,
            branch: filterBranch || undefined,
          };
          const comRes = await getCommissionsReport(comParams);
          setCommissionData(comRes.items || []);
          setCommissionTotals(comRes.totals || null);
          break;
        case 'net':
          const netRes = await getNetDailyReport(params);
          setNetData(netRes.chart_data || []);
          break;
        case 'suppliers':
          const suppRes = await getSuppliersReport();
          setSuppliersData(suppRes.suppliers || []);
          break;
        case 'branches':
          const branchRes = await getBranchesReport();
          setBranchesData(branchRes.branches || []);
          break;
        case 'inventory':
          const invParams: Record<string, string | number | undefined | null> = {
            warehouse: filterWarehouse || undefined,
            search: filterSearch || undefined,
          };
          const invRes = await getInventoryReport(invParams);
          setInventoryData(invRes.items || []);
          setInventoryTotals(invRes.totals || null);
          break;
        case 'inventory-movements':
          const movParams: Record<string, string | number | undefined | null> = {
            warehouse: filterWarehouse || undefined,
            movement_type: filterMovementType || undefined,
            date_from: dateFrom || undefined,
            date_to: dateTo || undefined,
          };
          const movRes = await getInventoryMovementsReport(movParams);
          setMovementsData(movRes.movements || []);
          setMovementsTotals(movRes.totals || null);
          break;
        case 'profit-loss':
          const plRes = await getProfitLossReport(params);
          setPlData(plRes);
          break;
        case 'cogs':
          const cogsRes = await getCogsReport(params);
          setCogsData(cogsRes.items || []);
          setCogsTotals(cogsRes.totals || null);
          break;
        case 'journal':
          const jrnRes = await getJournalReport(params);
          setJournalData(jrnRes.journal || []);
          setJournalTotals(jrnRes.totals || null);
          break;
      }
    } catch (err: any) {
      toast('error', err.message);
    } finally {
      setLoading(false);
    }
  }, [
    buildParams, budgetMonth, commissionMonth, dateFrom, dateTo, filterBranch,
    filterMovementType, filterSearch, filterWarehouse, toast,
  ]);

  useEffect(() => {
    loadTab(activeTab);
  }, [activeTab, loadTab]);

  /** مسار التصدير لكل تبويب، و ``undefined`` إن لم يكن له تصدير. */
  const getExportPath = (): string | undefined => {
    switch (activeTab) {
      case 'sales': return '/reports/sales/';
      case 'expenses': return '/reports/expenses/';
      case 'budget': return '/reports/expenses-budget/';
      case 'commissions': return '/reports/commissions/';
      case 'net': return '/reports/net-daily/';
      case 'suppliers': return '/reports/suppliers/';
      case 'branches': return '/reports/branches/';
      case 'inventory': return '/reports/inventory/';
      case 'inventory-movements': return '/reports/inventory-movements/';
      case 'profit-loss': return '/reports/profit-loss/';
      case 'cogs': return '/reports/cogs/';
      case 'journal': return '/reports/journal/';
      default: return undefined;
    }
  };

  /** معاملات التصدير، وهي تصفية التبويب نفسه. */
  const getExportParams = (): Record<string, string | undefined> => {
    switch (activeTab) {
      case 'budget':
        return { month: budgetMonth, branch: filterBranch };
      case 'commissions':
        return { month: commissionMonth, branch: filterBranch };
      case 'inventory':
        return { warehouse: filterWarehouse, search: filterSearch };
      case 'inventory-movements':
        return {
          warehouse: filterWarehouse,
          movement_type: filterMovementType,
          date_from: dateFrom,
          date_to: dateTo,
        };
      default:
        return { date_from: dateFrom, date_to: dateTo, branch: filterBranch };
    }
  };

  return (
    <AppShell>
      <div className="space-y-6">
        {activeTab === 'analytics' ? (
          <>
            <div className="flex flex-wrap items-end gap-4">
              <DateRangeToolbar from={dateFrom} to={dateTo} onChange={(f, t) => { setDateFrom(f); setDateTo(t); }} />
              <Select
                value={filterBranch}
                onChange={(e) => setFilterBranch(e.target.value)}
                options={[{ value: '', label: 'كل الفروع' }, ...branches.map((b) => ({ value: b.id, label: b.name }))]}
                className="w-full sm:w-48"
              />
            </div>
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div className="flex flex-wrap gap-2">
                {REPORT_GROUPS.map((g) => (
                  <button
                    key={g.key}
                    onClick={() => {
                      setAnalyticsGroup(g.key);
                      const first = ANALYTICS_REPORTS.find((r) => r.group === g.key);
                      if (first) setAnalyticsKey(first.key);
                    }}
                    className={`px-4 py-2 rounded-xl text-sm font-medium transition-all ${
                      analyticsGroup === g.key
                        ? 'bg-brand-600 text-white shadow-sm'
                        : 'bg-surface text-neutral-600 border border-sand-200 hover:bg-sand-50'
                    }`}
                  >
                    {g.label}
                  </button>
                ))}
              </div>
              <label className="flex items-center gap-2 text-sm text-neutral-600">
                <input
                  type="checkbox"
                  checked={compare === '1'}
                  onChange={(e) => setCompare(e.target.checked ? '1' : '0')}
                  className="w-4 h-4 rounded border-sand-300 text-brand-600"
                />
                مقارنة بالفترة السابقة
              </label>
            </div>
            <div className="flex flex-wrap gap-2">
              {ANALYTICS_REPORTS.filter((r) => r.group === analyticsGroup).map((r) => (
                <button
                  key={r.key}
                  onClick={() => setAnalyticsKey(r.key)}
                  className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
                    activeReport.key === r.key
                      ? 'bg-brand-100 text-brand-800 dark:bg-brand-500/20 dark:text-brand-200'
                      : 'bg-sand-100 text-neutral-600 hover:bg-sand-200'
                  }`}
                >
                  {r.label}
                </button>
              ))}
            </div>
            <AnalyticsReportView
              key={activeReport.key}
              report={activeReport}
              dateFrom={dateFrom}
              dateTo={dateTo}
              branch={filterBranch}
              compare={compare === '1'}
              idleDays={idleDays}
              onIdleDays={setIdleDays}
              groupBy={groupBy}
              onGroupBy={setGroupBy}
              refreshKey={refreshKey}
            />
          </>
        ) : (
          <>
        {/* Filters */}
        <Card className="!p-4">
          <div className="flex flex-wrap items-end gap-4">
            <DateRangeToolbar
              from={dateFrom}
              to={dateTo}
              onChange={(f, t) => { setDateFrom(f); setDateTo(t); }}
            />
            {(activeTab === 'budget' || activeTab === 'commissions') && (
              <div className="flex flex-col gap-1">
                <label className="text-xs font-medium text-neutral-500">الشهر</label>
                <input
                  type="month"
                  value={activeTab === 'budget' ? budgetMonth : commissionMonth}
                  onChange={(e) => {
                    const v = e.target.value;
                    if (activeTab === 'budget') setBudgetMonth(v);
                    else setCommissionMonth(v);
                  }}
                  className="rounded-xl border border-sand-300 bg-surface px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500/40"
                />
              </div>
            )}
            {(activeTab === 'sales' || activeTab === 'expenses' || activeTab === 'budget' || activeTab === 'commissions' || activeTab === 'net' || activeTab === 'profit-loss' || activeTab === 'journal') && (
              <Select
                value={filterBranch}
                onChange={(e) => setFilterBranch(e.target.value)}
                options={[{ value: '', label: 'كل الفروع' }, ...branches.map((b) => ({ value: b.id, label: b.name }))]}
                className="w-full sm:w-48"
              />
            )}
            {(activeTab === 'inventory' || activeTab === 'inventory-movements') && (
              <>
                <Select
                  value={filterWarehouse}
                  onChange={(e) => setFilterWarehouse(e.target.value)}
                  options={[{ value: '', label: 'كل المخازن' }, ...warehouses.map((w) => ({ value: w.id, label: w.name }))]}
                  className="w-full sm:w-48"
                />
                <input
                  type="search"
                  value={filterSearch}
                  onChange={(e) => setFilterSearch(e.target.value)}
                  placeholder="بحث في الأقمشة..."
                  className="flex-1 min-w-[180px] rounded-xl border border-sand-300 bg-surface px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500/40"
                />
                {activeTab === 'inventory-movements' && (
                  <Select
                    value={filterMovementType}
                    onChange={(e) => setFilterMovementType(e.target.value)}
                    options={[{ value: '', label: 'كل الحركات' }, ...MOVEMENT_TYPE_OPTIONS]}
                    className="w-full sm:w-44"
                  />
                )}
              </>
            )}
          </div>
        </Card>

        {/* Tabs */}
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex flex-wrap gap-2">
            {tabs
              .filter((t) => t.value === 'analytics' || hasWindow(me?.permissions, 'reports', t.value))
              .map((t) => (
              <button
                key={t.value}
                onClick={() => setActiveTab(t.value)}
                className={`px-4 py-2 rounded-xl text-sm font-medium transition-all duration-150 ${
                  activeTab === t.value
                    ? 'bg-brand-600 text-white shadow-sm'
                    : 'bg-surface text-neutral-600 border border-sand-200 hover:bg-sand-50'
                }`}
              >
                {t.label}
              </button>
            ))}
          </div>
          <ExportButton
            path={getExportPath()}
            params={getExportParams()}
            filename={`${tabs.find((t) => t.value === activeTab)?.label || 'تقرير'}.xlsx`}
          />
        </div>

        {/* Content */}
        <Card>
          {loading ? (
            <div className="flex justify-center py-12"><Spinner size={32} /></div>
          ) : (
            <>
              {/* Sales Tab */}
              {activeTab === 'sales' && (
                salesData.length === 0 ? (
                  <EmptyState title="لا توجد بيانات" description="لا توجد مبيعات في الفترة المحددة" />
                ) : (
                  <>
                    <Table>
                      <thead>
                        <tr>
                          <Th>التاريخ</Th>
                          <Th>الفرع</Th>
                          <Th>إجمالي المبيعات</Th>
                          <Th>نقدي</Th>
                          <Th>بطاقة</Th>
                          <Th>تحويل</Th>
                          <Th>أخرى</Th>
                        </tr>
                      </thead>
                      <tbody>
                        {salesData.map((r, i) => (
                          <Tr key={i}>
                            <Td>{formatDate(r.date)}</Td>
                            <Td className="font-medium">{r.branch_name}</Td>
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
                          <Td></Td>
                          <Td className="tabular-nums">{formatCurrency(salesData.reduce((s, r) => s + r.total_sales, 0))}</Td>
                          <Td className="tabular-nums">{formatCurrency(salesData.reduce((s, r) => s + r.cash_amount, 0))}</Td>
                          <Td className="tabular-nums">{formatCurrency(salesData.reduce((s, r) => s + r.card_amount, 0))}</Td>
                          <Td className="tabular-nums">{formatCurrency(salesData.reduce((s, r) => s + r.transfer_amount, 0))}</Td>
                          <Td className="tabular-nums">{formatCurrency(salesData.reduce((s, r) => s + r.other_amount, 0))}</Td>
                        </tr>
                      </tfoot>
                    </Table>
                  </>
                )
              )}

              {/* Expenses Tab */}
              {activeTab === 'expenses' && (
                expensesData.length === 0 ? (
                  <EmptyState title="لا توجد بيانات" description="لا توجد مصاريف في الفترة المحددة" />
                ) : (
                  <>
                    <Table>
                      <thead>
                        <tr>
                          <Th>التاريخ</Th>
                          <Th>الفرع</Th>
                          <Th>نوع المصروف</Th>
                          <Th>المبلغ</Th>
                          <Th>طريقة الدفع</Th>
                          <Th>الوصف</Th>
                        </tr>
                      </thead>
                      <tbody>
                        {expensesData.map((r, i) => (
                          <Tr key={i}>
                            <Td>{formatDate(r.date)}</Td>
                            <Td className="font-medium">{r.branch_name}</Td>
                            <Td>{r.category_name}</Td>
                            <Td className="tabular-nums font-medium">{formatCurrency(r.amount)}</Td>
                            <Td>{PAYMENT_METHODS_MAP[r.payment_method] || r.payment_method}</Td>
                            <Td className="max-w-[200px] truncate">{r.description || '-'}</Td>
                          </Tr>
                        ))}
                      </tbody>
                      <tfoot>
                        <tr className="bg-sand-100 font-semibold">
                          <Td>الإجمالي</Td>
                          <Td></Td>
                          <Td></Td>
                          <Td className="tabular-nums">{formatCurrency(expensesData.reduce((s, r) => s + r.amount, 0))}</Td>
                          <Td></Td>
                          <Td></Td>
                        </tr>
                      </tfoot>
                    </Table>
                  </>
                )
              )}

              {/* Budget Tab */}
              {activeTab === 'budget' && (
                budgetData.length === 0 ? (
                  <EmptyState title="لا توجد بيانات" description="لا توجد ميزانيات أو مصاريف في هذا الشهر" />
                ) : (
                  <>
                    <Table>
                      <thead>
                        <tr>
                          <Th>الفرع</Th>
                          <Th>التصنيف</Th>
                          <Th>الميزانية</Th>
                          <Th>المنصرف</Th>
                          <Th>المتبقي</Th>
                          <Th>نسبة الاستهلاك</Th>
                        </tr>
                      </thead>
                      <tbody>
                        {budgetData.map((r, i) => {
                          const over = r.spent > r.budget && r.budget > 0;
                          const high = r.used_pct >= 80;
                          return (
                            <Tr key={i}>
                              <Td className="font-medium">{r.branch_name}</Td>
                              <Td>{r.category_name}</Td>
                              <Td className="tabular-nums">{formatCurrency(r.budget)}</Td>
                              <Td className={`tabular-nums font-medium ${over ? 'text-red-600 dark:text-red-400' : 'text-neutral-800'}`}>{formatCurrency(r.spent)}</Td>
                              <Td className={`tabular-nums ${r.remaining < 0 ? 'text-red-600 dark:text-red-400' : 'text-neutral-600'}`}>{formatCurrency(r.remaining)}</Td>
                              <Td>
                                <div className="flex items-center gap-2">
                                  <div className="w-24 h-2 rounded-full bg-sand-200 overflow-hidden">
                                    <div
                                      className={`h-full rounded-full ${over || high ? 'bg-red-500' : 'bg-brand-500'}`}
                                      style={{ width: `${Math.min(r.used_pct, 100)}%` }}
                                    />
                                  </div>
                                  <span className={`text-xs font-medium tabular-nums ${over || high ? 'text-red-600 dark:text-red-400' : 'text-neutral-600'}`}>
                                    {r.used_pct}%
                                  </span>
                                </div>
                              </Td>
                            </Tr>
                          );
                        })}
                      </tbody>
                      {budgetTotals && budgetTotals.rows > 0 && (
                        <tfoot>
                          <tr className="bg-sand-100 font-semibold">
                            <Td colSpan={2}>الإجمالي</Td>
                            <Td className="tabular-nums">{formatCurrency(budgetTotals.budget)}</Td>
                            <Td className="tabular-nums">{formatCurrency(budgetTotals.spent)}</Td>
                            <Td className={`tabular-nums ${budgetTotals.remaining < 0 ? 'text-red-600 dark:text-red-400' : 'text-neutral-800'}`}>{formatCurrency(budgetTotals.remaining)}</Td>
                            <Td></Td>
                          </tr>
                        </tfoot>
                      )}
                    </Table>
                  </>
                )
              )}

              {/* Commissions Tab */}
              {activeTab === 'commissions' && (
                commissionData.length === 0 ? (
                  <EmptyState title="لا توجد بيانات" description="لا توجد ورديات مغلقة في هذا الشهر" />
                ) : (
                  <>
                    <Table>
                      <thead>
                        <tr>
                          <Th>الموظف</Th>
                          <Th>الفرع</Th>
                          <Th>عدد الورديات</Th>
                          <Th>عدد القطع</Th>
                          <Th>عدد الياردات</Th>
                          <Th>إجمالي المبيعات</Th>
                          <Th>العمولة</Th>
                        </tr>
                      </thead>
                      <tbody>
                        {commissionData.map((r, i) => (
                          <Tr key={i}>
                            <Td className="font-medium">{r.employee_name}</Td>
                            <Td>{r.branch_name}</Td>
                            <Td className="tabular-nums">{r.sessions_count}</Td>
                            <Td className="tabular-nums font-medium">{formatNumber(r.total_pieces)}</Td>
                            <Td className="tabular-nums">{formatNumber(r.total_yards)}</Td>
                            <Td className="tabular-nums">{formatCurrency(r.total_sales)}</Td>
                            <Td className={`tabular-nums font-medium ${r.total_commission > 0 ? 'text-emerald-700 dark:text-emerald-400' : 'text-neutral-500'}`}>{formatCurrency(r.total_commission)}</Td>
                          </Tr>
                        ))}
                      </tbody>
                      {commissionTotals && commissionTotals.employees > 0 && (
                        <tfoot>
                          <tr className="bg-sand-100 font-semibold">
                            <Td colSpan={2}>الإجمالي</Td>
                            <Td className="tabular-nums">{commissionTotals.sessions}</Td>
                            <Td className="tabular-nums">{formatNumber(commissionTotals.pieces)}</Td>
                            <Td className="tabular-nums">{formatNumber(commissionTotals.yards)}</Td>
                            <Td className="tabular-nums">{formatCurrency(commissionTotals.sales)}</Td>
                            <Td className="tabular-nums text-emerald-700 dark:text-emerald-400">{formatCurrency(commissionTotals.commission)}</Td>
                          </tr>
                        </tfoot>
                      )}
                    </Table>
                  </>
                )
              )}

              {/* Net Daily Tab */}
              {activeTab === 'net' && (
                netData.length === 0 ? (
                  <EmptyState title="لا توجد بيانات" description="لا توجد بيانات صافي يومي في الفترة المحددة" />
                ) : (
                  <>
                    <Table>
                      <thead>
                        <tr>
                          <Th>التاريخ</Th>
                          <Th>المبيعات</Th>
                          <Th>المصاريف</Th>
                          <Th>الصافي</Th>
                        </tr>
                      </thead>
                      <tbody>
                        {netData.map((r, i) => (
                          <Tr key={i}>
                            <Td>{formatDate(r.date)}</Td>
                            <Td className="tabular-nums">{formatCurrency(r.sales)}</Td>
                            <Td className="tabular-nums">{formatCurrency(r.expenses)}</Td>
                            <Td className={`tabular-nums font-medium ${r.net < 0 ? 'text-red-600 dark:text-red-400' : 'text-brand-700 dark:text-brand-400'}`}>
                              {formatCurrency(r.net)}
                            </Td>
                          </Tr>
                        ))}
                      </tbody>
                    </Table>
                    <div className="mt-4 p-4 bg-sand-50 rounded-xl flex justify-between items-center">
                      <span className="text-sm text-neutral-500">إجمالي الصافي</span>
                      <span className={`text-lg font-bold tabular-nums ${netData.reduce((s, r) => s + r.net, 0) < 0 ? 'text-red-600 dark:text-red-400' : 'text-brand-700 dark:text-brand-400'}`}>
                        {formatCurrency(netData.reduce((s, r) => s + r.net, 0))}
                      </span>
                    </div>
                  </>
                )
              )}

              {/* Suppliers Tab */}
              {activeTab === 'suppliers' && (
                suppliersData.length === 0 ? (
                  <EmptyState title="لا يوجد موردون" />
                ) : (
                  <Table>
                    <thead>
                      <tr>
                        <Th>الاسم</Th>
                        <Th>الشركة</Th>
                        <Th>الهاتف</Th>
                        <Th>البريد</Th>
                        <Th>المدينة</Th>
                        <Th>الدولة</Th>
                      </tr>
                    </thead>
                    <tbody>
                      {suppliersData.map((r, i) => (
                        <Tr key={i}>
                          <Td className="font-medium">{r.name}</Td>
                          <Td>{r.company_name || '-'}</Td>
                          <Td dir="ltr" className="text-left">{r.phone || '-'}</Td>
                          <Td dir="ltr" className="text-left">{r.email || '-'}</Td>
                          <Td>{r.city || '-'}</Td>
                          <Td>{r.country || '-'}</Td>
                        </Tr>
                      ))}
                    </tbody>
                  </Table>
                )
              )}

              {/* Branches Tab */}
              {activeTab === 'branches' && (
                branchesData.length === 0 ? (
                  <EmptyState title="لا توجد فروع" />
                ) : (
                  <Table>
                    <thead>
                      <tr>
                        <Th>الاسم</Th>
                        <Th>الكود</Th>
                        <Th>الهاتف</Th>
                        <Th>المدينة</Th>
                        <Th>المبيعات</Th>
                        <Th>المصاريف</Th>
                      </tr>
                    </thead>
                    <tbody>
                      {branchesData.map((r, i) => (
                        <Tr key={i}>
                          <Td className="font-medium">{r.name}</Td>
                          <Td><span className="font-mono text-xs bg-sand-100 px-2 py-1 rounded">{r.code}</span></Td>
                          <Td dir="ltr" className="text-left">{r.phone || '-'}</Td>
                          <Td>{r.city || '-'}</Td>
                          <Td className="tabular-nums">{r.sales_count}</Td>
                          <Td className="tabular-nums">{r.expenses_count}</Td>
                        </Tr>
                      ))}
                    </tbody>
                  </Table>
                )
              )}

              {/* Inventory Tab */}
              {activeTab === 'inventory' && (
                inventoryData.length === 0 ? (
                  <EmptyState title="لا توجد بيانات" description="لا توجد أرصدة مخزون مطابقة" />
                ) : (
                  <>
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
                            <Td className="tabular-nums">{r.rolls_available}</Td>
                            <Td className={`tabular-nums font-medium ${r.low_stock ? 'text-red-600' : 'text-neutral-800'}`}>
                              {formatNumber(r.total_yards)}
                            </Td>
                            <Td className="tabular-nums">{formatNumber(r.min_stock)}</Td>
                            <Td>
                              {r.low_stock ? (
                                <span className="inline-flex items-center gap-1 text-xs font-medium text-red-600 bg-red-50 dark:bg-red-500/15 dark:text-red-400 rounded-full px-2.5 py-1">تحت الحد الأدنى</span>
                              ) : (
                                <span className="inline-flex items-center text-xs font-medium text-emerald-600 bg-emerald-50 dark:bg-emerald-500/15 dark:text-emerald-400 rounded-full px-2.5 py-1">مناسب</span>
                              )}
                            </Td>
                          </Tr>
                        ))}
                      </tbody>
                      {inventoryTotals && (
                        <tfoot>
                          <tr className="bg-sand-100 font-semibold">
                            <Td colSpan={3}>الإجمالي ({inventoryTotals.fabrics} قماش)</Td>
                            <Td className="tabular-nums">{inventoryTotals.rolls_available}</Td>
                            <Td className="tabular-nums">{formatNumber(inventoryTotals.total_yards)}</Td>
                            <Td className="tabular-nums">{inventoryTotals.low_stock_count}</Td>
                            <Td></Td>
                          </tr>
                        </tfoot>
                      )}
                    </Table>
                  </>
                )
              )}

              {/* Inventory Movements Tab */}
              {activeTab === 'inventory-movements' && (
                movementsData.length === 0 ? (
                  <EmptyState title="لا توجد بيانات" description="لا توجد حركات مطابقة" />
                ) : (
                  <>
                    <Table>
                      <thead>
                        <tr>
                          <Th>التاريخ</Th>
                          <Th>المخزن</Th>
                          <Th>القماش</Th>
                          <Th>الحركة</Th>
                          <Th>الكمية</Th>
                          <Th>الرصيد قبل</Th>
                          <Th>الرصيد بعد</Th>
                          <Th>المرجع</Th>
                        </tr>
                      </thead>
                      <tbody>
                        {movementsData.map((r, i) => (
                          <Tr key={i}>
                            <Td className="tabular-nums">{r.date}</Td>
                            <Td>{r.warehouse_name}</Td>
                            <Td>{r.fabric_name}</Td>
                            <Td>{r.movement_type_label}</Td>
                            <Td className={`tabular-nums font-medium ${Number(r.quantity) < 0 ? 'text-red-600' : 'text-emerald-700'}`}>
                              {Number(r.quantity) > 0 ? '+' : ''}{formatNumber(Number(r.quantity))}
                            </Td>
                            <Td className="tabular-nums text-neutral-500">{r.balance_before != null ? formatNumber(Number(r.balance_before)) : '—'}</Td>
                            <Td className="tabular-nums font-medium">{r.balance_after != null ? formatNumber(Number(r.balance_after)) : '—'}</Td>
                            <Td className="text-xs text-neutral-500" dir="ltr">{r.reference_no || '—'}</Td>
                          </Tr>
                        ))}
                      </tbody>
                      {movementsTotals && (
                        <tfoot>
                          <tr className="bg-sand-100 font-semibold">
                            <Td colSpan={4}>الإجمالي ({movementsTotals.count} حركة)</Td>
                            <Td className="tabular-nums text-emerald-700">+{formatNumber(movementsTotals.in)}</Td>
                            <Td className="tabular-nums text-red-600">-{formatNumber(movementsTotals.out)}</Td>
                            <Td></Td>
                            <Td></Td>
                          </tr>
                        </tfoot>
                      )}
                    </Table>
                  </>
                )
              )}

              {/* Profit & Loss Tab */}
              {activeTab === 'profit-loss' && plData && (
                <>
                  <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3 p-4">
                    <div className="rounded-xl bg-sand-50 p-4">
                      <div className="text-xs text-neutral-500 mb-1">إجمالي المبيعات</div>
                      <div className="text-xl font-bold tabular-nums text-brand-700">{formatCurrency(plData.totals.total_sales)}</div>
                      <PlChange pct={plData.comparison?.change_pct?.total_sales} invert />
                    </div>
                    <div className="rounded-xl bg-sand-50 p-4">
                      <div className="text-xs text-neutral-500 mb-1">تكلفة البضاعة المباعة</div>
                      <div className="text-xl font-bold tabular-nums text-neutral-800">{formatCurrency(plData.totals.cogs)}</div>
                      <PlChange pct={plData.comparison?.change_pct?.cogs} />
                    </div>
                    <div className="rounded-xl bg-sand-50 p-4">
                      <div className="text-xs text-neutral-500 mb-1">مجمل الربح</div>
                      <div className="text-xl font-bold tabular-nums text-emerald-700">{formatCurrency(plData.totals.gross_profit)}</div>
                      <PlChange pct={plData.comparison?.change_pct?.gross_profit} invert />
                      {plData.totals.gross_margin_pct != null && (
                        <div className="text-xs text-neutral-400 mt-1">هامش {formatNumber(plData.totals.gross_margin_pct)}%</div>
                      )}
                    </div>
                    <div className="rounded-xl bg-red-50 dark:bg-red-950/30 p-4">
                      <div className="text-xs text-neutral-500 mb-1">الرواتب (شهر الفترة)</div>
                      <div className="text-xl font-bold tabular-nums text-red-700">{formatCurrency(plData.totals.salaries)}</div>
                      <div className="text-xs text-neutral-400 mt-1">المدفوع فعلياً: {formatCurrency(plData.totals.salaries_paid)}</div>
                      <PlChange pct={plData.comparison?.change_pct?.salaries} />
                    </div>
                    <div className="rounded-xl bg-sand-50 p-4">
                      <div className="text-xs text-neutral-500 mb-1">المصاريف</div>
                      <div className="text-xl font-bold tabular-nums text-red-600">{formatCurrency(plData.totals.expenses)}</div>
                      <PlChange pct={plData.comparison?.change_pct?.expenses} />
                    </div>
                    <div className="rounded-xl bg-brand-50 dark:bg-brand-950/30 p-4">
                      <div className="text-xs text-neutral-500 mb-1">صافي الربح بعد كل شيء (مبيعات - تكلفة - رواتب - مصاريف)</div>
                      <div className={`text-2xl font-bold tabular-nums ${plData.totals.net_profit < 0 ? 'text-red-600' : 'text-brand-700'}`}>{formatCurrency(plData.totals.net_profit)}</div>
                      <div className="flex items-center gap-2 mt-1 flex-wrap">
                        <PlChange pct={plData.comparison?.change_pct?.net_profit} invert />
                        {plData.totals.net_margin_pct != null && (
                          <span className="text-xs text-neutral-500">هامش {formatNumber(plData.totals.net_margin_pct)}%</span>
                        )}
                      </div>
                    </div>
                  </div>

                  {plData.stock && (
                    <div className="px-4 pb-4">
                      <h3 className="text-sm font-semibold text-neutral-700 mb-1">
                        المشتريات والمخزون
                        <span className="text-xs font-normal text-neutral-500"> — تكلفة البضاعة غير المباعة تهمّ رأس المال، لا نتيجة الفترة</span>
                      </h3>
                      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
                        <div className="rounded-xl bg-sand-50 p-3">
                          <div className="text-xs text-neutral-500 mb-1">تكلفة المشتريات</div>
                          <div className="text-base font-bold tabular-nums text-neutral-800">{formatCurrency(plData.stock.purchases.value)}</div>
                          <div className="text-xs text-neutral-400 mt-0.5">{formatNumber(plData.stock.purchases.yards)} ياردة</div>
                        </div>
                        <div className="rounded-xl bg-sand-50 p-3">
                          <div className="text-xs text-neutral-500 mb-1">رصيد الإقفال بالياردة</div>
                          <div className="text-base font-bold tabular-nums text-neutral-800">{formatNumber(plData.stock.closing.yards)}</div>
                        </div>
                        <div className="rounded-xl bg-sand-50 p-3">
                          <div className="text-xs text-neutral-500 mb-1">قيمة رصيد الإقفال</div>
                          <div className="text-base font-bold tabular-nums text-brand-700">{formatCurrency(plData.stock.closing.value)}</div>
                        </div>
                        <div className="rounded-xl bg-emerald-50 dark:bg-emerald-950/30 p-3">
                          <div className="text-xs text-neutral-500 mb-1">قيمة البضاعة غير المباعة</div>
                          <div className={`text-base font-bold tabular-nums ${plData.stock.unsold_value < 0 ? 'text-red-600' : 'text-emerald-700'}`}>
                            {formatCurrency(plData.stock.unsold_value)}
                          </div>
                          {plData.stock.unsold_margin_pct != null && (
                            <div className="text-xs text-neutral-400 mt-0.5">{formatNumber(plData.stock.unsold_margin_pct)}% من المخزون</div>
                          )}
                        </div>
                      </div>
                    </div>
                  )}

                  {plData.comparison && (
                    <div className="px-4 pb-4">
                      <Table>
                        <thead>
                          <tr>
                            <Th>البيان</Th>
                            <Th>الفترة الحالية</Th>
                            <Th>الفترة السابقة</Th>
                            <Th>نسبة التغيّر</Th>
                          </tr>
                        </thead>
                        <tbody>
                          {PL_COMPARISON_ROWS.map(([key, label, invert]) => (
                            <Tr key={key}>
                              <Td className="font-medium">{label}</Td>
                              <Td className="tabular-nums">{formatCurrency(plData.totals[key])}</Td>
                              <Td className="tabular-nums text-neutral-500">{formatCurrency(plData.comparison.totals[key])}</Td>
                              <Td className="tabular-nums">
                                <PlChange pct={plData.comparison.change_pct[key]} invert={invert} />
                              </Td>
                            </Tr>
                          ))}
                        </tbody>
                      </Table>
                      <p className="text-xs text-neutral-400 mt-2">
                        الفترة السابقة: {formatDate(plData.comparison.date_from)} — {formatDate(plData.comparison.date_to)}
                      </p>
                    </div>
                  )}

                  {plData.expense_breakdown?.items.length > 0 && (
                    <div className="px-4 pb-4">
                      <h3 className="text-sm font-semibold text-neutral-700 mb-2">تفصيل المصاريف حسب البند</h3>
                      <Table>
                        <thead>
                          <tr>
                            <Th>البند</Th>
                            <Th>المبلغ</Th>
                            <Th>النسبة من المصاريف</Th>
                          </tr>
                        </thead>
                        <tbody>
                          {plData.expense_breakdown.items.map((r) => (
                            <Tr key={r.category_id}>
                              <Td className="font-medium">{r.category_name}</Td>
                              <Td className="tabular-nums">{formatCurrency(r.amount)}</Td>
                              <Td className="tabular-nums">{r.pct_of_total != null ? `${formatNumber(r.pct_of_total)}%` : '—'}</Td>
                            </Tr>
                          ))}
                        </tbody>
                        <tfoot>
                          <tr className="bg-sand-100 font-semibold">
                            <Td>الإجمالي</Td>
                            <Td className="tabular-nums">{formatCurrency(plData.expense_breakdown.total)}</Td>
                            <Td className="tabular-nums">100%</Td>
                          </tr>
                        </tfoot>
                      </Table>
                    </div>
                  )}

                  {plData.collection && (
                    <div className="px-4 pb-4">
                      <h3 className="text-sm font-semibold text-neutral-700 mb-2">
                        تفصيل المبيعات حسب التحصيل
                        {plData.collection.collection_rate_pct != null && (
                          <span className="text-xs font-normal text-neutral-500"> — نسبة التحصيل {formatNumber(plData.collection.collection_rate_pct)}%</span>
                        )}
                      </h3>
                      <div className="grid grid-cols-2 sm:grid-cols-5 gap-3">
                        {([
                          ['نقدي', plData.collection.cash, 'text-emerald-700'],
                          ['تحويل', plData.collection.transfer, 'text-brand-700'],
                          ['بطاقة', plData.collection.card, 'text-neutral-800'],
                          ['أخرى', plData.collection.other, 'text-neutral-600'],
                          ['إجمالي المحصّل', plData.collection.collected, 'text-brand-700'],
                        ] as const).map(([label, value, color]) => (
                          <div key={label} className="rounded-xl bg-sand-50 p-3">
                            <div className="text-xs text-neutral-500 mb-1">{label}</div>
                            <div className={`text-base font-bold tabular-nums ${color}`}>{formatCurrency(value)}</div>
                            <div className="text-xs text-neutral-400 mt-0.5">
                              {plData.collection.sales > 0
                                ? `${formatNumber((value / plData.collection.sales) * 100)}%`
                                : '—'}
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {plData.daily.length > 0 && (
                    <div className="px-4 pb-4">
                      <h3 className="text-sm font-semibold text-neutral-700 mb-2">
                        التفصيل اليومي
                        <span className="text-xs font-normal text-neutral-500"> — الرواتب تُحتسب على مستوى الشهر ولا تُوزَّع على الأيام</span>
                      </h3>
                      <Table>
                        <thead>
                          <tr>
                            <Th>التاريخ</Th>
                            <Th>المبيعات</Th>
                            <Th>تكلفة البضاعة المباعة</Th>
                            <Th>مجمل الربح</Th>
                            <Th>المصاريف</Th>
                            <Th>الصافي</Th>
                            <Th>هامش الصافي</Th>
                          </tr>
                        </thead>
                        <tbody>
                          {plData.daily.map((r) => (
                            <Tr key={r.date}>
                              <Td className="font-medium">{formatDate(r.date)}</Td>
                              <Td className="tabular-nums">{formatCurrency(r.sales)}</Td>
                              <Td className="tabular-nums">{formatCurrency(r.cogs)}</Td>
                              <Td className="tabular-nums">{formatCurrency(r.gross_profit)}</Td>
                              <Td className="tabular-nums">{formatCurrency(r.expenses)}</Td>
                              <Td className={`tabular-nums font-medium ${r.net < 0 ? 'text-red-600' : 'text-emerald-700'}`}>{formatCurrency(r.net)}</Td>
                              <Td className="tabular-nums">{r.net_margin_pct != null ? `${formatNumber(r.net_margin_pct)}%` : '—'}</Td>
                            </Tr>
                          ))}
                        </tbody>
                        <tfoot>
                          <tr className="bg-sand-100 font-semibold">
                            <Td>الإجمالي</Td>
                            <Td className="tabular-nums">{formatCurrency(plData.totals.total_sales)}</Td>
                            <Td className="tabular-nums">{formatCurrency(plData.totals.cogs)}</Td>
                            <Td className="tabular-nums">{formatCurrency(plData.totals.gross_profit)}</Td>
                            <Td className="tabular-nums">{formatCurrency(plData.totals.expenses)}</Td>
                            <Td className="tabular-nums">{formatCurrency(plData.totals.net_profit)}</Td>
                            <Td className="tabular-nums">{plData.totals.net_margin_pct != null ? `${formatNumber(plData.totals.net_margin_pct)}%` : '—'}</Td>
                          </tr>
                        </tfoot>
                      </Table>
                    </div>
                  )}

                  {plData.branches.length === 0 ? (
                    <EmptyState title="لا توجد بيانات" description="لا توجد فروع في الفترة المحددة" />
                  ) : (
                    <div className="px-4 pb-4">
                      <h3 className="text-sm font-semibold text-neutral-700 mb-2">مقارنة الفروع</h3>
                      <Table>
                        <thead>
                          <tr>
                            <Th>الفرع</Th>
                            <Th>المبيعات</Th>
                            <Th>التكلفة</Th>
                            <Th>الرواتب</Th>
                            <Th>المصاريف</Th>
                            <Th>الصافي</Th>
                            <Th>هامش الصافي</Th>
                          </tr>
                        </thead>
                        <tbody>
                          {plData.branches.map((r) => (
                            <Tr key={r.branch}>
                              <Td className="font-medium">{r.branch_name}</Td>
                              <Td className="tabular-nums">{formatCurrency(r.sales)}</Td>
                              <Td className="tabular-nums">{formatCurrency(r.cogs)}</Td>
                              <Td className="tabular-nums">{formatCurrency(r.salaries)}</Td>
                              <Td className="tabular-nums">{formatCurrency(r.expenses)}</Td>
                              <Td className={`tabular-nums font-medium ${r.net < 0 ? 'text-red-600' : 'text-emerald-700'}`}>{formatCurrency(r.net)}</Td>
                              <Td className="tabular-nums">{r.net_margin_pct != null ? `${formatNumber(r.net_margin_pct)}%` : '—'}</Td>
                            </Tr>
                          ))}
                        </tbody>
                      </Table>
                    </div>
                  )}
                </>
              )}

              {/* COGS Tab */}
              {activeTab === 'cogs' && (
                cogsData.length === 0 ? (
                  <EmptyState title="لا توجد بيانات" description="لا يوجد مبيعات أقمشة في الفترة المحددة" />
                ) : (
                  <>
                    <Table>
                      <thead>
                        <tr>
                          <Th>القماش</Th>
                          <Th>الكود</Th>
                          <Th>الكمية المباعة</Th>
                          <Th>متوسط التكلفة</Th>
                          <Th>الإيراد (تقريبي)</Th>
                          <Th>التكلفة</Th>
                          <Th>الربح</Th>
                        </tr>
                      </thead>
                      <tbody>
                        {cogsData.map((r, i) => (
                          <Tr key={i}>
                            <Td className="font-medium">{r.fabric_name}</Td>
                            <Td><span className="font-mono text-xs bg-sand-100 px-2 py-1 rounded">{r.fabric_code}</span></Td>
                            <Td className="tabular-nums">{formatNumber(r.yards_sold)}</Td>
                            <Td className="tabular-nums">{formatCurrency(r.avg_cost)}</Td>
                            <Td className="tabular-nums">{formatCurrency(r.revenue)}</Td>
                            <Td className="tabular-nums">{formatCurrency(r.cogs)}</Td>
                            <Td className={`tabular-nums font-medium ${r.profit < 0 ? 'text-red-600' : 'text-emerald-700'}`}>{formatCurrency(r.profit)}</Td>
                          </Tr>
                        ))}
                      </tbody>
                      {cogsTotals && (
                        <tfoot>
                          <tr className="bg-sand-100 font-semibold">
                            <Td colSpan={2}>الإجمالي</Td>
                            <Td className="tabular-nums">{formatNumber(cogsTotals.yards_sold)}</Td>
                            <Td></Td>
                            <Td className="tabular-nums">{formatCurrency(cogsTotals.revenue)}</Td>
                            <Td className="tabular-nums">{formatCurrency(cogsTotals.cogs)}</Td>
                            <Td className={`tabular-nums ${cogsTotals.profit < 0 ? 'text-red-600' : 'text-emerald-700'}`}>{formatCurrency(cogsTotals.profit)}</Td>
                          </tr>
                        </tfoot>
                      )}
                    </Table>
                  </>
                )
              )}

              {/* Journal Tab */}
              {activeTab === 'journal' && (
                journalData.length === 0 ? (
                  <EmptyState title="لا توجد بيانات" description="لا توجد قيود في الفترة المحددة" />
                ) : (
                  <>
                    <Table>
                      <thead>
                        <tr>
                          <Th>التاريخ</Th>
                          <Th>المبيعات</Th>
                          <Th>المشتريات</Th>
                          <Th>المصاريف</Th>
                          <Th>دعم الشركاء</Th>
                          <Th>سحب الشركاء</Th>
                          <Th>الصافي</Th>
                          <Th>الرصيد التراكمي</Th>
                        </tr>
                      </thead>
                      <tbody>
                        {journalData.map((r, i) => (
                          <Tr key={i}>
                            <Td>{formatDate(r.date)}</Td>
                            <Td className="tabular-nums">{formatCurrency(r.sales)}</Td>
                            <Td className="tabular-nums">{formatCurrency(r.purchases)}</Td>
                            <Td className="tabular-nums">{formatCurrency(r.expenses)}</Td>
                            <Td className="tabular-nums text-emerald-700">{formatCurrency(r.support)}</Td>
                            <Td className="tabular-nums text-red-600">{formatCurrency(r.withdraw)}</Td>
                            <Td className={`tabular-nums font-medium ${r.net < 0 ? 'text-red-600' : 'text-brand-700'}`}>{formatCurrency(r.net)}</Td>
                            <Td className="tabular-nums font-semibold">{formatCurrency(r.running_balance)}</Td>
                          </Tr>
                        ))}
                      </tbody>
                      {journalTotals && (
                        <tfoot>
                          <tr className="bg-sand-100 font-semibold">
                            <Td>الإجمالي</Td>
                            <Td className="tabular-nums">{formatCurrency(journalTotals.sales)}</Td>
                            <Td className="tabular-nums">{formatCurrency(journalTotals.purchases)}</Td>
                            <Td className="tabular-nums">{formatCurrency(journalTotals.expenses)}</Td>
                            <Td className="tabular-nums text-emerald-700">{formatCurrency(journalTotals.support)}</Td>
                            <Td className="tabular-nums text-red-600">{formatCurrency(journalTotals.withdraw)}</Td>
                            <Td className="tabular-nums text-brand-700">{formatCurrency(journalTotals.net)}</Td>
                            <Td></Td>
                          </tr>
                        </tfoot>
                      )}
                     </Table>
                   </>
                 )
               )}
            </>
          )}
        </Card>
          </>
        )}
      </div>
    </AppShell>
  );
}
