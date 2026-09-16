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
import BranchForm from '@/components/forms/BranchForm';
import EmptyState from '@/components/ui/EmptyState';
import Spinner from '@/components/ui/Spinner';
import Badge from '@/components/ui/Badge';
import Switch from '@/components/ui/Switch';
import { Plus, Eye, Pencil, Trash2 } from 'lucide-react';
import { Branch, Paginated } from '@/types';
import { listBranches, createBranch, updateBranch, deleteBranch } from '@/services/branches';
import { formatCurrency } from '@/lib/format';
import { useToast } from '@/components/ui/Toast';
import { useSettings } from '@/components/providers/SettingsProvider';

export default function BranchesPage() {
  const { toast } = useToast();
  const { settings } = useSettings();
  const pageSize = settings?.default_page_size ?? 10;
  const [data, setData] = useState<Paginated<Branch> | null>(null);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [page, setPage] = useState(1);
  const [modalOpen, setModalOpen] = useState(false);
  const [editing, setEditing] = useState<Branch | null>(null);
  const [deleting, setDeleting] = useState<Branch | null>(null);
  const [deleteLoading, setDeleteLoading] = useState(false);
  const [stopping, setStopping] = useState<Branch | null>(null);
  const [toggleLoading, setToggleLoading] = useState(false);

  const fetchData = () => {
    let cancelled = false;
    setLoading(true);
    const params: Record<string, string | number | undefined | null> = { page, page_size: pageSize, search: search || undefined };
    listBranches(params)
      .then((res) => { if (!cancelled) setData(res); })
      .catch((err) => { if (!cancelled) toast('error', err.message); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  };

  useEffect(() => fetchData(), [page, search, settings?.default_page_size]);

  const totalPages = data ? Math.ceil(data.count / pageSize) : 1;

  const handleCreate = async (d: Partial<Branch>) => {
    await createBranch(d);
    toast('success', 'تمت إضافة الفرع بنجاح');
    setModalOpen(false);
    fetchData();
  };

  const handleUpdate = async (d: Partial<Branch>) => {
    if (!editing) return;
    await updateBranch(editing.id, d);
    toast('success', 'تم تحديث الفرع بنجاح');
    setEditing(null);
    fetchData();
  };

  const handleDelete = async () => {
    if (!deleting) return;
    setDeleteLoading(true);
    try {
      await deleteBranch(deleting.id);
      toast('success', 'تم حذف الفرع بنجاح');
      setDeleting(null);
      fetchData();
    } catch (err: any) {
      toast('error', err.message);
    } finally {
      setDeleteLoading(false);
    }
  };

  const handleToggle = async (target: Branch, next: boolean) => {
    setToggleLoading(true);
    try {
      const updated = await updateBranch(target.id, { is_active: next });
      setData((d) => d && { ...d, results: d.results.map((b) => (b.id === updated.id ? updated : b)) });
      toast('success', next ? 'تم تشغيل الفرع' : 'تم إيقاف الفرع');
    } catch (err: any) {
      toast('error', err.message);
    } finally {
      setToggleLoading(false);
      setStopping(null);
    }
  };

  return (
    <AppShell>
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <SearchInput value={search} onChange={(v) => { setSearch(v); setPage(1); }} />
          <Button onClick={() => setModalOpen(true)}>
            <Plus size={18} />
            إضافة فرع
          </Button>
        </div>

        <Card>
          {loading ? (
            <div className="flex justify-center py-12"><Spinner size={32} /></div>
          ) : !data || data.results.length === 0 ? (
            <EmptyState title="لا توجد فروع" description="لم يتم إضافة أي فرع بعد" />
          ) : (
            <>
              <Table>
                <thead>
                  <tr>
                    <Th>كود الفرع</Th>
                    <Th>اسم الفرع</Th>
                    <Th>المدينة</Th>
                    <Th>الهاتف</Th>
                    <Th>عدد المبيعات</Th>
                    <Th>عدد المصاريف</Th>
                    <Th>الهدف الشهري</Th>
                    <Th>الحالة</Th>
                    <Th>إجراءات</Th>
                  </tr>
                </thead>
                <tbody>
                  {data.results.map((b) => (
                    <Tr key={b.id}>
                      <Td><span className="font-mono text-xs bg-sand-100 px-2 py-1 rounded">{b.code}</span></Td>
                      <Td className="font-medium">{b.name}</Td>
                      <Td>{b.city || '-'}</Td>
                      <Td dir="ltr" className="text-left">{b.phone || '-'}</Td>
                      <Td className="tabular-nums">{b.sales_count}</Td>
                      <Td className="tabular-nums">{b.expenses_count}</Td>
                      <Td>
                        {b.target_progress_pct !== null && b.target_progress_pct !== undefined ? (
                          <div className="w-36">
                            <div className="flex items-center justify-between text-xs mb-1">
                              <span className="text-neutral-500 tabular-nums">
                                {formatCurrency(b.monthly_sales)} / {formatCurrency(b.monthly_sales_target)}
                              </span>
                              <span className={`font-semibold tabular-nums ${b.target_progress_pct >= 100 ? 'text-emerald-600' : 'text-neutral-600'}`}>
                                {b.target_progress_pct}%
                              </span>
                            </div>
                            <div className="h-1.5 rounded-full bg-sand-100 overflow-hidden">
                              <div
                                className={`h-full rounded-full ${b.target_progress_pct >= 100 ? 'bg-emerald-500' : 'bg-brand-500'}`}
                                style={{ width: `${Math.min(100, b.target_progress_pct)}%` }}
                              />
                            </div>
                          </div>
                        ) : (
                          <span className="text-neutral-300">—</span>
                        )}
                      </Td>
                      <Td>
                        <div className="flex items-center gap-2">
                          <Switch
                            size="sm"
                            checked={b.is_active}
                            disabled={toggleLoading}
                            onChange={(next) => {
                              if (next) handleToggle(b, true);
                              else setStopping(b);
                            }}
                            aria-label={b.is_active ? 'إيقاف الفرع' : 'تشغيل الفرع'}
                          />
                          <Badge variant={b.is_active ? 'success' : 'neutral'}>
                            {b.is_active ? 'يعمل' : 'موقوف'}
                          </Badge>
                        </div>
                      </Td>
                      <Td>
                        <div className="flex items-center gap-2">
                          <Link href={`/branches/${b.id}`} className="p-1.5 rounded-lg hover:bg-brand-50 text-brand-600 transition-colors">
                            <Eye size={16} />
                          </Link>
                          <button onClick={() => setEditing(b)} className="p-1.5 rounded-lg hover:bg-amber-50 text-amber-600 dark:hover:bg-amber-500/15 dark:text-amber-400 transition-colors">
                            <Pencil size={16} />
                          </button>
                          <button onClick={() => setDeleting(b)} className="p-1.5 rounded-lg hover:bg-red-50 text-red-500 dark:hover:bg-red-500/15 dark:text-red-400 transition-colors">
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

        {/* Create Modal */}
        <Modal open={modalOpen} onClose={() => setModalOpen(false)} title="إضافة فرع جديد">
          <BranchForm onSubmit={handleCreate} onCancel={() => setModalOpen(false)} />
        </Modal>

        {/* Edit Modal */}
        <Modal open={!!editing} onClose={() => setEditing(null)} title="تعديل الفرع">
          {editing && <BranchForm initial={editing} onSubmit={handleUpdate} onCancel={() => setEditing(null)} />}
        </Modal>

        <ConfirmDialog
          open={!!stopping}
          onClose={() => setStopping(null)}
          onConfirm={() => handleToggle(stopping!, false)}
          loading={toggleLoading}
          message={`هل أنت متأكد من إيقاف فرع "${stopping?.name}"؟ لن يتمكن من تسجيل مبيعات أو مصاريف جديدة، مع بقاء السجلات السابقة.`}
        />

        {/* Delete Confirm */}
        <ConfirmDialog
          open={!!deleting}
          onClose={() => setDeleting(null)}
          onConfirm={handleDelete}
          loading={deleteLoading}
          message={`هل أنت متأكد من حذف فرع "${deleting?.name}"؟ لا يمكن التراجع عن هذا الإجراء.`}
        />
      </div>
    </AppShell>
  );
}
