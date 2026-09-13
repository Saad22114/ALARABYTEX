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
import { Plus, Eye, Pencil, Trash2, BookOpen } from 'lucide-react';
import { Supplier, Paginated } from '@/types';
import { listSuppliers, createSupplier, updateSupplier, deleteSupplier } from '@/services/suppliers';
import { formatCurrency } from '@/lib/format';
import { useToast } from '@/components/ui/Toast';
import { useSettings } from '@/components/providers/SettingsProvider';

export default function SuppliersPage() {
  const { toast } = useToast();
  const { settings } = useSettings();
  const pageSize = settings?.default_page_size ?? 10;
  const [data, setData] = useState<Paginated<Supplier> | null>(null);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [page, setPage] = useState(1);
  const [modalOpen, setModalOpen] = useState(false);
  const [editing, setEditing] = useState<Supplier | null>(null);
  const [deleting, setDeleting] = useState<Supplier | null>(null);
  const [deleteLoading, setDeleteLoading] = useState(false);

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

  return (
    <AppShell>
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <SearchInput value={search} onChange={(v) => { setSearch(v); setPage(1); }} />
          <Button onClick={() => setModalOpen(true)}>
            <Plus size={18} />
            إضافة مورد
          </Button>
        </div>

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
