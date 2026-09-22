'use client';

import { useState, useEffect, useCallback } from 'react';
import AppShell from '@/components/layout/AppShell';
import Card from '@/components/ui/Card';
import Button from '@/components/ui/Button';
import Table, { Th, Td, Tr } from '@/components/ui/Table';
import Input from '@/components/ui/Input';
import Select from '@/components/ui/Select';
import Pagination from '@/components/ui/Pagination';
import Modal from '@/components/ui/Modal';
import ConfirmDialog from '@/components/ui/ConfirmDialog';
import Badge from '@/components/ui/Badge';
import EmptyState from '@/components/ui/EmptyState';
import Spinner from '@/components/ui/Spinner';
import { Plus, CheckCircle2, Trash2, X } from 'lucide-react';
import { GoodsReceipt, Paginated, Warehouse, Fabric, Supplier, ReceiptItem, Branch } from '@/types';
import { listReceipts, createReceipt, postReceipt, deleteReceipt, ReceiptWrite } from '@/services/warehouses';
import { listWarehouses } from '@/services/warehouses';
import { listBranches } from '@/services/branches';
import { listFabrics } from '@/services/fabrics';
import { listSuppliers } from '@/services/suppliers';
import { useToast } from '@/components/ui/Toast';
import { useSettings } from '@/components/providers/SettingsProvider';
import { useUrlState } from '@/lib/useUrlState';
import { formatCurrency, formatNumber } from '@/lib/format';

function ReceiptForm({
  warehouses,
  branches,
  fabrics,
  suppliers,
  onSubmit,
  loading,
}: {
  warehouses: Warehouse[];
  branches: Branch[];
  fabrics: Fabric[];
  suppliers: Supplier[];
  onSubmit: (d: ReceiptWrite) => void;
  loading: boolean;
}) {
  const [destType, setDestType] = useState<'warehouse' | 'branch'>('warehouse');
  const [warehouse, setWarehouse] = useState<number | undefined>(warehouses[0]?.id);
  const [branch, setBranch] = useState<number | undefined>(branches[0]?.id);
  const [supplier, setSupplier] = useState<string>('');
  const [date, setDate] = useState(new Date().toISOString().slice(0, 10));
  const [supplierReceiptNo, setSupplierReceiptNo] = useState('');
  const [items, setItems] = useState<ReceiptItem[]>([{ fabric: fabrics[0]?.id ?? 0, rolls_count: 1, yards: 0, unit_price: 0 }]);

  const updateItem = (i: number, patch: Partial<ReceiptItem>) => {
    setItems((rows) => rows.map((r, idx) => (idx === i ? { ...r, ...patch } : r)));
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const payload: ReceiptWrite = {
      supplier: supplier ? Number(supplier) : null,
      date,
      supplier_receipt_no: supplierReceiptNo,
      items: items.map((it) => ({ fabric: it.fabric, rolls_count: it.rolls_count, yards: it.yards, unit_price: it.unit_price })),
    };
    if (destType === 'branch') {
      if (!branch) return;
      payload.branch = branch;
    } else {
      if (!warehouse) return;
      payload.warehouse = warehouse;
    }
    onSubmit(payload);
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div className="grid grid-cols-2 gap-4">
        <div>
          <label className="block text-sm font-medium text-neutral-700 mb-1">وجهة الاستلام *</label>
          <Select
            value={destType}
            onChange={(e) => setDestType(e.target.value as 'warehouse' | 'branch')}
            options={[
              { value: 'warehouse', label: 'مخزن' },
              { value: 'branch', label: 'فرع' },
            ]}
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-neutral-700 mb-1">
            {destType === 'warehouse' ? 'المخزن المستلم *' : 'الفرع المستلم *'}
          </label>
          <Select
            value={destType === 'warehouse' ? (warehouse ?? '') : (branch ?? '')}
            onChange={(e) => (destType === 'warehouse' ? setWarehouse(Number(e.target.value)) : setBranch(Number(e.target.value)))}
            options={destType === 'warehouse' ? warehouses.map((w) => ({ value: w.id, label: w.name })) : branches.map((b) => ({ value: b.id, label: b.name }))}
            required
          />
        </div>
      </div>
      <div className="grid grid-cols-2 gap-4">
        <div>
          <label className="block text-sm font-medium text-neutral-700 mb-1">المورد</label>
          <Select value={supplier} onChange={(e) => setSupplier(e.target.value)} options={suppliers.map((s) => ({ value: s.id, label: s.name }))} placeholder="بلا مورد" />
        </div>
        <div>
          <label className="block text-sm font-medium text-neutral-700 mb-1">تاريخ الاستلام *</label>
          <Input type="date" value={date} onChange={(e) => setDate(e.target.value)} required />
        </div>
      </div>
      <div>
        <label className="block text-sm font-medium text-neutral-700 mb-1">رقم فاتورة المورد</label>
        <Input value={supplierReceiptNo} onChange={(e) => setSupplierReceiptNo(e.target.value)} />
      </div>

      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <label className="block text-sm font-medium text-neutral-700">الأصناف *</label>
          <Button type="button" variant="subtle" size="sm" onClick={() => setItems((r) => [...r, { fabric: fabrics[0]?.id ?? 0, rolls_count: 1, yards: 0, unit_price: 0 }])}>
            <Plus size={16} />
            إضافة صنف
          </Button>
        </div>
        {items.map((it, i) => (
          <div key={i} className="grid grid-cols-[1fr_1fr_1fr_1fr_auto] gap-2 items-center bg-sand-50 p-2 rounded-xl">
            <Select value={it.fabric} onChange={(e) => updateItem(i, { fabric: Number(e.target.value) })} options={fabrics.map((f) => ({ value: f.id, label: `${f.name} (${f.code})` }))} />
            <Input type="number" min={1} value={it.rolls_count} onChange={(e) => updateItem(i, { rolls_count: Number(e.target.value) })} placeholder="طاقات" title="عدد الطاقات" />
            <Input type="number" min={0} step="0.01" value={it.yards} onChange={(e) => updateItem(i, { yards: Number(e.target.value) })} placeholder="ياردات" required />
            <Input type="number" min={0} step="0.001" value={it.unit_price} onChange={(e) => updateItem(i, { unit_price: Number(e.target.value) })} placeholder="سعر الياردة" />
            <button type="button" onClick={() => setItems((r) => (r.length > 1 ? r.filter((_, idx) => idx !== i) : r))} className="p-2 rounded-lg text-neutral-400 hover:text-red-500">
              <X size={16} />
            </button>
          </div>
        ))}
      </div>

      <div className="flex justify-between items-center pt-2">
        <div className="text-sm text-neutral-500">
          الإجمالي: <b className="tabular-nums">{formatNumber(items.reduce((s, it) => s + it.yards * it.unit_price, 0))}</b>
        </div>
        <Button type="submit" loading={loading}>حفظ سند الاستلام</Button>
      </div>
    </form>
  );
}

export default function ReceiptsPage() {
  const { toast } = useToast();
  const { settings } = useSettings();
  const pageSize = settings?.default_page_size ?? 10;
  const [data, setData] = useState<Paginated<GoodsReceipt> | null>(null);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useUrlState('page', 1);
  const [modalOpen, setModalOpen] = useState(false);
  const [formLoading, setFormLoading] = useState(false);
  const [warehouses, setWarehouses] = useState<Warehouse[]>([]);
  const [branches, setBranches] = useState<Branch[]>([]);
  const [fabrics, setFabrics] = useState<Fabric[]>([]);
  const [suppliers, setSuppliers] = useState<Supplier[]>([]);
  const [posting, setPosting] = useState<GoodsReceipt | null>(null);
  const [postLoading, setPostLoading] = useState(false);
  const [deleting, setDeleting] = useState<GoodsReceipt | null>(null);
  const [deleteLoading, setDeleteLoading] = useState(false);

  const fetchData = useCallback(() => {
    let cancelled = false;
    setLoading(true);
    listReceipts({ page, page_size: pageSize })
      .then((res) => { if (!cancelled) setData(res); })
      .catch((err: any) => { if (!cancelled) toast('error', err.message); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [page, pageSize]);

  useEffect(() => fetchData(), [fetchData]);

  useEffect(() => {
    listWarehouses({ page_size: 100 }).then((r) => setWarehouses(r.results)).catch(() => {});
    listBranches({ page_size: 100 }).then((r) => setBranches(r.results)).catch(() => {});
    listSuppliers({ page_size: 100 }).then((r) => setSuppliers(r.results)).catch(() => {});
    listFabrics({ page_size: 100 }).then((r) => setFabrics(r.results)).catch(() => {});
  }, [modalOpen]);

  const totalPages = data ? Math.ceil(data.count / pageSize) : 1;

  const handleCreate = async (d: ReceiptWrite) => {
    setFormLoading(true);
    try {
      const r = await createReceipt(d);
      toast('success', `تم إنشاء سند الاستلام ${r.number}`);
      setModalOpen(false);
      fetchData();
    } catch (err: any) {
      toast('error', err.message);
    } finally {
      setFormLoading(false);
    }
  };

  const handlePost = async () => {
    if (!posting) return;
    setPostLoading(true);
    try {
      await postReceipt(posting.id);
      toast('success', 'تم ترحيل السند وإنشاء الطاقات');
      setPosting(null);
      fetchData();
    } catch (err: any) {
      toast('error', err.message);
    } finally {
      setPostLoading(false);
    }
  };

  const handleDelete = async () => {
    if (!deleting) return;
    setDeleteLoading(true);
    try {
      await deleteReceipt(deleting.id);
      toast('success', 'تم حذف السند');
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
          <div>
            <h1 className="text-xl font-bold text-neutral-800">استلام البضاعة</h1>
            <p className="text-sm text-neutral-500">استلام أقمشة من الموردين وإنشاء الطاقات</p>
          </div>
          <Button onClick={() => setModalOpen(true)}>
            <Plus size={18} />
            سند استلام جديد
          </Button>
        </div>

        <Card>
          {loading ? (
            <div className="flex justify-center py-12"><Spinner size={32} /></div>
          ) : !data || data.results.length === 0 ? (
            <EmptyState title="لا توجد سندات استلام" description="ابدأ بإنشاء أول سند استلام من المورد" />
          ) : (
            <>
              <Table>
                <thead>
                  <tr>
                    <Th>رقم السند</Th>
                    <Th>الوجهة</Th>
                    <Th>المورد</Th>
                    <Th>التاريخ</Th>
                    <Th>الياردات</Th>
                    <Th>القيمة</Th>
                    <Th>الحالة</Th>
                    <Th>إجراءات</Th>
                  </tr>
                </thead>
                <tbody>
                  {data.results.map((r) => (
                    <Tr key={r.id}>
                      <Td><span className="font-mono text-xs bg-sand-100 px-2 py-1 rounded" dir="ltr">{r.number}</span></Td>
                      <Td>
                        {r.dest_type === 'branch' ? (
                          <span className="text-brand-600">فرع: {r.dest_name}</span>
                        ) : (
                          <span>مخزن: {r.dest_name}</span>
                        )}
                      </Td>
                      <Td>{r.supplier_name || '—'}</Td>
                      <Td className="tabular-nums">{r.date}</Td>
                      <Td className="tabular-nums">{formatNumber(r.total_yards)}</Td>
                      <Td className="tabular-nums font-medium">{formatCurrency(r.total_value)}</Td>
                      <Td>
                        <Badge variant={r.status === 'posted' ? 'success' : 'warning'}>
                          {r.status_label}
                        </Badge>
                      </Td>
                      <Td>
                        <div className="flex gap-1">
                          {r.status === 'draft' && (
                            <>
                              <button
                                onClick={() => setPosting(r)}
                                className="p-2 rounded-lg text-emerald-600 hover:bg-emerald-50"
                                title="ترحيل السند"
                              >
                                <CheckCircle2 size={16} />
                              </button>
                              <button
                                onClick={() => setDeleting(r)}
                                className="p-2 rounded-lg text-neutral-500 hover:bg-red-50 hover:text-red-600"
                                title="حذف"
                              >
                                <Trash2 size={16} />
                              </button>
                            </>
                          )}
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
      </div>

      <Modal open={modalOpen} onClose={() => setModalOpen(false)} title="سند استلام جديد" maxWidth="max-w-3xl">
        <ReceiptForm
          warehouses={warehouses}
          branches={branches}
          fabrics={fabrics}
          suppliers={suppliers}
          onSubmit={handleCreate}
          loading={formLoading}
        />
      </Modal>

      <ConfirmDialog
        open={!!posting}
        title="ترحيل سند الاستلام"
        message={`سيتم إنشاء الطاقات وحركات المخزون للسند ${posting?.number}. لا يمكن التراجع بعد الترحيل.`}
        confirmLabel="ترحيل السند"
        loading={postLoading}
        onConfirm={handlePost}
        onClose={() => setPosting(null)}
      />

      <ConfirmDialog
        open={!!deleting}
        title="حذف سند الاستلام"
        message="هل أنت متأكد من حذف هذا السند؟"
        confirmLabel="حذف"
        loading={deleteLoading}
        onConfirm={handleDelete}
        onClose={() => setDeleting(null)}
      />
    </AppShell>
  );
}