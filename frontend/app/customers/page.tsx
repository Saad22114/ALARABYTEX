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
import { Plus, Pencil, Trash2, UserX, UserCheck } from 'lucide-react';
import { Customer, Paginated } from '@/types';
import { listCustomers, createCustomer, updateCustomer, deleteCustomer } from '@/services/customers';
import { formatDate } from '@/lib/format';
import { useToast } from '@/components/ui/Toast';
import { useSettings } from '@/components/providers/SettingsProvider';

export default function CustomersPage() {
  const { toast } = useToast();
  const { settings } = useSettings();
  const pageSize = settings?.default_page_size ?? 10;
  const [data, setData] = useState<Paginated<Customer> | null>(null);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [page, setPage] = useState(1);
  const [modalOpen, setModalOpen] = useState(false);
  const [editing, setEditing] = useState<Customer | null>(null);
  const [deleting, setDeleting] = useState<Customer | null>(null);
  const [deleteLoading, setDeleteLoading] = useState(false);
  const [togglingId, setTogglingId] = useState<number | null>(null);

  const fetchData = () => {
    let cancelled = false;
    setLoading(true);
    const params: Record<string, string | number | undefined | null> = { page, page_size: pageSize, search: search || undefined };
    listCustomers(params)
      .then((res) => { if (!cancelled) setData(res); })
      .catch((err) => { if (!cancelled) toast('error', err.message); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  };

  useEffect(() => fetchData(), [page, search, settings?.default_page_size]);

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
                      <Td dir="ltr" className="text-left">{c.phone || '-'}</Td>
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
          <CustomerForm onSubmit={handleCreate} onCancel={() => setModalOpen(false)} />
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