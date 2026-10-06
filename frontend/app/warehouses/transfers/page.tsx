'use client';

import { useState, useEffect, useCallback } from 'react';
import { useAutoRefresh } from '@/lib/useAutoRefresh';
import Link from 'next/link';
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
import Textarea from '@/components/ui/Textarea';
import { Plus, Send, Check, X, CheckCircle2, Ban, Printer, Eye, SendHorizonal, RotateCcw } from 'lucide-react';
import { StockTransfer, Paginated, Warehouse, Fabric, TransferItem, TransferStatus, Branch, TransferQuantityMode, Employee, SessionEmployee } from '@/types';
import { listTransfers, createTransfer, deleteTransfer, changeTransferStatus, reverseTransfer, TransferWrite } from '@/services/warehouses';
import { listWarehouses } from '@/services/warehouses';
import { listBranches } from '@/services/branches';
import { listFabrics } from '@/services/fabrics';
import { listEmployees } from '@/services/employees';
import { useToast } from '@/components/ui/Toast';
import { useSettings } from '@/components/providers/SettingsProvider';
import { useUrlState } from '@/lib/useUrlState';
import { formatNumber } from '@/lib/format';
import { useAuth } from '@/components/providers/AuthProvider';

const STATUS_VARIANT: Record<TransferStatus, 'success' | 'warning' | 'danger' | 'neutral'> = {
  draft: 'neutral',
  requested: 'warning',
  approved: 'warning',
  rejected: 'danger',
  completed: 'success',
  cancelled: 'danger',
  reversed: 'neutral',
};

type TransferActionType = 'request' | 'approve' | 'reject' | 'complete' | 'cancel' | 'delete' | 'reverse';

/** مسودة الصنف: الأرقام نصوص كما يكتبها المستخدم، حتى لا يظهر «0» في خانة فارغة. */
type TransferDraft = Omit<TransferItem, 'yards' | 'rolls_count'> & { yards: string; rolls_count: string };

function TransferForm({
  warehouses,
  branches,
  fabrics,
  employees,
  sessionEmployee,
  onSubmit,
  loading,
}: {
  warehouses: Warehouse[];
  branches: Branch[];
  fabrics: Fabric[];
  employees: Employee[];
  sessionEmployee: SessionEmployee | null;
  onSubmit: (d: TransferWrite) => void;
  loading: boolean;
}) {
  const [sourceType, setSourceType] = useState<'warehouse' | 'branch'>('warehouse');
  const [from, setFrom] = useState<number | undefined>();
  const [fromBranch, setFromBranch] = useState<number | undefined>();
  const [destType, setDestType] = useState<'warehouse' | 'branch'>('warehouse');
  const [toWarehouse, setToWarehouse] = useState<number | undefined>();
  const [toBranch, setToBranch] = useState<number | undefined>();
  const [date, setDate] = useState(new Date().toISOString().slice(0, 10));
  const [requestedByEmployee, setRequestedByEmployee] = useState<number | undefined>();
  const [notes, setNotes] = useState('');
  const [items, setItems] = useState<TransferDraft[]>([{ fabric: fabrics[0]?.id ?? 0, yards: '', rolls_count: '', quantity_mode: 'yard' }]);
  const canChooseRequester = sessionEmployee?.role === 'admin' || sessionEmployee?.role === 'supervisor';

  const physicalWarehouses = warehouses.filter((w) => !w.is_branch_stock);
  const eligibleDestinationWarehouses = physicalWarehouses.filter(
    (w) => (sourceType !== 'warehouse' || w.id !== from) && (sourceType !== 'branch' || w.branch !== fromBranch),
  );
  const eligibleDestinationBranches = branches.filter((b) => sourceType !== 'branch' || b.id !== fromBranch);

  useEffect(() => {
    if (!from && physicalWarehouses.length) setFrom(physicalWarehouses[0].id);
    if (!fromBranch && branches.length) setFromBranch(branches[0].id);
  }, [physicalWarehouses, branches, from, fromBranch]);

  useEffect(() => {
    if (destType === 'warehouse') {
      if (!eligibleDestinationWarehouses.some((w) => w.id === toWarehouse)) {
        setToWarehouse(eligibleDestinationWarehouses[0]?.id);
      }
    } else if (!eligibleDestinationBranches.some((b) => b.id === toBranch)) {
      setToBranch(eligibleDestinationBranches[0]?.id);
    }
  }, [destType, eligibleDestinationWarehouses, eligibleDestinationBranches, toWarehouse, toBranch]);

  useEffect(() => {
    if (sessionEmployee?.id) setRequestedByEmployee(sessionEmployee.id);
  }, [sessionEmployee?.id]);

  const updateItem = (i: number, patch: Partial<TransferDraft>) => {
    setItems((rows) => rows.map((r, idx) => (idx === i ? { ...r, ...patch } : r)));
  };

  const addItem = () =>
    setItems((r) => [...r, { fabric: fabrics[0]?.id ?? 0, yards: '', rolls_count: '', quantity_mode: 'yard' }]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if ((sourceType === 'warehouse' && !from) || (sourceType === 'branch' && !fromBranch)) return;
    const payload: TransferWrite = {
      date,
      notes,
      items: items.map((it) =>
        it.quantity_mode === 'roll'
          ? { fabric: it.fabric, rolls_count: Number(it.rolls_count) || 0, quantity_mode: 'roll' }
          : { fabric: it.fabric, yards: Number(it.yards) || 0, rolls_count: Number(it.rolls_count) || 0, quantity_mode: 'yard' }
      ),
    };
    if (sourceType === 'branch') {
      payload.from_branch = fromBranch;
      const branchWarehouse = warehouses.find((w) => w.is_branch_stock && w.branch === fromBranch);
      if (branchWarehouse) payload.from_warehouse = branchWarehouse.id;
    }
    else payload.from_warehouse = from;
    if (canChooseRequester && requestedByEmployee) {
      payload.requested_by_employee = requestedByEmployee;
    }
    if (destType === 'branch') {
      if (!toBranch || !eligibleDestinationBranches.some((b) => b.id === toBranch)) return;
      payload.to_branch = toBranch;
    } else {
      if (!toWarehouse || !eligibleDestinationWarehouses.some((w) => w.id === toWarehouse)) return;
      payload.to_warehouse = toWarehouse;
    }
    onSubmit(payload);
  };

  const destOptions = destType === 'warehouse'
    ? eligibleDestinationWarehouses.map((w) => ({ value: w.id, label: w.name }))
    : eligibleDestinationBranches.map((b) => ({ value: b.id, label: b.name }));

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div className="grid grid-cols-2 gap-4">
        <div>
          <label className="block text-sm font-medium text-neutral-700 mb-1">نوع المصدر *</label>
          <Select
            value={sourceType}
            onChange={(e) => setSourceType(e.target.value as 'warehouse' | 'branch')}
            options={[{ value: 'warehouse', label: 'مخزن' }, { value: 'branch', label: 'فرع' }]}
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-neutral-700 mb-1">نوع الوجهة *</label>
          <Select
            value={destType}
            onChange={(e) => setDestType(e.target.value as 'warehouse' | 'branch')}
            options={[
              { value: 'warehouse', label: 'مخزن' },
              { value: 'branch', label: 'فرع' },
            ]}
          />
        </div>
      </div>
      <div>
        <label className="block text-sm font-medium text-neutral-700 mb-1">{sourceType === 'branch' ? 'الفرع المُرسِل *' : 'المخزن المُرسِل *'}</label>
        <Select
          value={sourceType === 'branch' ? (fromBranch ?? '') : (from ?? '')}
          onChange={(e) => sourceType === 'branch' ? setFromBranch(Number(e.target.value)) : setFrom(Number(e.target.value))}
          options={sourceType === 'branch' ? branches.map((b) => ({ value: b.id, label: b.name })) : warehouses.filter((w) => !w.is_branch_stock).map((w) => ({ value: w.id, label: w.name }))}
          required
        />
      </div>
      <div className="grid grid-cols-2 gap-4">
        <div>
          <label className="block text-sm font-medium text-neutral-700 mb-1">
            {destType === 'warehouse' ? 'المخزن المُستقبِل *' : 'الفرع المُستقبِل *'}
          </label>
          <Select
            value={destType === 'warehouse' ? (toWarehouse ?? '') : (toBranch ?? '')}
            onChange={(e) => (destType === 'warehouse' ? setToWarehouse(Number(e.target.value)) : setToBranch(Number(e.target.value)))}
            options={destOptions}
            placeholder="اختر الوجهة"
            required
          />
          {destOptions.length === 0 && <p className="mt-1 text-xs text-red-600">لا توجد وجهة متاحة غير المصدر؛ اختر نوع وجهة أو مصدراً آخر.</p>}
        </div>
        <div>
          <label className="block text-sm font-medium text-neutral-700 mb-1">تاريخ التحويل</label>
          <Input type="date" value={date} onChange={(e) => setDate(e.target.value)} required />
        </div>
      </div>
      <div>
        <label className="block text-sm font-medium text-neutral-700 mb-1">مقدّم الطلب</label>
        {canChooseRequester ? (
          <Select
            value={requestedByEmployee ?? ''}
            onChange={(e) => setRequestedByEmployee(Number(e.target.value))}
            options={employees.map((employee) => ({ value: employee.id, label: employee.name }))}
            required
          />
        ) : (
          <Input value={sessionEmployee?.name ?? ''} readOnly placeholder="يُحدد من حساب تسجيل الدخول" />
        )}
      </div>

      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <label className="block text-sm font-medium text-neutral-700">الأصناف *</label>
          <Button type="button" variant="subtle" size="sm" onClick={addItem}>
            <Plus size={16} />
            إضافة صنف
          </Button>
        </div>
        {items.map((it, i) => (
          <div key={i} className="grid grid-cols-[1.5fr_1fr_1fr_auto] gap-2 items-center bg-sand-50 p-2 rounded-xl">
            <Select value={it.fabric} onChange={(e) => updateItem(i, { fabric: Number(e.target.value) })} options={fabrics.map((f) => ({ value: f.id, label: `${f.name} (${f.code})` }))} />
            <Select
              value={it.quantity_mode ?? 'yard'}
              onChange={(e) => updateItem(i, { quantity_mode: e.target.value as TransferQuantityMode })}
              options={[
                { value: 'yard', label: 'بالياردات' },
                { value: 'roll', label: 'بالطاقات' },
              ]}
            />
            {it.quantity_mode === 'roll' ? (
              <Input
                type="number"
                numeric="int"
                min={1}
                value={it.rolls_count}
                onChange={(e) => updateItem(i, { rolls_count: e.target.value })}
                placeholder="عدد الطاقات"
                required
              />
            ) : (
              <div className="flex gap-2">
                <Input
                  type="number"
                  min={0}
                  step="0.01"
                  value={it.yards}
                  onChange={(e) => updateItem(i, { yards: e.target.value })}
                  placeholder="الياردات"
                  required
                />
                <Input
                  type="number"
                  numeric="int"
                  min={0}
                  value={it.rolls_count}
                  onChange={(e) => updateItem(i, { rolls_count: e.target.value })}
                  placeholder="طاقات"
                  className="w-20"
                />
              </div>
            )}
            <button type="button" onClick={() => setItems((r) => (r.length > 1 ? r.filter((_, idx) => idx !== i) : r))} className="p-2 rounded-lg text-neutral-400 hover:text-red-500">
              <X size={16} />
            </button>
          </div>
        ))}
        {items.some((it) => it.quantity_mode === 'roll') && (
          <p className="text-xs text-neutral-500">وضع «بالطاقات» ينقل طاقات كاملة (أقدم طاقة أولاً) بحسب رصيد المخزن.</p>
        )}
      </div>

      <div>
        <label className="block text-sm font-medium text-neutral-700 mb-1">ملاحظات</label>
        <Textarea value={notes} onChange={(e) => setNotes(e.target.value)} rows={2} />
      </div>

      <div className="flex justify-end pt-2">
        <Button type="submit" loading={loading}>حفظ التحويل</Button>
      </div>
    </form>
  );
}

export default function TransfersPage() {
  const { toast } = useToast();
  const { session } = useAuth();
  const { settings } = useSettings();
  const pageSize = settings?.default_page_size ?? 10;
  const [data, setData] = useState<Paginated<StockTransfer> | null>(null);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useUrlState('page', 1);
  const [modalOpen, setModalOpen] = useState(false);
  const [formLoading, setFormLoading] = useState(false);
  const [warehouses, setWarehouses] = useState<Warehouse[]>([]);
  const [branches, setBranches] = useState<Branch[]>([]);
  const [fabrics, setFabrics] = useState<Fabric[]>([]);
  const [employees, setEmployees] = useState<Employee[]>([]);
  const [action, setAction] = useState<{ transfer: StockTransfer; type: TransferActionType } | null>(null);
  const [actionLoading, setActionLoading] = useState(false);
  const [viewing, setViewing] = useState<StockTransfer | null>(null);
  const [reasonInput, setReasonInput] = useState('');

  const fetchData = useCallback(() => {
    let cancelled = false;
    setLoading(true);
    listTransfers({ page, page_size: pageSize })
      .then((res) => { if (!cancelled) setData(res); })
      .catch((err: any) => { if (!cancelled) toast('error', err.message); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [page, pageSize]);

  useEffect(() => fetchData(), [fetchData]);
  useAutoRefresh(fetchData);

  useEffect(() => {
    listWarehouses({ page_size: 100 }).then((r) => setWarehouses(r.results)).catch(() => {});
    listBranches({ page_size: 100 }).then((r) => setBranches(r.results)).catch(() => {});
    listFabrics({ page_size: 100 }).then((r) => setFabrics(r.results)).catch(() => {});
  }, []);

  useEffect(() => {
    if (session?.employee.role === 'admin' || session?.employee.role === 'supervisor') {
      listEmployees({ page_size: 200 }).then((r) => setEmployees(r.results)).catch((err: any) => toast('error', err.message));
    }
  }, [session?.employee.role, toast]);

  const totalPages = data ? Math.ceil(data.count / pageSize) : 1;

  const handleCreate = async (d: TransferWrite) => {
    setFormLoading(true);
    try {
      const r = await createTransfer(d);
      toast('success', `تم إنشاء التحويل ${r.number}`);
      setModalOpen(false);
      fetchData();
    } catch (err: any) {
      toast('error', err.message);
    } finally {
      setFormLoading(false);
    }
  };

  const runAction = async () => {
    if (!action) return;
    if (['reject', 'cancel', 'delete', 'reverse'].includes(action.type) && !reasonInput.trim()) {
      toast('error', 'اكتب السبب أولاً لتوثيقه في سجل التحويل');
      return;
    }
    setActionLoading(true);
    try {
      if (action.type === 'delete') {
        await deleteTransfer(action.transfer.id, reasonInput.trim());
        toast('success', 'تمت أرشفة التحويل مع حفظ سجله');
        setAction(null);
        setReasonInput('');
        fetchData();
        return;
      }
      if (action.type === 'reverse') {
        const r = await reverseTransfer(action.transfer.id, reasonInput.trim());
        toast('success', `تم: ${r.status_label}`);
        setAction(null);
        setReasonInput('');
        fetchData();
        if (viewing) setViewing((v) => (v && v.id === r.id ? r : v));
        return;
      }
      const payload: Record<string, string> = {};
      if (action.type === 'reject' || action.type === 'cancel') payload.reason = reasonInput.trim();
      const r = await changeTransferStatus(action.transfer.id, action.type, payload);
      toast('success', `تم: ${r.status_label}`);
      setAction(null);
      setReasonInput('');
      fetchData();
      if (viewing) setViewing((v) => (v && v.id === r.id ? r : v));
    } catch (err: any) {
      toast('error', err.message);
    } finally {
      setActionLoading(false);
    }
  };

  const ACTION_META: Record<TransferActionType, { title: string; message: string; confirm: string }> = {
    request: { title: 'تقديم طلب التحويل', message: 'سيتم إرسال طلب التحويل للموافقة.', confirm: 'تقديم الطلب' },
    approve: { title: 'الموافقة على التحويل', message: 'سيتم اعتماد طلب التحويل ليصبح جاهزاً للتنفيذ.', confirm: 'اعتماد' },
    reject: { title: 'رفض التحويل', message: 'سيتم رفض طلب التحويل وإعادته لحالة المرفوض.', confirm: 'رفض' },
    complete: { title: 'تنفيذ التحويل', message: 'سيتم خصم البضاعة من المصدر وإضافتها للمُستقبِل مع تسجيل الحركات.', confirm: 'تنفيذ التحويل' },
    cancel: { title: 'إلغاء التحويل', message: 'سيتم إلغاء التحويل دون أي أثر على المخزون.', confirm: 'إلغاء' },
    delete: { title: 'أرشفة التحويل', message: 'سيُلغى التحويل وتُحفظ تفاصيله في السجل دون أثر على المخزون.', confirm: 'أرشفة' },
    reverse: { title: 'عكس التحويل المنفذ', message: 'سيُعاد المخزون إلى المصدر الأصلي بحركة موثقة. يلزم توفر الكمية في الوجهة الحالية.', confirm: 'عكس التحويل' },
  };

  const runRequestWithName = () => runAction();

  return (
    <AppShell>
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-xl font-bold text-neutral-800">التحويلات بين المخازن</h1>
            <p className="text-sm text-neutral-500">دورة عمل: طلب ← موافقة ← تنفيذ، مع سند تحويل قابل للطباعة</p>
          </div>
          <Button onClick={() => setModalOpen(true)}>
            <Plus size={18} />
            تحويل جديد
          </Button>
        </div>

        <Card>
          {loading ? (
            <div className="flex justify-center py-12"><Spinner size={32} /></div>
          ) : !data || data.results.length === 0 ? (
            <EmptyState title="لا توجد تحويلات" description="ابدأ بإنشاء أول تحويل بين المخازن" />
          ) : (
            <>
              <Table>
                <thead>
                  <tr>
                    <Th>رقم السند</Th>
                    <Th>من</Th>
                    <Th>إلى</Th>
                    <Th>التاريخ</Th>
                    <Th>الياردات</Th>
                    <Th>الحالة</Th>
                    <Th>إجراءات</Th>
                  </tr>
                </thead>
                <tbody>
                  {data.results.map((t) => (
                    <Tr key={t.id}>
                      <Td><span className="font-mono text-xs bg-sand-100 px-2 py-1 rounded" dir="ltr">{t.number}</span></Td>
                      <Td>{t.source_name || t.from_warehouse_name}</Td>
                      <Td>
                        {t.dest_type === 'branch' ? (
                          <span className="inline-flex items-center gap-1">
                            <span className="text-brand-600">فرع:</span>
                            {t.dest_name}
                          </span>
                        ) : (
                          t.dest_name
                        )}
                      </Td>
                      <Td className="tabular-nums">{t.date}</Td>
                      <Td className="tabular-nums font-medium">{formatNumber(t.total_yards)}</Td>
                      <Td><Badge variant={STATUS_VARIANT[t.status]}>{t.status_label}</Badge></Td>
                      <Td>
                        <div className="flex flex-wrap gap-1 items-center">
                          <button onClick={() => setViewing(t)} className="p-2 rounded-lg text-neutral-500 hover:bg-brand-50 hover:text-brand-600" title="عرض">
                            <Eye size={16} />
                          </button>
                          {t.status === 'draft' && (
                            <>
                              <button onClick={() => setAction({ transfer: t, type: 'request' })} className="p-2 rounded-lg text-brand-600 hover:bg-brand-50" title="تقديم الطلب">
                                <Send size={16} />
                              </button>
                              <button onClick={() => setAction({ transfer: t, type: 'delete' })} className="p-2 rounded-lg text-neutral-500 hover:bg-red-50 hover:text-red-600" title="حذف">
                                <X size={16} />
                              </button>
                            </>
                          )}
                          {t.status === 'requested' && (
                            <>
                              <button onClick={() => setAction({ transfer: t, type: 'approve' })} className="p-2 rounded-lg text-emerald-600 hover:bg-emerald-50" title="اعتماد">
                                <Check size={16} />
                              </button>
                              <button onClick={() => setAction({ transfer: t, type: 'reject' })} className="p-2 rounded-lg text-red-600 hover:bg-red-50" title="رفض">
                                <Ban size={16} />
                              </button>
                            </>
                          )}
                          {t.status === 'approved' && (
                            <button onClick={() => setAction({ transfer: t, type: 'complete' })} className="p-2 rounded-lg text-brand-600 hover:bg-brand-50" title="تنفيذ">
                              <CheckCircle2 size={16} />
                            </button>
                          )}
                          {t.status === 'rejected' && (
                            <button onClick={() => setAction({ transfer: t, type: 'request' })} className="p-2 rounded-lg text-brand-600 hover:bg-brand-50" title="إعادة الطلب">
                              <SendHorizonal size={16} />
                            </button>
                          )}
                          {t.status === 'completed' && (
                            <>
                              <Link href={`/warehouses/transfers/print/${t.id}`} target="_blank">
                                <button className="p-2 rounded-lg text-neutral-500 hover:bg-brand-50 hover:text-brand-600" title="طباعة السند">
                                  <Printer size={16} />
                                </button>
                              </Link>
                              <button onClick={() => setAction({ transfer: t, type: 'reverse' })} className="p-2 rounded-lg text-red-600 hover:bg-red-50" title="عكس التحويل">
                                <RotateCcw size={16} />
                              </button>
                            </>
                          )}
                          {(t.status === 'requested' || t.status === 'approved') && (
                            <button onClick={() => setAction({ transfer: t, type: 'cancel' })} className="p-2 rounded-lg text-neutral-400 hover:text-red-600" title="إلغاء">
                              <Ban size={14} />
                            </button>
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

      <Modal open={modalOpen} onClose={() => setModalOpen(false)} title="تحويل جديد بين المخازن" maxWidth="max-w-3xl">
        <TransferForm
          warehouses={warehouses}
          branches={branches}
          fabrics={fabrics}
          employees={employees}
          sessionEmployee={session?.employee ?? null}
          onSubmit={handleCreate}
          loading={formLoading}
        />
      </Modal>

      <Modal open={!!viewing} onClose={() => setViewing(null)} title={viewing ? `سند التحويل ${viewing.number}` : ''} maxWidth="max-w-2xl">
        {viewing && (
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <Badge variant={STATUS_VARIANT[viewing.status]}>{viewing.status_label}</Badge>
              <div className="flex gap-2">
                {viewing.status === 'completed' && (
                  <Link href={`/warehouses/transfers/print/${viewing.id}`} target="_blank">
                    <Button variant="secondary" size="sm">
                      <Printer size={16} />
                      طباعة السند
                    </Button>
                  </Link>
                )}
              </div>
            </div>
            <div className="grid grid-cols-2 gap-3 text-sm">
              <div className="bg-sand-50 rounded-xl p-3">
                <p className="text-neutral-500 text-xs mb-1">{viewing.source_type === 'branch' ? 'الفرع المُرسِل' : 'المخزن المُرسِل'}</p>
                <p className="font-semibold">{viewing.source_name || viewing.from_warehouse_name}</p>
              </div>
              <div className="bg-sand-50 rounded-xl p-3">
                <p className="text-neutral-500 text-xs mb-1">المُستقبِل</p>
                <p className="font-semibold">
                  {viewing.dest_type === 'branch' ? (
                    <>
                      <span className="text-brand-600">فرع: </span>
                      {viewing.dest_name}
                    </>
                  ) : (
                    viewing.dest_name
                  )}
                </p>
              </div>
            </div>
            {(viewing.rejection_reason || viewing.cancellation_reason || viewing.reversal_reason) && (
              <div className="space-y-2 text-sm">
                {viewing.rejection_reason && <p className="rounded-lg bg-red-50 p-3">سبب الرفض: {viewing.rejection_reason}{viewing.rejected_by && ` — ${viewing.rejected_by}`}</p>}
                {viewing.cancellation_reason && <p className="rounded-lg bg-neutral-100 p-3">سبب الإلغاء: {viewing.cancellation_reason}{viewing.cancelled_by && ` — ${viewing.cancelled_by}`}</p>}
                {viewing.reversal_reason && <p className="rounded-lg bg-amber-50 p-3">سبب العكس: {viewing.reversal_reason}{viewing.reversed_by && ` — ${viewing.reversed_by}`}</p>}
              </div>
            )}
            <div className="text-sm text-neutral-500">
              التاريخ: <b className="tabular-nums">{viewing.date}</b>
              {viewing.requested_by && <span className="mr-4">مقدّم الطلب: {viewing.requested_by}</span>}
              {viewing.approved_by && <span className="mr-4">الموافِق: {viewing.approved_by}</span>}
            </div>
            <Table>
              <thead>
                <tr>
                  <Th>القماش</Th>
                  <Th>الكمية</Th>
                </tr>
              </thead>
              <tbody>
                {viewing.items.map((it) => (
                  <Tr key={it.id ?? it.fabric}>
                    <Td>{it.fabric_name}</Td>
                    <Td className="tabular-nums">
                      {it.quantity_mode === 'roll' ? (
                        <>
                          {it.rolls_count} لفافات
                          {it.yards > 0 && <span className="text-neutral-400 mr-2">({formatNumber(it.yards)} ياردة)</span>}
                        </>
                      ) : (
                        <>{formatNumber(it.yards)} ياردة</>
                      )}
                    </Td>
                  </Tr>
                ))}
              </tbody>
            </Table>
            {viewing.notes && <p className="text-sm text-neutral-600 bg-sand-50 rounded-xl p-3">{viewing.notes}</p>}
          </div>
        )}
      </Modal>

      {action && (
        <ConfirmDialog
          open={!!action}
          title={ACTION_META[action.type].title}
          message={
            <>
              {ACTION_META[action.type].message}
              {(['reject', 'cancel', 'delete', 'reverse'] as TransferActionType[]).includes(action.type) && (
                <div className="mt-3">
                  <Textarea value={reasonInput} onChange={(e) => setReasonInput(e.target.value)} rows={3} placeholder="اكتب السبب لتوثيقه في سجل التحويل" required />
                </div>
              )}
            </>
          }
          confirmLabel={ACTION_META[action.type].confirm}
          loading={actionLoading}
          onConfirm={runRequestWithName}
          onClose={() => { setAction(null); setReasonInput(''); }}
        />
      )}
    </AppShell>
  );
}
