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
import { Plus, ClipboardCheck, CheckCircle2, Ban } from 'lucide-react';
import { StockCount, Paginated, Warehouse, CountItem, CountStatus } from '@/types';
import { listCounts, createCount, getCount, updateCountItems, postCount, cancelCount } from '@/services/warehouses';
import { listWarehouses } from '@/services/warehouses';
import { useToast } from '@/components/ui/Toast';
import { useSettings } from '@/components/providers/SettingsProvider';
import { useUrlState } from '@/lib/useUrlState';
import { formatNumber } from '@/lib/format';

const STATUS_VARIANT: Record<CountStatus, 'success' | 'warning' | 'danger' | 'neutral'> = {
  open: 'warning',
  posted: 'success',
  cancelled: 'neutral',
};

function NewCountForm({
  warehouses,
  onSubmit,
  loading,
}: {
  warehouses: Warehouse[];
  onSubmit: (d: { warehouse: number; date: string }) => void;
  loading: boolean;
}) {
  const [warehouse, setWarehouse] = useState<number | undefined>(warehouses[0]?.id);
  const [date, setDate] = useState(new Date().toISOString().slice(0, 10));
  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        if (!warehouse) return;
        onSubmit({ warehouse, date });
      }}
      className="space-y-4"
    >
      <div>
        <label className="block text-sm font-medium text-neutral-700 mb-1">المخزن *</label>
        <Select value={warehouse ?? ''} onChange={(e) => setWarehouse(Number(e.target.value))} options={warehouses.map((w) => ({ value: w.id, label: w.name }))} required />
      </div>
      <div>
        <label className="block text-sm font-medium text-neutral-700 mb-1">تاريخ الجرد</label>
        <Input type="date" value={date} onChange={(e) => setDate(e.target.value)} required />
      </div>
      <div className="flex justify-end pt-2">
        <Button type="submit" loading={loading}>بدء الجرد</Button>
      </div>
    </form>
  );
}

export default function CountsPage() {
  const { toast } = useToast();
  const { settings } = useSettings();
  const pageSize = settings?.default_page_size ?? 10;
  const [data, setData] = useState<Paginated<StockCount> | null>(null);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useUrlState('page', 1);
  const [modalOpen, setModalOpen] = useState(false);
  const [formLoading, setFormLoading] = useState(false);
  const [warehouses, setWarehouses] = useState<Warehouse[]>([]);
  const [working, setWorking] = useState<StockCount | null>(null);
  const [countedVals, setCountedVals] = useState<Record<number, string>>({});
  const [saveLoading, setSaveLoading] = useState(false);
  const [confirm, setConfirm] = useState<{ count: StockCount; type: 'post' | 'cancel' } | null>(null);
  const [confirmLoading, setConfirmLoading] = useState(false);

  const fetchData = useCallback(() => {
    let cancelled = false;
    setLoading(true);
    listCounts({ page, page_size: pageSize })
      .then((res) => { if (!cancelled) setData(res); })
      .catch((err: any) => { if (!cancelled) toast('error', err.message); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [page, pageSize]);

  useEffect(() => fetchData(), [fetchData]);

  useEffect(() => {
    listWarehouses({ page_size: 100 }).then((r) => setWarehouses(r.results)).catch(() => {});
  }, []);

  const totalPages = data ? Math.ceil(data.count / pageSize) : 1;

  const handleCreate = async (d: { warehouse: number; date: string }) => {
    setFormLoading(true);
    try {
      const r = await createCount(d);
      toast('success', `تم بدء جلسة الجرد ${r.number}`);
      setModalOpen(false);
      fetchData();
    } catch (err: any) {
      toast('error', err.message);
    } finally {
      setFormLoading(false);
    }
  };

  const openWork = async (c: StockCount) => {
    setWorking(c);
    setCountedVals(
      c.items.reduce<Record<string, string>>((acc, it: CountItem) => {
        if (it.counted_yards !== null && it.counted_yards !== undefined) acc[it.fabric] = String(it.counted_yards);
        return acc;
      }, {})
    );
  };

  const updateWorking = async () => {
    if (!working) return;
    setSaveLoading(true);
    try {
      const items = Object.entries(countedVals).map(([fabric, yards]) => ({
        fabric: Number(fabric),
        counted_yards: yards ? Number(yards) : null,
      }));
      await updateCountItems(working.id, items);
      const fresh = await getCount(working.id);
      setWorking(fresh);
      setCountedVals(
        fresh.items.reduce<Record<string, string>>((acc, it: CountItem) => {
          if (it.counted_yards !== null && it.counted_yards !== undefined) acc[it.fabric] = String(it.counted_yards);
          return acc;
        }, {})
      );
      toast('success', 'تم حفظ الرصيد الفعلي');
      fetchData();
    } catch (err: any) {
      toast('error', err.message);
    } finally {
      setSaveLoading(false);
    }
  };

  const runConfirm = async () => {
    if (!confirm) return;
    setConfirmLoading(true);
    try {
      if (confirm.type === 'post') {
        await postCount(confirm.count.id);
        toast('success', 'تم نشر الجرد وتسجيل الفروق');
      } else {
        await cancelCount(confirm.count.id);
        toast('success', 'تم إلغاء جلسة الجرد');
      }
      setConfirm(null);
      setWorking(null);
      fetchData();
    } catch (err: any) {
      toast('error', err.message);
    } finally {
      setConfirmLoading(false);
    }
  };

  return (
    <AppShell>
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-xl font-bold text-neutral-800">جرد المخزون</h1>
            <p className="text-sm text-neutral-500">رصد الأرصدة الدفترية ومقارنتها بالرصيد الفعلي وتسجيل الفروق</p>
          </div>
          <Button onClick={() => setModalOpen(true)}>
            <Plus size={18} />
            جلسة جرد جديدة
          </Button>
        </div>

        <Card>
          {loading ? (
            <div className="flex justify-center py-12"><Spinner size={32} /></div>
          ) : !data || data.results.length === 0 ? (
            <EmptyState title="لا توجد جلسات جرد" description="ابدأ أول جلسة جرد لمخزن" />
          ) : (
            <>
              <Table>
                <thead>
                  <tr>
                    <Th>رقم الجلسة</Th>
                    <Th>المخزن</Th>
                    <Th>التاريخ</Th>
                    <Th>الأصناف</Th>
                    <Th>الحالة</Th>
                    <Th>إجراءات</Th>
                  </tr>
                </thead>
                <tbody>
                  {data.results.map((c) => (
                    <Tr key={c.id}>
                      <Td><span className="font-mono text-xs bg-sand-100 px-2 py-1 rounded" dir="ltr">{c.number}</span></Td>
                      <Td>{c.warehouse_name}</Td>
                      <Td className="tabular-nums">{c.date}</Td>
                      <Td className="tabular-nums">{c.items.length}</Td>
                      <Td><Badge variant={STATUS_VARIANT[c.status]}>{c.status_label}</Badge></Td>
                      <Td>
                        <div className="flex gap-1">
                          {c.status === 'open' && (
                            <>
                              <button onClick={() => openWork(c)} className="p-2 rounded-lg text-brand-600 hover:bg-brand-50" title="إدخال الرصيد الفعلي">
                                <ClipboardCheck size={16} />
                              </button>
                              <button onClick={() => setConfirm({ count: c, type: 'post' })} className="p-2 rounded-lg text-emerald-600 hover:bg-emerald-50" title="نشر الجرد">
                                <CheckCircle2 size={16} />
                              </button>
                              <button onClick={() => setConfirm({ count: c, type: 'cancel' })} className="p-2 rounded-lg text-neutral-500 hover:bg-red-50 hover:text-red-600" title="إلغاء">
                                <Ban size={16} />
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

      <Modal open={modalOpen} onClose={() => setModalOpen(false)} title="بدء جلسة جرد">
        <NewCountForm warehouses={warehouses} onSubmit={handleCreate} loading={formLoading} />
      </Modal>

      <Modal open={!!working} onClose={() => setWorking(null)} title={working ? `جرد ${working.number} - ${working.warehouse_name}` : ''} maxWidth="max-w-3xl">
        {working && (
          <div className="space-y-4">
            <div className="text-sm text-neutral-500 bg-sand-50 rounded-xl p-3">
              أدخل الرصيد الفعلي المقاس لكل قماش. الفرق سيُسجل كحركة «فارق جرد» عند النشر.
            </div>
            <Table>
              <thead>
                <tr>
                  <Th>القماش</Th>
                  <Th>الرصيد الدفتري</Th>
                  <Th>الرصيد الفعلي</Th>
                  <Th>الفرق</Th>
                </tr>
              </thead>
              <tbody>
                {working.items.map((it: CountItem) => {
                  const val = countedVals[it.fabric];
                  const counted = val ? Number(val) : null;
                  const diff = counted !== null ? counted - Number(it.system_yards) : 0;
                  return (
                    <Tr key={it.id}>
                      <Td className="font-medium">{it.fabric_name}</Td>
                      <Td className="tabular-nums">{formatNumber(Number(it.system_yards))}</Td>
                      <Td width={140}>
                        <Input
                          type="number"
                          min={0}
                          step="0.01"
                          value={countedVals[it.fabric] ?? ''}
                          onChange={(e) => setCountedVals((v) => ({ ...v, [it.fabric]: e.target.value }))}
                          placeholder="الفعلي"
                        />
                      </Td>
                      <Td>
                        <span className={`tabular-nums font-medium ${diff > 0 ? 'text-emerald-700' : diff < 0 ? 'text-red-600' : 'text-neutral-400'}`}>
                          {diff ? (diff > 0 ? '+' : '') + formatNumber(diff) : '—'}
                        </span>
                      </Td>
                    </Tr>
                  );
                })}
              </tbody>
            </Table>
            <div className="flex justify-end gap-3">
              <Button variant="secondary" onClick={() => setWorking(null)}>إغلاق</Button>
              <Button onClick={updateWorking} loading={saveLoading}>
                <CheckCircle2 size={16} />
                حفظ الرصيد الفعلي
              </Button>
            </div>
          </div>
        )}
      </Modal>

      <ConfirmDialog
        open={!!confirm}
        title={confirm?.type === 'post' ? 'نشر الجرد' : 'إلغاء الجرد'}
        message={
          confirm?.type === 'post'
            ? 'سيتم تسجيل فروق الجرد كحركات مخزون وإغلاق الجلسة نهائياً.'
            : 'سيتم إلغاء الجلسة دون أي تغيير على المخزون.'
        }
        confirmLabel={confirm?.type === 'post' ? 'نشر الجرد' : 'إلغاء الجلسة'}
        loading={confirmLoading}
        onConfirm={runConfirm}
        onClose={() => setConfirm(null)}
      />
    </AppShell>
  );
}