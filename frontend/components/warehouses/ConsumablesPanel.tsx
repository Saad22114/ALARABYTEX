'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import AppShell from '@/components/layout/AppShell';
import Card from '@/components/ui/Card';
import Button from '@/components/ui/Button';
import Input from '@/components/ui/Input';
import Select from '@/components/ui/Select';
import Table, { Td, Th, Tr } from '@/components/ui/Table';
import Badge from '@/components/ui/Badge';
import Spinner from '@/components/ui/Spinner';
import EmptyState from '@/components/ui/EmptyState';
import { useToast } from '@/components/ui/Toast';
import { useAuth } from '@/components/providers/AuthProvider';
import { Branch, Fabric } from '@/types';
import { listBranches } from '@/services/branches';
import { listFabrics } from '@/services/fabrics';
import {
  approveConsumableRequest,
  getConsumableAvailability,
  ConsumableRequest,
  createConsumableRequest,
  listConsumableRequests,
  rejectConsumableRequest,
} from '@/services/warehouses';
import { formatDate, formatNumber } from '@/lib/format';
import { toISODate } from '@/components/ui/DateRangeToolbar';
import { Check, Clock3, PackageMinus, X } from 'lucide-react';

export default function ConsumablesPanel() {
  const { toast } = useToast();
  const { session } = useAuth();
  const employee = session?.employee;
  const isManager = employee?.role === 'admin' || employee?.role === 'supervisor';
  const canView = Boolean(employee?.permissions?.consumables?.view);
  const canCreate = Boolean(employee?.permissions?.consumables?.create);
  const [branches, setBranches] = useState<Branch[]>([]);
  const [fabrics, setFabrics] = useState<Fabric[]>([]);
  const [requests, setRequests] = useState<ConsumableRequest[]>([]);
  const [branch, setBranch] = useState('');
  const [fabric, setFabric] = useState('');
  const [yards, setYards] = useState('');
  const [stockByFabric, setStockByFabric] = useState<Record<number, number>>({});
  const [checkingAvailability, setCheckingAvailability] = useState(false);
  const [date, setDate] = useState(toISODate(new Date()));
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [acting, setActing] = useState<number | null>(null);
  const availableYards = fabric ? stockByFabric[Number(fabric)] ?? null : null;
  const requestedYards = Number(yards) || 0;
  const remainingAfterRequest = availableYards === null ? null : availableYards - requestedYards;

  const load = useCallback(async () => {
    if (!employee || !canView) return;
    setLoading(true);
    try {
      const result = await listConsumableRequests({ page_size: 200 });
      setRequests(result.results);
    } catch (error: any) {
      toast('error', error?.message || 'تعذر تحميل طلبات المستهلكات');
    } finally {
      setLoading(false);
    }
  }, [employee, canView, toast]);

  useEffect(() => {
    if (!employee || !canView) return;
    let cancelled = false;
    Promise.all([
      listBranches({ page_size: 200 }),
      listFabrics({ page_size: 500 }),
    ]).then(([branchResult, fabricResult]) => {
      if (cancelled) return;
      setBranches(branchResult.results.filter((item) => item.is_active));
      setFabrics(fabricResult.results.filter((item) => item.is_active));
      if (employee.branch) setBranch(String(employee.branch));
    }).catch((error: any) => {
      if (!cancelled) toast('error', error?.message || 'تعذر تحميل الفروع والأقمشة');
    });
    return () => { cancelled = true; };
  }, [employee, canView, toast]);

  useEffect(() => { load(); }, [load]);

  useEffect(() => {
    if (!branch || !canView) {
      setStockByFabric({});
      return;
    }
    let cancelled = false;
    setCheckingAvailability(true);
    setStockByFabric({});
    getConsumableAvailability({ branch: Number(branch) })
      .then((result) => {
        if (!cancelled) setStockByFabric(Object.fromEntries(result.items.map((item) => [item.fabric, Number(item.available_yards)])));
      })
      .catch((error: any) => {
        if (!cancelled) {
          setStockByFabric({});
          toast('error', error?.message || 'تعذر تحميل أقمشة الفرع المتاحة');
        }
      })
      .finally(() => { if (!cancelled) setCheckingAvailability(false); });
    return () => { cancelled = true; };
  }, [branch, canView, toast]);

  const pendingCount = useMemo(() => requests.filter((item) => item.status === 'requested').length, [requests]);

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!branch || !fabric || Number(yards) <= 0 || !date) {
      toast('error', 'اختر الفرع والقماش والكمية والتاريخ بصورة صحيحة');
      return;
    }
    setSaving(true);
    try {
      const availability = await getConsumableAvailability({ branch: Number(branch), fabric: Number(fabric) });
      const available = Number(availability.available_yards);
      setStockByFabric((current) => ({ ...current, [Number(fabric)]: available }));
      if (Number(yards) > available) {
        throw new Error(`الكمية المطلوبة أكبر من المتاح في ${availability.warehouse_name}. المتاح ${formatNumber(available)} ياردة.`);
      }
      await createConsumableRequest({ branch: Number(branch), fabric: Number(fabric), yards: Number(yards), date });
      toast('success', 'تم تسجيل الطلب، ولن يُخصم المخزون حتى موافقة المدير');
      try {
        const updatedAvailability = await getConsumableAvailability({ branch: Number(branch) });
        setStockByFabric(Object.fromEntries(updatedAvailability.items.map((item) => [item.fabric, Number(item.available_yards)])));
      } catch { /* تسجيل الطلب تم؛ تحديث القائمة الإضافي لا يغيّر نجاحه. */ }
      setFabric('');
      setYards('');
      await load();
    } catch (error: any) {
      toast('error', error?.message || 'تعذر تسجيل طلب المستهلكات');
    } finally {
      setSaving(false);
    }
  };

  const decide = async (item: ConsumableRequest, approve: boolean) => {
    setActing(item.id);
    try {
      if (approve) await approveConsumableRequest(item.id);
      else await rejectConsumableRequest(item.id);
      toast('success', approve ? 'تم اعتماد الطلب وخصم الكمية من المخزون' : 'تم رفض الطلب دون خصم المخزون');
      await load();
    } catch (error: any) {
      // قد يفشل الرد بعد اكتمال المعاملة في الخادم؛ أعد قراءة الحالة قبل
      // عرض الخطأ حتى لا نُظهر اعتماداً ناجحاً على أنه فشل.
      try {
        const latest = await listConsumableRequests({ page_size: 200 });
        setRequests(latest.results);
        const saved = latest.results.find((request) => request.id === item.id);
        if (saved?.status === (approve ? 'approved' : 'rejected')) {
          toast('success', approve ? 'تم اعتماد الطلب وخصم الكمية من المخزون' : 'تم رفض الطلب');
          return;
        }
      } catch { /* نعتمد رسالة العملية الأصلية إذا تعذر تحديث الحالة. */ }
      toast('error', error?.message || 'تعذر تنفيذ القرار');
    } finally {
      setActing(null);
    }
  };

  return (
      <div className="space-y-5">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h1 className="flex items-center gap-2 text-xl font-bold text-neutral-900"><PackageMinus className="text-orange-600" />مستهلكات المخزون</h1>
            <p className="mt-1 text-sm text-neutral-500">سجّل القماش المستخدم؛ لا ينقص المخزون إلا بعد اعتماد المدير.</p>
          </div>
          <div className="inline-flex items-center gap-2 rounded-xl border border-amber-200 bg-amber-50 px-3 py-2 text-sm font-semibold text-amber-800">
            <Clock3 size={16} />طلبات بانتظار الاعتماد: {pendingCount}
          </div>
        </div>

        {!canView ? (
          <Card><p className="py-6 text-center text-sm text-neutral-600">لا تملك صلاحية عرض قسم المستهلكات.</p></Card>
        ) : (
          <>
            {canCreate && (
              <Card>
                <form onSubmit={submit} className="space-y-4">
                  <h2 className="font-bold text-neutral-800">تسجيل استهلاك جديد</h2>
                  <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
                    <Select label="الفرع" value={branch} onChange={(event) => { setBranch(event.target.value); setFabric(''); setYards(''); setStockByFabric({}); }} options={branches.map((item) => ({ value: item.id, label: item.name }))} placeholder="اختر الفرع" required />
                    <Select label="القماش" value={fabric} onChange={(event) => { setFabric(event.target.value); setYards(''); }} options={fabrics.filter((item) => (stockByFabric[item.id] || 0) > 0).map((item) => ({ value: item.id, label: `${item.name} (${item.code})` }))} placeholder={checkingAvailability ? 'جارٍ تحميل أقمشة الفرع…' : branch ? 'اختر قماشًا متوفرًا' : 'اختر الفرع أولًا'} required disabled={!branch || checkingAvailability} />
                    <div>
                      <Input label="الكمية المستهلكة (ياردة)" type="number" min="0.01" step="0.01" value={yards} onChange={(event) => setYards(event.target.value)} required />
                      {branch && fabric && availableYards !== null && <div className="mt-1 space-y-0.5 text-xs" aria-live="polite"><p className="font-semibold text-emerald-700 dark:text-emerald-400">الموجود في الفرع: {formatNumber(availableYards)} ياردة</p>{requestedYards > 0 && <p className={`font-semibold ${remainingAfterRequest! < 0 ? 'text-rose-600 dark:text-rose-400' : 'text-emerald-700 dark:text-emerald-400'}`}>{remainingAfterRequest! < 0 ? `الكمية تتجاوز الموجود بـ ${formatNumber(Math.abs(remainingAfterRequest!))} ياردة` : `الرصيد بعد الخصم: ${formatNumber(remainingAfterRequest!)} ياردة`}</p>}</div>}
                    </div>
                    <Input label="تاريخ الاستهلاك" type="date" value={date} onChange={(event) => setDate(event.target.value)} required />
                  </div>
                  {branch && !checkingAvailability && Object.keys(stockByFabric).length === 0 && <p className="text-xs font-medium text-amber-700 dark:text-amber-300">لا توجد أقمشة برصيد متاح في هذا الفرع.</p>}
                  <div className="flex flex-wrap items-center justify-between gap-3">
                    <p className="text-xs text-neutral-500">سيُخصم الرصيد من مخزن الفرع عند الموافقة فقط، ويُسجّل في حركة المخزون.</p>
                    <Button type="submit" loading={saving} disabled={checkingAvailability || availableYards === null || requestedYards > availableYards}><PackageMinus size={17} />إرسال للموافقة</Button>
                  </div>
                </form>
              </Card>
            )}

            <Card className="!p-0 overflow-hidden">
              <div className="border-b border-sand-200 px-4 py-3"><h2 className="font-bold text-neutral-800">سجل طلبات المستهلكات</h2></div>
              {loading ? <div className="flex justify-center py-12"><Spinner size={28} /></div> : requests.length === 0 ? (
                <div className="p-5"><EmptyState title="لا توجد طلبات مستهلكات" description="ستظهر هنا الطلبات المسجلة وحالات اعتمادها." /></div>
              ) : (
                <Table>
                  <thead><tr><Th>التاريخ</Th><Th>الفرع</Th><Th>القماش</Th><Th>الكمية</Th><Th>مقدم الطلب</Th><Th>الحالة</Th><Th>اعتماد المدير</Th>{isManager && <Th>الإجراء</Th>}</tr></thead>
                  <tbody>{requests.map((item) => (
                    <Tr key={item.id}>
                      <Td>{formatDate(item.date)}</Td>
                      <Td>{item.branch_name}</Td>
                      <Td className="font-semibold">{item.fabric_name}<span className="ms-1 text-xs text-neutral-400">{item.fabric_code}</span></Td>
                      <Td className="tabular-nums">{formatNumber(item.yards)} ياردة</Td>
                      <Td>{item.requested_by_name}</Td>
                      <Td><Badge variant={item.status === 'approved' ? 'success' : item.status === 'rejected' ? 'danger' : 'warning'}>{item.status_label}</Badge></Td>
                      <Td>{item.approved_by_name || item.decision_note || '—'}</Td>
                      {isManager && <Td>{item.status === 'requested' ? (
                        <div className="flex gap-1">
                          <Button size="sm" onClick={() => decide(item, true)} loading={acting === item.id}><Check size={15} />اعتماد وخصم</Button>
                          <Button size="sm" variant="secondary" onClick={() => decide(item, false)} disabled={acting === item.id}><X size={15} />رفض</Button>
                        </div>
                      ) : '—'}</Td>}
                    </Tr>
                  ))}</tbody>
                </Table>
              )}
            </Card>
          </>
        )}
      </div>
  );
}

