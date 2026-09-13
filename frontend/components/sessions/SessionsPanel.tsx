'use client';

import { useState, useEffect, useMemo, useCallback } from 'react';
import Card from '@/components/ui/Card';
import Button from '@/components/ui/Button';
import Table, { Th, Td, Tr } from '@/components/ui/Table';
import Select from '@/components/ui/Select';
import Input from '@/components/ui/Input';
import ConfirmDialog from '@/components/ui/ConfirmDialog';
import EmptyState from '@/components/ui/EmptyState';
import Spinner from '@/components/ui/Spinner';
import Badge from '@/components/ui/Badge';
import StatCard from '@/components/ui/StatCard';
import { Plus, Trash2, Pencil, LogIn, CircleDollarSign, RefreshCcw, Users, Package, Layers } from 'lucide-react';
import {
  SaleSession, Employee, Fabric, Branch, SessionSaleItem,
  SessionSaleType, SessionPaymentMethod, SaleSessionSummary, SaleStockResult,
} from '@/types';
import {
  listEmployees,
  listSaleSessions,
  openSaleSession,
  addSessionItem,
  removeSessionItem,
  closeSaleSession,
  getSaleSessionSummary,
} from '@/services/sessions';
import { listFabrics } from '@/services/fabrics';
import { listBranches } from '@/services/branches';
import { getSaleStock } from '@/services/sales';
import SessionItemEditModal from '@/components/sessions/SessionItemEditModal';
import { formatCurrency, formatDate, formatNumber } from '@/lib/format';
import { useToast } from '@/components/ui/Toast';
import Link from 'next/link';

const PAYMENT_OPTIONS = [
  { value: 'cash', label: 'كاش' },
  { value: 'transfer', label: 'تحويل' },
  { value: 'card', label: 'ماكينة' },
];

interface ItemForm {
  fabric: number | null;
  sale_type: SessionSaleType;
  quantity: string;
  unit_price: string;
  payment_method: SessionPaymentMethod;
}

const emptyItemForm = (): ItemForm => ({ fabric: null, sale_type: 'yard', quantity: '', unit_price: '', payment_method: 'cash' });

function elapsedText(minutes: number | null): string {
  if (minutes == null) return '';
  const m = Math.max(0, minutes);
  if (m < 60) return `منذ ${formatNumber(m)} دقيقة`;
  const h = Math.floor(m / 60);
  const r = m % 60;
  return r === 0 ? `منذ ${formatNumber(h)} ساعة` : `منذ ${formatNumber(h)} ساعة و ${formatNumber(r)} دقيقة`;
}

export default function SessionsPanel({ onChanged }: { onChanged?: () => void }) {
  const { toast } = useToast();

  const [employees, setEmployees] = useState<Employee[]>([]);
  const [fabrics, setFabrics] = useState<Fabric[]>([]);
  const [branches, setBranches] = useState<Branch[]>([]);
  const [sessions, setSessions] = useState<SaleSession[]>([]);
  const [summary, setSummary] = useState<SaleSessionSummary | null>(null);
  const [stock, setStock] = useState<SaleStockResult | null>(null);
  const [loading, setLoading] = useState(true);

  const [branchFilter, setBranchFilter] = useState('');
  const [openingEmp, setOpeningEmp] = useState<number | null>(null);
  const [opening, setOpening] = useState(false);
  const [selectedId, setSelectedId] = useState<number | null>(null);

  const [form, setForm] = useState<ItemForm>(emptyItemForm());
  const [adding, setAdding] = useState(false);
  const [refreshing, setRefreshing] = useState(false);

  const [closing, setClosing] = useState<SaleSession | null>(null);
  const [closeLoading, setCloseLoading] = useState(false);
  const [editingItem, setEditingItem] = useState<{ session: SaleSession; item: SessionSaleItem } | null>(null);

  const fetchSessions = useCallback((silent = false) => {
    let cancelled = false;
    if (!silent) setLoading(true);
    listSaleSessions({ status: 'open', page_size: 100, branch: branchFilter || undefined })
      .then((res) => {
        if (cancelled) return;
        setSessions(res.results);
        setSelectedId((cur) => (cur && res.results.some((s) => s.id === cur) ? cur : res.results[0]?.id ?? null));
      })
      .catch((err) => { if (!cancelled) toast('error', err.message); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [branchFilter]);

  const fetchSummary = useCallback(() => {
    let cancelled = false;
    getSaleSessionSummary({ status: 'open', branch: branchFilter || undefined })
      .then((res) => { if (!cancelled) setSummary(res); })
      .catch(() => {});
    return () => { cancelled = true; };
  }, [branchFilter]);

  useEffect(() => fetchSessions(), [fetchSessions]);
  useEffect(() => fetchSummary(), [fetchSummary]);

  useEffect(() => {
    let cancelled = false;
    listEmployees({ page_size: 100 })
      .then((res) => { if (!cancelled) setEmployees(res.results); })
      .catch(() => {});
    listFabrics({ page_size: 100 })
      .then((res) => { if (!cancelled) setFabrics(res.results); })
      .catch(() => {});
    listBranches({ page_size: 100 })
      .then((res) => { if (!cancelled) setBranches(res.results.filter((b) => b.is_active)); })
      .catch(() => {});
    return () => { cancelled = true; };
  }, []);

  useEffect(() => {
    const id = setInterval(() => {
      fetchSessions(true);
      fetchSummary();
    }, 60000);
    return () => clearInterval(id);
  }, [fetchSessions, fetchSummary]);

  const selected = useMemo(() => sessions.find((s) => s.id === selectedId) || null, [sessions, selectedId]);

  useEffect(() => {
    let cancelled = false;
    if (!selected) { setStock(null); return; }
    getSaleStock(selected.branch)
      .then((res) => { if (!cancelled) setStock(res); })
      .catch(() => { if (!cancelled) setStock(null); });
    return () => { cancelled = true; };
  }, [selected]);

  const fabricAutoPrice = () => {
    const fabric = fabrics.find((f) => f.id === form.fabric);
    if (!fabric) return 0;
    const base = Number(fabric.sale_price_yard) || 0;
    if (form.sale_type === 'roll') {
      if (fabric.sale_price_roll != null) return Number(fabric.sale_price_roll) || 0;
      return base * (Number(fabric.yards_per_roll) || 0);
    }
    return base;
  };

  const availableYards = form.fabric != null ? stock?.items.find((i) => i.fabric === form.fabric)?.yards : undefined;
  const selectedFabric = form.fabric != null ? fabrics.find((f) => f.id === form.fabric) : undefined;
  const yardsPerRoll = Number(selectedFabric?.yards_per_roll) || 0;
  const availableUnit =
    availableYards === undefined
      ? null
      : form.sale_type === 'roll'
        ? yardsPerRoll > 0
          ? availableYards / yardsPerRoll
          : null
        : availableYards;
  const quantityNum = parseFloat(form.quantity);
  const priceNum = form.unit_price !== '' && !isNaN(parseFloat(form.unit_price)) ? parseFloat(form.unit_price) : 0;
  const subtotal = form.quantity.trim() !== '' && quantityNum > 0 && priceNum >= 0 ? quantityNum * priceNum : null;
  const quantityExceeds = availableUnit !== null && !isNaN(quantityNum) && quantityNum > availableUnit;

  const manualRefresh = async () => {
    setRefreshing(true);
    fetchSessions(true);
    fetchSummary();
    setTimeout(() => setRefreshing(false), 600);
  };

  const handleOpen = async () => {
    if (!openingEmp) {
      toast('error', 'اختر الموظف الذي يفتح الوردية');
      return;
    }
    setOpening(true);
    try {
      const s = await openSaleSession(openingEmp);
      toast('success', `تمت فتح الوردية للموظف ${s.employee_name}`);
      setOpeningEmp(null);
      fetchSessions();
      fetchSummary();
      setSelectedId(s.id);
    } catch (err: any) {
      toast('error', err.message);
    } finally {
      setOpening(false);
    }
  };

  const changeFabricOrType = (patch: Partial<ItemForm>) => {
    const next = { ...form, ...patch };
    const candidate = fabrics.find((f) => f.id === next.fabric);
    if (candidate) {
      const base = Number(candidate.sale_price_yard) || 0;
      let price = base;
      if (next.sale_type === 'roll') {
        price = candidate.sale_price_roll != null ? (Number(candidate.sale_price_roll) || 0) : base * (Number(candidate.yards_per_roll) || 0);
      }
      next.unit_price = String(price);
    }
    setForm(next);
  };

  const handleAddItem = async () => {
    if (!selected) return;
    if (!form.fabric) {
      toast('error', 'اختر القماش');
      return;
    }
    const quantity = parseFloat(form.quantity);
    const price = parseFloat(form.unit_price);
    if (!quantity || quantity <= 0) {
      toast('error', 'أدخل كمية صحيحة أكبر من صفر');
      return;
    }
    if (isNaN(price) || price < 0) {
      toast('error', 'أدخل سعر وحدة صحيح');
      return;
    }
    if (form.sale_type === 'roll') {
      const fabric = fabrics.find((f) => f.id === form.fabric);
      if (fabric && !fabric.yards_per_roll) {
        toast('error', `القماش «${fabric.name}» لا توجد له ياردات اللفة`);
        return;
      }
    }
    if (selectedFabric && stock) {
      const entry = stock.items.find((i) => i.fabric === form.fabric);
      const avail = entry ? entry.yards : 0;
      const need = form.sale_type === 'roll'
        ? quantity * (Number(selectedFabric.yards_per_roll) || 0)
        : quantity;
      if (avail <= 0) {
        toast('error', `القماش «${selectedFabric.name}» غير متوفر في مخزون الفرع`);
        return;
      }
      if (need > avail) {
        toast('error', `الكمية غير متوفرة في مخزون الفرع — المتوفر ${formatNumber(avail)} ياردة فقط`);
        return;
      }
    }
    setAdding(true);
    try {
      await addSessionItem(selected.id, {
        fabric: form.fabric,
        sale_type: form.sale_type,
        quantity,
        unit_price: price,
        payment_method: form.payment_method,
      });
      toast('success', 'تمت إضافة البند');
      setForm((cur) => ({ ...cur, quantity: '', unit_price: String(fabricAutoPrice()) }));
      fetchSessions();
      fetchSummary();
    } catch (err: any) {
      toast('error', err.message);
    } finally {
      setAdding(false);
    }
  };

  const handleRemoveItem = async (itemId: number) => {
    if (!selected) return;
    try {
      await removeSessionItem(selected.id, itemId);
      toast('success', 'تم حذف البند');
      fetchSessions();
      fetchSummary();
      onChanged?.();
    } catch (err: any) {
      toast('error', err.message);
    }
  };

  const handleClose = async () => {
    if (!closing) return;
    setCloseLoading(true);
    try {
      const s = await closeSaleSession(closing.id);
      toast('success', `تم إغلاق الوردية — إجمالي ${formatCurrency(s.totals.total)}`);
      setClosing(null);
      fetchSessions();
      fetchSummary();
      onChanged?.();
    } catch (err: any) {
      toast('error', err.message);
    } finally {
      setCloseLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold">ورديات البيع</h1>
          <p className="text-sm text-neutral-500 mt-1">
            وردية مفتوحة لكل موظف تبقى مفتوحة حتى يغلقها، ويُسجَّل البيع بتاريخ اليوم أو اليوم السابق بعد منتصف الليل حتى الساعة 2 صباحاً
          </p>
        </div>
        <Button variant="secondary" onClick={manualRefresh} loading={refreshing}>
          <RefreshCcw size={16} />
          تحديث الآن
        </Button>
      </div>

      {/* KPIs */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          icon={<Users size={20} />}
          label="الورديات المفتوحة"
          value={summary ? formatNumber(summary.open_count) : '—'}
          sub={summary ? `${formatNumber(summary.items_count)} بند معلّق` : undefined}
        />
        <StatCard
          icon={<Layers size={20} />}
          iconBg="bg-emerald-50 text-emerald-600"
          label="الكمية المعلّقة"
          value={summary ? `${formatNumber(summary.yards)} ياردة` : '—'}
          sub="ياردات فعالة بالبنود"
        />
        <StatCard
          icon={<CircleDollarSign size={20} />}
          iconBg="bg-blue-50 text-blue-600"
          label="مبيعات الورديات المعلّقة"
          value={summary ? formatCurrency(summary.total) : '—'}
          sub={summary ? `${formatNumber(summary.count)} وردية` : undefined}
        />
        <StatCard
          icon={<Package size={20} />}
          iconBg="bg-amber-50 text-amber-600"
          label="كاش متوقع"
          value={summary ? formatCurrency(summary.cash) : '—'}
          sub={summary ? `تحويل ${formatCurrency(summary.transfer)} • ماكينة ${formatCurrency(summary.card)}` : undefined}
        />
      </div>

      <Card className="!p-5">
        <div className="flex flex-wrap items-end gap-4">
          <div className="flex-1 min-w-[220px]">
            <label className="block text-sm font-medium text-neutral-700 mb-1.5">فتح وردية لموظف</label>
            {employees.length === 0 ? (
              <div className="rounded-xl border border-sand-300 px-4 py-2.5 text-sm text-neutral-500">
                لا يوجد موظفون بعد —{' '}
                <Link href="/employees" className="font-medium text-brand-600 hover:underline">أضف الموظفين أولاً</Link>
              </div>
            ) : (
              <Select
                value={openingEmp ?? ''}
                onChange={(e) => setOpeningEmp(Number(e.target.value))}
                options={employees.map((emp) => ({ value: emp.id, label: `${emp.name} — ${emp.branch_name}` }))}
                placeholder="اختر الموظف"
              />
            )}
          </div>
          <Button onClick={handleOpen} loading={opening} disabled={employees.length === 0}>
            <LogIn size={18} />
            فتح وردية
          </Button>
        </div>
      </Card>

      <Card>
        <div className="border-b border-sand-200 px-4 py-3 flex flex-wrap items-center justify-between gap-2">
          <h2 className="font-semibold">الورديات المفتوحة ({sessions.length})</h2>
          <Select
            value={branchFilter}
            onChange={(e) => setBranchFilter(e.target.value)}
            options={[{ value: '', label: 'كل الفروع' }, ...branches.map((b) => ({ value: b.id, label: b.name }))]}
            className="w-44"
          />
        </div>
        {loading ? (
          <div className="flex justify-center py-12"><Spinner size={32} /></div>
        ) : sessions.length === 0 ? (
          <EmptyState
            title="لا توجد ورديات مفتوحة"
            description="افتح وردية لموظف من القسم أعلاه لبدء تسجيل بيوعات الوردية"
          />
        ) : (
          <div className="grid gap-3 p-4 sm:grid-cols-2 lg:grid-cols-3">
            {sessions.map((s) => (
              <button
                key={s.id}
                onClick={() => setSelectedId(s.id)}
                className={`text-right rounded-xl border p-4 transition-colors ${
                  selectedId === s.id
                    ? 'border-brand-500 ring-2 ring-brand-100'
                    : 'border-sand-300 hover:border-brand-300'
                }`}
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="font-semibold">{s.employee_name}</span>
                  <Badge variant="success">مفتوحة</Badge>
                </div>
                <div className="mt-1 text-sm text-neutral-500">{s.branch_name}</div>
                <div className="mt-2 text-xs text-neutral-400">
                  فُتحت {formatDate(s.opened_at)} {new Date(s.opened_at).toLocaleTimeString('ar-EG-u-nu-latn', { hour: '2-digit', minute: '2-digit' })} • {elapsedText(s.elapsed_minutes)}
                </div>
                <div className="mt-2 grid grid-cols-3 gap-2 text-sm">
                  <div>
                    <div className="text-xs text-neutral-400">{s.items.length} بند</div>
                    <div className="text-xs text-neutral-400 tabular-nums">{formatNumber(s.totals.yards)} ياردة</div>
                  </div>
                  <div className="col-span-2 text-left">
                    <div className="font-semibold tabular-nums">{formatCurrency(s.totals.total)}</div>
                    <div className="text-xs text-neutral-400">{s.items.reduce((acc, it) => acc + (it.payment_method === 'card' ? it.total : 0), 0) > 0 ? 'يشمل ماكينة' : 'كله بطرق أخرى'}</div>
                  </div>
                </div>
              </button>
            ))}
          </div>
        )}
      </Card>

      {selected && (
        <Card className="!p-5 space-y-5">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <h2 className="font-semibold">وردية {selected.employee_name} — {selected.branch_name}</h2>
              <p className="text-sm text-neutral-500">
                فُتحت {formatDate(selected.opened_at)} {new Date(selected.opened_at).toLocaleTimeString('ar-EG-u-nu-latn', { hour: '2-digit', minute: '2-digit' })} • {elapsedText(selected.elapsed_minutes)}
              </p>
            </div>
            <Button variant="danger" onClick={() => setClosing(selected)}>
              <CircleDollarSign size={18} />
              إغلاق الوردية وتسجيل البيع
            </Button>
          </div>

          <div className="grid gap-4 rounded-xl border border-sand-300 p-4 sm:grid-cols-2 lg:grid-cols-6">
            <Select
              label="القماش"
              value={form.fabric ?? ''}
              onChange={(e) => changeFabricOrType({ fabric: Number(e.target.value) })}
              options={fabrics.map((f) => ({ value: f.id, label: `${f.name} — ي: ${formatNumber(f.sale_price_yard)}${f.sale_price_roll_display ? ` / ل: ${formatNumber(f.sale_price_roll_display)}` : ''}` }))}
              placeholder="اختر القماش"
            />
            <div>
              <label className="block text-sm font-medium text-neutral-700 mb-1.5">نوع البيع</label>
              <div className="flex rounded-xl border border-sand-300 overflow-hidden">
                <button
                  type="button"
                  onClick={() => changeFabricOrType({ sale_type: 'yard' })}
                  className={`flex-1 py-2.5 text-sm font-medium transition-colors ${form.sale_type === 'yard' ? 'bg-brand-600 text-white' : 'bg-surface text-neutral-600 hover:bg-sand-100'}`}
                >
                  ياردة
                </button>
                <button
                  type="button"
                  onClick={() => changeFabricOrType({ sale_type: 'roll' })}
                  className={`flex-1 py-2.5 text-sm font-medium transition-colors ${form.sale_type === 'roll' ? 'bg-brand-600 text-white' : 'bg-surface text-neutral-600 hover:bg-sand-100'}`}
                >
                  لفة (بالطاقة)
                </button>
              </div>
            </div>
            <Input
              label={form.sale_type === 'roll' ? 'عدد اللفات' : 'الكمية (ياردات)'}
              type="number"
              min="0"
              step="0.01"
              value={form.quantity}
              onChange={(e) => setForm({ ...form, quantity: e.target.value })}
              placeholder="0"
              className={quantityExceeds ? 'border-red-400 ring-2 ring-red-200' : ''}
            />
            <Input
              label="سعر الوحدة"
              type="number"
              min="0"
              step="0.001"
              value={form.unit_price}
              onChange={(e) => setForm({ ...form, unit_price: e.target.value })}
              placeholder={String(fabricAutoPrice()) || '0'}
            />
            <Select
              label="طريقة الدفع"
              value={form.payment_method}
              onChange={(e) => setForm({ ...form, payment_method: e.target.value as SessionPaymentMethod })}
              options={PAYMENT_OPTIONS}
            />
            <div className="flex items-end">
              <Button onClick={handleAddItem} loading={adding} className="w-full">
                <Plus size={18} />
                إضافة
              </Button>
            </div>
          </div>

          <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl bg-sand-50 border border-sand-200 px-4 py-3">
            <span className="text-sm text-neutral-600">إجمالي البند قبل الحفظ ({form.sale_type === 'roll' ? `${form.quantity || '0'} لفة × ${formatCurrency(priceNum)}` : `${form.quantity || '0'} ياردة × ${formatCurrency(priceNum)}`}):</span>
            <span className="text-xl font-bold tabular-nums text-brand-700">
              {subtotal != null ? formatCurrency(subtotal) : '—'}
            </span>
          </div>

          <div className="space-y-1.5">
            <p className="text-xs text-neutral-400">
              السعر التلقائي يُؤخذ من ملف القماش (ياردات × سعر الياردة = سعر اللفة) — لا يمكن البيع بأقل من الحد الأدنى المحدد لكل قماش.
            </p>
            {stock && availableUnit !== null && (
              <p className={`text-xs ${quantityExceeds ? 'text-red-500 font-medium' : 'text-neutral-400'}`}>
                المتوفر في مخزون الفرع ({stock.warehouse_name}): {formatNumber(availableUnit)} {form.sale_type === 'roll' ? 'لفة' : 'ياردة'}
                {quantityExceeds ? ' — الكمية تتجاوز المتوفر' : ''}
              </p>
            )}
            {selectedFabric && form.sale_type === 'roll' && !selectedFabric.yards_per_roll && (
              <p className="text-xs text-amber-600 font-medium">هذا القماش لا يملك ياردات اللفة — لا يمكن بيعه باللفة</p>
            )}
          </div>

          {selected.items.length === 0 ? (
            <EmptyState title="لا توجد بنود بعد" description="أضف أول بند من النموذج أعلاه" />
          ) : (
            <>
              <div className="overflow-x-auto">
                <Table>
                  <thead>
                    <tr>
                      <Th>القماش</Th>
                      <Th>النوع</Th>
                      <Th>الكمية</Th>
                      <Th>الياردات الفعلية</Th>
                      <Th>سعر الوحدة</Th>
                      <Th>طريقة الدفع</Th>
                      <Th>الإجمالي</Th>
                      <Th>تاريخ البيع</Th>
                      <Th>{''}</Th>
                    </tr>
                  </thead>
                  <tbody>
                    {selected.items.map((item) => (
                      <Tr key={item.id}>
                        <Td className="font-medium">{item.fabric_name}</Td>
                        <Td><Badge variant="neutral">{item.sale_type_label}</Badge></Td>
                        <Td className="tabular-nums">{item.quantity} {item.sale_type === 'roll' ? 'لفة' : 'يارد'}</Td>
                        <Td className="tabular-nums text-neutral-500">{formatNumber(item.yards_effective)} ياردة</Td>
                        <Td className="tabular-nums">{formatCurrency(item.unit_price)}</Td>
                        <Td>
                          <Badge variant={item.payment_method === 'card' ? 'warning' : item.payment_method === 'transfer' ? 'neutral' : 'success'}>
                            {item.payment_method_label}
                          </Badge>
                        </Td>
                        <Td className="tabular-nums font-semibold">{formatCurrency(item.total)}</Td>
                        <Td className="tabular-nums text-sm text-neutral-500">{formatDate(item.sale_date)}</Td>
                        <Td>
                          <div className="flex items-center gap-1.5">
                            <button onClick={() => setEditingItem({ session: selected, item })} className="p-1.5 rounded-lg hover:bg-amber-50 text-amber-600 dark:hover:bg-amber-500/15 dark:text-amber-400 transition-colors" title="تعديل البيع">
                              <Pencil size={15} />
                            </button>
                            <button onClick={() => handleRemoveItem(item.id)} className="p-1.5 rounded-lg hover:bg-red-50 text-red-500 dark:hover:bg-red-500/15 dark:text-red-400 transition-colors" title="حذف البيع">
                              <Trash2 size={15} />
                            </button>
                          </div>
                        </Td>
                      </Tr>
                    ))}
                  </tbody>
                </Table>
              </div>

              <div className="flex flex-wrap items-center justify-between gap-3 border-t border-sand-200 pt-4">
                <span className="flex items-center gap-2 text-sm">
                  <Badge variant="success">كاش {formatCurrency(selected.totals.cash)}</Badge>
                  <Badge variant="neutral">تحويل {formatCurrency(selected.totals.transfer)}</Badge>
                  <Badge variant="warning">ماكينة {formatCurrency(selected.totals.card)}</Badge>
                  <Badge variant="neutral">{formatNumber(selected.totals.yards)} ياردة</Badge>
                </span>
                <span className="text-lg font-bold tabular-nums">{formatCurrency(selected.totals.total)}</span>
              </div>
            </>
          )}
        </Card>
      )}

      <ConfirmDialog
        open={!!closing}
        onClose={() => setClosing(null)}
        onConfirm={handleClose}
        loading={closeLoading}
        title="إغلاق الوردية"
        confirmLabel="حفظ وإغلاق"
        message={
          closing
            ? `هل أنت متأكد من إغلاق وردية ${closing.employee_name}؟ سيتم تسجيل المبيعات في قيود اليوم وخصم الكميات من مخزون الفرع (${closing.items.length} بند — إجمالي ${formatCurrency(closing.totals.total)}: كاش ${formatCurrency(closing.totals.cash)}، تحويل ${formatCurrency(closing.totals.transfer)}، ماكينة ${formatCurrency(closing.totals.card)}).`
            : ''
        }
      />

      <SessionItemEditModal
        open={!!editingItem}
        session={editingItem?.session ?? null}
        item={editingItem?.item ?? null}
        fabrics={fabrics}
        onClose={() => setEditingItem(null)}
        onSaved={() => {
          fetchSessions();
          fetchSummary();
          onChanged?.();
        }}
      />
    </div>
  );
}