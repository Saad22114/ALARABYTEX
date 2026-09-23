'use client';

import { useState, useEffect, useMemo, useCallback, useRef } from 'react';
import AppShell from '@/components/layout/AppShell';
import Card from '@/components/ui/Card';
import Button from '@/components/ui/Button';
import Table, { Th, Td, Tr } from '@/components/ui/Table';
import Select from '@/components/ui/Select';
import DateRangeToolbar, { getRangeForKey, DateRangeKey } from '@/components/ui/DateRangeToolbar';
import Modal from '@/components/ui/Modal';
import ConfirmDialog from '@/components/ui/ConfirmDialog';
import SessionsPanel from '@/components/sessions/SessionsPanel';
import SessionItemEditModal from '@/components/sessions/SessionItemEditModal';
import SessionDetailsModal from '@/components/sessions/SessionDetailsModal';
import SessionEditModal from '@/components/sessions/SessionEditModal';
import ManualSessionModal from '@/components/sessions/ManualSessionModal';
import Badge from '@/components/ui/Badge';
import Spinner from '@/components/ui/Spinner';
import StatCard from '@/components/ui/StatCard';
import {
  Plus, Pencil, Trash2, Store, Timer,
  IndianRupee, Banknote, Download, Users, ChevronDown, ChevronLeft, Archive, Eye, EyeOff, ChevronsUp, ChevronsDownUp,
  Printer, Share2, CheckCircle,
} from 'lucide-react';
import {
  Branch, Employee, DailySale,
  SaleSummary, SalesByEmployeeResult, SaleSession, SessionSaleItem, Fabric,
} from '@/types';
import { listSales, getSalesSummary, getSalesByEmployee, salesExportUrl } from '@/services/sales';
import { listSaleSessions, removeSessionItem, deleteSaleSession } from '@/services/sessions';
import { listBranches } from '@/services/branches';
import { listEmployees } from '@/services/employees';
import { listFabrics } from '@/services/fabrics';
import { formatCurrency, formatNumber, formatDate } from '@/lib/format';
import { openSalesInvoice, sessionToDailySales } from '@/lib/invoice';
import { API_URL } from '@/services/api';
import { useToast } from '@/components/ui/Toast';
import { useSettings } from '@/components/providers/SettingsProvider';
import { useAuth } from '@/components/providers/AuthProvider';
import { toEmployee } from '@/lib/sessionEmployee';
import { hasWindow } from '@/lib/permissions';
import { useUrlState } from '@/lib/useUrlState';

export default function SalesPage() {
  const { toast } = useToast();
  const { settings } = useSettings();
  const { session } = useAuth();
  const me = session?.employee;
  const isManager = Boolean(me && (me.role === 'admin' || me.role === 'supervisor'));
  const [tab, setTab] = useUrlState<'sales' | 'sessions'>('tab', 'sales');

  const [branches, setBranches] = useState<Branch[]>([]);
  const [employees, setEmployees] = useState<Employee[]>([]);
  const [fabrics, setFabrics] = useState<Fabric[]>([]);
  const modalEmployees = isManager ? employees : me ? [toEmployee(me)] : [];

  const [filterBranch, setFilterBranch] = useUrlState('branch', '');
  const [filterEmployee, setFilterEmployee] = useUrlState('employee', '');
  const [dateFrom, setDateFrom] = useUrlState('from', getRangeForKey('today').from);
  const [dateTo, setDateTo] = useUrlState('to', getRangeForKey('today').to);

  const [empFrom, setEmpFrom] = useUrlState('emp_from', getRangeForKey('today').from);
  const [empTo, setEmpTo] = useUrlState('emp_to', getRangeForKey('today').to);

  const [summary, setSummary] = useState<SaleSummary | null>(null);
  const [byEmployee, setByEmployee] = useState<SalesByEmployeeResult | null>(null);
  const [showByEmployee, setShowByEmployee] = useState(false);
  const [byEmployeeLoading, setByEmployeeLoading] = useState(false);

  const [manualOpen, setManualOpen] = useState(false);
  const [generatedOpen, setGeneratedOpen] = useState(false);
  const [generatedSales, setGeneratedSales] = useState<DailySale[]>([]);

  const [closedSessions, setClosedSessions] = useState<SaleSession[]>([]);
  const [closedLoading, setClosedLoading] = useState(true);
  const [expandedClosed, setExpandedClosed] = useState<Set<number>>(new Set());
  const [showClosedSessions, setShowClosedSessions] = useState<boolean>(true);

  const [editClosedItem, setEditClosedItem] = useState<{ session: SaleSession; item: SessionSaleItem } | null>(null);
  const [deleteClosedItem, setDeleteClosedItem] = useState<{ session: SaleSession; item: SessionSaleItem } | null>(null);
  const [deleteClosedLoading, setDeleteClosedLoading] = useState(false);
  const [viewClosedSession, setViewClosedSession] = useState<SaleSession | null>(null);
  const [editClosedSession, setEditClosedSession] = useState<SaleSession | null>(null);
  const [deleteClosedSession, setDeleteClosedSession] = useState<SaleSession | null>(null);
  const [deleteClosedSessionLoading, setDeleteClosedSessionLoading] = useState(false);

  const [selectedClosed, setSelectedClosed] = useState<Set<number>>(new Set());
  const selectedClosedSessions = useMemo(
    () => closedSessions.filter((s) => selectedClosed.has(s.id)),
    [closedSessions, selectedClosed]
  );
  const allClosedSelected = closedSessions.length > 0 && closedSessions.every((s) => selectedClosed.has(s.id));

  useEffect(() => setSelectedClosed(new Set()), [filterBranch, filterEmployee, dateFrom, dateTo, tab]);

  const appliedDefaultPeriod = useRef<string | null>(null);
  useEffect(() => {
    if (!settings?.default_period) return;
    if (appliedDefaultPeriod.current === settings.default_period) return;
    appliedDefaultPeriod.current = settings.default_period;
    const r = getRangeForKey(settings.default_period as DateRangeKey);
    setDateFrom(r.from);
    setDateTo(r.to);
    setEmpFrom(r.from);
    setEmpTo(r.to);
  }, [settings?.default_period]);

  useEffect(() => {
    try {
      if (localStorage.getItem('showClosedSessions') === '0') setShowClosedSessions(false);
    } catch {}
  }, []);

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
    branch: filterBranch || undefined,
    employee: filterEmployee || undefined,
    date_from: dateFrom || undefined,
    date_to: dateTo || undefined,
  }), [filterBranch, filterEmployee, dateFrom, dateTo]);

  const fetchSummary = useCallback(() => {
    let cancelled = false;
    getSalesSummary(filterParams)
      .then((res) => { if (!cancelled) setSummary(res); })
      .catch(() => {});
    return () => { cancelled = true; };
  }, [filterParams]);

  useEffect(() => fetchSummary(), [fetchSummary]);

  const sessionParams = useMemo(() => ({
    status: 'closed',
    branch: filterBranch || undefined,
    employee: filterEmployee || undefined,
    closed_from: dateFrom || undefined,
    closed_to: dateTo || undefined,
    page_size: 200,
  }), [filterBranch, filterEmployee, dateFrom, dateTo]);

  const fetchClosedSessions = useCallback(() => {
    let cancelled = false;
    setClosedLoading(true);
    listSaleSessions(sessionParams)
      .then((res) => { if (!cancelled) setClosedSessions(res.results); })
      .catch((err) => { if (!cancelled) toast('error', err.message); })
      .finally(() => { if (!cancelled) setClosedLoading(false); });
    return () => { cancelled = true; };
  }, [sessionParams]);

  useEffect(() => {
    if (tab === 'sales') {
      fetchClosedSessions();
    }
  }, [tab, fetchClosedSessions]);

  const byEmployeeParams = useMemo(() => ({
    branch: filterBranch || undefined,
    employee: filterEmployee || undefined,
    date_from: empFrom || undefined,
    date_to: empTo || undefined,
  }), [filterBranch, filterEmployee, empFrom, empTo]);

  const fetchByEmployee = useCallback(() => {
    let cancelled = false;
    setByEmployeeLoading(true);
    getSalesByEmployee(byEmployeeParams)
      .then((res) => { if (cancelled) return; setByEmployee(res); })
      .catch(() => {})
      .finally(() => { if (!cancelled) setByEmployeeLoading(false); });
    return () => { cancelled = true; };
  }, [byEmployeeParams]);

  useEffect(() => { return fetchByEmployee(); }, [fetchByEmployee]);

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
      fetchSummary();
    } catch (err: any) {
      toast('error', err.message);
    } finally {
      setDeleteClosedLoading(false);
    }
  };

  const handleDeleteClosedSession = async () => {
    if (!deleteClosedSession) return;
    setDeleteClosedSessionLoading(true);
    try {
      await deleteSaleSession(deleteClosedSession.id);
      toast('success', 'تم حذف الوردية وإرجاع المخزون');
      setDeleteClosedSession(null);
      fetchClosedSessions();
      fetchSummary();
    } catch (err: any) {
      toast('error', err.message);
    } finally {
      setDeleteClosedSessionLoading(false);
    }
  };

  const toggleClosedExpand = useCallback((id: number) => {
    setExpandedClosed((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id); else next.add(id);
      return next;
    });
  }, []);

  const toggleClosedSelect = useCallback((id: number) => {
    setSelectedClosed((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id); else next.add(id);
      return next;
    });
  }, []);

  const toggleClosedSelectAll = useCallback(() => {
    setSelectedClosed(allClosedSelected ? new Set() : new Set(closedSessions.map((s) => s.id)));
  }, [closedSessions, allClosedSelected]);

  const closedSalesForInvoice = useMemo(
    () => selectedClosedSessions.flatMap((s) => sessionToDailySales(s)),
    [selectedClosedSessions]
  );

  const handlePrintClosedCombined = useCallback(() => {
    if (closedSalesForInvoice.length === 0) return;
    openSalesInvoice(closedSalesForInvoice, settings, { title: 'فاتورة مجمعة — الورديات المحفوظة', autoPrint: true });
  }, [closedSalesForInvoice, settings]);

  const handleShareClosedCombined = useCallback(() => {
    if (closedSalesForInvoice.length === 0) return;
    openSalesInvoice(closedSalesForInvoice, settings, { title: 'فاتورة مجمعة — الورديات المحفوظة', autoPrint: true });
  }, [closedSalesForInvoice, settings]);

  const allClosedExpanded = closedSessions.length > 0 && closedSessions.every((s) => expandedClosed.has(s.id));

  const toggleClosedAll = useCallback(() => {
    setExpandedClosed((prev) => (prev.size === 0 ? new Set(closedSessions.map((s) => s.id)) : new Set()));
  }, [closedSessions]);

  const sTotals = useMemo(() => {
    let items = 0, yards = 0, cash = 0, transfer = 0, card = 0, total = 0;
    for (const s of closedSessions) {
      items += s.items.length;
      yards += s.totals.yards;
      cash += s.totals.cash;
      transfer += s.totals.transfer;
      card += s.totals.card;
      total += s.totals.total;
    }
    return { items, yards, cash, transfer, card, total };
  }, [closedSessions]);

  const handleSaleGenerated = useCallback(async (session: SaleSession) => {
    const dates = Array.from(new Set(session.items.map((i) => i.sale_date))).sort();
    if (dates.length === 0) {
      const built = sessionToDailySales(session);
      if (built.length > 0) {
        setGeneratedSales(built);
        setGeneratedOpen(true);
      }
      return;
    }
    try {
      const res = await listSales({
        branch: String(session.branch),
        date_from: dates[0],
        date_to: dates[dates.length - 1],
        page: 1,
        page_size: 50,
      });
      const matched = res.results.filter((s) => s.branch === session.branch);
      if (matched.length > 0) {
        setGeneratedSales(matched);
        setGeneratedOpen(true);
        return;
      }
    } catch {
      /* fall through to local build */
    }
    setGeneratedSales(sessionToDailySales(session));
    setGeneratedOpen(true);
  }, []);

  const handleManualSaved = useCallback((session: SaleSession) => {
    setGeneratedSales(sessionToDailySales(session));
    setGeneratedOpen(true);
    fetchClosedSessions();
    fetchSummary();
  }, [fetchClosedSessions, fetchSummary]);

  const exportUrl = useMemo(() => `${API_URL}${salesExportUrl(filterParams)}`, [filterParams]);
  const avgPerDay = summary && summary.days_count > 0 ? summary.total_sales / summary.days_count : 0;

  return (
    <AppShell>
      <div className="space-y-4 lg:space-y-6">
        {/* Tab bar + actions */}
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex rounded-xl border border-sand-300 overflow-hidden bg-surface">
            {hasWindow(me?.permissions, 'sales', 'sales') && (
              <button type="button" onClick={() => setTab('sales')} className={`flex items-center gap-2 px-4 sm:px-6 py-2.5 text-sm font-medium transition-colors ${tab === 'sales' ? 'bg-brand-600 text-white' : 'text-neutral-600 hover:bg-sand-100'}`}>
                <Store size={16} />
                المبيعات
              </button>
            )}
            {hasWindow(me?.permissions, 'sales', 'sessions') && (
              <button type="button" onClick={() => setTab('sessions')} className={`flex items-center gap-2 px-4 sm:px-6 py-2.5 text-sm font-medium transition-colors ${tab === 'sessions' ? 'bg-brand-600 text-white' : 'text-neutral-600 hover:bg-sand-100'}`}>
                <Timer size={16} />
                ورديات البيع
              </button>
            )}
          </div>
          {tab === 'sales' && (
            <div className="flex items-center gap-2">
              <a href={exportUrl} target="_blank" rel="noreferrer">
                <Button variant="secondary" type="button">
                  <Download size={16} />
                  تصدير Excel
                </Button>
              </a>
              {hasWindow(me?.permissions, 'sessions', 'manual') && (
                <Button onClick={() => setManualOpen(true)}>
                  <Plus size={18} />
                  إضافة وردية كاملة
                </Button>
              )}
            </div>
          )}
        </div>

        {tab === 'sales' ? (
        <>
        {/* KPIs (الداشبورد) */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 lg:gap-4">
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

        {/* Closed sessions (الورديات المحفوظة) */}
        <Card>
          <div className="flex flex-wrap items-center justify-between gap-3 px-4 py-4 border-b border-sand-100">
            <button
              type="button"
              onClick={() => setShowClosedSessions((v) => {
                const next = !v;
                localStorage.setItem('showClosedSessions', next ? '1' : '0');
                return next;
              })}
              className="flex flex-wrap items-center gap-3 text-right"
              title={showClosedSessions ? 'طي قائمة الورديات المحفوظة' : 'عرض قائمة الورديات المحفوظة'}
            >
              <ChevronDown size={16} className={`text-neutral-400 transition-transform ${showClosedSessions ? '' : '-rotate-180'}`} />
              <span className="flex items-center gap-2 font-semibold text-neutral-800">
                <Archive size={18} className="text-brand-600" />
                الورديات المحفوظة
              </span>
              <Badge variant="neutral">{closedSessions.length} وردية</Badge>
              <span className="text-sm text-neutral-500 tabular-nums">
                الإجمالي: <b className="text-brand-700">{formatCurrency(closedSessions.reduce((sum, s) => sum + s.totals.total, 0))}</b>
              </span>
            </button>
            <div className="flex flex-wrap items-center gap-2">
              {(showClosedSessions && closedSessions.length > 0) && (
                <button
                  type="button"
                  onClick={toggleClosedAll}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-medium text-neutral-600 hover:bg-sand-100 dark:text-neutral-300 dark:hover:bg-neutral-800 transition-colors"
                  title={allClosedExpanded ? 'طي كل الورديات' : 'توسيع كل الورديات'}
                >
                  {allClosedExpanded ? <ChevronsUp size={16} /> : <ChevronsDownUp size={16} />}
                  {allClosedExpanded ? 'طي الكل' : 'توسيع الكل'}
                </button>
              )}
              <button
                type="button"
                onClick={() => setShowClosedSessions((v) => {
                  const next = !v;
                  localStorage.setItem('showClosedSessions', next ? '1' : '0');
                  return next;
                })}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
                  showClosedSessions
                    ? 'text-neutral-600 hover:bg-sand-100 dark:text-neutral-300 dark:hover:bg-neutral-800'
                    : 'text-brand-600 hover:bg-brand-50 dark:text-brand-400 dark:hover:bg-brand-500/15'
                }`}
                title={showClosedSessions ? 'إخفاء الورديات المحفوظة' : 'إظهار الورديات المحفوظة'}
              >
                {showClosedSessions ? <EyeOff size={16} /> : <Eye size={16} />}
                {showClosedSessions ? 'إخفاء' : 'إظهار'}
              </button>
            </div>
          </div>
          {showClosedSessions && (
            <>
              {closedSessions.length > 0 && (
              <div className="flex flex-wrap items-center justify-between gap-2 px-4 py-2.5 border-b border-sand-100">
                <label className="flex items-center gap-2 text-sm font-medium text-neutral-700 cursor-pointer select-none">
                  <input type="checkbox" checked={allClosedSelected} onChange={toggleClosedSelectAll} className="w-4 h-4 accent-brand-600" title="تحديد كل الورديات لدمجها في فاتورة واحدة" />
                  تحديد الكل
                </label>
                {selectedClosed.size > 0 ? (
                  <div className="flex flex-wrap items-center gap-2">
                    <Badge variant="neutral">{selectedClosed.size} وردية</Badge>
                    <span className="text-sm text-neutral-500 tabular-nums">
                      الإجمالي: <b className="text-brand-700">{formatCurrency(selectedClosedSessions.reduce((sum, s) => sum + s.totals.total, 0))}</b>
                    </span>
                    <Button size="sm" onClick={handlePrintClosedCombined}>
                      <Printer size={15} />
                      طباعة الفاتورة المجمعة
                    </Button>
                    <Button size="sm" variant="secondary" onClick={handleShareClosedCombined}>
                      <Share2 size={15} />
                      مشاركة الملف
                    </Button>
                    <button onClick={() => setSelectedClosed(new Set())} className="text-sm text-neutral-500 hover:text-red-600 transition-colors">
                      إلغاء التحديد
                    </button>
                  </div>
                ) : (
                  <span className="text-xs text-neutral-400">حدِّد أكثر من وردية لدمجها في فاتورة واحدة</span>
                )}
              </div>
              )}
              <div className="flex flex-wrap items-center gap-3 px-4 py-3 border-b border-sand-100">
                <Select
                  value={filterBranch}
                  onChange={(e) => { setFilterBranch(e.target.value); setFilterEmployee(''); }}
                  options={[{ value: '', label: 'كل الفروع' }, ...branches.map((b) => ({ value: b.id, label: b.name }))]}
                  className="w-full sm:w-44"
                />
                <Select
                  value={filterEmployee}
                  onChange={(e) => setFilterEmployee(e.target.value)}
                  options={[{ value: '', label: 'كل الموظفين' }, ...employees.map((emp) => ({ value: emp.id, label: emp.name }))]}
                  className="w-full sm:w-44"
                />
                <DateRangeToolbar
                  from={dateFrom}
                  to={dateTo}
                  onChange={(f, t) => { setDateFrom(f); setDateTo(t); }}
                />
                {(filterBranch || filterEmployee || dateFrom || dateTo) && (
                  <button
                    type="button"
                    onClick={() => { setFilterBranch(''); setFilterEmployee(''); setDateFrom(''); setDateTo(''); }}
                    className="text-sm text-brand-600 hover:underline"
                  >
                    مسح الفلاتر
                  </button>
                )}
              </div>
              {closedSessions.length > 0 && (
              <div className="flex flex-wrap items-center gap-3 px-4 py-3 border-b border-sand-100 bg-sand-50/60 dark:bg-neutral-900/40">
                <SummaryChip label="ورديات" value={String(closedSessions.length)} />
                <SummaryChip label="بنود" value={formatNumber(sTotals.items)} />
                <SummaryChip label="ياردات" value={formatNumber(sTotals.yards)} />
                <SummaryChip label="كاش" value={formatCurrency(sTotals.cash)} color="text-emerald-600" />
                <SummaryChip label="تحويل" value={formatCurrency(sTotals.transfer)} />
                <SummaryChip label="ماكينة" value={formatCurrency(sTotals.card)} color="text-amber-600" />
                <span className="mr-auto text-sm font-bold tabular-nums text-brand-700">
                  الإجمالي: {formatCurrency(sTotals.total)}
                </span>
              </div>
              )}
            </>
          )}
          {!showClosedSessions ? (
            <p className="px-4 py-6 text-center text-sm text-neutral-400">
              الورديات المحفوظة مخفية — اضغط «إظهار» لعرضها
            </p>
          ) : closedLoading ? (
            <div className="flex justify-center py-10"><Spinner size={28} /></div>
          ) : closedSessions.length === 0 ? (
            <p className="py-8 text-center text-sm text-neutral-400">لا توجد ورديات محفوظة — أغلِق وردية من تبويب «ورديات البيع» أو أضف وردية كاملة</p>
          ) : (
            <div>
              {closedSessions.map((s) => {
                const expanded = expandedClosed.has(s.id);
                return (
                  <div key={s.id} className="border-b border-sand-100 last:border-0">
                    <div className="flex flex-wrap items-center gap-1 px-4 py-2">
                      <input
                        type="checkbox"
                        className="h-4 w-4 rounded border-sand-300 accent-brand-600 shrink-0"
                        checked={selectedClosed.has(s.id)}
                        onChange={() => toggleClosedSelect(s.id)}
                        title="تحديد الوردية لدمج الفاتورة"
                      />
                      <button
                        type="button"
                        onClick={() => toggleClosedExpand(s.id)}
                        className={`flex-1 min-w-[240px] flex flex-wrap items-center justify-between gap-3 rounded-lg px-1 py-1 text-right transition-colors hover:bg-sand-50 ${expanded ? 'bg-sand-50' : ''}`}
                      >
                        <div className="flex flex-wrap items-center gap-3">
                          <ChevronLeft size={16} className={`text-neutral-400 transition-transform ${expanded ? 'rotate-90' : ''}`} />
                          <span className="font-medium text-neutral-800">{s.employee_name}</span>
                          <span className="text-sm text-neutral-500">{s.branch_name}</span>
                          <span className="text-xs text-neutral-400 tabular-nums">
                            {s.is_manual
                              ? formatDate(s.manual_date || s.closed_at || s.opened_at)
                              : `${formatDate(s.opened_at)}${s.closed_at ? ` → ${formatDate(s.closed_at)}` : ''}`}
                          </span>
                          {s.is_manual && <Badge variant="warning">يدوية</Badge>}
                        </div>
                        <div className="flex flex-wrap items-center gap-3">
                          <span className="text-sm text-neutral-500 tabular-nums">
                            {s.is_manual ? 'مجموع يدوي' : `${s.items.length} بند · ${formatNumber(s.totals.yards)} ياردة`}
                          </span>
                          <span className="font-bold tabular-nums text-brand-700">{formatCurrency(s.totals.total)}</span>
                        </div>
                      </button>
                      <div className="flex items-center gap-1.5">
                        <button onClick={() => setViewClosedSession(s)} className="p-1.5 rounded-lg hover:bg-sky-50 text-sky-600 dark:hover:bg-sky-500/15 dark:text-sky-400 transition-colors" title="مشاهدة الوردية">
                          <Eye size={15} />
                        </button>
                        <button onClick={() => setEditClosedSession(s)} className="p-1.5 rounded-lg hover:bg-amber-50 text-amber-600 dark:hover:bg-amber-500/15 dark:text-amber-400 transition-colors" title="تعديل الوردية">
                          <Pencil size={15} />
                        </button>
                        <button onClick={() => setDeleteClosedSession(s)} className="p-1.5 rounded-lg hover:bg-red-50 text-red-500 dark:hover:bg-red-500/15 dark:text-red-400 transition-colors" title="حذف الوردية">
                          <Trash2 size={15} />
                        </button>
                      </div>
                    </div>
                    {expanded && (
                      <div className="px-4 pb-4">
                        {s.is_manual ? (
                          <div className="rounded-xl border border-amber-200 bg-amber-50 p-3 text-sm text-amber-800">
                            <p className="font-medium">وردية مُدخلة يدوياً كمجموع — بدون تفاصيل أصناف.</p>
                            {s.notes && <p className="mt-1 whitespace-pre-wrap text-amber-700">{s.notes}</p>}
                            <div className="mt-3 flex flex-wrap items-center gap-2">
                              <Badge variant="success">كاش {formatCurrency(s.totals.cash)}</Badge>
                              <Badge variant="neutral">تحويل {formatCurrency(s.totals.transfer)}</Badge>
                              <Badge variant="warning">ماكينة {formatCurrency(s.totals.card)}</Badge>
                            </div>
                          </div>
                        ) : (
                          <>
                            <div className="overflow-x-auto rounded-xl border border-sand-200">
                              <Table>
                                <thead>
                                  <tr>
                                    <Th>القماش</Th>
                                    <Th>النوع</Th>
                                    <Th>الكمية</Th>
                                    <Th>هاتف الزبون</Th>
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
                                      <Td className="font-medium">
                                        <span className="flex flex-wrap items-center gap-1.5">
                                          {it.fabric_name}
                                          {it.is_returned && <Badge variant="danger">مسترجع</Badge>}
                                        </span>
                                        {it.is_returned && (
                                          <span className="block text-[11px] text-red-400 mt-0.5">{it.return_reason || 'بدون سبب'}</span>
                                        )}
                                      </Td>
                                      <Td><Badge variant="neutral">{it.sale_type_label}</Badge></Td>
                                      <Td className="tabular-nums">{it.quantity} {it.sale_type === 'roll' ? 'طاقة' : 'يارد'}</Td>
                                      <Td className="tabular-nums text-neutral-500">
                                        {it.customer_phone ? it.customer_phone : <span className="text-neutral-300">—</span>}
                                      </Td>
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
                                          <button onClick={() => setEditClosedItem({ session: s, item: it })} disabled={it.is_returned} title={it.is_returned ? 'لا يمكن تعديل بند مسترجع' : 'تعديل البيعة'} className="p-1.5 rounded-lg hover:bg-amber-50 text-amber-600 dark:hover:bg-amber-500/15 dark:text-amber-400 transition-colors disabled:opacity-30 disabled:cursor-not-allowed">
                                            <Pencil size={15} />
                                          </button>
                                          <button onClick={() => setDeleteClosedItem({ session: s, item: it })} disabled={it.is_returned} title={it.is_returned ? 'لا يمكن حذف بند مسترجع' : 'حذف البيعة'} className="p-1.5 rounded-lg hover:bg-red-50 text-red-500 dark:hover:bg-red-500/15 dark:text-red-400 transition-colors disabled:opacity-30 disabled:cursor-not-allowed">
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
                          </>
                        )}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </Card>

        {/* Per-employee breakdown */}
        <Card>
          <div className="flex flex-wrap items-center justify-between gap-3 px-4 py-3 border-b border-sand-100">
            <div className="flex flex-wrap items-center gap-3">
              <button
                type="button"
                onClick={() => setShowByEmployee((p) => { const next = !p; if (next) fetchByEmployee(); return next; })}
                className="flex items-center gap-2 font-semibold text-neutral-800"
                title={showByEmployee ? 'طي التوزيع' : 'عرض التوزيع'}
              >
                <Users size={18} className="text-brand-600" />
                توزيع المبيعات على الموظفين
                <ChevronDown size={15} className={`text-neutral-400 transition-transform ${showByEmployee ? '' : '-rotate-180'}`} />
              </button>
              <Badge variant="neutral">{byEmployee ? byEmployee.items.length : 0} موظف</Badge>
            </div>
            <span className="text-sm text-neutral-500 tabular-nums">
              الإجمالي: <b className="text-brand-700">{byEmployee ? formatCurrency(byEmployee.grand_total) : '—'}</b>
            </span>
          </div>
          {showByEmployee && (
            <div className="flex flex-wrap items-center gap-3 px-4 py-3 border-b border-sand-100">
              <DateRangeToolbar from={empFrom} to={empTo} onChange={(f, t) => { setEmpFrom(f); setEmpTo(t); }} />
            </div>
          )}
          {showByEmployee && (
            byEmployeeLoading && !byEmployee ? (
              <div className="flex justify-center py-10"><Spinner size={28} /></div>
            ) : !byEmployee || byEmployee.items.length === 0 ? (
              <p className="py-8 text-center text-sm text-neutral-400">لا توجد مبيعات مسندة لموظفين في هذه الفترة</p>
            ) : (
                <div className="overflow-x-auto">
                  <Table>
                    <thead>
                      <tr>
                        <Th>الموظف</Th>
                        <Th>عدد السجلات</Th>
                        <Th>عدد القطع</Th>
                        <Th>الياردات</Th>
                        <Th>النقدي</Th>
                        <Th>التحويل</Th>
                        <Th>البطاقة</Th>
                        <Th>الإجمالي</Th>
                        <Th className="min-w-[160px]">الحصة من الإجمالي</Th>
                      </tr>
                    </thead>
                    <tbody>
                      {byEmployee.items.map((row) => {
                        const pct = byEmployee.grand_total > 0 ? (row.total_sales / byEmployee.grand_total) * 100 : 0;
                        return (
                          <Tr key={row.employee}>
                            <Td className="font-medium">{row.employee_name}</Td>
                            <Td className="tabular-nums">{row.sales_count}</Td>
                            <Td className="tabular-nums">{formatNumber(row.items_count)}</Td>
                            <Td className="tabular-nums">{formatNumber(row.yards_total)}</Td>
                            <Td className="tabular-nums">{formatCurrency(row.cash_total)}</Td>
                            <Td className="tabular-nums">{formatCurrency(row.transfer_total)}</Td>
                            <Td className="tabular-nums">{formatCurrency(row.card_total)}</Td>
                            <Td className="tabular-nums font-semibold">{formatCurrency(row.total_sales)}</Td>
                            <Td>
                              <div className="flex items-center gap-2">
                                <div className="h-2.5 w-24 overflow-hidden rounded-full bg-sand-200">
                                  <div className="h-full rounded-full bg-brand-500" style={{ width: `${Math.min(100, pct)}%` }} />
                                </div>
                                <span className="text-xs tabular-nums text-neutral-500">{formatNumber(pct)}%</span>
                              </div>
                            </Td>
                          </Tr>
                        );
                      })}
                      {byEmployee.unassigned_total > 0 && (
                        <Tr>
                          <Td className="text-neutral-500 italic">غير مسندة لموظف</Td>
                          <Td className="text-neutral-400">—</Td>
                          <Td className="text-neutral-400">—</Td>
                          <Td className="text-neutral-400">—</Td>
                          <Td className="text-neutral-400">—</Td>
                          <Td className="text-neutral-400">—</Td>
                          <Td className="text-neutral-400">—</Td>
                          <Td className="tabular-nums font-semibold">{formatCurrency(byEmployee.unassigned_total)}</Td>
                          <Td className="text-xs text-neutral-400">—</Td>
                        </Tr>
                      )}
                    </tbody>
                    <tfoot>
                      <tr>
                        <Th>الإجمالي</Th>
                        <Th className="tabular-nums">{byEmployee.items.reduce((s, r) => s + r.sales_count, 0)}</Th>
                        <Th className="tabular-nums">{formatNumber(byEmployee.items.reduce((s, r) => s + r.items_count, 0))}</Th>
                        <Th className="tabular-nums">{formatNumber(byEmployee.items.reduce((s, r) => s + r.yards_total, 0))}</Th>
                        <Th className="tabular-nums">{formatCurrency(byEmployee.items.reduce((s, r) => s + r.cash_total, 0))}</Th>
                        <Th className="tabular-nums">{formatCurrency(byEmployee.items.reduce((s, r) => s + r.transfer_total, 0))}</Th>
                        <Th className="tabular-nums">{formatCurrency(byEmployee.items.reduce((s, r) => s + r.card_total, 0))}</Th>
                        <Th className="tabular-nums">{formatCurrency(byEmployee.grand_total)}</Th>
                        <Th>100%</Th>
                      </tr>
                    </tfoot>
                  </Table>
                </div>
              )
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

        <SessionDetailsModal
          open={!!viewClosedSession}
          session={viewClosedSession}
          onClose={() => setViewClosedSession(null)}
          onReopened={() => {
            fetchClosedSessions();
            fetchSummary();
          }}
        />

        <SessionEditModal
          open={!!editClosedSession}
          session={editClosedSession}
          employees={modalEmployees}
          branches={branches}
          onClose={() => setEditClosedSession(null)}
          onSaved={() => {
            fetchClosedSessions();
            fetchSummary();
          }}
        />

        <ConfirmDialog
          open={!!deleteClosedSession}
          onClose={() => setDeleteClosedSession(null)}
          onConfirm={handleDeleteClosedSession}
          loading={deleteClosedSessionLoading}
          title="حذف الوردية المحفوظة"
          message={
            deleteClosedSession
              ? deleteClosedSession.is_manual
                ? `هل أنت متأكد من حذف وردية ${deleteClosedSession.employee_name} اليدوية (إجمالي ${formatCurrency(deleteClosedSession.totals.total)})؟ سيتم عكس مبالغها من السجل اليومي.`
                : `هل أنت متأكد من حذف وردية ${deleteClosedSession.employee_name} (${deleteClosedSession.items.length} بند — إجمالي ${formatCurrency(deleteClosedSession.totals.total)})؟ سيتم حذف سجلاتها اليومية وإرجاع المخزون المستهلك.`
              : ''
          }
        />

        </>
        ) : (
          <SessionsPanel onChanged={refreshSalesTab} onSaleGenerated={handleSaleGenerated} />
        )}

        <ManualSessionModal
          open={manualOpen}
          employees={modalEmployees}
          onClose={() => setManualOpen(false)}
          onSaved={handleManualSaved}
        />

        <Modal open={generatedOpen} onClose={() => setGeneratedOpen(false)} title="تم توليد البيعة" maxWidth="max-w-2xl">
          {generatedSales.length > 0 && (
            <div className="space-y-5">
              <div className="flex items-start gap-3 p-4 bg-emerald-50 border border-emerald-200 rounded-xl">
                <CheckCircle size={20} className="text-emerald-500 mt-0.5 shrink-0" />
                <div className="text-sm text-emerald-800">
                  <p className="font-medium">
                    تم توليد {generatedSales.length === 1 ? 'بيعة' : `${generatedSales.length} بيعات`} بنجاح
                  </p>
                  <ul className="mt-2 space-y-1 text-emerald-700">
                    {generatedSales.map((s) => (
                      <li key={s.id || s.date}>
                        رقم الفاتورة {settings?.invoice_prefix}{s.id || '—'} · {formatDate(s.date)} · {s.branch_name} ·{' '}
                        {formatCurrency(s.total_sales)} {settings?.currency_symbol}
                      </li>
                    ))}
                  </ul>
                  <p className="mt-2 font-medium">
                    الإجمالي: {formatCurrency(generatedSales.reduce((a, s) => a + Number(s.total_sales), 0))} {settings?.currency_symbol}
                  </p>
                </div>
              </div>
              <div className="flex flex-wrap items-center gap-3">
                <Button size="sm" onClick={() => openSalesInvoice(generatedSales, settings, { title: generatedSales.length > 1 ? 'فاتورة مجمعة' : 'فاتورة بيع', autoPrint: true })}>
                  <Printer size={15} />
                  طباعة الفاتورة
                </Button>
                <Button size="sm" variant="secondary" onClick={() => openSalesInvoice(generatedSales, settings, { title: generatedSales.length > 1 ? 'فاتورة مجمعة' : 'فاتورة بيع', autoPrint: true })}>
                  <Share2 size={15} />
                  مشاركة PDF
                </Button>
                <Button size="sm" variant="ghost" onClick={() => setGeneratedOpen(false)}>تم</Button>
              </div>
            </div>
          )}
        </Modal>
      </div>
    </AppShell>
  );
}

function SummaryChip({ label, value, color = 'text-neutral-800' }: { label: string; value: string; color?: string }) {
  return (
    <div className="flex flex-col items-center rounded-xl border border-sand-200/80 bg-surface px-3 py-1.5 min-w-[72px]">
      <span className={`text-sm font-bold tabular-nums ${color}`}>{value}</span>
      <span className="text-xs text-neutral-400">{label}</span>
    </div>
  );
}
