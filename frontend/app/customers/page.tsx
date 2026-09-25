'use client';

import { useState, useEffect } from 'react';
import AppShell from '@/components/layout/AppShell';
import Card from '@/components/ui/Card';
import Button from '@/components/ui/Button';
import Table, { Th, Td, Tr } from '@/components/ui/Table';
import SearchInput from '@/components/ui/SearchInput';
import Pagination from '@/components/ui/Pagination';
import Modal from '@/components/ui/Modal';
import ConfirmDialog from '@/components/ui/ConfirmDialog';
import CustomerForm from '@/components/forms/CustomerForm';
import EmptyState from '@/components/ui/EmptyState';
import Spinner from '@/components/ui/Spinner';
import Badge from '@/components/ui/Badge';
import Select from '@/components/ui/Select';
import StatCard from '@/components/ui/StatCard';
import DateRangeToolbar, { currentMonthRange } from '@/components/ui/DateRangeToolbar';
import { Plus, Pencil, Trash2, UserX, UserCheck, Users, UserPlus, Phone, MessageCircle } from 'lucide-react';
import { Customer, CustomersSummary, Paginated, Branch } from '@/types';
import { listCustomers, createCustomer, updateCustomer, deleteCustomer, getCustomersSummary } from '@/services/customers';
import { listBranches } from '@/services/branches';
import { formatDate, formatCurrency } from '@/lib/format';
import { useToast } from '@/components/ui/Toast';
import { useSettings } from '@/components/providers/SettingsProvider';
import { useUrlState } from '@/lib/useUrlState';

export default function CustomersPage() {
  const { toast } = useToast();
  const { settings } = useSettings();
  const pageSize = settings?.default_page_size ?? 10;
  const [data, setData] = useState<Paginated<Customer> | null>(null);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useUrlState('q', '');
  const [page, setPage] = useUrlState('page', 1);
  const [filterBranch, setFilterBranch] = useUrlState('branch', '');
  const [dateFrom, setDateFrom] = useUrlState('from', currentMonthRange().from);
  const [dateTo, setDateTo] = useUrlState('to', currentMonthRange().to);
  const [summary, setSummary] = useState<CustomersSummary | null>(null);
  const [branches, setBranches] = useState<Branch[]>([]);
  const [modalOpen, setModalOpen] = useState(false);
  const [editing, setEditing] = useState<Customer | null>(null);
  const [deleting, setDeleting] = useState<Customer | null>(null);
  const [deleteLoading, setDeleteLoading] = useState(false);
  const [togglingId, setTogglingId] = useState<number | null>(null);

  const fetchData = () => {
    let cancelled = false;
    setLoading(true);
    const params: Record<string, string | number | undefined | null> = {
      page, page_size: pageSize, search: search || undefined,
      branch: filterBranch || undefined,
      date_from: dateFrom || undefined,
      date_to: dateTo || undefined,
    };
    listCustomers(params)
      .then((res) => { if (!cancelled) setData(res); })
      .catch((err) => { if (!cancelled) toast('error', err.message); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  };

  useEffect(() => fetchData(), [page, search, settings?.default_page_size, filterBranch, dateFrom, dateTo]);

  useEffect(() => {
    getCustomersSummary({
      branch: filterBranch || undefined,
      date_from: dateFrom || undefined,
      date_to: dateTo || undefined,
    })
      .then(setSummary)
      .catch(() => setSummary(null));
  }, [filterBranch, dateFrom, dateTo]);

  useEffect(() => {
    listBranches({ page_size: 200 }).then((res) => setBranches(res.results)).catch(() => {});
  }, []);

  const totalPages = data ? Math.ceil(data.count / pageSize) : 1;

  const handleCreate = async (d: Partial<Customer>) => {
    await createCustomer(d);
    toast('success', 'تمت إضافة الزبون بنجاح');
    setModalOpen(false);
    fetchData();
  };

  const handleUpdate = async (d: Partial<Customer>) => {
    if (!editing) return;
    await updateCustomer(editing.id, d);
    toast('success', 'تم تحديث الزبون بنجاح');
    setEditing(null);
    fetchData();
  };

  const handleDelete = async () => {
    if (!deleting) return;
    setDeleteLoading(true);
    try {
      await deleteCustomer(deleting.id);
      toast('success', 'تم حذف الزبون بنجاح');
      setDeleting(null);
      fetchData();
    } catch (err: any) {
      toast('error', err.message);
    } finally {
      setDeleteLoading(false);
    }
  };

  const toggleActive = async (c: Customer) => {
    setTogglingId(c.id);
    try {
      await updateCustomer(c.id, { is_active: !c.is_active });
      toast('success', c.is_active ? 'تم تعطيل الزبون' : 'تم تفعيل الزبون');
      fetchData();
    } catch (err: any) {
      toast('error', err.message);
    } finally {
      setTogglingId(null);
    }
  };

  return (
    <AppShell>
      <div className="space-y-6">
        <div className="flex flex-wrap items-center gap-3">
          <DateRangeToolbar
            from={dateFrom}
            to={dateTo}
            onChange={(f, t) => { setDateFrom(f); setDateTo(t); }}
          />
          <Select
            value={filterBranch}
            onChange={(e) => { setFilterBranch(e.target.value); setPage(1); }}
            options={[{ value: '', label: 'كل الفروع' }, ...branches.map((b) => ({ value: String(b.id), label: b.name }))]}
            className="w-full sm:w-48"
          />
        </div>

        {summary && (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            <StatCard icon={<Users size={22} />} label="إجمالي الزبائن" value={summary.total_customers} sub={`${summary.active_count} نشط`} />
            <StatCard icon={<UserCheck size={22} />} iconBg="bg-emerald-50 text-emerald-600" label="الزبائن النشطون" value={summary.active_count} />
            <StatCard icon={<UserPlus size={22} />} iconBg="bg-amber-50 text-amber-600" label="الجدد في الفترة" value={summary.new_count} />
            <StatCard icon={<Phone size={22} />} iconBg="bg-indigo-50 text-indigo-600" label="لديهم رقم هاتف" value={summary.with_phone_count} />
          </div>
        )}

        <div className="flex items-center justify-between">
          <SearchInput value={search} onChange={(v) => { setSearch(v); setPage(1); }} />
          <Button onClick={() => setModalOpen(true)}>
            <Plus size={18} />
            إضافة زبون
          </Button>
        </div>

        <Card>
          {loading ? (
            <div className="flex justify-center py-12"><Spinner size={32} /></div>
          ) : !data || data.results.length === 0 ? (
            <EmptyState title="لا يوجد زبائن" description="لم يتم تسجيل أي زبون بعد — سيتم تسجيل الزبائن تلقائياً عند كتابة الاسم والهاتف في نقطة البيع أو في الفاتورة" />
          ) : (
            <>
              <Table>
                <thead>
                  <tr>
                    <Th>اسم الزبون</Th>
                    <Th>رقم الهاتف</Th>
                    <Th>إجمالي المشتريات</Th>
                    <Th>آخر شراء</Th>
                    <Th>البريد الإلكتروني</Th>
                    <Th>الفرع</Th>
                    <Th>ملاحظات</Th>
                    <Th>الحالة</Th>
                    <Th>تاريخ التسجيل</Th>
                    <Th>إجراءات</Th>
                  </tr>
                </thead>
                <tbody>
                  {data.results.map((c) => (
                    <Tr key={c.id}>
                      <Td className="font-medium">{c.name}</Td>
                      <Td>
                        <div className="flex items-center gap-2">
                          <span dir="ltr" className="text-left">{c.phone || '-'}</span>
                          {c.phone ? (
                            <a
                              href={`https://wa.me/${c.phone.replace(/[^\d]/g, '')}`}
                              target="_blank"
                              rel="noreferrer"
                              className="p-1 rounded-lg hover:bg-emerald-50 text-emerald-600 transition-colors"
                              title="تواصل عبر واتساب"
                            >
                              <MessageCircle size={15} />
                            </a>
                          ) : null}
                        </div>
                      </Td>
                      <Td className="text-sm tabular-nums">
                        {c.purchase_count ? (
                          <span className="block">{formatCurrency(c.purchase_total ?? 0)}</span>
                        ) : (
                          <span className="text-xs text-neutral-400">بدون مشتريات</span>
                        )}
                      </Td>
                      <Td className="text-sm">{c.last_purchase_date ? formatDate(c.last_purchase_date) : '-'}</Td>
                      <Td>{c.email || '-'}</Td>
                      <Td>{c.branch_name || '-'}</Td>
                      <Td className="max-w-[200px] truncate">{c.notes || '-'}</Td>
                      <Td>
                        <Badge variant={c.is_active ? 'success' : 'neutral'}>
                          {c.is_active ? 'نشط' : 'موقوف'}
                        </Badge>
                      </Td>
                      <Td>{formatDate(c.created_at)}</Td>
                      <Td>
                        <div className="flex items-center gap-2">
                          <button onClick={() => setEditing(c)} className="p-1.5 rounded-lg hover:bg-amber-50 text-amber-600 dark:hover:bg-amber-500/15 dark:text-amber-400 transition-colors" title="تعديل">
                            <Pencil size={16} />
                          </button>
                          <button onClick={() => toggleActive(c)} disabled={togglingId === c.id} className="p-1.5 rounded-lg hover:bg-brand-50 text-brand-600 transition-colors disabled:opacity-50" title={c.is_active ? 'تعطيل' : 'تفعيل'}>
                            {c.is_active ? <UserX size={16} /> : <UserCheck size={16} />}
                          </button>
                          <button onClick={() => setDeleting(c)} className="p-1.5 rounded-lg hover:bg-red-50 text-red-500 dark:hover:bg-red-500/15 dark:text-red-400 transition-colors" title="حذف">
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

        <Modal open={modalOpen} onClose={() => setModalOpen(false)} title="إضافة زبون جديد" maxWidth="max-w-2xl">
          <CustomerForm defaultBranch={filterBranch ? Number(filterBranch) : null} onSubmit={handleCreate} onCancel={() => setModalOpen(false)} />
        </Modal>

        <Modal open={!!editing} onClose={() => setEditing(null)} title="تعديل الزبون" maxWidth="max-w-2xl">
          {editing && <CustomerForm initial={editing} onSubmit={handleUpdate} onCancel={() => setEditing(null)} />}
        </Modal>

        <ConfirmDialog
          open={!!deleting}
          onClose={() => setDeleting(null)}
          onConfirm={handleDelete}
          loading={deleteLoading}
          message={`هل أنت متأكد من حذف الزبون "${deleting?.name}"؟ لا يمكن التراجع عن هذا الإجراء.`}
        />
      </div>
    </AppShell>
  );
}