'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link';
import AppShell from '@/components/layout/AppShell';
import Card from '@/components/ui/Card';
import Button from '@/components/ui/Button';
import Table, { Th, Td, Tr } from '@/components/ui/Table';
import SearchInput from '@/components/ui/SearchInput';
import Pagination from '@/components/ui/Pagination';
import Modal from '@/components/ui/Modal';
import ConfirmDialog from '@/components/ui/ConfirmDialog';
import SupplierForm from '@/components/forms/SupplierForm';
import EmptyState from '@/components/ui/EmptyState';
import Spinner from '@/components/ui/Spinner';
import StatCard from '@/components/ui/StatCard';
import Badge from '@/components/ui/Badge';
import Select from '@/components/ui/Select';
import DateRangeToolbar, { currentMonthRange } from '@/components/ui/DateRangeToolbar';
import { Plus, Eye, Pencil, Trash2, BookOpen, Users, ShoppingBag, Wallet, Undo2, Scale, ChevronLeft, Printer, Share2, HandCoins } from 'lucide-react';
import { Supplier, Paginated, SuppliersOverview, Warehouse, Branch } from '@/types';
import { listSuppliers, createSupplier, updateSupplier, deleteSupplier, getSuppliersOverview, createLedgerEntry } from '@/services/suppliers';
import { listWarehouses } from '@/services/warehouses';
import { listBranches } from '@/services/branches';
import { formatCurrency, formatDate } from '@/lib/format';
import Input from '@/components/ui/Input';
import { openSuppliersOverviewReport } from '@/lib/supplierReport';
import { useToast } from '@/components/ui/Toast';
import { useSettings } from '@/components/providers/SettingsProvider';
import { useUrlState } from '@/lib/useUrlState';

export default function SuppliersPage() {
  const { toast } = useToast();
  const { settings } = useSettings();
  const pageSize = settings?.default_page_size ?? 10;
  const [data, setData] = useState<Paginated<Supplier> | null>(null);
  const [overview, setOverview] = useState<SuppliersOverview | null>(null);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useUrlState('q', '');
  const [page, setPage] = useUrlState('page', 1);
  const [dateFrom, setDateFrom] = useUrlState('from', currentMonthRange().from);
  const [dateTo, setDateTo] = useUrlState('to', currentMonthRange().to);
  const [filterWarehouse, setFilterWarehouse] = useUrlState('warehouse', '');
  const [filterBranch, setFilterBranch] = useUrlState('branch', '');
  const [warehouses, setWarehouses] = useState<Warehouse[]>([]);
  const [branches, setBranches] = useState<Branch[]>([]);
  const [modalOpen, setModalOpen] = useState(false);
  const [editing, setEditing] = useState<Supplier | null>(null);
  const [deleting, setDeleting] = useState<Supplier | null>(null);
  const [deleteLoading, setDeleteLoading] = useState(false);
  const [reportLoading, setReportLoading] = useState(false);
  const [payTarget, setPayTarget] = useState<Supplier | null>(null);
  const [payAmount, setPayAmount] = useState('');
  const [payDate, setPayDate] = useState(new Date().toISOString().slice(0, 10));
  const [payMethod, setPayMethod] = useState<'cash' | 'bank_transfer'>('cash');
  const [payLoading, setPayLoading] = useState(false);

  const openReport = async (autoPrint: boolean) => {
    if (!overview) return;
    setReportLoading(true);
    try {
      const all = await listSuppliers({ page: 1, page_size: 200, search: search || undefined });
      openSuppliersOverviewReport(overview, all.results, settings, {
        title: 'تقرير الموردين',
        autoPrint,
      });
    } catch (err: any) {
      toast('error', err.message);
    } finally {
      setReportLoading(false);
    }
  };

  const fetchData = () => {
    let cancelled = false;
    setLoading(true);
    const params: Record<string, string | number | undefined | null> = { page, page_size: pageSize, search: search || undefined };
    listSuppliers(params)
      .then((res) => { if (!cancelled) setData(res); })
      .catch((err) => { if (!cancelled) toast('error', err.message); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  };

  useEffect(() => fetchData(), [page, search, settings?.default_page_size]);

  useEffect(() => {
    let cancelled = false;
    getSuppliersOverview({
      date_from: dateFrom || undefined,
      date_to: dateTo || undefined,
      warehouse: filterWarehouse || undefined,
      branch: filterBranch || undefined,
    })
      .then((res) => { if (!cancelled) setOverview(res); })
      .catch(() => {});
    return () => { cancelled = true; };
  }, [dateFrom, dateTo, filterWarehouse, filterBranch]);

  useEffect(() => {
    listWarehouses({ page_size: 200 }).then((res) => setWarehouses(res.results)).catch(() => {});
    listBranches({ page_size: 200 }).then((res) => setBranches(res.results)).catch(() => {});
  }, []);

  const totalPages = data ? Math.ceil(data.count / pageSize) : 1;

  const handleCreate = async (d: Partial<Supplier>) => {
    await createSupplier(d);
    toast('success', 'تمت إضافة المورد بنجاح');
    setModalOpen(false);
    fetchData();
  };

  const handleUpdate = async (d: Partial<Supplier>) => {
    if (!editing) return;
    await updateSupplier(editing.id, d);
    toast('success', 'تم تحديث المورد بنجاح');
    setEditing(null);
    fetchData();
  };

  const handleDelete = async () => {
    if (!deleting) return;
    setDeleteLoading(true);
    try {
      await deleteSupplier(deleting.id);
      toast('success', 'تم حذف المورد بنجاح');
      setDeleting(null);
      fetchData();
    } catch (err: any) {
      toast('error', err.message);
    } finally {
      setDeleteLoading(false);
    }
  };

  const handleQuickPay = async () => {
    if (!payTarget) return;
    const amount = Number(payAmount);
    if (!amount || amount <= 0) {
      toast('error', 'أدخل مبلغاً صحيحاً أكبر من صفر');
      return;
    }
    setPayLoading(true);
    try {
      await createLedgerEntry(payTarget.id, {
        entry_type: 'payment',
        date: payDate,
        amount,
        payment_method: payMethod,
        description: 'دفعة سريعة',
      });
      toast('success', 'تم تسجيل الدفعة بنجاح');
      setPayTarget(null);
      setPayAmount('');
      fetchData();
      getSuppliersOverview({
        date_from: dateFrom || undefined,
        date_to: dateTo || undefined,
        warehouse: filterWarehouse || undefined,
        branch: filterBranch || undefined,
      })
        .then(setOverview)
        .catch(() => {});
    } catch (err: any) {
      toast('error', err.message);
    } finally {
      setPayLoading(false);
    }
  };

  return (
    <AppShell>
      <div className="space-y-6">
        <div className="flex flex-wrap items-center gap-3">
          <DateRangeToolbar
            from={dateFrom}
            to={dateTo}
            onChange={(f, t) => { setDateFrom(f); setDateTo(t); setPage(1); }}
          />
          <Select
            value={filterWarehouse}
            onChange={(e) => { setFilterWarehouse(e.target.value); setPage(1); }}
            options={[{ value: '', label: 'كل المخازن' }, ...warehouses.map((w) => ({ value: String(w.id), label: w.name }))]}
          />
          <Select
            value={filterBranch}
            onChange={(e) => { setFilterBranch(e.target.value); setPage(1); }}
            options={[{ value: '', label: 'كل الفروع' }, ...branches.map((b) => ({ value: String(b.id), label: b.name }))]}
          />
        </div>

        <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <SearchInput value={search} onChange={(v) => { setSearch(v); setPage(1); }} />
              <Button variant="secondary" loading={reportLoading} onClick={() => openReport(false)} title="مشاركة تقرير الموردين كملف PDF">
                <Share2 size={16} />
                مشاركة التقرير
              </Button>
              <Button variant="secondary" loading={reportLoading} onClick={() => openReport(true)} title="طباعة تقرير الموردين">
                <Printer size={16} />
                طباعة التقرير
              </Button>
            </div>
            <Button onClick={() => setModalOpen(true)}>
              <Plus size={18} />
              إضافة مورد
            </Button>
          </div>

        {overview && (
          <>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4">
              <StatCard
                icon={<Users size={22} />}
                iconBg="bg-brand-50 text-brand-600 dark:bg-brand-500/15 dark:text-brand-400"
                label="إجمالي الموردين"
                value={overview.total_suppliers}
                sub={`${overview.active_count} نشط`}
              />
              <StatCard
                icon={<ShoppingBag size={22} />}
                iconBg="bg-amber-50 text-amber-600 dark:bg-amber-500/15 dark:text-amber-400"
                label="إجمالي المشتريات"
                value={formatCurrency(overview.total_purchases)}
                sub={`${overview.purchases_count} فاتورة`}
              />
              <StatCard
                icon={<Wallet size={22} />}
                iconBg="bg-emerald-50 text-emerald-600 dark:bg-emerald-500/15 dark:text-emerald-400"
                label="إجمالي المدفوعات"
                value={formatCurrency(overview.total_payments)}
                sub={`${overview.payments_count} دفعة`}
              />
              <StatCard
                icon={<Undo2 size={22} />}
                iconBg="bg-blue-50 text-blue-600 dark:bg-blue-500/15 dark:text-blue-400"
                label="المرتجعات"
                value={formatCurrency(overview.total_returns)}
                sub={`${overview.returns_count} مرتجع`}
              />
              <StatCard
                icon={<Scale size={22} />}
                iconBg="bg-red-50 text-red-600 dark:bg-red-500/15 dark:text-red-400"
                label="المستحق للموردين"
                value={formatCurrency(overview.outstanding_debit)}
                sub={`${overview.owing_count} مورد بمديونية`}
              />
            </div>

            {overview.top_suppliers.length > 0 && (
              <Card title="أعلى الموردين رصيداً" subtitle="الموردون الأكثر استحقاقاً">
                <ul className="divide-y divide-sand-100">
                  {overview.top_suppliers.map((t) => (
                    <li key={t.id}>
                      <Link href={`/suppliers/${t.id}?tab=ledger`} className="flex items-center justify-between gap-3 px-2 py-2.5 rounded-lg hover:bg-sand-50 transition-colors">
                        <span className="flex flex-col min-w-0">
                          <span className="font-medium text-sm text-neutral-800 truncate">{t.name}</span>
                          {t.company_name && <span className="text-xs text-neutral-400 truncate">{t.company_name}</span>}
                        </span>
                        <span className="flex items-center gap-2 shrink-0">
                          <Badge variant="danger">{formatCurrency(t.balance)}</Badge>
                          <ChevronLeft size={15} className="text-neutral-300" />
                        </span>
                      </Link>
                    </li>
                  ))}
                </ul>
              </Card>
            )}
          </>
        )}

        <Card>
          {loading ? (
            <div className="flex justify-center py-12"><Spinner size={32} /></div>
          ) : !data || data.results.length === 0 ? (
            <EmptyState title="لا يوجد موردون" description="لم يتم إضافة أي مورد بعد" />
          ) : (
            <>
              <Table>
                <thead>
                  <tr>
                    <Th>اسم المورد</Th>
                    <Th>الشركة</Th>
                    <Th>الهاتف</Th>
                    <Th>المدينة</Th>
                    <Th>الدولة</Th>
                    <Th>الرصيد</Th>
                    <Th>إجراءات</Th>
                  </tr>
                </thead>
                <tbody>
                  {data.results.map((s) => (
                    <Tr key={s.id}>
                      <Td className="font-medium">{s.name}</Td>
                      <Td>{s.company_name || '-'}</Td>
                      <Td dir="ltr" className="text-left">{s.phone || '-'}</Td>
                      <Td>{s.city || '-'}</Td>
                      <Td>{s.country || '-'}</Td>
                      <Td className={`tabular-nums font-medium ${s.current_balance > 0 ? 'text-red-600 dark:text-red-400' : 'text-emerald-600 dark:text-emerald-400'}`}>
                        {formatCurrency(s.current_balance)}
                      </Td>
                      <Td>
                        <div className="flex items-center gap-2">
                          <button
                            onClick={() => setPayTarget(s)}
                            className="p-1.5 rounded-lg hover:bg-emerald-50 text-emerald-600 transition-colors"
                            title={s.current_balance > 0 ? `تسجيل دفعة للمورد (المستحق: ${formatCurrency(s.current_balance)})` : 'تسجيل دفعة للمورد'}
                          >
                            <HandCoins size={16} />
                          </button>
                          <Link href={`/suppliers/${s.id}?tab=ledger`} title="دفتر الحساب" className="p-1.5 rounded-lg hover:bg-brand-50 text-brand-600 transition-colors">
                            <BookOpen size={16} />
                          </Link>
                          <Link href={`/suppliers/${s.id}`} className="p-1.5 rounded-lg hover:bg-brand-50 text-brand-600 transition-colors">
                            <Eye size={16} />
                          </Link>
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
              <Pagination page={page} totalPages={totalPages} onChange={setPage} count={data.count} pageSize={pageSize} />
            </>
          )}
        </Card>

        <Modal open={modalOpen} onClose={() => setModalOpen(false)} title="إضافة مورد جديد" maxWidth="max-w-2xl">
          <SupplierForm onSubmit={handleCreate} onCancel={() => setModalOpen(false)} />
        </Modal>

        <Modal open={!!editing} onClose={() => setEditing(null)} title="تعديل المورد" maxWidth="max-w-2xl">
          {editing && <SupplierForm initial={editing} onSubmit={handleUpdate} onCancel={() => setEditing(null)} />}
        </Modal>

        <Modal open={!!payTarget} onClose={() => setPayTarget(null)} title="تسجيل دفعة للمورد" maxWidth="max-w-md">
          <div className="space-y-4">
            <div className="rounded-xl bg-sand-50 border border-sand-200 p-4 flex items-center justify-between">
              <div>
                <p className="text-sm font-semibold text-neutral-800">{payTarget?.name}</p>
                <p className="text-xs text-neutral-500 mt-0.5">المبلغ المستحق حالياً</p>
              </div>
              <span className="text-lg font-bold tabular-nums text-red-600">{formatCurrency(payTarget?.current_balance ?? 0)}</span>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="text-xs font-medium text-neutral-500 block mb-1">المبلغ</label>
                <input
                  type="number"
                  min="0"
                  step="0.001"
                  value={payAmount}
                  onChange={(e) => setPayAmount(e.target.value)}
                  className="w-full rounded-xl border border-sand-300 bg-surface px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500/40"
                  placeholder="0.000"
                />
              </div>
              <div>
                <label className="text-xs font-medium text-neutral-500 block mb-1">التاريخ</label>
                <input
                  type="date"
                  value={payDate}
                  onChange={(e) => setPayDate(e.target.value)}
                  className="w-full rounded-xl border border-sand-300 bg-surface px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500/40"
                />
              </div>
            </div>
            <Select
              label="طريقة الدفع"
              value={payMethod}
              onChange={(e) => setPayMethod(e.target.value as 'cash' | 'bank_transfer')}
              options={[
                { value: 'cash', label: 'كاش' },
                { value: 'bank_transfer', label: 'تحويل بنكي' },
              ]}
            />
            <div className="flex justify-start gap-3 pt-2">
              <Button onClick={handleQuickPay} loading={payLoading}>
                <HandCoins size={16} />
                تسجيل الدفعة
              </Button>
              <Button variant="secondary" onClick={() => setPayTarget(null)}>إلغاء</Button>
            </div>
          </div>
        </Modal>

        <ConfirmDialog
          open={!!deleting}
          onClose={() => setDeleting(null)}
          onConfirm={handleDelete}
          loading={deleteLoading}
          message={`هل أنت متأكد من حذف مورد "${deleting?.name}"؟ لا يمكن التراجع عن هذا الإجراء.`}
        />
      </div>
    </AppShell>
  );
}
