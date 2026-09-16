'use client';

import { useState, useEffect, Fragment } from 'react';
import { useRouter, useParams } from 'next/navigation';
import AppShell from '@/components/layout/AppShell';
import Card from '@/components/ui/Card';
import Button from '@/components/ui/Button';
import Table, { Th, Td, Tr } from '@/components/ui/Table';
import Modal from '@/components/ui/Modal';
import Select from '@/components/ui/Select';
import ConfirmDialog from '@/components/ui/ConfirmDialog';
import Spinner from '@/components/ui/Spinner';
import EmptyState from '@/components/ui/EmptyState';
import StatCard from '@/components/ui/StatCard';
import Badge from '@/components/ui/Badge';
import Pagination from '@/components/ui/Pagination';
import SupplierForm from '@/components/forms/SupplierForm';
import PurchaseForm from '@/components/forms/PurchaseForm';
import PaymentForm from '@/components/forms/PaymentForm';
import ReturnForm from '@/components/forms/ReturnForm';
import AdjustmentForm from '@/components/forms/AdjustmentForm';
import {
  ArrowRight,
  Pencil,
  Plus,
  Trash2,
  ChevronDown,
  ChevronUp,
  ShoppingBag,
  Wallet,
  Undo2,
  Scale,
  Printer,
  Download,
  Share2,
} from 'lucide-react';
import { Supplier, LedgerEntry, LedgerSummary, CreateLedgerEntry } from '@/types';
import { getSupplier, updateSupplier, getSupplierSummary, getSupplierLedger, createLedgerEntry, deleteLedgerEntry, receiveLedgerEntry } from '@/services/suppliers';
import { formatCurrency, formatDate } from '@/lib/format';
import { openSupplierReport } from '@/lib/supplierReport';
import { useToast } from '@/components/ui/Toast';
import { useSettings } from '@/components/providers/SettingsProvider';

type Tab = 'ledger' | 'purchases' | 'statement';
type EntryModalType = '' | 'purchase' | 'payment' | 'return' | 'adjustment';

const ENTRY_TYPE_OPTIONS = [
  { value: 'purchase', label: 'شراء' },
  { value: 'payment', label: 'دفعة' },
  { value: 'return', label: 'مرتجع' },
  { value: 'adjustment', label: 'تسوية' },
];

const BADGE_VARIANT: Record<string, 'neutral' | 'warning' | 'success' | 'danger'> = {
  opening: 'neutral',
  purchase: 'warning',
  payment: 'success',
  return: 'danger',
  adjustment: 'neutral',
};

function getTabFromUrl(): Tab {
  const t = new URLSearchParams(window.location.search).get('tab');
  if (t === 'ledger' || t === 'purchases' || t === 'statement') return t;
  return 'ledger';
}

export default function SupplierDetailPage() {
  const { toast } = useToast();
  const { settings } = useSettings();
  const router = useRouter();
  const params = useParams();
  const id = Number(params.id);

  const pageSize = settings?.default_page_size ?? 20;

  const [supplier, setSupplier] = useState<Supplier | null>(null);
  const [summary, setSummary] = useState<LedgerSummary | null>(null);
  const [ledger, setLedger] = useState<{ count: number; results: LedgerEntry[] } | null>(null);
  const [loading, setLoading] = useState(true);

  const [activeTab, setActiveTab] = useState<Tab>('ledger');
  const [page, setPage] = useState(1);

  useEffect(() => {
    setActiveTab(getTabFromUrl());
  }, []);

  const [editOpen, setEditOpen] = useState(false);
  const [entryOpen, setEntryOpen] = useState(false);
  const [entryModalType, setEntryModalType] = useState<EntryModalType>('');
  const [entryKey, setEntryKey] = useState(0);

  const [expanded, setExpanded] = useState<number | null>(null);
  const [deleting, setDeleting] = useState<LedgerEntry | null>(null);
  const [deleteLoading, setDeleteLoading] = useState(false);
  const [receivingId, setReceivingId] = useState<number | null>(null);
  const [reportLoading, setReportLoading] = useState(false);

  const openReport = async (autoPrint: boolean) => {
    if (!supplier || !summary) return;
    setReportLoading(true);
    try {
      const full = await getSupplierLedger(id, 1, 200);
      openSupplierReport(supplier, full.results, summary, settings, {
        title: 'كشف حساب مورد',
        autoPrint,
      });
    } catch (err: any) {
      toast('error', err.message);
    } finally {
      setReportLoading(false);
    }
  };

  const listPageSize = activeTab === 'ledger' ? pageSize : 500;

  const fetchAll = () => {
    let cancelled = false;
    setLoading(true);
    Promise.all([
      getSupplier(id),
      getSupplierSummary(id),
      getSupplierLedger(id, activeTab === 'ledger' ? page : 1, listPageSize),
    ])
      .then(([s, sum, ledg]) => {
        if (!cancelled) {
          setSupplier(s);
          setSummary(sum);
          setLedger(ledg);
        }
      })
      .catch((err) => { if (!cancelled) toast('error', err.message); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  };

  useEffect(() => fetchAll(), [id, page, activeTab, settings?.default_page_size]);

  const handleTabChange = (tab: Tab) => {
    setActiveTab(tab);
    setPage(1);
    setExpanded(null);
  };

  const handleUpdateSupplier = async (d: Partial<Supplier>) => {
    await updateSupplier(id, d);
    toast('success', 'تم تحديث المورد بنجاح');
    setEditOpen(false);
    fetchAll();
  };

  const handleCreateEntry = async (data: CreateLedgerEntry) => {
    await createLedgerEntry(id, data);
    toast('success', 'تم تسجيل القيد بنجاح');
    setEntryOpen(false);
    setEntryModalType('');
    fetchAll();
  };

  const handleDeleteEntry = async () => {
    if (!deleting) return;
    setDeleteLoading(true);
    try {
      await deleteLedgerEntry(id, deleting.id);
      toast('success', 'تم حذف القيد بنجاح');
      setDeleting(null);
      fetchAll();
    } catch (err: any) {
      toast('error', err.message);
    } finally {
      setDeleteLoading(false);
    }
  };

  const handleReceive = async (entry: LedgerEntry) => {
    setReceivingId(entry.id);
    try {
      await receiveLedgerEntry(id, entry.id);
      toast('success', `تم توريد البضاعة إلى ${entry.destination_name}`);
      fetchAll();
    } catch (err: any) {
      toast('error', err.message);
    } finally {
      setReceivingId(null);
    }
  };

  const openEntryModal = (type: EntryModalType) => {
    setEntryModalType(type);
    setEntryKey(Date.now());
    setEntryOpen(true);
  };

  const purchaseEntries = ledger ? ledger.results.filter((e) => e.entry_type === 'purchase') : [];
  const allEntries = ledger ? ledger.results : [];
  const allTotalDebit = allEntries.reduce((s, e) => s + (e.debit || 0), 0);
  const allTotalCredit = allEntries.reduce((s, e) => s + (e.credit || 0), 0);
  const balanceColor = summary
    ? summary.balance > 0
      ? 'text-red-600'
      : summary.balance === 0
        ? 'text-emerald-600'
        : 'text-neutral-800'
    : 'text-neutral-800';
  const balanceIconBg = summary
    ? summary.balance > 0
      ? 'bg-red-50 text-red-600'
      : 'bg-emerald-50 text-emerald-600'
    : 'bg-red-50 text-red-600';

  const downloadCsv = () => {
    const header = ['التاريخ', 'البيان', 'مدين', 'دائن', 'الرصيد'];
    const rows = allEntries.map((e) => [
      formatDate(e.date),
      ((e.description || e.entry_type_label) + (e.receiver_name ? ` (استلم: ${e.receiver_name})` : '')).replace(/"/g, '""'),
      String(e.debit || 0),
      String(e.credit || 0),
      e.running_balance !== null ? String(e.running_balance) : '',
    ]);
    const csv = [header, ...rows].map((r) => r.map((c) => `"${c}"`).join(',')).join('\n');
    const blob = new Blob(['\uFEFF' + csv], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `kashf-hesab-${supplier?.name || 'supplier'}.csv`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  if (loading && !supplier) {
    return (
      <AppShell>
        <div className="flex justify-center py-20"><Spinner size={40} /></div>
      </AppShell>
    );
  }

  if (!supplier || !summary) {
    return (
      <AppShell>
        <div className="text-center py-20 text-neutral-400">المورد غير موجود</div>
      </AppShell>
    );
  }

  return (
    <AppShell>
      <div className="space-y-6">
        <div className="flex items-center justify-between no-print">
          <Button variant="ghost" onClick={() => router.push('/suppliers')}>
            <ArrowRight size={18} />
            عودة إلى الموردين
          </Button>
          <div className="flex items-center gap-3">
            <Button variant="secondary" loading={reportLoading} onClick={() => openReport(false)} title="مشاركة كشف الحساب كملف PDF">
              <Share2 size={16} />
              مشاركة التقرير
            </Button>
            <Button variant="secondary" loading={reportLoading} onClick={() => openReport(true)} title="طباعة كشف حساب المورد">
              <Printer size={16} />
              طباعة التقرير
            </Button>
            <Button variant="secondary" onClick={() => setEditOpen(true)}>
              <Pencil size={16} />
              تعديل
            </Button>
            <Button onClick={() => openEntryModal('')}>
              <Plus size={16} />
              قيد جديد
            </Button>
          </div>
        </div>

        <div className="flex items-start gap-3">
          <h2 className="text-xl font-bold text-neutral-800">{supplier.name}</h2>
          {supplier.company_name && (
            <span className="text-sm text-neutral-500 mt-1">- {supplier.company_name}</span>
          )}
        </div>

        {summary && (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            <StatCard
              icon={<ShoppingBag size={20} />}
              iconBg="bg-brand-50 text-brand-600"
              label="إجمالي المشتريات"
              value={formatCurrency(summary.total_purchases)}
              sub={`${summary.purchases_count} فاتورة`}
            />
            <StatCard
              icon={<Wallet size={20} />}
              iconBg="bg-emerald-50 text-emerald-600"
              label="إجمالي المدفوعات"
              value={formatCurrency(summary.total_payments)}
              sub={`${summary.payments_count} دفعة`}
            />
            <StatCard
              icon={<Undo2 size={20} />}
              iconBg="bg-amber-50 text-amber-600"
              label="المرتجعات"
              value={formatCurrency(summary.total_returns)}
              sub={`${summary.returns_count} مرتجع`}
            />
            <div className="rounded-2xl bg-surface border border-sand-200 shadow-sm p-5 card-hover">
              <div className="flex items-start gap-4">
                <div className={`p-3 rounded-xl ${balanceIconBg}`}><Scale size={20} /></div>
                <div className="flex-1 min-w-0">
                  <p className="text-sm text-neutral-500 mb-1">الرصيد المتبقي</p>
                  <p className={`text-2xl font-bold tabular-nums ${balanceColor}`}>{formatCurrency(summary.balance)}</p>
                </div>
              </div>
            </div>
          </div>
        )}

        <div className="flex flex-wrap gap-2 no-print">
          {[
            { value: 'ledger' as Tab, label: 'دفتر الأستاذ' },
            { value: 'purchases' as Tab, label: 'فواتير الشراء' },
            { value: 'statement' as Tab, label: 'كشف الحساب' },
          ].map((t) => (
            <button
              key={t.value}
              onClick={() => handleTabChange(t.value)}
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

        {loading ? (
          <div className="flex justify-center py-12"><Spinner size={32} /></div>
        ) : (
          <>
            {activeTab === 'ledger' && (
              <Card>
                {allEntries.length === 0 ? (
                  <EmptyState
                    title="لا توجد قيود"
                    description="لم يتم تسجيل أي قيد بعد"
                    action={
                      <Button size="sm" onClick={() => openEntryModal('')}>
                        <Plus size={16} />
                        قيد جديد
                      </Button>
                    }
                  />
                ) : (
                  <>
                    <Table>
                      <thead>
                        <tr>
                          <Th>التاريخ</Th>
                          <Th>البيان</Th>
                          <Th>مدين</Th>
                          <Th>دائن</Th>
                          <Th>الرصيد</Th>
                          <Th className="w-12">إجراءات</Th>
                        </tr>
                      </thead>
                      <tbody>
                        {allEntries.map((e) => {
                          const isPurchase = e.entry_type === 'purchase';
                          const isExpanded = expanded === e.id && isPurchase;
                          return (
                            <Fragment key={e.id}>
                              <Tr
                                className={isPurchase ? 'cursor-pointer' : ''}
                                onClick={isPurchase ? () => setExpanded(isExpanded ? null : e.id) : undefined}
                              >
                                <Td>{formatDate(e.date)}</Td>
                                <Td>
                                  <div className="flex items-center gap-2 flex-wrap">
                                    {isPurchase && (
                                      isExpanded ? <ChevronUp size={16} className="text-neutral-400" /> : <ChevronDown size={16} className="text-neutral-400" />
                                    )}
                                    <Badge variant={BADGE_VARIANT[e.entry_type] || 'neutral'}>
                                      {e.entry_type_label}
                                    </Badge>
                                    {e.description && (
                                      <span className="text-neutral-500 text-xs">{e.description}</span>
                                    )}
                                    {e.receipt_no && (
                                      <span className="text-xs text-neutral-400">فاتورة {e.receipt_no}</span>
                                    )}
                                    {e.destination_name && (
                                      <span className="text-xs text-brand-600">التوريد: {e.destination_name}</span>
                                    )}
                                    {isPurchase && e.destination_name && (
                                      e.goods_receipt_number ? (
                                        <span className="text-xs text-emerald-600">استُلم ({e.goods_receipt_number})</span>
                                      ) : (
                                        <span className="text-xs text-amber-600">لم يُستلم بعد</span>
                                      )
                                    )}
                                    {e.payment_method_label && (
                                      <span className="text-xs text-neutral-400">({e.payment_method_label})</span>
                                    )}
                                    {e.receiver_name && (
                                      <span className="text-xs text-neutral-400">استلم: {e.receiver_name}</span>
                                    )}
                                  </div>
                                </Td>
                                <Td className="tabular-nums font-medium">
                                  {e.debit ? formatCurrency(e.debit) : ''}
                                </Td>
                                <Td className="tabular-nums font-medium">
                                  {e.credit ? formatCurrency(e.credit) : ''}
                                </Td>
                                <Td className="tabular-nums font-medium">
                                  {e.running_balance !== null ? formatCurrency(e.running_balance) : '-'}
                                </Td>
                                <Td>
                                  <button
                                    onClick={(ev) => { ev.stopPropagation(); setDeleting(e); }}
                                    className="p-1.5 rounded-lg hover:bg-red-50 text-red-500 dark:hover:bg-red-500/15 dark:text-red-400 transition-colors"
                                  >
                                    <Trash2 size={14} />
                                  </button>
                                </Td>
                              </Tr>
                              {isExpanded && (
                                <tr>
                                  <Td colSpan={6} className="bg-sand-50 !px-6 !py-4">
                                    {e.items && e.items.length > 0 ? (
                                      <Table>
                                        <thead>
                                          <tr>
                                            <Th>القماش</Th>
                                            <Th>الكمية بالياردة</Th>
                                            <Th>عدد اللفات</Th>
                                            <Th>سعر الياردة</Th>
                                            <Th>الإجمالي</Th>
                                            <Th>الوجهة</Th>
                                          </tr>
                                        </thead>
                                        <tbody>
                                          {e.items.map((item) => (
                                            <Tr key={item.id}>
                                              <Td className="font-medium">{item.fabric_name}</Td>
                                              <Td className="tabular-nums">{item.quantity_yards || '-'}</Td>
                                              <Td className="tabular-nums">{item.rolls || '-'}</Td>
                                              <Td className="tabular-nums">{formatCurrency(item.unit_price)}</Td>
                                              <Td className="tabular-nums font-medium">{formatCurrency(item.total)}</Td>
                                              <Td>
                                                {item.destination_name ? (
                                                  <Badge variant={item.destination_type === 'branch' ? 'warning' : 'neutral'}>
                                                    {item.destination_type === 'branch' ? 'فرع' : 'مخزن'}: {item.destination_name}
                                                  </Badge>
                                                ) : (
                                                  <span className="text-xs text-neutral-400">—</span>
                                                )}
                                              </Td>
                                            </Tr>
                                          ))}
                                        </tbody>
                                      </Table>
                                    ) : (
                                      <p className="text-sm text-neutral-400">لا توجد أصناف مرتبطة</p>
                                    )}
                                  </Td>
                                </tr>
                              )}
                            </Fragment>
                          );
                        })}
                      </tbody>
                    </Table>
                    <Pagination page={page} totalPages={Math.ceil(ledger!.count / pageSize)} onChange={setPage} count={ledger!.count} pageSize={pageSize} />
                  </>
                )}
              </Card>
            )}

            {activeTab === 'purchases' && (
              <div className="space-y-4">
                {purchaseEntries.length === 0 ? (
                  <Card>
                    <EmptyState title="لا توجد فواتير شراء" description="لم يتم تسجيل أي فاتورة شراء بعد" />
                  </Card>
                ) : (
                  purchaseEntries.map((e) => (
                    <Card key={e.id} title={`فاتورة ${e.receipt_no || '-'}`} subtitle={formatDate(e.date)}>
                      <div className="space-y-4">
                        {e.items && e.items.length > 0 && (
                          <Table>
                            <thead>
                              <tr>
                                <Th>القماش</Th>
                                <Th>الكمية بالياردة</Th>
                                <Th>عدد اللفات</Th>
                                <Th>سعر الياردة</Th>
                                <Th>الإجمالي</Th>
                                <Th>الوجهة</Th>
                              </tr>
                            </thead>
                            <tbody>
                              {e.items.map((item) => (
                                <Tr key={item.id}>
                                  <Td className="font-medium">{item.fabric_name}</Td>
                                  <Td className="tabular-nums">{item.quantity_yards || '-'}</Td>
                                  <Td className="tabular-nums">{item.rolls || '-'}</Td>
                                  <Td className="tabular-nums">{formatCurrency(item.unit_price)}</Td>
                                  <Td className="tabular-nums font-medium">{formatCurrency(item.total)}</Td>
                                  <Td>
                                    {item.destination_name ? (
                                      <Badge variant={item.destination_type === 'branch' ? 'warning' : 'neutral'}>
                                        {item.destination_type === 'branch' ? 'فرع' : 'مخزن'}: {item.destination_name}
                                      </Badge>
                                    ) : (
                                      <span className="text-xs text-neutral-400">—</span>
                                    )}
                                  </Td>
                                </Tr>
                              ))}
                            </tbody>
                          </Table>
                        )}
                        <div className="flex items-center justify-between pt-3 border-t border-sand-100">
                          <div className="flex items-center gap-3">
                            <span className="text-sm text-neutral-500">الإجمالي:</span>
                            <span className="text-lg font-bold tabular-nums text-neutral-800">{formatCurrency(e.debit)}</span>
                          </div>
                          {e.payment_method_label && (
                            <div className="flex items-center gap-2 text-sm text-neutral-500">
                              <span>طريقة الدفع:</span>
                              <Badge variant="success">{e.payment_method_label}</Badge>
                            </div>
                          )}
                        </div>
                        {e.destination_name && (
                          <div className="flex items-center gap-3 text-sm pt-2">
                            <span className="text-neutral-500">وجهة التوريد:</span>
                            <Badge variant={e.destination_type === 'branch' ? 'warning' : 'neutral'}>
                              {e.destination_type === 'branch' ? 'فرع' : e.destination_type === 'mixed' ? 'وجوه متعددة' : 'مخزن'}: {e.destination_name}
                            </Badge>
                            {e.goods_receipt_number ? (
                              <span className="text-xs text-emerald-600">استُلمت تلقائياً ({e.goods_receipt_number})</span>
                            ) : (
                              <Button size="sm" loading={receivingId === e.id} onClick={() => handleReceive(e)}>
                                توريد الآن
                              </Button>
                            )}
                          </div>
                        )}
                        {e.notes && (
                          <p className="text-xs text-neutral-400 mt-2">{e.notes}</p>
                        )}
                      </div>
                    </Card>
                  ))
                )}
              </div>
            )}

            {activeTab === 'statement' && (
              <div>
                <div className="flex items-center justify-end gap-3 mb-4 no-print">
                  <Button variant="secondary" size="sm" onClick={() => window.print()}>
                    <Printer size={16} />
                    طباعة
                  </Button>
                  <Button variant="secondary" size="sm" onClick={downloadCsv}>
                    <Download size={16} />
                    تنزيل CSV
                  </Button>
                </div>

                <div className="bg-surface rounded-2xl border border-sand-200 shadow-sm p-6 print:shadow-none print:border-0 print:p-0">
                  <div className="flex flex-col md:flex-row md:items-start justify-between gap-4 pb-6 mb-6 border-b border-sand-200">
                    <div>
                      <h2 className="text-xl font-bold text-neutral-800">{settings?.business_name || 'المؤسسة'}</h2>
                      {settings?.business_address && <p className="text-sm text-neutral-500">{settings.business_address}</p>}
                      {settings?.business_phone && <p className="text-sm text-neutral-500" dir="ltr">{settings.business_phone}</p>}
                    </div>
                    <div className="text-left md:text-right">
                      <h3 className="text-lg font-bold text-neutral-800 mb-1">كشف حساب مورد</h3>
                      <p className="text-sm font-medium text-neutral-700">{supplier.name}</p>
                      {supplier.company_name && <p className="text-sm text-neutral-500">{supplier.company_name}</p>}
                      {supplier.city && <p className="text-sm text-neutral-500">{supplier.city}</p>}
                      {supplier.phone && <p className="text-sm text-neutral-500" dir="ltr">{supplier.phone}</p>}
                    </div>
                  </div>

                  <div className="mb-4 p-3 bg-sand-50 rounded-xl text-sm text-neutral-700">
                    <span className="text-neutral-500">الرصيد الافتتاحي: </span>
                    <span className="font-semibold tabular-nums">{formatCurrency(summary.opening_balance)}</span>
                  </div>

                  {allEntries.length === 0 ? (
                    <EmptyState title="لا توجد قيود" />
                  ) : (
                    <table className="w-full text-sm mb-6">
                      <thead>
                        <tr className="bg-sand-100">
                          <Th>التاريخ</Th>
                          <Th>البيان</Th>
                          <Th>مدين</Th>
                          <Th>دائن</Th>
                          <Th>الرصيد</Th>
                        </tr>
                      </thead>
                      <tbody>
                        {allEntries.map((e) => (
                          <Tr key={e.id}>
                            <Td>{formatDate(e.date)}</Td>
                            <Td>
                              <span className="text-neutral-500 text-xs ml-1">[{e.entry_type_label}]</span>
                              {e.description || ''}
                              {e.receipt_no && <span className="text-xs text-neutral-400 mr-1">فاتورة {e.receipt_no}</span>}
                              {e.receiver_name && <span className="text-xs text-neutral-400 mr-1">استلم: {e.receiver_name}</span>}
                            </Td>
                            <Td className="tabular-nums">{e.debit ? formatCurrency(e.debit) : ''}</Td>
                            <Td className="tabular-nums">{e.credit ? formatCurrency(e.credit) : ''}</Td>
                            <Td className="tabular-nums font-medium">{e.running_balance !== null ? formatCurrency(e.running_balance) : ''}</Td>
                          </Tr>
                        ))}
                      </tbody>
                      <tfoot>
                        <tr className="bg-sand-100 font-semibold">
                          <Td>الإجمالي</Td>
                          <Td></Td>
                          <Td className="tabular-nums">{formatCurrency(allTotalDebit)}</Td>
                          <Td className="tabular-nums">{formatCurrency(allTotalCredit)}</Td>
                          <Td></Td>
                        </tr>
                      </tfoot>
                    </table>
                  )}

                  <div className="grid grid-cols-3 gap-6 p-4 bg-sand-50 rounded-xl text-sm mb-8">
                    <div>
                      <span className="text-neutral-500">إجمالي المشتريات: </span>
                      <span className="font-semibold tabular-nums">{formatCurrency(summary.total_purchases)}</span>
                    </div>
                    <div>
                      <span className="text-neutral-500">إجمالي المدفوعات: </span>
                      <span className="font-semibold tabular-nums">{formatCurrency(summary.total_payments)}</span>
                    </div>
                    <div>
                      <span className="text-neutral-500">الرصيد النهائي: </span>
                      <span className={`font-bold tabular-nums ${balanceColor}`}>{formatCurrency(summary.balance)}</span>
                    </div>
                  </div>

                  <div className="grid grid-cols-2 gap-12 mt-12">
                    <div className="text-center">
                      <div className="border-t-2 border-dashed border-sand-300 mb-2 mt-16" />
                      <p className="text-sm text-neutral-500">توقيع المورد</p>
                    </div>
                    <div className="text-center">
                      <div className="border-t-2 border-dashed border-sand-300 mb-2 mt-16" />
                      <p className="text-sm text-neutral-500">توقيع الإدارة</p>
                    </div>
                  </div>
                </div>
              </div>
            )}
          </>
        )}
      </div>

      <Modal open={editOpen} onClose={() => setEditOpen(false)} title="تعديل المورد" maxWidth="max-w-2xl">
        <SupplierForm initial={supplier} onSubmit={handleUpdateSupplier} onCancel={() => setEditOpen(false)} />
      </Modal>

      <Modal open={entryOpen} onClose={() => { setEntryOpen(false); setEntryModalType(''); }} title="قيد جديد" maxWidth="max-w-3xl">
        <div className="space-y-4">
          {!entryModalType && (
            <Select
              label="نوع القيد"
              value=""
              onChange={(e) => setEntryModalType(e.target.value as EntryModalType)}
              options={[{ value: '', label: 'اختر نوع القيد' }, ...ENTRY_TYPE_OPTIONS]}
              placeholder="اختر نوع القيد"
            />
          )}
          {entryModalType === 'purchase' && (
            <div key={entryKey}>
              <PurchaseForm onSubmit={handleCreateEntry} onCancel={() => { setEntryOpen(false); setEntryModalType(''); }} />
            </div>
          )}
          {entryModalType === 'payment' && (
            <div key={entryKey}>
              <PaymentForm onSubmit={handleCreateEntry} onCancel={() => { setEntryOpen(false); setEntryModalType(''); }} />
            </div>
          )}
          {entryModalType === 'return' && (
            <div key={entryKey}>
              <ReturnForm onSubmit={handleCreateEntry} onCancel={() => { setEntryOpen(false); setEntryModalType(''); }} />
            </div>
          )}
          {entryModalType === 'adjustment' && (
            <div key={entryKey}>
              <AdjustmentForm onSubmit={handleCreateEntry} onCancel={() => { setEntryOpen(false); setEntryModalType(''); }} />
            </div>
          )}
        </div>
      </Modal>

      <ConfirmDialog
        open={!!deleting}
        onClose={() => setDeleting(null)}
        onConfirm={handleDeleteEntry}
        loading={deleteLoading}
        message={`هل أنت متأكد من حذف قيد "${deleting?.entry_type_label || ''}" بتاريخ ${deleting ? formatDate(deleting.date) : ''}؟ لا يمكن التراجع عن هذا الإجراء.`}
      />
    </AppShell>
  );
}