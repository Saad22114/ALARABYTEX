'use client';

import { useState, useEffect } from 'react';
import Card from '@/components/ui/Card';
import Button from '@/components/ui/Button';
import Table, { Th, Td, Tr } from '@/components/ui/Table';
import SearchInput from '@/components/ui/SearchInput';
import Select from '@/components/ui/Select';
import Input from '@/components/ui/Input';
import Textarea from '@/components/ui/Textarea';
import Modal from '@/components/ui/Modal';
import Badge from '@/components/ui/Badge';
import EmptyState from '@/components/ui/EmptyState';
import Spinner from '@/components/ui/Spinner';
import { Plus, X, ChevronDown, AlertTriangle, Pencil, Trash2, Warehouse as WarehouseIcon } from 'lucide-react';
import {
  StockBalanceResult,
  StockBalanceItem,
  StockOpening,
  Warehouse,
  Fabric,
} from '@/types';
import { getStockBalances, listOpenings, createOpening, listWarehouses, setStockBalance } from '@/services/warehouses';
import { listFabrics } from '@/services/fabrics';
import { formatNumber } from '@/lib/format';
import { useToast } from '@/components/ui/Toast';

const UNIT_LABEL: Record<string, string> = {
  yard: 'ياردة',
  roll: 'طاقة',
};

interface OpeningLine {
  fabric: string;
  yards: string;
  rolls: string;
  unit_price: string;
}

export default function StockTab() {
  const { toast } = useToast();
  const [data, setData] = useState<StockBalanceResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [warehouse, setWarehouse] = useState('');
  const [warehouses, setWarehouses] = useState<Warehouse[]>([]);
  const [tab, setTab] = useState<'balances' | 'openings'>('balances');

  const [openings, setOpenings] = useState<StockOpening[] | null>(null);
  const [openingsLoading, setOpeningsLoading] = useState(false);

  const [formOpen, setFormOpen] = useState(false);
  const [fabrics, setFabrics] = useState<Fabric[]>([]);
  const [lines, setLines] = useState<OpeningLine[]>([{ fabric: '', yards: '', rolls: '', unit_price: '' }]);
  const [form, setForm] = useState({ warehouse: '', date: new Date().toISOString().slice(0, 10), notes: '' });
  const [formErrors, setFormErrors] = useState<Record<string, string>>({});
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    listWarehouses({ page_size: 100 })
      .then((r) => setWarehouses(r.results.filter((w) => w.is_active)))
      .catch(() => {});
    listFabrics({ page_size: 200 })
      .then((r) => setFabrics(r.results.filter((f) => f.is_active)))
      .catch(() => {});
  }, []);

  const fetchBalances = () => {
    let cancelled = false;
    setLoading(true);
    getStockBalances({ search: search || undefined, warehouse: warehouse || undefined })
      .then((res) => { if (!cancelled) setData(res); })
      .catch((err: any) => { if (!cancelled) toast('error', err.message); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  };

  const fetchOpenings = () => {
    let cancelled = false;
    setOpeningsLoading(true);
    listOpenings({ page_size: 100 })
      .then((res) => { if (!cancelled) setOpenings(res.results); })
      .catch((err: any) => { if (!cancelled) toast('error', err.message); })
      .finally(() => { if (!cancelled) setOpeningsLoading(false); });
    return () => { cancelled = true; };
  };

  useEffect(() => fetchBalances(), [search, warehouse]);

  useEffect(() => {
    if (tab === 'openings' && openings === null) fetchOpenings();
  }, [tab]);

  const setLine = (idx: number, patch: Partial<OpeningLine>) =>
    setLines((prev) => prev.map((l, i) => (i === idx ? { ...l, ...patch } : l)));
  const addLine = () => setLines((prev) => [...prev, { fabric: '', yards: '', rolls: '', unit_price: '' }]);
  const removeLine = (idx: number) => setLines((prev) => prev.filter((_, i) => i !== idx));

  const handleCreateOpening = async () => {
    const e: Record<string, string> = {};
    if (!form.warehouse) e.warehouse = 'اختر المخزن';
    const validLines = lines.filter((l) => l.fabric && parseFloat(l.yards) > 0);
    if (validLines.length === 0) e.items = 'أضف صنفاً واحداً على الأقل';
    setFormErrors(e);
    if (Object.keys(e).length > 0) return;

    setSubmitting(true);
    try {
      await createOpening({
        warehouse: Number(form.warehouse),
        date: form.date,
        notes: form.notes,
        items: validLines.map((l) => ({
          fabric: Number(l.fabric),
          yards: parseFloat(l.yards) || 0,
          rolls_count: Math.max(1, parseInt(l.rolls, 10) || 1),
          unit_price: parseFloat(l.unit_price) || 0,
        })),
      });
      toast('success', 'تم تسجيل الرصيد الافتتاحي وترحيله بنجاح');
      setFormOpen(false);
      setLines([{ fabric: '', yards: '', rolls: '', unit_price: '' }]);
      setForm({ warehouse: '', date: new Date().toISOString().slice(0, 10), notes: '' });
      fetchBalances();
      setOpenings(null);
    } catch (err: any) {
      toast('error', err.message);
    } finally {
      setSubmitting(false);
    }
  };

  const totals = data?.totals;

  const [editItem, setEditItem] = useState<StockBalanceItem | null>(null);
  const [editRows, setEditRows] = useState<Record<number, string>>({});
  const [editing, setEditing] = useState(false);
  const [deleteItem, setDeleteItem] = useState<StockBalanceItem | null>(null);
  const [deleting, setDeleting] = useState(false);

  const openEdit = (item: StockBalanceItem) => {
    setEditItem(item);
    setEditRows(
      Object.fromEntries(item.warehouses.map((w) => [w.warehouse, String(w.total_yards)])),
    );
  };

  const handleSaveEdit = async () => {
    if (!editItem) return;
    const items = Object.entries(editRows)
      .map(([warehouse, val]) => ({ warehouse: Number(warehouse), yards: parseFloat(val) }))
      .filter((row) => !isNaN(row.yards) && row.yards >= 0);
    if (items.length === 0) {
      toast('error', 'أدخل قيماً صحيحة للكمية لكل مخزن');
      return;
    }
    setEditing(true);
    try {
      await setStockBalance({ fabric: editItem.fabric, items });
      toast('success', 'تم تعديل رصيد المخزون بنجاح');
      setEditItem(null);
      fetchBalances();
    } catch (err: any) {
      toast('error', err.message);
    } finally {
      setEditing(false);
    }
  };

  const handleDelete = async () => {
    if (!deleteItem) return;
    setDeleting(true);
    try {
      const items = deleteItem.warehouses.map((w) => ({ warehouse: w.warehouse, yards: 0 }));
      if (items.length === 0) {
        toast('success', 'لا يوجد رصيد لهذا القماش');
        setDeleteItem(null);
        return;
      }
      await setStockBalance({ fabric: deleteItem.fabric, items });
      toast('success', `تم حذف رصيد «${deleteItem.fabric_name}» من جميع المخازن`);
      setDeleteItem(null);
      fetchBalances();
    } catch (err: any) {
      toast('error', err.message);
    } finally {
      setDeleting(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h2 className="text-lg font-bold text-neutral-800">المخزون الموحد</h2>
          <p className="text-sm text-neutral-500">أرصدة الأقمشة في جميع المخازن والفروع مع تنبيهات الحد الأدنى</p>
        </div>
        <Button onClick={() => setFormOpen(true)}>
          <Plus size={18} />
          تسجيل رصيد افتتاحي
        </Button>
      </div>

      {totals && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <Card>
            <p className="text-xs text-neutral-500 mb-1">إجمالي الكمية</p>
            <p className="text-2xl font-bold text-neutral-800 tabular-nums">{formatNumber(totals.total_yards)}</p>
          </Card>
          <Card>
            <p className="text-xs text-neutral-500 mb-1">الطاقات المتاحة</p>
            <p className="text-2xl font-bold text-neutral-800 tabular-nums">{formatNumber(totals.rolls_available)}</p>
          </Card>
          <Card>
            <p className="text-xs text-neutral-500 mb-1">أقمشة تحت الحد الأدنى</p>
            <p className={`text-2xl font-bold tabular-nums ${totals.low_stock_count > 0 ? 'text-red-600' : 'text-emerald-600'}`}>
              {formatNumber(totals.low_stock_count)}
            </p>
          </Card>
          <Card>
            <p className="text-xs text-neutral-500 mb-1">عدد المخازن</p>
            <p className="text-2xl font-bold text-neutral-800 tabular-nums">{formatNumber(totals.warehouses)}</p>
          </Card>
        </div>
      )}

      <Card>
        <div className="p-4 border-b border-sand-100 flex flex-wrap items-center gap-3">
          <SearchInput value={search} onChange={setSearch} placeholder="بحث في الأقمشة..." />
          <Select
            value={warehouse}
            onChange={(e) => setWarehouse(e.target.value)}
            options={[{ value: '', label: 'كل المخازن' }, ...warehouses.map((w) => ({ value: w.id, label: w.name }))]}
            className="w-full sm:w-56"
          />
        </div>
      </Card>

      <div className="flex gap-2">
        {([
          { k: 'balances', label: 'الأرصدة' },
          { k: 'openings', label: 'الأرصدة الافتتاحية' },
        ] as const).map((t) => (
          <button
            key={t.k}
            onClick={() => setTab(t.k)}
            className={`px-4 py-2 rounded-xl text-sm font-medium transition-all duration-150 ${
              tab === t.k
                ? 'bg-brand-600 text-white shadow-sm'
                : 'bg-surface text-neutral-600 border border-sand-200 hover:bg-sand-50'
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {tab === 'balances' && (
        <Card>
          {loading ? (
            <div className="flex justify-center py-12"><Spinner size={32} /></div>
          ) : !data || data.items.length === 0 ? (
            <EmptyState
              title="لا توجد أرصدة"
              description="سجّل استلاماً أو رصيداً افتتاحياً لبناء رصيد المخزون"
            />
          ) : (
            <Table>
              <thead>
                <tr>
                  <Th>القماش</Th>
                  <Th>الكود</Th>
                  <Th>الوحدة</Th>
                  <Th>الطاقات المتاحة</Th>
                  <Th>الكمية</Th>
                  <Th>الحد الأدنى</Th>
                  <Th>الحالة</Th>
                  <Th>التوزيع</Th>
                  <Th>إجراءات</Th>
                </tr>
              </thead>
              <tbody>
                {data.items.map((item) => (
                  <Tr key={item.fabric}>
                    <Td className="font-medium">{item.fabric_name}</Td>
                    <Td><span className="font-mono text-xs bg-sand-100 px-2 py-1 rounded">{item.fabric_code}</span></Td>
                    <Td>{UNIT_LABEL[item.unit] || item.unit}</Td>
                    <Td className="tabular-nums">{formatNumber(item.rolls_available)}</Td>
                    <Td className={`tabular-nums font-bold ${item.low_stock ? 'text-red-600' : 'text-neutral-800'}`}>
                      {formatNumber(item.total_yards)}
                    </Td>
                    <Td className="tabular-nums">{formatNumber(item.min_stock)}</Td>
                    <Td>
                      {item.low_stock ? (
                        <Badge variant="danger">
                          <AlertTriangle size={12} />
                          تحت الحد الأدنى
                        </Badge>
                      ) : (
                        <Badge variant="success">مناسب</Badge>
                      )}
                    </Td>
                    <Td>
                      <details className="group">
                        <summary className="flex items-center gap-1 text-xs font-medium text-brand-700 cursor-pointer select-none list-none">
                          <WarehouseIcon size={14} />
                          {item.warehouses.length} مخزن
                          <ChevronDown size={14} className="transition-transform group-open:rotate-180" />
                        </summary>
                        <div className="mt-2 space-y-1">
                          {item.warehouses.map((w) => (
                            <div key={w.warehouse} className="flex items-center justify-between gap-4 text-xs py-1 px-2 rounded-lg bg-sand-50">
                              <span className="text-neutral-600">
                                {w.warehouse_name}
                                {w.is_branch_stock && <Badge variant="neutral">فرع</Badge>}
                              </span>
                              <span className="tabular-nums text-neutral-700 font-medium">
                                {formatNumber(w.total_yards)} ({formatNumber(w.rolls_available)} لف)
                              </span>
                            </div>
                          ))}
                        </div>
                      </details>
                    </Td>
                    <Td>
                      <div className="flex items-center gap-1">
                        <button
                          onClick={() => openEdit(item)}
                          className="p-1.5 rounded-lg text-neutral-400 hover:bg-brand-50 hover:text-brand-600"
                          title="تعديل الرصيد"
                        >
                          <Pencil size={15} />
                        </button>
                        <button
                          onClick={() => setDeleteItem(item)}
                          className="p-1.5 rounded-lg text-neutral-400 hover:bg-red-50 hover:text-red-600"
                          title="حذف الرصيد"
                        >
                          <Trash2 size={15} />
                        </button>
                      </div>
                    </Td>
                  </Tr>
                ))}
              </tbody>
            </Table>
          )}
        </Card>
      )}

      {tab === 'openings' && (
        <Card>
          {openingsLoading && openings === null ? (
            <div className="flex justify-center py-12"><Spinner size={32} /></div>
          ) : openings === null ? null : openings.length === 0 ? (
            <EmptyState
              title="لا توجد أرصدة افتتاحية"
              description="سجّل رصيداً افتتاحياً للمخازن التي بدأت برصيد سابق"
            />
          ) : (
            <Table>
              <thead>
                <tr>
                  <Th>الرقم</Th>
                  <Th>التاريخ</Th>
                  <Th>المخزن</Th>
                  <Th>عدد الأصناف</Th>
                  <Th>إجمالي الكمية</Th>
                  <Th>ملاحظات</Th>
                </tr>
              </thead>
              <tbody>
                {openings.map((o) => (
                  <Tr key={o.id}>
                    <Td><span className="font-mono text-xs bg-sand-100 px-2 py-1 rounded" dir="ltr">{o.number}</span></Td>
                    <Td className="tabular-nums">{o.date}</Td>
                    <Td className="font-medium">{o.warehouse_name}</Td>
                    <Td className="tabular-nums">{o.items.length}</Td>
                    <Td className="tabular-nums font-medium">{formatNumber(o.total_yards)}</Td>
                    <Td className="text-xs text-neutral-500 max-w-[200px] truncate">{o.notes || '—'}</Td>
                  </Tr>
                ))}
              </tbody>
            </Table>
          )}
        </Card>
      )}

      <Modal open={formOpen} onClose={() => setFormOpen(false)} title="تسجيل رصيد افتتاحي" maxWidth="max-w-3xl">
        <div className="space-y-4">
          <p className="text-xs text-neutral-500">
            يتم إنشاء الأرصدة الافتتاحية مرة واحدة لكل قماش في المخزن، وتظهر في حركات المخزون كرصيد افتتاحي.
          </p>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <Select
              label="المخزن *"
              value={form.warehouse}
              onChange={(e) => setForm({ ...form, warehouse: e.target.value })}
              options={warehouses.map((w) => ({ value: w.id, label: w.name }))}
              placeholder="اختر المخزن"
              error={formErrors.warehouse}
            />
            <Input
              label="التاريخ"
              type="date"
              value={form.date}
              onChange={(e) => setForm({ ...form, date: e.target.value })}
            />
          </div>

          <div className="space-y-3">
            {lines.map((line, idx) => (
              <div key={idx} className="rounded-xl border border-sand-200 p-3 space-y-3">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-semibold text-neutral-600">صنف {idx + 1}</span>
                  <button
                    type="button"
                    onClick={() => removeLine(idx)}
                    className="p-1.5 rounded-lg text-neutral-400 hover:bg-red-50 hover:text-red-600"
                    disabled={lines.length === 1}
                    title="حذف الصنف"
                  >
                    <X size={16} />
                  </button>
                </div>
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                  <Select
                    value={line.fabric}
                    onChange={(e) => setLine(idx, { fabric: e.target.value })}
                    options={fabrics.map((f) => ({ value: f.id, label: `${f.name} (${f.code})` }))}
                    placeholder="اختر القماش"
                  />
                  <Input
                    label="الكمية"
                    type="number"
                    min="0"
                    step="0.01"
                    value={line.yards}
                    onChange={(e) => setLine(idx, { yards: e.target.value })}
                    placeholder=""
                  />
                  <div className="grid grid-cols-2 gap-3">
                    <Input
                      label="الطاقات"
                      type="number"
                      min="1"
                      step="1"
                      value={line.rolls}
                      onChange={(e) => setLine(idx, { rolls: e.target.value })}
                      placeholder="1"
                    />
                    <Input
                      label="سعر الوحدة"
                      type="number"
                      min="0"
                      step="0.01"
                      value={line.unit_price}
                      onChange={(e) => setLine(idx, { unit_price: e.target.value })}
                      placeholder=""
                    />
                  </div>
                </div>
              </div>
            ))}
            <Button type="button" variant="secondary" size="sm" onClick={addLine}>
              <Plus size={14} />
              إضافة صنف
            </Button>
            {formErrors.items && <p className="text-xs text-red-500 font-medium">{formErrors.items}</p>}
          </div>

          <Textarea
            label="ملاحظات"
            value={form.notes}
            onChange={(e) => setForm({ ...form, notes: e.target.value })}
            rows={2}
            placeholder="ملاحظات..."
          />

          <div className="flex justify-end gap-3 pt-2">
            <Button onClick={handleCreateOpening} loading={submitting}>تسجيل وترحيل</Button>
            <Button variant="secondary" onClick={() => setFormOpen(false)}>إلغاء</Button>
          </div>
        </div>
      </Modal>

      <Modal open={editItem !== null} onClose={() => setEditItem(null)} title="تعديل رصيد المخزون" maxWidth="max-w-2xl">
        {editItem && (
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="font-bold text-neutral-800">{editItem.fabric_name}</p>
                <p className="text-xs text-neutral-500 font-mono">{editItem.fabric_code}</p>
              </div>
              <Badge variant="neutral">{UNIT_LABEL[editItem.unit] || editItem.unit}</Badge>
            </div>
            <p className="text-xs text-neutral-500 bg-sand-50 rounded-xl p-3">
              يتم إنشاء تسوية مخزون (إضافة أو خصم) تلقائياً لتصحيح الرصيد في كل مخزن، وتظهر في حركات المخزون.
            </p>
            <div className="space-y-3">
              {editItem.warehouses.map((w) => (
                <div key={w.warehouse} className="grid grid-cols-1 sm:grid-cols-2 gap-2 items-center rounded-xl border border-sand-200 p-3">
                  <div>
                    <p className="text-sm font-medium text-neutral-700">{w.warehouse_name}</p>
                    <p className="text-xs text-neutral-400">
                      الرصيد الحالي: <span className="tabular-nums font-medium">{formatNumber(w.total_yards)}</span> ({formatNumber(w.rolls_available)} لف)
                    </p>
                  </div>
                  <Input
                    label="الرصيد الجديد"
                    type="number"
                    min="0"
                    step="0.01"
                    value={editRows[w.warehouse] ?? ''}
                    onChange={(e) => setEditRows((prev) => ({ ...prev, [w.warehouse]: e.target.value }))}
                    placeholder=""
                  />
                </div>
              ))}
            </div>
            <div className="flex justify-end gap-3 pt-2">
              <Button onClick={handleSaveEdit} loading={editing}>حفظ التعديل</Button>
              <Button variant="secondary" onClick={() => setEditItem(null)}>إلغاء</Button>
            </div>
          </div>
        )}
      </Modal>

      <Modal open={deleteItem !== null} onClose={() => setDeleteItem(null)} title="حذف رصيد القماش" maxWidth="max-w-md">
        {deleteItem && (
          <div className="space-y-4">
            <div className="flex items-center gap-3">
              <span className="p-3 rounded-2xl bg-red-50 text-red-600">
                <AlertTriangle size={22} />
              </span>
              <p className="text-sm text-neutral-700">
                سيتم خصم الرصيد الحالي ({' '}
                <span className="font-bold tabular-nums">{formatNumber(deleteItem.total_yards)}</span> {' '}
                {UNIT_LABEL[deleteItem.unit] || deleteItem.unit} ) للقماش «<span className="font-bold">{deleteItem.fabric_name}</span>»
                من جميع المخازن عبر تسوية خصم.
              </p>
            </div>
            <p className="text-xs text-neutral-500 bg-sand-50 rounded-xl p-3">
              هذا إجراء موثق في حركات المخزون ولا يمكن التراجع عنه من هنا.
            </p>
            <div className="flex justify-end gap-3 pt-2">
              <Button variant="danger" onClick={handleDelete} loading={deleting}>
                <Trash2 size={16} />
                حذف الرصيد
              </Button>
              <Button variant="secondary" onClick={() => setDeleteItem(null)}>إلغاء</Button>
            </div>
          </div>
        )}
      </Modal>
    </div>
  );
}