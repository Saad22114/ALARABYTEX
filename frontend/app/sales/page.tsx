'use client';

import { useState, useEffect, useMemo, useCallback } from 'react';
import AppShell from '@/components/layout/AppShell';
import Card from '@/components/ui/Card';
import Button from '@/components/ui/Button';
import Table, { Th, Td, Tr } from '@/components/ui/Table';
import SearchInput from '@/components/ui/SearchInput';
import Select from '@/components/ui/Select';
import DateRangePicker from '@/components/ui/DateRangePicker';
import Pagination from '@/components/ui/Pagination';
import Modal from '@/components/ui/Modal';
import ConfirmDialog from '@/components/ui/ConfirmDialog';
import SalesForm from '@/components/forms/SalesForm';
import SessionsPanel from '@/components/sessions/SessionsPanel';
import SessionItemEditModal from '@/components/sessions/SessionItemEditModal';
import Badge from '@/components/ui/Badge';
import EmptyState from '@/components/ui/EmptyState';
import Spinner from '@/components/ui/Spinner';
import StatCard from '@/components/ui/StatCard';
import {
  Plus, Pencil, Trash2, Store, Timer,
  IndianRupee, Banknote, Download, Users, ChevronDown, ChevronLeft, Archive,
} from 'lucide-react';
import {
  DailySale, Branch, Employee, Paginated,
  SaleWritePayload, SaleSummary, SalesByEmployeeResult, SaleSession, SessionSaleItem, Fabric,
} from '@/types';
import {
  listSales, createSale, updateSale, deleteSale,
  getSalesSummary, getSalesByEmployee, salesExportUrl,
} from '@/services/sales';
import { listSaleSessions, removeSessionItem } from '@/services/sessions';
import { listBranches } from '@/services/branches';
import { listEmployees } from '@/services/employees';
import { listFabrics } from '@/services/fabrics';
import { formatCurrency, formatNumber, formatDate } from '@/lib/format';
import { API_URL } from '@/services/api';
import { useToast } from '@/components/ui/Toast';
import { useSettings } from '@/components/providers/SettingsProvider';

export default function SalesPage() {
  const { toast } = useToast();
  const { settings } = useSettings();
  const [tab, setTab] = useState<'sales' | 'sessions'>('sales');
  const pageSize = settings?.default_page_size ?? 10;

  const [data, setData] = useState<Paginated<DailySale> | null>(null);
  const [branches, setBranches] = useState<Branch[]>([]);
  const [employees, setEmployees] = useState<Employee[]>([]);
  const [fabrics, setFabrics] = useState<Fabric[]>([]);
  const [loading, setLoading] = useState(true);

  const [search, setSearch] = useState('');
  const [filterBranch, setFilterBranch] = useState('');
  const [filterEmployee, setFilterEmployee] = useState('');
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');
  const [page, setPage] = useState(1);

  const [summary, setSummary] = useState<SaleSummary | null>(null);
  const [byEmployee, setByEmployee] = useState<SalesByEmployeeResult | null>(null);
  const [showByEmployee, setShowByEmployee] = useState(false);

  const [modalOpen, setModalOpen] = useState(false);
  const [editing, setEditing] = useState<DailySale | null>(null);
  const [deleting, setDeleting] = useState<DailySale | null>(null);
  const [deleteLoading, setDeleteLoading] = useState(false);

  const [closedSessions, setClosedSessions] = useState<SaleSession[]>([]);
  const [closedLoading, setClosedLoading] = useState(true);
  const [expandedClosed, setExpandedClosed] = useState<number | null>(null);
  const [editClosedItem, setEditClosedItem] = useState<{ session: SaleSession; item: SessionSaleItem } | null>(null);
  const [deleteClosedItem, setDeleteClosedItem] = useState<{ session: SaleSession; item: SessionSaleItem } | null>(null);
  const [deleteClosedLoading, setDeleteClosedLoading] = useState(false);

  useEffect(() => {
    let cancelled = false;
    listBranches({ page_size: 100 }).then((res) => {
      if (!cancelled) setBranches(res.results.filter((b) => b.is_active));
    });
    listFabrics({ page_size: 200 }).then((res) => {
      if (!cancelled) setFabrics(res.results);
    }).catch(() => {});
    return () => { cancelled = true; };
  }, []);

  useEffect(() => {
    let cancelled = false;
    listEmployees({ page_size: 200, branch: filterBranch || undefined })
      .then((res) => { if (!cancelled) setEmployees(res.results.filter((e) => e.is_active)); })
      .catch(() => { if (!cancelled) setEmployees([]); });
    return () => { cancelled = true; };
  }, [filterBranch]);

  const filterParams = useMemo(() => ({
    search: search || undefined,
    branch: filterBranch || undefined,
    employee: filterEmployee || undefined,
    date_from: dateFrom || undefined,
    date_to: dateTo || undefined,
  }), [search, filterBranch, filterEmployee, dateFrom, dateTo]);

  const fetchData = useCallback(() => {
    let cancelled = false;
    setLoading(true);
    listSales({ ...filterParams, page, page_size: pageSize })
      .then((res) => { if (!cancelled) setData(res); })
      .catch((err) => { if (!cancelled) toast('error', err.message); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [filterParams, page, pageSize]);

  useEffect(() => fetchData(), [fetchData]);

  const fetchSummary = useCallback(() => {
    let cancelled = false;
    getSalesSummary(filterParams)
      .then((res) => { if (!cancelled) setSummary(res); })
      .catch(() => {});
    return () => { cancelled = true; };
  }, [filterParams]);

  useEffect(() => fetchSummary(), [fetchSummary]);

  const fetchClosedSessions = useCallback(() => {
    let cancelled = false;
    setClosedLoading(true);
    listSaleSessions({ status: 'closed', branch: filterBranch || undefined, page_size: 100 })
      .then((res) => { if (!cancelled) setClosedSessions(res.results); })
      .catch((err) => { if (!cancelled) toast('error', err.message); })
      .finally(() => { if (!cancelled) setClosedLoading(false); });
    return () => { cancelled = true; };
  }, [filterBranch]);

  useEffect(() => {
    if (tab === 'sales') {
      fetchClosedSessions();
    }
  }, [tab, fetchClosedSessions]);

  const refreshSalesTab = useCallback(() => {
    fetchClosedSessions();
  }, [fetchClosedSessions]);

  const handleClosedDelete = async () => {
    if (!deleteClosedItem) return;
    setDeleteClosedLoading(true);
    try {
      await removeSessionItem(deleteClosedItem.session.id, deleteClosedItem.item.id);
      toast('success', 'تم حذف البيعة من الوردية وتحديث المبيعات');
      setDeleteClosedItem(null);
      fetchClosedSessions();
      fetchData();
      fetchSummary();
    } catch (err: any) {
      toast('error', err.message);
    } finally {
      setDeleteClosedLoading(false);
    }
  };

  const fetchByEmployee = useCallback(() => {
    let cancelled = false;
    getSalesByEmployee(filterParams)
      .then((res) => { if (!cancelled) setByEmployee(res); })
      .catch(() => {});
    return () => { cancelled = true; };
  }, [filterParams]);

  useEffect(() => { if (showByEmployee) return fetchByEmployee(); }, [showByEmployee, fetchByEmployee]);

  const totalPages = data ? Math.ceil(data.count / pageSize) : 1;

  const editBranches = useMemo(() => {
    if (!editing || branches.some((b) => b.id === editing.branch)) return branches;
    return [...branches, {
      id: editing.branch, name: editing.branch_name || 'فرع (موقوف)',
      code: '', phone: '', address: '', city: '', notes: '',
      is_active: false, sales_count: 0, expenses_count: 0, created_at: '', updated_at: '',
    }];
  }, [branches, editing]);

  const handleCreate = async (d: SaleWritePayload) => {
    await createSale(d);
    toast('success', 'تم تسجيل المبيعات بنجاح');
    setModalOpen(false);
    fetchData();
    fetchSummary();
    if (showByEmployee) fetchByEmployee();
  };

  const handleUpdate = async (d: SaleWritePayload) => {
    if (!editing) return;
    await updateSale(editing.id, d);
    toast('success', 'تم تحديث المبيعات بنجاح');
    setEditing(null);
    fetchData();
    fetchSummary();
    if (showByEmployee) fetchByEmployee();
  };

  const handleDelete = async () => {
    if (!deleting) return;
    setDeleteLoading(true);
    try {
      await deleteSale(deleting.id);
      toast('success', 'تم حذف السجل بنجاح');
      setDeleting(null);
      fetchData();
      fetchSummary();
      if (showByEmployee) fetchByEmployee();
    } catch (err: any) {
      toast('error', err.message);
    } finally {
      setDeleteLoading(false);
    }
  };

  const exportUrl = useMemo(() => `${API_URL}${salesExportUrl(filterParams)}`, [filterParams]);
  const avgPerDay = summary && summary.days_count > 0 ? summary.total_sales / summary.days_count : 0;

  return (
    <AppShell>
      <div className="space-y-6">
        {/* Tab bar + actions */}
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex rounded-xl border border-sand-300 overflow-hidden bg-surface">
            <button type="button" onClick={() => setTab('sales')} className={`flex items-center gap-2 px-4 sm:px-6 py-2.5 text-sm font-medium transition-colors ${tab === 'sales' ? 'bg-brand-600 text-white' : 'text-neutral-600 hover:bg-sand-100'}`}>
              <Store size={16} />
              المبيعات
            </button>
            <button type="button" onClick={() => setTab('sessions')} className={`flex items-center gap-2 px-4 sm:px-6 py-2.5 text-sm font-medium transition-colors ${tab === 'sessions' ? 'bg-brand-600 text-white' : 'text-neutral-600 hover:bg-sand-100'}`}>
              <Timer size={16} />
              ورديات البيع
            </button>
          </div>
          {tab === 'sales' && (
            <div className="flex items-center gap-2">
              <a href={exportUrl} target="_blank" rel="noreferrer">
                <Button variant="secondary" type="button">
                  <Download size={16} />
                  تصدير Excel
                </Button>
              </a>
              <Button onClick={() => setModalOpen(true)}>
                <Plus size={18} />
                تسجيل مبيعات
              </Button>
            </div>
          )}
        </div>

        {tab === 'sales' ? (
        <>
        {/* KPIs */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          <StatCard
            icon={<IndianRupee size={20} />}
            label="إجمالي المبيعات"
            value={summary ? formatCurrency(summary.total_sales) : '—'}
            sub={summary ? `${summary.sales_count} سجل في ${summary.days_count} يوم` : undefined}
          />
          <StatCard
            icon={<Banknote size={20} />}
            iconBg="bg-emerald-50 text-emerald-600"
            label="النقدي"
            value={summary ? formatCurrency(summary.cash) : '—'}
            sub={summary && summary.total_sales > 0 ? `${((summary.cash / summary.total_sales) * 100).toFixed(0)}% من الإجمالي` : undefined}
          />
          <StatCard
            icon={<Banknote size={20} />}
            iconBg="bg-blue-50 text-blue-600"
            label="التحويل والبطاقة"
            value={summary ? formatCurrency((summary.transfer || 0) + (summary.card || 0)) : '—'}
            sub={summary && summary.total_sales > 0 ? `${((((summary.transfer || 0) + (summary.card || 0)) / summary.total_sales) * 100).toFixed(0)}% من الإجمالي` : undefined}
          />
          <StatCard
            icon={<IndianRupee size={20} />}
            iconBg="bg-amber-50 text-amber-600"
            label="متوسط اليوم"
            value={summary ? formatCurrency(avgPerDay) : '—'}
            sub={summary ? `أخرى: ${formatCurrency(summary.other || 0)}` : undefined}
          />
        </div>

        {/* Filters */}
        <Card className="!p-4">
          <div className="flex flex-wrap items-end gap-3">
            <div className="flex-1 min-w-[180px]">
              <SearchInput value={search} onChange={(v) => { setSearch(v); setPage(1); }} placeholder="بحث في المبيعات..." />
            </div>
            <Select
              value={filterBranch}
              onChange={(e) => { setFilterBranch(e.target.value); setFilterEmployee(''); setPage(1); }}
              options={[{ value: '', label: 'كل الفروع' }, ...branches.map((b) => ({ value: b.id, label: b.name }))]}
              className="w-full sm:w-44"
            />
            <Select
              value={filterEmployee}
              onChange={(e) => { setFilterEmployee(e.target.value); setPage(1); }}
              options={[{ value: '', label: 'كل الموظفين' }, ...employees.map((emp) => ({ value: emp.id, label: emp.name }))]}
              className="w-full sm:w-44"
            />
            <DateRangePicker
              from={dateFrom}
              to={dateTo}
              onChangeFrom={(v) => { setDateFrom(v); setPage(1); }}
              onChangeTo={(v) => { setDateTo(v); setPage(1); }}
            />
          </div>
        </Card>

        {/* Per-employee breakdown */}
        {summary && summary.sales_count > 0 && (
          <button
            type="button"
            onClick={() => setShowByEmployee((p) => !p)}
            className="flex items-center gap-2 text-sm font-medium text-brand-600 hover:underline"
          >
            <Users size={16} />
            {showByEmployee ? 'إخفاء' : 'عرض'} توزيع المبيعات على الموظفين
            <ChevronDown size={14} className={`transition-transform ${showByEmployee ? 'rotate-180' : ''}`} />
          </button>
        )}
        {showByEmployee && byEmployee && (
          <Card className="!p-4">
            <h3 className="text-sm font-semibold text-neutral-700 mb-3">توزيع المبيعات على الموظفين</h3>
            {byEmployee.items.length === 0 ? (
              <p className="text-sm text-neutral-400">لا توجد مبيعات مسندة لموظفين في هذه الفترة</p>
            ) : (
              <div className="overflow-x-auto">
                <Table>
                  <thead>
                    <tr>
                      <Th>الموظف</Th>
                      <Th>عدد السجلات</Th>
                      <Th>النقدي</Th>
                      <Th>التحويل</Th>
                      <Th>البطاقة</Th>
                      <Th>الإجمالي</Th>
                    </tr>
                  </thead>
                  <tbody>
                    {byEmployee.items.map((row) => (
                      <Tr key={row.employee}>
                        <Td className="font-medium">{row.employee_name}</Td>
                        <Td className="tabular-nums">{row.sales_count}</Td>
                        <Td className="tabular-nums">{formatCurrency(row.cash_total)}</Td>
                        <Td className="tabular-nums">{formatCurrency(row.transfer_total)}</Td>
                        <Td className="tabular-nums">{formatCurrency(row.card_total)}</Td>
                        <Td className="tabular-nums font-semibold">{formatCurrency(row.total_sales)}</Td>
                      </Tr>
                    ))}
                    {byEmployee.unassigned_total > 0 && (
                      <Tr>
                        <Td className="text-neutral-500 italic">غير مسندة لموظف</Td>
                        <Td className="text-neutral-400">—</Td>
                        <Td className="text-neutral-400">—</Td>
                        <Td className="text-neutral-400">—</Td>
                        <Td className="text-neutral-400">—</Td>
                        <Td className="tabular-nums font-semibold">{formatCurrency(byEmployee.unassigned_total)}</Td>
                      </Tr>
                    )}
                  </tbody>
                </Table>
              </div>
            )}
          </Card>
        )}

        {/* Table */}
        <Card>
          {loading ? (
            <div className="flex justify-center py-12"><Spinner size={32} /></div>
          ) : !data || data.results.length === 0 ? (
            <EmptyState title="لا توجد مبيعات" description="لم يتم تسجيل أي مبيعات بعد" />
          ) : (
            <>
              <div className="overflow-x-auto">
                <Table>
                  <thead>
                    <tr>
                      <Th>التاريخ</Th>
                      <Th>الفرع</Th>
                      <Th>الموظف</Th>
                      <Th>الأصناف</Th>
                      <Th>إجمالي المبيعات</Th>
                      <Th>نقدي</Th>
                      <Th>تحويل</Th>
                      <Th>بطاقة</Th>
                      <Th>أخرى</Th>
                      <Th>إجمالي الدفع</Th>
                      <Th>الحالة</Th>
                      <Th>إجراءات</Th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.results.map((s) => (
                      <Tr key={s.id}>
                        <Td>{formatDate(s.date)}</Td>
                        <Td className="font-medium">{s.branch_name}</Td>
                        <Td>{s.employee_name || <span className="text-neutral-400">—</span>}</Td>
                        <Td>
                          {s.items && s.items.length > 0 ? (
                            <div className="flex flex-col gap-1">
                              {s.items.map((it) => (
                                <span key={it.id} className="text-xs text-neutral-600 whitespace-nowrap">
                                  {it.fabric_name}: <b className="tabular-nums">{it.yards}</b>
                                </span>
                              ))}
                            </div>
                          ) : (
                            <span className="text-xs text-neutral-400">—</span>
                          )}
                        </Td>
                        <Td className="tabular-nums font-medium">{formatCurrency(s.total_sales)}</Td>
                        <Td className="tabular-nums">{formatCurrency(s.cash_amount)}</Td>
                        <Td className="tabular-nums">{formatCurrency(s.transfer_amount)}</Td>
                        <Td className="tabular-nums">{formatCurrency(s.card_amount)}</Td>
                        <Td className="tabular-nums">{formatCurrency(s.other_amount)}</Td>
                        <Td className="tabular-nums">{formatCurrency(s.payment_total)}</Td>
                        <Td>
                          {s.mismatch ? (
                            <Badge variant="warning">غير متوازن</Badge>
                          ) : (
                            <Badge variant="success">متوازن</Badge>
                          )}
                        </Td>
                        <Td>
                          <div className="flex items-center gap-2">
                            <button onClick={() => setEditing(s)} className="p-1.5 rounded-lg hover:bg-amber-50 text-amber-600 dark:hover:bg-amber-500/15 dark:text-amber-400 transition-colors">
                              <Pencil size={16} />
                            </button>
                            <button onClick={() => setDeleting(s)} className="p-1.5 rounded-lg hover:bg-red-50 text-red-500 dark:hover:bg-red-500/15 dark:text-red-400 transition-colors">
                              <Trash2 size={16} />
                            </button>
                          </div>
                        </Td>
                      </Tr>
                    ))}
                  </tbody>
                </Table>
              </div>
              <Pagination page={page} totalPages={totalPages} onChange={setPage} count={data.count} pageSize={pageSize} />
            </>
          )}
        </Card>

        {/* Closed sessions (المبيعات المحفوظة) */}
        <Card>
          <div className="flex flex-wrap items-center justify-between gap-3 px-4 py-4 border-b border-sand-100">
            <div className="flex flex-wrap items-center gap-3">
              <span className="flex items-center gap-2 font-semibold text-neutral-800">
                <Archive size={18} className="text-brand-600" />
                الورديات المحفوظة
              </span>
              <Badge variant="neutral">{closedSessions.length} وردية</Badge>
              <span className="text-sm text-neutral-500 tabular-nums">
                الإجمالي: <b className="text-brand-700">{formatCurrency(closedSessions.reduce((sum, s) => sum + s.totals.total, 0))}</b>
              </span>
            </div>
          </div>
          {closedLoading ? (
            <div className="flex justify-center py-10"><Spinner size={28} /></div>
          ) : closedSessions.length === 0 ? (
            <p className="py-8 text-center text-sm text-neutral-400">لا توجد ورديات محفوظة — أغلِق وردية من تبويب «ورديات البيع» لتظهر هنا</p>
          ) : (
            <div>
              {closedSessions.map((s) => {
                const expanded = expandedClosed === s.id;
                return (
                  <div key={s.id} className="border-b border-sand-100 last:border-0">
                    <button
                      type="button"
                      onClick={() => setExpandedClosed(expanded ? null : s.id)}
                      className={`w-full flex flex-wrap items-center justify-between gap-3 px-4 py-3 text-right transition-colors hover:bg-sand-50 ${expanded ? 'bg-sand-50' : ''}`}
                    >
                      <div className="flex flex-wrap items-center gap-3">
                        <ChevronLeft size={16} className={`text-neutral-400 transition-transform ${expanded ? 'rotate-90' : ''}`} />
                        <span className="font-medium text-neutral-800">{s.employee_name}</span>
                        <span className="text-sm text-neutral-500">{s.branch_name}</span>
                        <span className="text-xs text-neutral-400 tabular-nums">{formatDate(s.opened_at)} {s.closed_at ? `→ ${formatDate(s.closed_at)}` : ''}</span>
                      </div>
                      <div className="flex flex-wrap items-center gap-3">
                        <span className="text-sm text-neutral-500 tabular-nums">{s.items.length} بند · {formatNumber(s.totals.yards)} ياردة</span>
                        <span className="font-bold tabular-nums text-brand-700">{formatCurrency(s.totals.total)}</span>
                      </div>
                    </button>
                    {expanded && (
                      <div className="px-4 pb-4">
                        <div className="overflow-x-auto rounded-xl border border-sand-200">
                          <Table>
                            <thead>
                              <tr>
                                <Th>القماش</Th>
                                <Th>النوع</Th>
                                <Th>الكمية</Th>
                                <Th>الياردات الفعلية</Th>
                                <Th>سعر الوحدة</Th>
                                <Th>طريقة الدفع</Th>
                                <Th>الإجمالي</Th>
                                <Th>تاريخ البيع</Th>
                                <Th>إجراءات</Th>
                              </tr>
                            </thead>
                            <tbody>
                              {s.items.map((it) => (
                                <Tr key={it.id}>
                                  <Td className="font-medium">{it.fabric_name}</Td>
                                  <Td><Badge variant="neutral">{it.sale_type_label}</Badge></Td>
                                  <Td className="tabular-nums">{it.quantity} {it.sale_type === 'roll' ? 'لفة' : 'يارد'}</Td>
                                  <Td className="tabular-nums text-neutral-500">{formatNumber(it.yards_effective)} ياردة</Td>
                                  <Td className="tabular-nums">{formatCurrency(it.unit_price)}</Td>
                                  <Td>
                                    <Badge variant={it.payment_method === 'card' ? 'warning' : it.payment_method === 'transfer' ? 'neutral' : 'success'}>
                                      {it.payment_method_label}
                                    </Badge>
                                  </Td>
                                  <Td className="tabular-nums font-semibold">{formatCurrency(it.total)}</Td>
                                  <Td className="tabular-nums text-sm text-neutral-500">{formatDate(it.sale_date)}</Td>
                                  <Td>
                                    <div className="flex items-center gap-1.5">
                                      <button onClick={() => setEditClosedItem({ session: s, item: it })} className="p-1.5 rounded-lg hover:bg-amber-50 text-amber-600 dark:hover:bg-amber-500/15 dark:text-amber-400 transition-colors" title="تعديل البيعة">
                                        <Pencil size={15} />
                                      </button>
                                      <button onClick={() => setDeleteClosedItem({ session: s, item: it })} className="p-1.5 rounded-lg hover:bg-red-50 text-red-500 dark:hover:bg-red-500/15 dark:text-red-400 transition-colors" title="حذف البيعة">
                                        <Trash2 size={15} />
                                      </button>
                                    </div>
                                  </Td>
                                </Tr>
                              ))}
                            </tbody>
                          </Table>
                        </div>
                        <div className="mt-3 flex flex-wrap items-center gap-2 text-sm">
                          <Badge variant="success">كاش {formatCurrency(s.totals.cash)}</Badge>
                          <Badge variant="neutral">تحويل {formatCurrency(s.totals.transfer)}</Badge>
                          <Badge variant="warning">ماكينة {formatCurrency(s.totals.card)}</Badge>
                        </div>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </Card>

        <SessionItemEditModal
          open={!!editClosedItem}
          session={editClosedItem?.session ?? null}
          item={editClosedItem?.item ?? null}
          fabrics={fabrics}
          onClose={() => setEditClosedItem(null)}
          onSaved={() => {
            fetchClosedSessions();
            fetchData();
            fetchSummary();
          }}
        />

        <ConfirmDialog
          open={!!deleteClosedItem}
          onClose={() => setDeleteClosedItem(null)}
          onConfirm={handleClosedDelete}
          loading={deleteClosedLoading}
          title="حذف بيعة من وردية محفوظة"
          message="هل أنت متأكد من حذف هذه البيعة؟ سيتم تحديث إجمالي الوردية والسجل اليومي والمخزون تلقائياً."
        />

        <Modal open={modalOpen} onClose={() => setModalOpen(false)} title="تسجيل مبيعات جديدة" maxWidth="max-w-2xl">
          <SalesForm branches={branches} allowNegative={settings?.allow_negative_stock} onSubmit={handleCreate} onCancel={() => setModalOpen(false)} />
        </Modal>

        <Modal open={!!editing} onClose={() => setEditing(null)} title="تعديل المبيعات" maxWidth="max-w-2xl">
          {editing && <SalesForm initial={editing} branches={editBranches} allowNegative={settings?.allow_negative_stock} onSubmit={handleUpdate} onCancel={() => setEditing(null)} />}
        </Modal>

        <ConfirmDialog
          open={!!deleting}
          onClose={() => setDeleting(null)}
          onConfirm={handleDelete}
          loading={deleteLoading}
          message="هل أنت متأكد من حذف سجل المبيعات هذا؟ لا يمكن التراجع عن هذا الإجراء."
        />
        </>
        ) : (
          <SessionsPanel onChanged={refreshSalesTab} />
        )}
      </div>
    </AppShell>
  );
}
