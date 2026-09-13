'use client';

import { useState, useEffect } from 'react';
import AppShell from '@/components/layout/AppShell';
import Card from '@/components/ui/Card';
import Button from '@/components/ui/Button';
import Table, { Th, Td, Tr } from '@/components/ui/Table';
import Select from '@/components/ui/Select';
import DateRangePicker from '@/components/ui/DateRangePicker';
import Spinner from '@/components/ui/Spinner';
import EmptyState from '@/components/ui/EmptyState';
import { Download } from 'lucide-react';
import { Branch, SalesReportData, ExpensesReportData, NetDailyReportData, BranchesReportData, SuppliersReportData, InventoryReportRow, InventoryMovementReportRow, Warehouse, CogsReportRow, ProfitLossReportResult, JournalReportRow } from '@/types';
import { listBranches } from '@/services/branches';
import { listWarehouses } from '@/services/warehouses';
import { getSalesReport, getExpensesReport, getNetDailyReport, getSuppliersReport, getBranchesReport, getInventoryReport, getInventoryMovementsReport, getCogsReport, getProfitLossReport, getJournalReport } from '@/services/reports';
import { formatCurrency, formatDate, formatNumber } from '@/lib/format';
import { PAYMENT_METHODS_MAP } from '@/lib/constants';
import { API_URL } from '@/services/api';
import { useToast } from '@/components/ui/Toast';

type Tab = 'sales' | 'expenses' | 'net' | 'suppliers' | 'branches' | 'inventory' | 'inventory-movements' | 'profit-loss' | 'cogs' | 'journal';

const tabs: { value: Tab; label: string }[] = [
  { value: 'sales', label: 'تقرير المبيعات' },
  { value: 'expenses', label: 'تقرير المصاريف' },
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
  { value: 'transfer_in', label: 'تحويل وارد' },
  { value: 'adjustment_in', label: 'تسوية إضافة' },
  { value: 'adjustment_out', label: 'تسوية خصم' },
  { value: 'count', label: 'فارق جرد' },
  { value: 'opening', label: 'رصيد افتتاحي' },
  { value: 'sale', label: 'مبيعات' },
];

const UNIT_LABEL: Record<string, string> = {
  yard: 'ياردة',
  meter: 'متر',
  roll: 'لفة',
};

export default function ReportsPage() {
  const { toast } = useToast();
  const [activeTab, setActiveTab] = useState<Tab>('sales');
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');
  const [filterBranch, setFilterBranch] = useState('');
  const [branches, setBranches] = useState<Branch[]>([]);
  const [loading, setLoading] = useState(false);

  const [salesData, setSalesData] = useState<SalesReportData[]>([]);
  const [expensesData, setExpensesData] = useState<ExpensesReportData[]>([]);
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
  const [filterWarehouse, setFilterWarehouse] = useState('');
  const [filterMovementType, setFilterMovementType] = useState('');
  const [filterSearch, setFilterSearch] = useState('');

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

  const buildParams = () => {
    const p: Record<string, string | number | undefined | null> = {};
    if (dateFrom) p.date_from = dateFrom;
    if (dateTo) p.date_to = dateTo;
    if (filterBranch) p.branch = filterBranch;
    return p;
  };

  const buildExportUrl = (base: string) => {
    const params = new URLSearchParams();
    if (dateFrom) params.append('date_from', dateFrom);
    if (dateTo) params.append('date_to', dateTo);
    if (filterBranch) params.append('branch', filterBranch);
    params.append('export', 'xlsx');
    return `${API_URL}${base}?${params.toString()}`;
  };

  const loadTab = async (tab: Tab) => {
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
  };

  useEffect(() => {
    loadTab(activeTab);
  }, [activeTab, dateFrom, dateTo, filterBranch, filterWarehouse, filterMovementType, filterSearch]);

  const getExportUrl = () => {
    switch (activeTab) {
      case 'sales': return buildExportUrl('/reports/sales/');
      case 'expenses': return buildExportUrl('/reports/expenses/');
      case 'net': return buildExportUrl('/reports/net-daily/');
      case 'suppliers': return buildExportUrl('/reports/suppliers/');
      case 'branches': return buildExportUrl('/reports/branches/');
      case 'inventory':
        const invParams = new URLSearchParams();
        if (filterWarehouse) invParams.append('warehouse', filterWarehouse);
        if (filterSearch) invParams.append('search', filterSearch);
        invParams.append('export', 'xlsx');
        return `${API_URL}/reports/inventory/?${invParams.toString()}`;
      case 'inventory-movements':
        const movParams = new URLSearchParams();
        if (filterWarehouse) movParams.append('warehouse', filterWarehouse);
        if (filterMovementType) movParams.append('movement_type', filterMovementType);
        if (dateFrom) movParams.append('date_from', dateFrom);
        if (dateTo) movParams.append('date_to', dateTo);
        movParams.append('export', 'xlsx');
        return `${API_URL}/reports/inventory-movements/?${movParams.toString()}`;
      case 'profit-loss': return buildExportUrl('/reports/profit-loss/');
      case 'cogs': return buildExportUrl('/reports/cogs/');
      case 'journal': return buildExportUrl('/reports/journal/');
    }
  };

  return (
    <AppShell>
      <div className="space-y-6">
        {/* Filters */}
        <Card className="!p-4">
          <div className="flex flex-wrap items-end gap-4">
            <DateRangePicker
              from={dateFrom}
              to={dateTo}
              onChangeFrom={setDateFrom}
              onChangeTo={setDateTo}
            />
            {(activeTab === 'sales' || activeTab === 'expenses' || activeTab === 'net' || activeTab === 'profit-loss' || activeTab === 'journal') && (
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
            {tabs.map((t) => (
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
          <a
            href={getExportUrl() || '#'}
            target="_blank"
            rel="noopener noreferrer"
          >
            <Button variant="secondary" size="sm">
              <Download size={16} />
              تصدير Excel
            </Button>
          </a>
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
                          <Th>اللفات</Th>
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
                  <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3 p-4">
                    <div className="rounded-xl bg-sand-50 p-4">
                      <div className="text-xs text-neutral-500 mb-1">إجمالي المبيعات</div>
                      <div className="text-xl font-bold tabular-nums text-brand-700">{formatCurrency(plData.totals.total_sales)}</div>
                    </div>
                    <div className="rounded-xl bg-sand-50 p-4">
                      <div className="text-xs text-neutral-500 mb-1">تكلفة البضاعة المباعة</div>
                      <div className="text-xl font-bold tabular-nums text-neutral-800">{formatCurrency(plData.totals.cogs)}</div>
                    </div>
                    <div className="rounded-xl bg-sand-50 p-4">
                      <div className="text-xs text-neutral-500 mb-1">مجمل الربح</div>
                      <div className="text-xl font-bold tabular-nums text-emerald-700">{formatCurrency(plData.totals.gross_profit)}</div>
                    </div>
                    <div className="rounded-xl bg-sand-50 p-4">
                      <div className="text-xs text-neutral-500 mb-1">المصاريف</div>
                      <div className="text-xl font-bold tabular-nums text-red-600">{formatCurrency(plData.totals.expenses)}</div>
                    </div>
                    <div className="rounded-xl bg-sand-50 p-4">
                      <div className="text-xs text-neutral-500 mb-1">صافي الربح</div>
                      <div className={`text-xl font-bold tabular-nums ${plData.totals.net_profit < 0 ? 'text-red-600' : 'text-brand-700'}`}>{formatCurrency(plData.totals.net_profit)}</div>
                    </div>
                  </div>
                  {plData.branches.length === 0 ? (
                    <EmptyState title="لا توجد بيانات" description="لا توجد فروع في الفترة المحددة" />
                  ) : (
                    <Table>
                      <thead>
                        <tr>
                          <Th>الفرع</Th>
                          <Th>المبيعات</Th>
                          <Th>المصاريف</Th>
                          <Th>النتيجة</Th>
                        </tr>
                      </thead>
                      <tbody>
                        {plData.branches.map((r, i) => (
                          <Tr key={i}>
                            <Td className="font-medium">{r.branch_name}</Td>
                            <Td className="tabular-nums">{formatCurrency(r.sales)}</Td>
                            <Td className="tabular-nums">{formatCurrency(r.expenses)}</Td>
                            <Td className={`tabular-nums font-medium ${r.net < 0 ? 'text-red-600' : 'text-emerald-700'}`}>{formatCurrency(r.net)}</Td>
                          </Tr>
                        ))}
                      </tbody>
                    </Table>
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
      </div>
    </AppShell>
  );
}
