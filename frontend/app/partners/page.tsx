'use client';

import { useState, useEffect, useMemo } from 'react';
import AppShell from '@/components/layout/AppShell';
import Card from '@/components/ui/Card';
import Button from '@/components/ui/Button';
import Table, { Th, Td, Tr } from '@/components/ui/Table';
import SearchInput from '@/components/ui/SearchInput';
import Select from '@/components/ui/Select';
import Input from '@/components/ui/Input';
import Textarea from '@/components/ui/Textarea';
import Pagination from '@/components/ui/Pagination';
import Modal from '@/components/ui/Modal';
import ConfirmDialog from '@/components/ui/ConfirmDialog';
import EmptyState from '@/components/ui/EmptyState';
import Spinner from '@/components/ui/Spinner';
import Badge from '@/components/ui/Badge';
import StatCard from '@/components/ui/StatCard';
import DateRangeToolbar, { currentMonthRange } from '@/components/ui/DateRangeToolbar';
import {
  Plus, Pencil, Trash2, TrendingUp, TrendingDown, Scale, UserRoundPlus,
  FileText, Download, Receipt, Wallet, Sparkles, Percent, ArrowRightLeft, Users, Printer,
} from 'lucide-react';
import Link from 'next/link';
import { Partner, PartnerOperation, Paginated, PartnerOperationType, PartnerPaymentMethod, PartnerOperationsSummary, PartnerDistributionResult } from '@/types';
import {
  listPartners,
  createPartner,
  updatePartner,
  deletePartner,
  listPartnerOperations,
  createPartnerOperation,
  deletePartnerOperation,
  getPartnerOperationsSummary,
  getPartnerDistribution,
} from '@/services/partners';
import { formatCurrency, formatDate } from '@/lib/format';
import { API_URL } from '@/services/api';
import { useToast } from '@/components/ui/Toast';
import { useSettings } from '@/components/providers/SettingsProvider';
import { useUrlState } from '@/lib/useUrlState';

const OPERATION_TYPE_OPTIONS = [
  { value: 'support', label: 'دعم (إيداع)' },
  { value: 'withdraw', label: 'سحب' },
];

const PAYMENT_METHOD_OPTIONS = [
  { value: 'cash', label: 'كاش' },
  { value: 'transfer', label: 'تحويل بنكي' },
];

interface OperationForm {
  partner: number | null;
  date: string;
  operation_type: PartnerOperationType;
  payment_method: PartnerPaymentMethod;
  amount: string;
  reason: string;
  notes: string;
}

interface PartnerForm {
  name: string;
  share_percent: string;
  notes: string;
  is_active: boolean;
}

type Tab = 'partners' | 'operations' | 'distribution';

const TABS: { value: Tab; label: string; icon: React.ReactNode }[] = [
  { value: 'partners', label: 'الشركاء والحسابات', icon: <Users size={16} /> },
  { value: 'operations', label: 'عمليات الشركاء', icon: <ArrowRightLeft size={16} /> },
  { value: 'distribution', label: 'توزيع الأرباح', icon: <Percent size={16} /> },
];

const emptyOperationForm = (): OperationForm => ({
  partner: null,
  date: '',
  operation_type: 'support',
  payment_method: 'cash',
  amount: '',
  reason: '',
  notes: '',
});

const emptyPartnerForm = (): PartnerForm => ({
  name: '',
  share_percent: '50',
  notes: '',
  is_active: true,
});

export default function PartnersPage() {
  const { toast } = useToast();
  const { settings } = useSettings();
  const pageSize = settings?.default_page_size ?? 10;

  const [partners, setPartners] = useState<Partner[]>([]);
  const [loadingPartners, setLoadingPartners] = useState(true);
  const [data, setData] = useState<Paginated<PartnerOperation> | null>(null);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useUrlState('q', '');
  const [page, setPage] = useUrlState('page', 1);
  const [tab, setTab] = useUrlState<Tab>('tab', 'partners');

  const [summary, setSummary] = useState<PartnerOperationsSummary | null>(null);
  const [summaryLoading, setSummaryLoading] = useState(true);
  const [distribution, setDistribution] = useState<PartnerDistributionResult | null>(null);
  const [distributionLoading, setDistributionLoading] = useState(false);

  const [from, setFrom] = useUrlState('from', currentMonthRange().from);
  const [to, setTo] = useUrlState('to', currentMonthRange().to);

  const [opModalOpen, setOpModalOpen] = useState(false);
  const [opForm, setOpForm] = useState<OperationForm>(emptyOperationForm());
  const [opSaving, setOpSaving] = useState(false);

  const [partnerModalOpen, setPartnerModalOpen] = useState(false);
  const [partnerForm, setPartnerForm] = useState<PartnerForm>(emptyPartnerForm());
  const [partnerEditing, setPartnerEditing] = useState<Partner | null>(null);
  const [partnerSaving, setPartnerSaving] = useState(false);

  const [deletingOp, setDeletingOp] = useState<PartnerOperation | null>(null);
  const [deletingPartner, setDeletingPartner] = useState<Partner | null>(null);
  const [deleteLoading, setDeleteLoading] = useState(false);

  const refreshPartners = () => {
    let cancelled = false;
    setLoadingPartners(true);
    listPartners({ page_size: 100 })
      .then((res) => { if (!cancelled) setPartners(res.results); })
      .catch((err) => { if (!cancelled) toast('error', err.message); })
      .finally(() => { if (!cancelled) setLoadingPartners(false); });
    return () => { cancelled = true; };
  };

  useEffect(refreshPartners, []);

  const fetchOperations = () => {
    let cancelled = false;
    setLoading(true);
    const params: Record<string, string | number | undefined | null> = {
      page,
      page_size: pageSize,
      search: search || undefined,
      date_from: from,
      date_to: to,
    };
    listPartnerOperations(params)
      .then((res) => { if (!cancelled) setData(res); })
      .catch((err) => { if (!cancelled) toast('error', err.message); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  };

  const fetchSummary = () => {
    let cancelled = false;
    setSummaryLoading(true);
    getPartnerOperationsSummary({ date_from: from, date_to: to })
      .then((res) => { if (!cancelled) setSummary(res); })
      .catch((err) => { if (!cancelled) toast('error', err.message); })
      .finally(() => { if (!cancelled) setSummaryLoading(false); });
    return () => { cancelled = true; };
  };

  const fetchDistribution = () => {
    let cancelled = false;
    setDistributionLoading(true);
    getPartnerDistribution({ date_from: from, date_to: to })
      .then((res) => { if (!cancelled) setDistribution(res); })
      .catch((err) => { if (!cancelled) toast('error', err.message); })
      .finally(() => { if (!cancelled) setDistributionLoading(false); });
    return () => { cancelled = true; };
  };

  useEffect(() => {
    const c1 = fetchOperations();
    const c2 = fetchSummary();
    return () => { c1(); c2(); };
  }, [page, search, from, to, pageSize]);

  useEffect(() => {
    if (tab === 'distribution') return fetchDistribution();
  }, [tab, from, to]);

  const totalPages = data ? Math.ceil(data.count / pageSize) : 1;

  const operationsExportUrl = useMemo(() => {
    const p = new URLSearchParams();
    p.append('export', 'xlsx');
    if (from) p.append('date_from', from);
    if (to) p.append('date_to', to);
    return `${API_URL}/partner-operations/?${p.toString()}`;
  }, [from, to]);

  const distributionExportUrl = useMemo(() => {
    const p = new URLSearchParams();
    p.append('export', 'xlsx');
    if (from) p.append('date_from', from);
    if (to) p.append('date_to', to);
    return `${API_URL}/partners/distribution/?${p.toString()}`;
  }, [from, to]);

  const printDistribution = () => {
    if (!distribution) return;
    const periodTitle = from || to
      ? `الفترة: ${formatDate(from)} إلى ${formatDate(to)}`
      : 'كل الفترات';
    const rows = distribution.items.map((it) => `
      <tr>
        <td>${it.name}</td>
        <td>${it.share_percent}%</td>
        <td>${formatCurrency(it.total_support)}</td>
        <td>${formatCurrency(it.total_withdraw)}</td>
        <td>${formatCurrency(it.actual_net)}</td>
        <td>${formatCurrency(it.theoretical_share)}</td>
        <td>${it.difference > 0.005 ? '+' : ''}${formatCurrency(it.difference)}</td>
        <td>${it.settlement === 'balanced' ? 'متوازن' : it.settlement === 'add' ? 'إضافة (دعم)' : 'سحب من الرصيد'}</td>
      </tr>`).join('');
    const html = `<!DOCTYPE html><html dir="rtl" lang="ar"><head><meta charset="utf-8"/>
      <title>تقرير حصص الشركاء</title>
      <style>
        body { font-family: 'Segoe UI', Tahoma, sans-serif; margin: 32px; color: #1a1a1a; }
        h1 { font-size: 20px; margin-bottom: 4px; }
        p { color: #555; margin: 2px 0; font-size: 13px; }
        table { width: 100%; border-collapse: collapse; margin-top: 16px; font-size: 12px; }
        th, td { border: 1px solid #ccc; padding: 8px; text-align: right; }
        th { background: #f1f1e9; }
        tfoot td { font-weight: bold; background: #f7f7ef; }
      </style></head><body>
      <h1>تقرير حصة كل شريك مع احتساب التوزيع والإطفاء</h1>
      <p>${periodTitle}</p>
      <table>
        <thead><tr>
          <th>الشريك</th><th>نسبة المشاركة</th><th>الدعم</th><th>السحب</th>
          <th>الصافي الفعلي</th><th>النصيب النظري</th><th>الفرق</th><th>التسوية</th>
        </tr></thead>
        <tbody>${rows}</tbody>
        <tfoot><tr>
          <td>الإجمالي</td>
          <td>${distribution.items.reduce((s, it) => s + it.share_percent, 0)}%</td>
          <td>${formatCurrency(distribution.total_support)}</td>
          <td>${formatCurrency(distribution.total_withdraw)}</td>
          <td>${formatCurrency(distribution.total_net)}</td>
          <td>${formatCurrency(distribution.total_net)}</td>
          <td>0.00</td>
          <td>متوازن</td>
        </tr></tfoot>
      </table>
      <script>setTimeout(() => window.print(), 200);</script>
    </body></html>`;
    const win = window.open('', '_blank', 'width=900,height=700');
    if (!win) {
      toast('error', 'الرجاء السماح بالنوافذ المنبثقة للطباعة');
      return;
    }
    win.document.open();
    win.document.write(html);
    win.document.close();
  };

  const totalNetForBars = partners.reduce((s, p) => s + Math.max(p.net_balance || 0, 0), 0);

  const refreshAll = () => {
    refreshPartners();
    fetchOperations();
    fetchSummary();
    fetchDistribution();
  };

  const handleCreateOperation = async () => {
    const amount = parseFloat(opForm.amount);
    if (!opForm.partner) {
      toast('error', 'يرجى اختيار الشريك المسجل عليه العملية');
      return;
    }
    if (!opForm.date || !amount || amount <= 0) {
      toast('error', 'يرجى إدخال التاريخ ومبلغ صحيح أكبر من صفر');
      return;
    }
    setOpSaving(true);
    try {
      await createPartnerOperation({
        partner: opForm.partner,
        date: opForm.date,
        operation_type: opForm.operation_type,
        payment_method: opForm.payment_method,
        amount,
        reason: opForm.reason,
        notes: opForm.notes,
      });
      toast('success', 'تم تسجيل عملية الشريك');
      setOpModalOpen(false);
      setOpForm(emptyOperationForm());
      refreshAll();
    } catch (err: any) {
      toast('error', err.message);
    } finally {
      setOpSaving(false);
    }
  };

  const handleDeleteOperation = async () => {
    if (!deletingOp) return;
    setDeleteLoading(true);
    try {
      await deletePartnerOperation(deletingOp.id);
      toast('success', 'تم حذف عملية الشريك');
      setDeletingOp(null);
      refreshAll();
    } catch (err: any) {
      toast('error', err.message);
    } finally {
      setDeleteLoading(false);
    }
  };

  const openPartnerModal = (partner?: Partner) => {
    setPartnerEditing(partner || null);
    setPartnerForm(partner
      ? { name: partner.name, share_percent: String(partner.share_percent), notes: partner.notes, is_active: partner.is_active }
      : emptyPartnerForm());
    setPartnerModalOpen(true);
  };

  const handleSavePartner = async () => {
    if (!partnerForm.name.trim()) {
      toast('error', 'يرجى إدخال اسم الشريك');
      return;
    }
    const share = parseFloat(partnerForm.share_percent);
    if (!share || share <= 0 || share > 100) {
      toast('error', 'نسبة المشاركة يجب أن تكون بين 1 و 100');
      return;
    }
    setPartnerSaving(true);
    try {
      if (partnerEditing) {
        await updatePartner(partnerEditing.id, { name: partnerForm.name, share_percent: share, notes: partnerForm.notes, is_active: partnerForm.is_active });
        toast('success', 'تم تحديث بيانات الشريك');
      } else {
        await createPartner({ name: partnerForm.name, share_percent: share, notes: partnerForm.notes });
        toast('success', 'تم إضافة الشريك بنجاح');
      }
      setPartnerModalOpen(false);
      refreshAll();
    } catch (err: any) {
      toast('error', err.message);
    } finally {
      setPartnerSaving(false);
    }
  };

  const handleDeletePartner = async () => {
    if (!deletingPartner) return;
    setDeleteLoading(true);
    try {
      await deletePartner(deletingPartner.id);
      toast('success', 'تم حذف الشريك');
      setDeletingPartner(null);
      refreshAll();
    } catch (err: any) {
      toast('error', err.message);
    } finally {
      setDeleteLoading(false);
    }
  };

  const opsTotal = data?.results.reduce((s, op) => s + op.amount, 0) ?? 0;

  return (
    <AppShell>
      <div className="space-y-6">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <h1 className="text-2xl font-bold">الشركاء</h1>
            <Badge variant="neutral">{partners.length} شريك</Badge>
          </div>
          <div className="flex items-center gap-2">
            {tab === 'operations' && (
              <a href={operationsExportUrl} target="_blank" rel="noreferrer">
                <Button variant="secondary" type="button">
                  <Download size={16} />
                  تصدير العمليات
                </Button>
              </a>
            )}
            {tab === 'distribution' && (
              <>
                <a href={distributionExportUrl} target="_blank" rel="noreferrer">
                  <Button variant="secondary" type="button">
                    <Download size={16} />
                    تصدير التوزيع
                  </Button>
                </a>
                <Button variant="secondary" type="button" onClick={printDistribution}>
                  <Printer size={16} />
                  طباعة / PDF
                </Button>
              </>
            )}
            <Button variant="secondary" onClick={() => openPartnerModal()}>
              <UserRoundPlus size={18} />
              إضافة شريك
            </Button>
            <Button
              onClick={() => { setOpForm({ ...emptyOperationForm(), partner: partners[0]?.id ?? null }); setOpModalOpen(true); }}
              disabled={partners.length === 0}
            >
              <Plus size={18} />
              عملية شريك
            </Button>
          </div>
        </div>

        {summaryLoading && !summary ? (
          <Card><div className="flex justify-center py-10"><Spinner size={28} /></div></Card>
        ) : summary ? (
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-4">
            <StatCard icon={<Receipt size={20} />} label="عمليات الفترة" value={summary.count} sub={summary.count === 1 ? 'عملية واحدة' : `${summary.count} عملية`} />
            <StatCard icon={<Wallet size={20} />} label="إجمالي العمليات" value={formatCurrency(summary.total_amount)} sub="مجموع كل العمليات في الفترة" />
            <StatCard icon={<TrendingUp size={20} />} iconBg="bg-emerald-50 text-emerald-600" label="الدعم في الفترة" value={formatCurrency(summary.support_amount)} sub={`${summary.support_count} عملية دعم`} />
            <StatCard icon={<TrendingDown size={20} />} iconBg="bg-red-50 text-red-600" label="السحب في الفترة" value={formatCurrency(summary.withdraw_amount)} sub={`${summary.withdraw_count} عملية سحب`} />
            <StatCard
              icon={<Scale size={20} />}
              iconBg={summary.net < 0 ? 'bg-red-50 text-red-600' : 'bg-emerald-50 text-emerald-600'}
              label="صافي الفترة"
              value={formatCurrency(summary.net)}
              sub="دعم − سحب"
            />
          </div>
        ) : null}

        <Card className="!p-4">
          <div className="flex flex-wrap items-end justify-between gap-4">
            <DateRangeToolbar from={from} to={to} onChange={(f, t) => { setFrom(f); setTo(t); setPage(1); }} />
            <div className="flex items-center gap-2">
              {tab === 'operations' && (
                <div className="w-[220px]">
                  <SearchInput value={search} onChange={(v) => { setSearch(v); setPage(1); }} placeholder="بحث برقم العملية..." />
                </div>
              )}
            </div>
          </div>
        </Card>

        <div className="flex flex-wrap gap-2">
          {TABS.map((t) => (
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

        {tab === 'partners' && (
          loadingPartners ? (
            <Card><div className="flex justify-center py-8"><Spinner size={28} /></div></Card>
          ) : partners.length === 0 ? (
            <Card className="!p-6">
              <EmptyState
                title="لا يوجد شركاء بعد"
                description="أضف شركاء المشروع أولاً لتسجيل حركات رأس المال بينهم"
              />
            </Card>
          ) : (
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {partners.map((p) => {
                const barPct = totalNetForBars > 0 ? (Math.max(p.net_balance || 0, 0) / totalNetForBars) * 100 : 0;
                return (
                  <Card key={p.id} className="!p-5">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-3">
                        <div className="flex h-11 w-11 items-center justify-center rounded-full bg-brand-50 text-lg font-bold text-brand-700">
                          {p.name.charAt(0)}
                        </div>
                        <div>
                          <div className="font-semibold">{p.name}</div>
                          <Badge variant={p.is_active ? 'success' : 'neutral'}>
                            {p.is_active ? `النسبة ${p.share_percent}%` : 'موقوف'}
                          </Badge>
                        </div>
                      </div>
                      <div className="flex items-center gap-1">
                        <button onClick={() => openPartnerModal(p)} className="p-1.5 rounded-lg hover:bg-amber-50 text-amber-600 dark:hover:bg-amber-500/15 dark:text-amber-400 transition-colors">
                          <Pencil size={15} />
                        </button>
                        <button onClick={() => setDeletingPartner(p)} className="p-1.5 rounded-lg hover:bg-red-50 text-red-500 dark:hover:bg-red-500/15 dark:text-red-400 transition-colors">
                          <Trash2 size={15} />
                        </button>
                      </div>
                    </div>
                    <div className="mt-4 space-y-2 text-sm">
                      <div className="flex items-center justify-between">
                        <span className="flex items-center gap-1.5 text-emerald-600"><TrendingUp size={15} /> إجمالي الدعم</span>
                        <span className="tabular-nums font-medium">{formatCurrency(p.total_support || 0)}</span>
                      </div>
                      <div className="flex items-center justify-between">
                        <span className="flex items-center gap-1.5 text-red-500"><TrendingDown size={15} /> إجمالي السحب</span>
                        <span className="tabular-nums font-medium">{formatCurrency(p.total_withdraw || 0)}</span>
                      </div>
                      <div className="flex items-center justify-between border-t border-sand-200 pt-2">
                        <span className="flex items-center gap-1.5 text-brand-600 font-medium"><Scale size={15} /> الصافي</span>
                        <span className={`tabular-nums font-semibold ${(p.net_balance || 0) < 0 ? 'text-red-500' : ''}`}>{formatCurrency(p.net_balance || 0)}</span>
                      </div>
                    </div>
                    <div className="mt-3">
                      <div className="mb-1 flex items-center justify-between text-xs text-neutral-500">
                        <span>نسبة المساهمة من إجمالي رأس المال</span>
                        <span className="tabular-nums">{barPct.toFixed(1)}%</span>
                      </div>
                      <div className="h-2 rounded-full bg-sand-100 overflow-hidden">
                        <div className={`h-full rounded-full ${(p.net_balance || 0) < 0 ? 'bg-red-400' : 'bg-brand-500'}`} style={{ width: `${Math.min(barPct, 100)}%` }} />
                      </div>
                    </div>
                    <Link
                      href={`/partners/${p.id}`}
                      className="mt-4 flex items-center justify-center gap-2 rounded-xl border border-sand-300 py-2 text-sm font-medium text-brand-600 transition-colors hover:bg-brand-50"
                    >
                      <FileText size={15} />
                      كشف الحساب والتقارير
                    </Link>
                  </Card>
                );
              })}
            </div>
          )
        )}

        {tab === 'operations' && (
          <Card>
            {loading ? (
              <div className="flex justify-center py-12"><Spinner size={32} /></div>
            ) : !data || data.results.length === 0 ? (
              <EmptyState title="لا توجد عمليات" description="لم يتم تسجيل أي عمليات شركاء في هذه الفترة" />
            ) : (
              <>
                <div className="p-3 border-b border-sand-100 flex items-center justify-between">
                  <span className="text-sm text-neutral-500">{data.count} عملية</span>
                  <span className="text-sm text-neutral-500">
                    إجمالي الصفحة: <span className="font-bold text-neutral-800 tabular-nums">{formatCurrency(opsTotal)}</span>
                  </span>
                </div>
                <Table>
                  <thead>
                    <tr>
                      <Th>الرقم</Th>
                      <Th>التاريخ</Th>
                      <Th>الشريك</Th>
                      <Th>النوع</Th>
                      <Th>طريقة الدفع</Th>
                      <Th>المبلغ</Th>
                      <Th>السبب</Th>
                      <Th>إجراءات</Th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.results.map((op) => (
                      <Tr key={op.id}>
                        <Td className="tabular-nums font-medium">{op.number}</Td>
                        <Td>{formatDate(op.date)}</Td>
                        <Td className="font-medium">{op.partner_name || '—'}</Td>
                        <Td>
                          <Badge variant={op.operation_type === 'support' ? 'success' : 'danger'}>
                            {op.operation_type_label}
                          </Badge>
                        </Td>
                        <Td>
                          <Badge variant={op.payment_method === 'cash' ? 'neutral' : 'warning'}>
                            {op.payment_method_label}
                          </Badge>
                        </Td>
                        <Td className={`tabular-nums font-bold ${op.operation_type === 'support' ? 'text-emerald-600' : 'text-red-500'}`}>
                          {formatCurrency(op.amount)}
                        </Td>
                        <Td className="max-w-[180px] truncate">{op.reason || op.notes || '-'}</Td>
                        <Td>
                          <button onClick={() => setDeletingOp(op)} className="p-1.5 rounded-lg hover:bg-red-50 text-red-500 dark:hover:bg-red-500/15 dark:text-red-400 transition-colors">
                            <Trash2 size={16} />
                          </button>
                        </Td>
                      </Tr>
                    ))}
                  </tbody>
                </Table>
                <Pagination page={page} totalPages={totalPages} onChange={setPage} count={data.count} pageSize={pageSize} />
              </>
            )}
          </Card>
        )}

        {tab === 'distribution' && (
          <div className="space-y-4">
            {distribution && (
              <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
                <StatCard icon={<Scale size={20} />} iconBg="bg-emerald-50 text-emerald-600" label="إجمالي صافي رأس المال" value={formatCurrency(distribution.total_net)} sub="دعم − سحب لجميع الشركاء" />
                <StatCard icon={<TrendingUp size={20} />} iconBg="bg-emerald-50 text-emerald-600" label="إجمالي الدعم" value={formatCurrency(distribution.total_support)} />
                <StatCard icon={<TrendingDown size={20} />} iconBg="bg-red-50 text-red-600" label="إجمالي السحب" value={formatCurrency(distribution.total_withdraw)} />
              </div>
            )}
            <Card title={`توزيع الأرباح حسب نسب المشاركة (${distribution?.items.length ?? 0})`}>
              {distributionLoading && distribution === null ? (
                <div className="flex justify-center py-12"><Spinner size={32} /></div>
              ) : !distribution || distribution.items.length === 0 ? (
                <EmptyState title="لا يوجد شركاء نشطون" description="أضف شركاء نشطين لعرض توزيع الأرباح" />
              ) : (
                <Table>
                  <thead>
                    <tr>
                      <Th>الشريك</Th>
                      <Th>نسبة المشاركة</Th>
                      <Th>الدعم</Th>
                      <Th>السحب</Th>
                      <Th>الصافي الفعلي</Th>
                      <Th>النصيب النظري</Th>
                      <Th>الفرق</Th>
                      <Th>التسوية المطلوبة</Th>
                    </tr>
                  </thead>
                  <tbody>
                    {distribution.items.map((it) => (
                      <Tr key={it.id}>
                        <Td className="font-medium">{it.name}</Td>
                        <Td className="tabular-nums">{it.share_percent}%</Td>
                        <Td className="tabular-nums text-emerald-600">{formatCurrency(it.total_support)}</Td>
                        <Td className="tabular-nums text-red-500">{formatCurrency(it.total_withdraw)}</Td>
                        <Td className="tabular-nums">{formatCurrency(it.actual_net)}</Td>
                        <Td className="tabular-nums">{formatCurrency(it.theoretical_share)}</Td>
                        <Td className={`tabular-nums font-medium ${it.difference > 0.005 ? 'text-amber-600' : it.difference < -0.005 ? 'text-red-500' : ''}`}>
                          {it.difference > 0.005 ? '+' : ''}{formatCurrency(it.difference)}
                        </Td>
                        <Td>
                          {it.settlement === 'balanced' ? (
                            <Badge variant="success">متوازن</Badge>
                          ) : it.settlement === 'add' ? (
                            <Badge variant="warning">يجب دعم {formatCurrency(it.settlement_amount)}</Badge>
                          ) : (
                            <Badge variant="danger">يستحق سحب {formatCurrency(it.settlement_amount)}</Badge>
                          )}
                        </Td>
                      </Tr>
                    ))}
                  </tbody>
                  <tfoot>
                    <tr className="bg-sand-100 font-semibold">
                      <Td className="font-bold">الإجمالي</Td>
                      <Td className="tabular-nums">{distribution.items.reduce((s, it) => s + it.share_percent, 0)}%</Td>
                      <Td className="tabular-nums">{formatCurrency(distribution.total_support)}</Td>
                      <Td className="tabular-nums">{formatCurrency(distribution.total_withdraw)}</Td>
                      <Td className="tabular-nums">{formatCurrency(distribution.total_net)}</Td>
                      <Td className="tabular-nums">{formatCurrency(distribution.total_net)}</Td>
                      <Td className="tabular-nums">0.00</Td>
                      <Td>
                        <Badge variant={Math.abs(distribution.total_net) < 0.005 ? 'neutral' : 'success'}>
                          متوازن
                        </Badge>
                      </Td>
                    </tr>
                  </tfoot>
                </Table>
              )}
            </Card>
            <Card className="!p-4">
              <p className="flex items-start gap-2 text-sm text-neutral-500">
                <Sparkles size={16} className="mt-0.5 text-brand-500 shrink-0" />
                «النصيب النظري» = إجمالي صافي الفترة × نسبة مشاركة الشريك ÷ 100. «الفرق» يوضّح انحراف رصيد كل شريك عن نصيبه النظري،
                و«التسوية المطلوبة» (الإطفاء) تحدد الإجراء الموصى به — دعم إضافي أو سحب رصيد — لضبط الحسابات إلى توزيع عادل خلال الفترة المحددة.
              </p>
            </Card>
          </div>
        )}

        <Modal open={opModalOpen} onClose={() => setOpModalOpen(false)} title="عملية شريك جديدة" maxWidth="max-w-lg">
          <div className="space-y-4">
            <div className="rounded-xl border border-brand-200 bg-brand-50 px-4 py-3 text-sm text-brand-800">
              تُسجَّل العملية على الشريك المحدد فقط: دعم يزيد رصيده، وسحب يخصمه من رصيده.
            </div>
            <Select
              label="الشريك المسجل عليه العملية"
              value={opForm.partner ?? ''}
              onChange={(e) => setOpForm({ ...opForm, partner: Number(e.target.value) })}
              options={partners.map((p) => ({ value: p.id, label: p.name }))}
              placeholder="اختر الشريك"
            />
            <Input
              label="التاريخ"
              type="date"
              value={opForm.date}
              onChange={(e) => setOpForm({ ...opForm, date: e.target.value })}
            />
            <Select
              label="نوع العملية"
              value={opForm.operation_type}
              onChange={(e) => setOpForm({ ...opForm, operation_type: e.target.value as PartnerOperationType })}
              options={OPERATION_TYPE_OPTIONS}
            />
            <Select
              label="طريقة الدفع"
              value={opForm.payment_method}
              onChange={(e) => setOpForm({ ...opForm, payment_method: e.target.value as PartnerPaymentMethod })}
              options={PAYMENT_METHOD_OPTIONS}
            />
            <Input
              label="المبلغ"
              type="number"
              min="0"
              step="0.01"
              value={opForm.amount}
              onChange={(e) => setOpForm({ ...opForm, amount: e.target.value })}
              placeholder=""
            />
            <Input
              label="السبب"
              value={opForm.reason}
              onChange={(e) => setOpForm({ ...opForm, reason: e.target.value })}
              placeholder="مثال: سداد دفعة للشريك / دعم رأس المال..."
            />
            <Textarea
              label="ملاحظات"
              value={opForm.notes}
              onChange={(e) => setOpForm({ ...opForm, notes: e.target.value })}
              placeholder="ملاحظات اختيارية..."
            />
            <div className="flex items-center justify-end gap-2 pt-2">
              <Button variant="secondary" onClick={() => setOpModalOpen(false)}>إلغاء</Button>
              <Button onClick={handleCreateOperation} loading={opSaving}>تسجيل العملية</Button>
            </div>
          </div>
        </Modal>

        <Modal open={partnerModalOpen} onClose={() => setPartnerModalOpen(false)} title={partnerEditing ? 'تعديل الشريك' : 'إضافة شريك'} maxWidth="max-w-md">
          <div className="space-y-4">
            <Input
              label="اسم الشريك"
              value={partnerForm.name}
              onChange={(e) => setPartnerForm({ ...partnerForm, name: e.target.value })}
              placeholder="مثال: أحمد"
            />
            <Input
              label="نسبة المشاركة %"
              type="number"
              min="1"
              max="100"
              step="0.01"
              value={partnerForm.share_percent}
              onChange={(e) => setPartnerForm({ ...partnerForm, share_percent: e.target.value })}
            />
            <Textarea
              label="ملاحظات"
              value={partnerForm.notes}
              onChange={(e) => setPartnerForm({ ...partnerForm, notes: e.target.value })}
              placeholder="ملاحظات اختيارية..."
            />
            {partnerEditing && (
              <div className="flex items-center justify-between">
                <span className="text-sm font-medium text-neutral-700">شريك نشط</span>
                <input
                  type="checkbox"
                  checked={partnerForm.is_active}
                  onChange={(e) => setPartnerForm({ ...partnerForm, is_active: e.target.checked })}
                  className="h-4 w-4 accent-brand-600"
                />
              </div>
            )}
            <div className="flex items-center justify-end gap-2 pt-2">
              <Button variant="secondary" onClick={() => setPartnerModalOpen(false)}>إلغاء</Button>
              <Button onClick={handleSavePartner} loading={partnerSaving}>
                {partnerEditing ? 'حفظ التعديلات' : 'إضافة الشريك'}
              </Button>
            </div>
          </div>
        </Modal>

        <ConfirmDialog
          open={!!deletingOp}
          onClose={() => setDeletingOp(null)}
          onConfirm={handleDeleteOperation}
          loading={deleteLoading}
          message="هل أنت متأكد من حذف هذه العملية؟ سيتم حذف الحركة المرتبطة بها من حساب الشريك."
        />

        <ConfirmDialog
          open={!!deletingPartner}
          onClose={() => setDeletingPartner(null)}
          onConfirm={handleDeletePartner}
          loading={deleteLoading}
          message="هل أنت متأكد من حذف هذا الشريك؟ لا يمكن حذف شريك لديه حركات مسجلة."
        />
      </div>
    </AppShell>
  );
}