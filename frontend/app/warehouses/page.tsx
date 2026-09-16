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
import Badge from '@/components/ui/Badge';
import EmptyState from '@/components/ui/EmptyState';
import Spinner from '@/components/ui/Spinner';
import Input from '@/components/ui/Input';
import { Plus, Pencil, Trash2, Eye, ArrowLeftRight } from 'lucide-react';
import StockTab from '@/components/warehouses/StockTab';
import {
  Warehouse,
  Paginated,
  FabricRoll,
  WarehouseBalance,
  StockMovement,
} from '@/types';
import {
  listWarehouses,
  createWarehouse,
  updateWarehouse,
  deleteWarehouse,
  getWarehouseSummary,
  listRolls,
  listMovements,
} from '@/services/warehouses';
import { useToast } from '@/components/ui/Toast';
import { useSettings } from '@/components/providers/SettingsProvider';

const MOVEMENT_LABEL: Record<string, string> = {
  receipt: 'استلام',
  transfer_out: 'تحويل صادر',
  transfer_in: 'تحويل ياردةد',
  adjustment_in: 'تسوية إضافة',
  adjustment_out: 'تسوية خصم',
  count: 'فارق جرد',
  opening: 'رصيد افتتاحي',
  sale: 'مبيعات',
};

function WarehouseForm({
  initial,
  onSubmit,
  loading,
}: {
  initial: Partial<Warehouse>;
  onSubmit: (d: Partial<Warehouse>) => void;
  loading: boolean;
}) {
  const [form, setForm] = useState<Partial<Warehouse>>(initial);
  const set = (k: keyof Warehouse, v: string | boolean) => setForm((f) => ({ ...f, [k]: v }));
  return (
    <form
      onSubmit={(e) => { e.preventDefault(); onSubmit(form); }}
      className="space-y-4"
    >
      <div className="grid grid-cols-2 gap-4">
        <div>
          <label className="block text-sm font-medium text-neutral-700 mb-1">اسم المخزن *</label>
          <Input value={form.name || ''} onChange={(e) => set('name', e.target.value)} required placeholder="مثال: المخزن الرئيسي" />
        </div>
        <div>
          <label className="block text-sm font-medium text-neutral-700 mb-1">كود المخزن *</label>
          <Input value={form.code || ''} onChange={(e) => set('code', e.target.value)} required placeholder="WH-01" dir="ltr" />
        </div>
      </div>
      <div className="grid grid-cols-2 gap-4">
        <div>
          <label className="block text-sm font-medium text-neutral-700 mb-1">الموقع</label>
          <Input value={form.location || ''} onChange={(e) => set('location', e.target.value)} />
        </div>
        <div>
          <label className="block text-sm font-medium text-neutral-700 mb-1">الهاتف</label>
          <Input value={form.phone || ''} onChange={(e) => set('phone', e.target.value)} dir="ltr" />
        </div>
      </div>
      <div>
        <label className="block text-sm font-medium text-neutral-700 mb-1">أمين المخزن</label>
        <Input value={form.manager_name || ''} onChange={(e) => set('manager_name', e.target.value)} />
      </div>
      <div>
        <label className="block text-sm font-medium text-neutral-700 mb-1">ملاحظات</label>
        <textarea
          className="w-full rounded-xl border border-sand-300 bg-surface px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500/40"
          value={form.notes || ''}
          onChange={(e) => set('notes', e.target.value)}
          rows={2}
        />
      </div>
      <label className="flex items-center gap-2 text-sm text-neutral-700">
        <input
          type="checkbox"
          checked={form.is_active ?? true}
          onChange={(e) => set('is_active', e.target.checked)}
          className="h-4 w-4 rounded border-sand-300 text-brand-600 focus:ring-brand-500"
        />
        مخزن نشط
      </label>
      <div className="flex justify-end gap-3 pt-2">
        <Button type="submit" loading={loading}>
          {initial.id ? 'حفظ التعديلات' : 'إضافة المخزن'}
        </Button>
      </div>
    </form>
  );
}

export default function WarehousesPage() {
  const { toast } = useToast();
  const { settings } = useSettings();
  const pageSize = settings?.default_page_size ?? 10;
  const [data, setData] = useState<Paginated<Warehouse> | null>(null);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [page, setPage] = useState(1);
  const [modalOpen, setModalOpen] = useState(false);
  const [editing, setEditing] = useState<Warehouse | null>(null);
  const [formLoading, setFormLoading] = useState(false);
  const [deleting, setDeleting] = useState<Warehouse | null>(null);
  const [deleteLoading, setDeleteLoading] = useState(false);
  const [viewing, setViewing] = useState<Warehouse | null>(null);
  const [pageTab, setPageTab] = useState<'warehouses' | 'stock'>('warehouses');
  const [tab, setTab] = useState<'stock' | 'rolls' | 'movements'>('stock');
  const [summary, setSummary] = useState<WarehouseBalance[]>([]);
  const [rolls, setRolls] = useState<FabricRoll[]>([]);
  const [movements, setMovements] = useState<StockMovement[]>([]);
  const [detailLoading, setDetailLoading] = useState(false);

  const fetchData = () => {
    let cancelled = false;
    setLoading(true);
    const params: Record<string, string | number | undefined | null> = { page, page_size: pageSize, search: search || undefined };
    listWarehouses(params)
      .then((res) => { if (!cancelled) setData(res); })
      .catch((err: any) => { if (!cancelled) toast('error', err.message); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  };

  useEffect(() => fetchData(), [page, search, settings?.default_page_size]);

  useEffect(() => {
    if (!viewing) return;
    let cancelled = false;
    setDetailLoading(true);
    setSummary([]);
    setRolls([]);
    setMovements([]);
    getWarehouseSummary(viewing.id)
      .then((r) => { if (!cancelled) setSummary(r); })
      .catch(() => {});
    listRolls({ warehouse: viewing.id, page_size: 50 })
      .then((r) => { if (!cancelled) setRolls(r.results); })
      .catch(() => {});
    listMovements({ warehouse: viewing.id, page_size: 20 })
      .then((r) => { if (!cancelled) setMovements(r.results); })
      .catch(() => {})
      .finally(() => { if (!cancelled) setDetailLoading(false); });
    return () => { cancelled = true; };
  }, [viewing]);

  const totalPages = data ? Math.ceil(data.count / pageSize) : 1;

  const handleCreate = async (d: Partial<Warehouse>) => {
    setFormLoading(true);
    try {
      await createWarehouse(d);
      toast('success', 'تمت إضافة المخزن بنجاح');
      setModalOpen(false);
      fetchData();
    } catch (err: any) {
      toast('error', err.message);
    } finally {
      setFormLoading(false);
    }
  };

  const handleUpdate = async (d: Partial<Warehouse>) => {
    if (!editing) return;
    setFormLoading(true);
    try {
      await updateWarehouse(editing.id, d);
      toast('success', 'تم تحديث المخزن بنجاح');
      setEditing(null);
      fetchData();
    } catch (err: any) {
      toast('error', err.message);
    } finally {
      setFormLoading(false);
    }
  };

  const handleDelete = async () => {
    if (!deleting) return;
    setDeleteLoading(true);
    try {
      await deleteWarehouse(deleting.id);
      toast('success', 'تم حذف المخزن بنجاح');
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
        <div className="flex items-center justify-between flex-wrap gap-3">
          <div>
            <h1 className="text-xl font-bold text-neutral-800">المخازن</h1>
            <p className="text-sm text-neutral-500">إدارة المخازن وأرصدة المخزون والحركات الموثقة</p>
          </div>
          <div className="flex gap-2">
            {([
              { k: 'warehouses', label: 'المخازن' },
              { k: 'stock', label: 'المخزون' },
            ] as const).map((t) => (
              <button
                key={t.k}
                onClick={() => setPageTab(t.k)}
                className={`px-4 py-2 rounded-xl text-sm font-medium transition-all duration-150 ${
                  pageTab === t.k
                    ? 'bg-brand-600 text-white shadow-sm'
                    : 'bg-surface text-neutral-600 border border-sand-200 hover:bg-sand-50'
                }`}
              >
                {t.label}
              </button>
            ))}
          </div>
        </div>

        {pageTab === 'stock' ? (
          <StockTab />
        ) : (
          <>
        <div className="flex items-center justify-end gap-3">
          <Link href="/warehouses/transfers">
            <Button variant="secondary">
              <ArrowLeftRight size={18} />
              التحويلات
            </Button>
          </Link>
          <Button onClick={() => setModalOpen(true)}>
            <Plus size={18} />
            إضافة مخزن
          </Button>
        </div>

        {data && data.results.length > 0 && (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            {data.results.slice(0, 4).map((w) => (
              <Card key={w.id}>
                <div className="flex items-center justify-between mb-2">
                  <span className="font-semibold text-neutral-800">{w.name}</span>
                  <Badge variant={w.is_active ? 'success' : 'danger'}>
                    {w.is_active ? 'نشط' : 'موقوف'}
                  </Badge>
                </div>
                <p className="text-xs text-neutral-500 mb-3">{w.code}</p>
                <div className="flex gap-4 text-sm">
                  <span className="text-neutral-600">لفات: <b className="tabular-nums">{w.total_rolls}</b></span>
                  <span className="text-neutral-600">ياردات: <b className="tabular-nums">{w.total_yards}</b></span>
                </div>
              </Card>
            ))}
          </div>
        )}

        <Card>
          <div className="p-4 border-b border-sand-100">
            <SearchInput value={search} onChange={(v) => { setSearch(v); setPage(1); }} />
          </div>
          {loading ? (
            <div className="flex justify-center py-12"><Spinner size={32} /></div>
          ) : !data || data.results.length === 0 ? (
            <EmptyState title="لا توجد مخازن" description="أضف أول مخزن لإدارة المخزون" />
          ) : (
            <>
              <Table>
                <thead>
                  <tr>
                    <Th>اسم المخزن</Th>
                    <Th>الكود</Th>
                    <Th>الموقع</Th>
                    <Th>أمين المخزن</Th>
                    <Th>اللفات</Th>
                    <Th>الياردات</Th>
                    <Th>الحالة</Th>
                    <Th>إجراءات</Th>
                  </tr>
                </thead>
                <tbody>
                  {data.results.map((w) => (
                    <Tr key={w.id}>
                      <Td className="font-medium">{w.name}</Td>
                      <Td><span className="font-mono text-xs bg-sand-100 px-2 py-1 rounded" dir="ltr">{w.code}</span></Td>
                      <Td>{w.location || '—'}</Td>
                      <Td>{w.manager_name || '—'}</Td>
                      <Td className="tabular-nums">{w.total_rolls}</Td>
                      <Td className="tabular-nums font-medium">{w.total_yards}</Td>
                      <Td>
                        <Badge variant={w.is_active ? 'success' : 'danger'}>
                          {w.is_active ? 'نشط' : 'موقوف'}
                        </Badge>
                      </Td>
                      <Td>
                        <div className="flex gap-1">
                          <button
                            onClick={() => setViewing(w)}
                            className="p-2 rounded-lg text-neutral-500 hover:bg-brand-50 hover:text-brand-600"
                            title="عرض التفاصيل"
                          >
                            <Eye size={16} />
                          </button>
                          <button
                            onClick={() => { setEditing(w); setModalOpen(true); }}
                            className="p-2 rounded-lg text-neutral-500 hover:bg-brand-50 hover:text-brand-600"
                            title="تعديل"
                          >
                            <Pencil size={16} />
                          </button>
                          <button
                            onClick={() => setDeleting(w)}
                            className="p-2 rounded-lg text-neutral-500 hover:bg-red-50 hover:text-red-600"
                            title="حذف"
                          >
                            <Trash2 size={16} />
                          </button>
                        </div>
                      </Td>
                    </Tr>
                  ))}
                </tbody>
              </Table>
              {totalPages > 1 && (
                <div className="p-4">
                  <Pagination page={page} totalPages={totalPages} onChange={setPage} />
                </div>
              )}
            </>
          )}
        </Card>
          </>
        )}
      </div>

      <Modal open={modalOpen} onClose={() => { setModalOpen(false); setEditing(null); }} title={editing ? 'تعديل مخزن' : 'إضافة مخزن'}>
        <WarehouseForm
          initial={editing || { is_active: true }}
          onSubmit={editing ? handleUpdate : handleCreate}
          loading={formLoading}
        />
      </Modal>

      <ConfirmDialog
        open={!!deleting}
        title="حذف المخزن"
        message="هل أنت متأكد من حذف هذا المخزن؟ لا يمكن حذف مخزن يحتوي على لفات أو حركات."
        confirmLabel="حذف"
        loading={deleteLoading}
        onConfirm={handleDelete}
        onClose={() => setDeleting(null)}
      />

      <Modal open={!!viewing} onClose={() => setViewing(null)} title={viewing ? `تفاصيل: ${viewing.name}` : ''} maxWidth="max-w-3xl">
        {viewing && (
          <div className="space-y-4">
            <div className="text-sm text-neutral-500">
              <span dir="ltr" className="font-mono text-xs bg-sand-100 px-2 py-1 rounded">{viewing.code}</span>
              {viewing.location && <span className="mr-3">الموقع: {viewing.location}</span>}
              {viewing.manager_name && <span className="mr-3">أمين المخزن: {viewing.manager_name}</span>}
            </div>

            <div className="flex gap-2 border-b border-sand-100">
              {([
                { k: 'stock', label: 'الأرصدة' },
                { k: 'rolls', label: 'اللفات' },
                { k: 'movements', label: 'الحركات' },
              ] as const).map((t) => (
                <button
                  key={t.k}
                  onClick={() => setTab(t.k)}
                  className={`px-4 py-2 text-sm font-medium border-b-2 -mb-px transition-colors ${tab === t.k ? 'border-brand-600 text-brand-700' : 'border-transparent text-neutral-500 hover:text-neutral-700'}`}
                >
                  {t.label}
                </button>
              ))}
            </div>

            {detailLoading ? (
              <div className="flex justify-center py-10"><Spinner size={28} /></div>
            ) : (
              <>
                {tab === 'stock' && (
                  summary.length === 0 ? (
                    <EmptyState title="لا توجد أرصدة" description="أضف استلاماً أو تسوية لبناء رصيد المخزن" />
                  ) : (
                    <Table>
                      <thead>
                        <tr>
                          <Th>القماش</Th>
                          <Th>عدد اللفات</Th>
                          <Th>إجمالي الياردات</Th>
                        </tr>
                      </thead>
                      <tbody>
                        {summary.map((b) => (
                          <Tr key={b.fabric}>
                            <Td className="font-medium">{b.fabric_name}</Td>
                            <Td className="tabular-nums">{b.rolls_available}</Td>
                            <Td className="tabular-nums font-medium">{b.total_yards}</Td>
                          </Tr>
                        ))}
                      </tbody>
                    </Table>
                  )
                )}

                {tab === 'rolls' && (
                  rolls.length === 0 ? (
                    <EmptyState title="لا توجد لفات" />
                  ) : (
                    <Table>
                      <thead>
                        <tr>
                          <Th>كود اللفة</Th>
                          <Th>القماش</Th>
                          <Th>الأصلية</Th>
                          <Th>المتبقي</Th>
                          <Th>الحالة</Th>
                        </tr>
                      </thead>
                      <tbody>
                        {rolls.map((r) => (
                          <Tr key={r.id}>
                            <Td><span className="font-mono text-xs bg-sand-100 px-2 py-1 rounded" dir="ltr">{r.code}</span></Td>
                            <Td>{r.fabric_name}</Td>
                            <Td className="tabular-nums">{r.yards}</Td>
                            <Td className="tabular-nums font-medium">{r.remaining_yards}</Td>
                            <Td>
                              <Badge variant={r.status === 'available' ? 'success' : r.status === 'damaged' ? 'danger' : 'neutral'}>
                                {r.status_label}
                              </Badge>
                            </Td>
                          </Tr>
                        ))}
                      </tbody>
                    </Table>
                  )
                )}

                {tab === 'movements' && (
                  movements.length === 0 ? (
                    <EmptyState title="لا توجد حركات" />
                  ) : (
                    <Table>
                      <thead>
                        <tr>
                          <Th>التاريخ</Th>
                          <Th>الحركة</Th>
                          <Th>القماش</Th>
                          <Th>الكمية</Th>
                          <Th>المرجع</Th>
                        </tr>
                      </thead>
                      <tbody>
                        {movements.map((m: StockMovement) => (
                          <Tr key={m.id}>
                            <Td className="tabular-nums">{m.date}</Td>
                            <Td>
                              <span className="text-xs">{MOVEMENT_LABEL[m.movement_type] || m.movement_type_label}</span>
                            </Td>
                            <Td>{m.fabric_name}</Td>
                            <Td className={`tabular-nums font-medium ${m.quantity < 0 ? 'text-red-600' : 'text-emerald-700'}`}>
                              {m.quantity > 0 ? '+' : ''}{m.quantity}
                            </Td>
                            <Td className="text-neutral-500 text-xs" dir="ltr">{m.reference_no || '—'}</Td>
                          </Tr>
                        ))}
                      </tbody>
                    </Table>
                  )
                )}
              </>
            )}
          </div>
        )}
      </Modal>
    </AppShell>
  );
}