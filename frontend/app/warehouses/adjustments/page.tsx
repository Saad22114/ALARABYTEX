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
import Badge from '@/components/ui/Badge';
import EmptyState from '@/components/ui/EmptyState';
import Spinner from '@/components/ui/Spinner';
import Textarea from '@/components/ui/Textarea';
import { Plus, X } from 'lucide-react';
import { StockAdjustment, Paginated, Warehouse, Fabric, AdjustmentItem, AdjustmentReason, AdjustmentDirection } from '@/types';
import { listAdjustments, createAdjustment, AdjustmentWrite } from '@/services/warehouses';
import { listWarehouses } from '@/services/warehouses';
import { listFabrics } from '@/services/fabrics';
import { useToast } from '@/components/ui/Toast';
import { useSettings } from '@/components/providers/SettingsProvider';
import { useUrlState } from '@/lib/useUrlState';
import { formatNumber } from '@/lib/format';

const REASON_LABEL: Record<AdjustmentReason, string> = {
  damage: 'تلف',
  loss: 'فقد / نقص',
  gain: 'زيادة',
  correction: 'تصحيح جرد',
  '': 'بدون سبب',
};

function AdjustmentForm({
  warehouses,
  fabrics,
  onSubmit,
  loading,
}: {
  warehouses: Warehouse[];
  fabrics: Fabric[];
  onSubmit: (d: AdjustmentWrite) => void;
  loading: boolean;
}) {
  const [warehouse, setWarehouse] = useState<number | undefined>(warehouses[0]?.id);
  const [date, setDate] = useState(new Date().toISOString().slice(0, 10));
  const [direction, setDirection] = useState<AdjustmentDirection>('in');
  const [reason, setReason] = useState<AdjustmentReason>('');
  const [notes, setNotes] = useState('');
  const [items, setItems] = useState<AdjustmentItem[]>([{ fabric: fabrics[0]?.id ?? 0, yards: 0, rolls_count: 0 }]);

  const updateItem = (i: number, patch: Partial<AdjustmentItem>) => {
    setItems((rows) => rows.map((r, idx) => (idx === i ? { ...r, ...patch } : r)));
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!warehouse) return;
    onSubmit({
      warehouse,
      date,
      direction,
      reason,
      notes,
      items: items.map((it) => ({ fabric: it.fabric, yards: it.yards, rolls_count: it.rolls_count })),
    });
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div className="grid grid-cols-2 gap-4">
        <div>
          <label className="block text-sm font-medium text-neutral-700 mb-1">المخزن *</label>
          <Select value={warehouse ?? ''} onChange={(e) => setWarehouse(Number(e.target.value))} options={warehouses.map((w) => ({ value: w.id, label: w.name }))} required />
        </div>
        <div>
          <label className="block text-sm font-medium text-neutral-700 mb-1">التاريخ</label>
          <Input type="date" value={date} onChange={(e) => setDate(e.target.value)} required />
        </div>
      </div>
      <div className="grid grid-cols-2 gap-4">
        <div>
          <label className="block text-sm font-medium text-neutral-700 mb-1">نوع التسوية *</label>
          <Select
            value={direction}
            onChange={(e) => setDirection(e.target.value as AdjustmentDirection)}
            options={[
              { value: 'in', label: 'إضافة للمخزون (هالك/زيادة)' },
              { value: 'out', label: 'خصم من المخزون (تلف/نقص)' },
            ]}
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-neutral-700 mb-1">السبب</label>
          <Select
            value={reason}
            onChange={(e) => setReason(e.target.value as AdjustmentReason)}
            options={[
              { value: '', label: 'بدون سبب' },
              { value: 'damage', label: 'تلف' },
              { value: 'loss', label: 'فقد / نقص' },
              { value: 'gain', label: 'زيادة' },
              { value: 'correction', label: 'تصحيح جرد' },
            ]}
          />
        </div>
      </div>

      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <label className="block text-sm font-medium text-neutral-700">الأصناف *</label>
          <Button type="button" variant="subtle" size="sm" onClick={() => setItems((r) => [...r, { fabric: fabrics[0]?.id ?? 0, yards: 0, rolls_count: 0 }])}>
            <Plus size={16} />
            إضافة صنف
          </Button>
        </div>
        {items.map((it, i) => (
          <div key={i} className="grid grid-cols-[1fr_1fr_1fr_auto] gap-2 items-center bg-sand-50 p-2 rounded-xl">
            <Select value={it.fabric} onChange={(e) => updateItem(i, { fabric: Number(e.target.value) })} options={fabrics.map((f) => ({ value: f.id, label: `${f.name} (${f.code})` }))} />
            <Input type="number" min={0} step="0.01" value={it.yards} onChange={(e) => updateItem(i, { yards: Number(e.target.value) })} placeholder="الياردات" required />
            <Input type="number" min={0} value={it.rolls_count} onChange={(e) => updateItem(i, { rolls_count: Number(e.target.value) })} placeholder="لفات" />
            <button type="button" onClick={() => setItems((r) => (r.length > 1 ? r.filter((_, idx) => idx !== i) : r))} className="p-2 rounded-lg text-neutral-400 hover:text-red-500">
              <X size={16} />
            </button>
          </div>
        ))}
      </div>

      <div>
        <label className="block text-sm font-medium text-neutral-700 mb-1">ملاحظات</label>
        <Textarea value={notes} onChange={(e) => setNotes(e.target.value)} rows={2} />
      </div>

      <div className="flex justify-end pt-2">
        <Button type="submit" loading={loading}>حفظ التسوية وتنفيذها</Button>
      </div>
    </form>
  );
}

export default function AdjustmentsPage() {
  const { toast } = useToast();
  const { settings } = useSettings();
  const pageSize = settings?.default_page_size ?? 10;
  const [data, setData] = useState<Paginated<StockAdjustment> | null>(null);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useUrlState('page', 1);
  const [modalOpen, setModalOpen] = useState(false);
  const [formLoading, setFormLoading] = useState(false);
  const [warehouses, setWarehouses] = useState<Warehouse[]>([]);
  const [fabrics, setFabrics] = useState<Fabric[]>([]);

  const fetchData = useCallback(() => {
    let cancelled = false;
    setLoading(true);
    listAdjustments({ page, page_size: pageSize })
      .then((res) => { if (!cancelled) setData(res); })
      .catch((err: any) => { if (!cancelled) toast('error', err.message); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [page, pageSize]);

  useEffect(() => fetchData(), [fetchData]);

  useEffect(() => {
    listWarehouses({ page_size: 100 }).then((r) => setWarehouses(r.results)).catch(() => {});
    listFabrics({ page_size: 100 }).then((r) => setFabrics(r.results)).catch(() => {});
  }, []);

  const totalPages = data ? Math.ceil(data.count / pageSize) : 1;

  const handleCreate = async (d: AdjustmentWrite) => {
    setFormLoading(true);
    try {
      const r = await createAdjustment(d);
      toast('success', `تم تنفيذ التسوية ${r.number}`);
      setModalOpen(false);
      fetchData();
    } catch (err: any) {
      toast('error', err.message);
    } finally {
      setFormLoading(false);
    }
  };

  return (
    <AppShell>
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-xl font-bold text-neutral-800">تسويات المخزون</h1>
            <p className="text-sm text-neutral-500">تلف، فقدان، زيادة، وتصحيحات بهوامش مسجلة</p>
          </div>
          <Button onClick={() => setModalOpen(true)}>
            <Plus size={18} />
            تسوية جديدة
          </Button>
        </div>

        <Card>
          {loading ? (
            <div className="flex justify-center py-12"><Spinner size={32} /></div>
          ) : !data || data.results.length === 0 ? (
            <EmptyState title="لا توجد تسويات" description="سجّل أول تسوية لتصحيح المخزون" />
          ) : (
            <>
              <Table>
                <thead>
                  <tr>
                    <Th>رقم السند</Th>
                    <Th>المخزن</Th>
                    <Th>التاريخ</Th>
                    <Th>النوع</Th>
                    <Th>السبب</Th>
                    <Th>الياردات</Th>
                  </tr>
                </thead>
                <tbody>
                  {data.results.map((a) => (
                    <Tr key={a.id}>
                      <Td><span className="font-mono text-xs bg-sand-100 px-2 py-1 rounded" dir="ltr">{a.number}</span></Td>
                      <Td>{a.warehouse_name}</Td>
                      <Td className="tabular-nums">{a.date}</Td>
                      <Td>
                        <Badge variant={a.direction === 'in' ? 'success' : 'danger'}>
                          {a.direction_label}
                        </Badge>
                      </Td>
                      <Td>{a.reason ? REASON_LABEL[a.reason as AdjustmentReason] : '—'}</Td>
                      <Td className="tabular-nums font-medium">{formatNumber(a.items.reduce((s, it) => s + Number(it.yards), 0))}</Td>
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

      <Modal open={modalOpen} onClose={() => setModalOpen(false)} title="تسوية مخزون جديدة" maxWidth="max-w-3xl">
        <AdjustmentForm warehouses={warehouses} fabrics={fabrics} onSubmit={handleCreate} loading={formLoading} />
      </Modal>
    </AppShell>
  );
}