'use client';

import { useState, useEffect, useMemo, useCallback } from 'react';
import AppShell from '@/components/layout/AppShell';
import Card from '@/components/ui/Card';
import Button from '@/components/ui/Button';
import Table, { Th, Td, Tr } from '@/components/ui/Table';
import SearchInput from '@/components/ui/SearchInput';
import Select from '@/components/ui/Select';
import Pagination from '@/components/ui/Pagination';
import Modal from '@/components/ui/Modal';
import ConfirmDialog from '@/components/ui/ConfirmDialog';
import Badge from '@/components/ui/Badge';
import EmptyState from '@/components/ui/EmptyState';
import Spinner from '@/components/ui/Spinner';
import StatCard from '@/components/ui/StatCard';
import FabricForm from '@/components/forms/FabricForm';
import {
  Plus, Pencil, Trash2, Eye, Package, AlertTriangle,
  IndianRupee, Boxes, Download, Tags, TrendingUp, Percent,
} from 'lucide-react';
import { Fabric, FabricStockResult, FabricSummary, Paginated } from '@/types';
import {
  listFabrics, createFabric, updateFabric, deleteFabric,
  getFabricSummary, getFabricStock, bulkPriceUpdate,
} from '@/services/fabrics';
import { formatCurrency, formatNumber } from '@/lib/format';
import { API_URL } from '@/services/api';
import { useToast } from '@/components/ui/Toast';
import { useSettings } from '@/components/providers/SettingsProvider';
import { useUrlState } from '@/lib/useUrlState';

const UNIT_LABEL: Record<string, string> = { yard: 'ياردة', roll: 'طاقة' };

const FABRIC_TYPE_OPTIONS = [
  { value: '', label: 'كل الأنواع' },
  { value: 'منسوج', label: 'منسوج' },
  { value: 'قطن', label: 'قطن' },
  { value: 'صوف', label: 'صوف' },
  { value: 'حرير', label: 'حرير' },
  { value: 'بوليستر', label: 'بوليستر' },
  { value: 'مخمل', label: 'مخمل' },
  { value: 'ساتان', label: 'ساتان' },
  { value: 'جينز', label: 'جينز' },
  { value: 'أخرى', label: 'أخرى' },
];

const UNIT_FILTER_OPTIONS = [
  { value: '', label: 'كل الوحدات' },
  { value: 'yard', label: 'ياردة' },
  { value: 'roll', label: 'طاقة' },
];

const STATUS_FILTER_OPTIONS = [
  { value: '', label: 'كل الحالات' },
  { value: 'active', label: 'نشط' },
  { value: 'inactive', label: 'غير نشط' },
];

const LOW_STOCK_FILTER_OPTIONS = [
  { value: '', label: 'كل مستويات المخزون' },
  { value: 'low', label: 'منخفض فقط' },
  { value: 'ok', label: 'متوفر' },
];

export default function FabricsPage() {
  const { toast } = useToast();
  const { settings } = useSettings();
  const pageSize = settings?.default_page_size ?? 10;

  const [data, setData] = useState<Paginated<Fabric> | null>(null);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useUrlState('q', '');
  const [fabricType, setFabricType] = useUrlState('type', '');
  const [unit, setUnit] = useUrlState('unit', '');
  const [status, setStatus] = useUrlState('status', '');
  const [lowStock, setLowStock] = useUrlState('low_stock', '');
  const [page, setPage] = useUrlState('page', 1);

  const [summary, setSummary] = useState<FabricSummary | null>(null);

  const [modalOpen, setModalOpen] = useState(false);
  const [editing, setEditing] = useState<Fabric | null>(null);
  const [details, setDetails] = useState<Fabric | null>(null);
  const [stock, setStock] = useState<FabricStockResult | null>(null);
  const [stockLoading, setStockLoading] = useState(false);
  const [deleting, setDeleting] = useState<Fabric | null>(null);
  const [deleteLoading, setDeleteLoading] = useState(false);

  const [bulkOpen, setBulkOpen] = useState(false);
  const [bulkLoading, setBulkLoading] = useState(false);
  const [bulkForm, setBulkForm] = useState<{
    field: 'sale_price_yard' | 'purchase_price' | 'min_sale_yard';
    mode: 'percent' | 'fixed';
    value: string;
    direction: 'increase' | 'decrease';
  }>({ field: 'sale_price_yard', mode: 'percent', value: '', direction: 'increase' });

  const fetchData = useCallback(() => {
    let cancelled = false;
    setLoading(true);
    const params: Record<string, string | number | undefined | null> = {
      page, page_size: pageSize,
      search: search || undefined,
      fabric_type: fabricType || undefined,
      unit: unit || undefined,
      is_active: status === 'active' ? 'true' : status === 'inactive' ? 'false' : undefined,
      low_stock: lowStock === 'low' ? 'true' : lowStock === 'ok' ? 'false' : undefined,
    };
    listFabrics(params)
      .then((res) => { if (!cancelled) setData(res); })
      .catch((err) => { if (!cancelled) toast('error', err.message); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [page, pageSize, search, fabricType, unit, status, lowStock]);

  useEffect(() => fetchData(), [fetchData]);

  const fetchSummary = useCallback(() => {
    let cancelled = false;
    getFabricSummary()
      .then((res) => { if (!cancelled) setSummary(res); })
      .catch(() => { /* KPIs تبقى فارغة عند الخطأ */ });
    return () => { cancelled = true; };
  }, []);

  useEffect(() => fetchSummary(), [fetchSummary]);

  const totalPages = data ? Math.ceil(data.count / pageSize) : 1;

  const handleCreate = async (d: Partial<Fabric>) => {
    await createFabric(d);
    toast('success', 'تمت إضافة القماش بنجاح');
    setModalOpen(false);
    fetchData();
    fetchSummary();
  };

  const handleUpdate = async (d: Partial<Fabric>) => {
    if (!editing) return;
    await updateFabric(editing.id, d);
    toast('success', 'تم تحديث القماش بنجاح');
    setEditing(null);
    fetchData();
    fetchSummary();
  };

  const handleDelete = async () => {
    if (!deleting) return;
    setDeleteLoading(true);
    try {
      await deleteFabric(deleting.id);
      toast('success', 'تم حذف القماش بنجاح');
      setDeleting(null);
      fetchData();
      fetchSummary();
    } catch (err: any) {
      toast('error', err.message);
    } finally {
      setDeleteLoading(false);
    }
  };

  const handleBulkUpdate = async () => {
    const value = Number(bulkForm.value);
    if (!value || value <= 0) {
      toast('error', 'أدخل قيمة صحيحة أكبر من صفر');
      return;
    }
    if (bulkForm.mode === 'percent' && value > 100) {
      toast('error', 'النسبة لا يمكن أن تتجاوز 100%');
      return;
    }
    setBulkLoading(true);
    try {
      const res = await bulkPriceUpdate({
        field: bulkForm.field,
        mode: bulkForm.mode,
        value,
        direction: bulkForm.direction,
      });
      toast('success', res.detail);
      setBulkOpen(false);
      fetchData();
      fetchSummary();
    } catch (err: any) {
      toast('error', err.message);
    } finally {
      setBulkLoading(false);
    }
  };

  const openDetails = async (f: Fabric) => {
    setDetails(f);
    setStock(null);
    setStockLoading(true);
    try {
      const res = await getFabricStock(f.id);
      setStock(res);
    } catch (err: any) {
      toast('error', err.message);
    } finally {
      setStockLoading(false);
    }
  };

  const exportUrl = useMemo(() => {
    const p = new URLSearchParams();
    p.append('export', 'xlsx');
    if (search) p.append('search', search);
    if (fabricType) p.append('fabric_type', fabricType);
    if (unit) p.append('unit', unit);
    if (status === 'active') p.append('is_active', 'true');
    if (status === 'inactive') p.append('is_active', 'false');
    if (lowStock === 'low') p.append('low_stock', 'true');
    if (lowStock === 'ok') p.append('low_stock', 'false');
    return `${API_URL}/fabrics/?${p.toString()}`;
  }, [search, fabricType, unit, status, lowStock]);

  return (
    <AppShell>
      <div className="space-y-6">
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          <StatCard icon={<Tags size={20} />} label="إجمالي الأقمشة" value={summary ? formatNumber(summary.fabric_count) : '—'} sub={summary ? `${formatNumber(summary.active_count)} نشط` : undefined} />
          <StatCard icon={<AlertTriangle size={20} />} iconBg="bg-amber-50 text-amber-600" label="منخفضة المخزون" value={summary ? formatNumber(summary.low_stock_count) : '—'} sub="تحت الحد الأدنى" />
          <StatCard icon={<Boxes size={20} />} label="الطاقات المتاحة" value={summary ? formatNumber(summary.total_rolls) : '—'} sub={summary ? `${formatNumber(summary.total_stock_yards)} ياردة` : undefined} />
          <StatCard icon={<IndianRupee size={20} />} iconBg="bg-emerald-50 text-emerald-600" label="قيمة المخزون" value={summary ? formatCurrency(summary.inventory_cost_value) : '—'} sub={summary ? `قيمة بيع: ${formatCurrency(summary.inventory_retail_value)}` : undefined} />
        </div>

        <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3 lg:flex-1">
            <SearchInput value={search} onChange={(v) => { setSearch(v); setPage(1); }} />
            <Select value={fabricType} onChange={(e) => { setFabricType(e.target.value); setPage(1); }} options={FABRIC_TYPE_OPTIONS} />
            <Select value={unit} onChange={(e) => { setUnit(e.target.value); setPage(1); }} options={UNIT_FILTER_OPTIONS} />
            <Select value={lowStock} onChange={(e) => { setLowStock(e.target.value); setPage(1); }} options={LOW_STOCK_FILTER_OPTIONS} />
            <Select value={status} onChange={(e) => { setStatus(e.target.value); setPage(1); }} options={STATUS_FILTER_OPTIONS} />
          </div>
          <div className="flex items-center gap-2">
            <a href={exportUrl} target="_blank" rel="noreferrer">
              <Button variant="secondary" type="button">
                <Download size={16} />
                تصدير Excel
              </Button>
            </a>
            <Button variant="secondary" type="button" onClick={() => setBulkOpen(true)}>
              <Percent size={16} />
              تعديل أسعار بالجملة
            </Button>
            <Button onClick={() => setModalOpen(true)}>
              <Plus size={18} />
              إضافة قماش
            </Button>
          </div>
        </div>

        <Card>
          {loading ? (
            <div className="flex justify-center py-12"><Spinner size={32} /></div>
          ) : !data || data.results.length === 0 ? (
            <EmptyState title="لا توجد أقمشة" description="لم يتم العثور على نتائج مطابقة" />
          ) : (
            <>
              <div className="overflow-x-auto">
                <Table>
                  <thead>
                    <tr>
                      <Th>الاسم / الكود</Th>
                      <Th>النوع / اللون</Th>
                      <Th>أسعار البيع</Th>
                      <Th>الحد الأدنى</Th>
                      <Th>المخزون</Th>
                      <Th>هامش الربح</Th>
                      <Th>المورد</Th>
                      <Th>الحالة</Th>
                      <Th>إجراءات</Th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.results.map((f) => (
                      <Tr key={f.id}>
                        <Td>
                          <button onClick={() => openDetails(f)} className="text-left">
                            <span className="block font-semibold text-neutral-800 text-sm hover:text-brand-700 transition-colors">{f.name}</span>
                            <span className="block font-mono text-xs text-neutral-400">{f.code}</span>
                          </button>
                        </Td>
                        <Td>
                          <span className="block text-sm">{f.fabric_type || '-'}</span>
                          {f.color && <span className="block text-xs text-neutral-400">{f.color}</span>}
                        </Td>
                        <Td>
                          <span className="block text-sm tabular-nums">{formatCurrency(f.sale_price_yard)} <span className="text-xs text-neutral-400">/ياردة</span></span>
                          <span className="block text-xs tabular-nums text-neutral-500">{f.sale_price_roll_display != null ? formatCurrency(f.sale_price_roll_display) : '-'} <span className="text-neutral-400">/طاقة</span></span>
                        </Td>
                        <Td>
                          <span className="block text-xs tabular-nums text-neutral-500">ي: {formatCurrency(f.min_sale_yard)}</span>
                          {f.min_sale_roll_display != null && <span className="block text-xs tabular-nums text-neutral-500">ط: {formatCurrency(f.min_sale_roll_display)}</span>}
                        </Td>
                        <Td>
                          <span className="block text-sm tabular-nums">{formatNumber(f.stock_yards)} <span className="text-xs text-neutral-400">ياردة</span></span>
                          <span className="block text-xs tabular-nums text-neutral-500">{formatNumber(f.total_rolls)} <span className="text-neutral-400">طاقة</span></span>
                          {f.low_stock && <Badge variant="warning">منخفض</Badge>}
                        </Td>
                        <Td className="tabular-nums">
                          <span className={`text-sm font-medium ${f.profit_yard >= 0 ? 'text-emerald-600' : 'text-red-500'}`}>{f.profit_margin_pct ? `${f.profit_margin_pct.toFixed(1)}%` : '-'}</span>
                        </Td>
                        <Td className="text-sm">{f.supplier_name || '-'}</Td>
                        <Td>
                          <Badge variant={f.is_active ? 'success' : 'neutral'}>
                            {f.is_active ? 'نشط' : 'غير نشط'}
                          </Badge>
                        </Td>
                        <Td>
                          <div className="flex items-center gap-2">
                            <button onClick={() => openDetails(f)} className="p-1.5 rounded-lg hover:bg-brand-50 text-brand-600 transition-colors" title="التفاصيل والمخزون">
                              <Eye size={16} />
                            </button>
                            <button onClick={() => setEditing(f)} className="p-1.5 rounded-lg hover:bg-amber-50 text-amber-600 transition-colors" title="تعديل">
                              <Pencil size={16} />
                            </button>
                            <button onClick={() => setDeleting(f)} className="p-1.5 rounded-lg hover:bg-red-50 text-red-500 transition-colors" title="حذف">
                              <Trash2 size={16} />
                            </button>
                          </div>
                        </Td>
                      </Tr>
                    ))}
                  </tbody>
                </Table>
              </div>
              <Pagination page={page} totalPages={totalPages} onChange={setPage} count={data.count} pageSize={pageSize} />
            </>
          )}
        </Card>

        <Modal open={modalOpen} onClose={() => setModalOpen(false)} title="إضافة قماش جديد" maxWidth="max-w-2xl">
          <FabricForm onSubmit={handleCreate} onCancel={() => setModalOpen(false)} />
        </Modal>

        <Modal open={!!editing} onClose={() => setEditing(null)} title="تعديل القماش" maxWidth="max-w-2xl">
          {editing && <FabricForm initial={editing} onSubmit={handleUpdate} onCancel={() => setEditing(null)} />}
        </Modal>

        <Modal open={!!details} onClose={() => setDetails(null)} title={details ? `${details.name} — التفاصيل والمخزون` : ''} maxWidth="max-w-2xl">
          {details && (
            <div className="space-y-4">
              <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
                <div className="rounded-xl bg-sand-50 border border-sand-200 p-3">
                  <p className="text-xs text-neutral-500 mb-1">الكود</p>
                  <p className="text-sm font-mono font-semibold">{details.code}</p>
                </div>
                <div className="rounded-xl bg-sand-50 border border-sand-200 p-3">
                  <p className="text-xs text-neutral-500 mb-1">الوحدة</p>
                  <p className="text-sm font-semibold">{UNIT_LABEL[details.unit] || details.unit}</p>
                </div>
                <div className="rounded-xl bg-sand-50 border border-sand-200 p-3">
                  <p className="text-xs text-neutral-500 mb-1">ياردات الطاقة</p>
                  <p className="text-sm font-semibold tabular-nums">{details.yards_per_roll != null ? formatNumber(details.yards_per_roll) : '-'}</p>
                </div>
                <div className="rounded-xl bg-sand-50 border border-sand-200 p-3">
                  <p className="text-xs text-neutral-500 mb-1">تكلفة الشراء</p>
                  <p className="text-sm font-semibold tabular-nums">{formatCurrency(details.purchase_price)}</p>
                </div>
                <div className="rounded-xl bg-sand-50 border border-sand-200 p-3">
                  <p className="text-xs text-neutral-500 mb-1">سعر بيع الياردة</p>
                  <p className="text-sm font-semibold tabular-nums">{formatCurrency(details.sale_price_yard)}</p>
                </div>
                <div className="rounded-xl bg-sand-50 border border-sand-200 p-3">
                  <p className="text-xs text-neutral-500 mb-1">سعر بيع الطاقة</p>
                  <p className="text-sm font-semibold tabular-nums">{details.sale_price_roll_display != null ? formatCurrency(details.sale_price_roll_display) : '-'}</p>
                </div>
                <div className="rounded-xl bg-sand-50 border border-sand-200 p-3">
                  <p className="text-xs text-neutral-500 mb-1">حد أدنى ياردة</p>
                  <p className="text-sm font-semibold tabular-nums">{formatCurrency(details.min_sale_yard)}</p>
                </div>
                <div className="rounded-xl bg-sand-50 border border-sand-200 p-3">
                  <p className="text-xs text-neutral-500 mb-1">حد أدنى طاقة</p>
                  <p className="text-sm font-semibold tabular-nums">{details.min_sale_roll_display != null ? formatCurrency(details.min_sale_roll_display) : '-'}</p>
                </div>
                <div className="rounded-xl bg-sand-50 border border-sand-200 p-3">
                  <p className="text-xs text-neutral-500 mb-1">هامش الربح</p>
                  <p className={`text-sm font-semibold tabular-nums ${details.profit_margin_pct >= 0 ? 'text-emerald-600' : 'text-red-500'}`}>
                    {details.profit_margin_pct ? `${details.profit_margin_pct.toFixed(1)}%` : '-'}
                  </p>
                </div>
              </div>

              {details.barcode || details.fabric_type || details.color || details.composition ? (
                <div className="rounded-xl border border-sand-200 divide-y divide-sand-200">
                  {details.barcode && (
                    <div className="px-4 py-2 flex items-center justify-between">
                      <span className="text-sm text-neutral-500">الباركود</span>
                      <span className="text-sm font-mono">{details.barcode}</span>
                    </div>
                  )}
                  {details.fabric_type && (
                    <div className="px-4 py-2 flex items-center justify-between">
                      <span className="text-sm text-neutral-500">النوع</span>
                      <span className="text-sm">{details.fabric_type}</span>
                    </div>
                  )}
                  {details.color && (
                    <div className="px-4 py-2 flex items-center justify-between">
                      <span className="text-sm text-neutral-500">اللون</span>
                      <span className="text-sm">{details.color}</span>
                    </div>
                  )}
                  {details.composition && (
                    <div className="px-4 py-2 flex items-center justify-between">
                      <span className="text-sm text-neutral-500">التركيبة</span>
                      <span className="text-sm">{details.composition}</span>
                    </div>
                  )}
                  {details.width_cm != null && (
                    <div className="px-4 py-2 flex items-center justify-between">
                      <span className="text-sm text-neutral-500">العرض</span>
                      <span className="text-sm tabular-nums">{details.width_cm} سم</span>
                    </div>
                  )}
                  {details.weight_gsm != null && (
                    <div className="px-4 py-2 flex items-center justify-between">
                      <span className="text-sm text-neutral-500">الوزن</span>
                      <span className="text-sm tabular-nums">{details.weight_gsm} جم/م²</span>
                    </div>
                  )}
                  {details.origin && (
                    <div className="px-4 py-2 flex items-center justify-between">
                      <span className="text-sm text-neutral-500">بلد المنشأ</span>
                      <span className="text-sm">{details.origin}</span>
                    </div>
                  )}
                  {details.manufacturer && (
                    <div className="px-4 py-2 flex items-center justify-between">
                      <span className="text-sm text-neutral-500">الشركة المصنعة</span>
                      <span className="text-sm">{details.manufacturer}</span>
                    </div>
                  )}
                  {details.supplier_name && (
                    <div className="px-4 py-2 flex items-center justify-between">
                      <span className="text-sm text-neutral-500">المورد</span>
                      <span className="text-sm">{details.supplier_name}</span>
                    </div>
                  )}
                </div>
              ) : null}

              <div className="rounded-xl bg-sand-50 border border-sand-200 p-4">
                <div className="flex items-center gap-2 mb-3">
                  <Package size={18} className="text-brand-600" />
                  <h4 className="text-sm font-bold text-neutral-800">المخزون حسب المخازن</h4>
                </div>
                {stockLoading ? (
                  <div className="flex justify-center py-6"><Spinner size={24} /></div>
                ) : !stock || stock.items.length === 0 ? (
                  <p className="text-sm text-neutral-400">لا توجد طاقات متاحة لهذا القماش</p>
                ) : (
                  <>
                    <div className="divide-y divide-sand-200">
                      {stock.items.map((it) => (
                        <div key={it.warehouse} className="py-2.5 flex items-center justify-between">
                          <div>
                            <p className="text-sm font-medium text-neutral-700">{it.warehouse_name}</p>
                            <p className="text-xs text-neutral-400 tabular-nums">{it.rolls} طاقة • {formatNumber(it.yards)} ياردة</p>
                          </div>
                          <span className="text-sm text-neutral-500 tabular-nums">{formatCurrency(it.cost_value)}</span>
                        </div>
                      ))}
                    </div>
                    <div className="mt-3 pt-3 border-t border-sand-200 flex items-center justify-between">
                      <span className="text-sm font-medium text-neutral-700">الإجمالي</span>
                      <div className="text-left">
                        <p className="text-sm font-bold text-neutral-800 tabular-nums">{stock.totals.rolls} طاقة • {formatNumber(stock.totals.yards)} ياردة</p>
                        <p className="text-xs text-neutral-500 tabular-nums">قيمة التكلفة: {formatCurrency(stock.totals.cost_value)}</p>
                      </div>
                    </div>
                  </>
                )}
              </div>
            </div>
          )}
        </Modal>

        <ConfirmDialog
          open={!!deleting}
          onClose={() => setDeleting(null)}
          onConfirm={handleDelete}
          loading={deleteLoading}
          message={`هل أنت متأكد من حذف قماش "${deleting?.name}"؟ لا يمكن التراجع عن هذا الإجراء.${(deleting?.total_rolls ?? 0) > 0 ? ' ملاحظة: إذا كان للقماش طاقات أو مشتريات أو مبيعات أو حركات مرتبطة، فلن يسمح النظام بحذفه حفاظاً على السجل المالي، ويمكنك إيقافه بدلاً من ذلك من خلال التعديل وتحديد الحالة «غير نشط».' : ''}`}
        />

        <Modal open={bulkOpen} onClose={() => setBulkOpen(false)} title="تعديل أسعار بالجملة" maxWidth="max-w-lg">
          <div className="space-y-4">
            <p className="text-sm text-neutral-500">
              يُطبق التعديل على الأقمشة الظاهرة بالفلتر الحالي. يمكنك تضييق النطاق أولاً بالبحث أو الفلاتر ثم فتح هذه النافذة.
            </p>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="text-xs font-medium text-neutral-500 block mb-1">الحقل</label>
                <Select
                  value={bulkForm.field}
                  options={[
                    { value: 'sale_price_yard', label: 'سعر بيع الياردة' },
                    { value: 'purchase_price', label: 'تكلفة الشراء' },
                    { value: 'min_sale_yard', label: 'الحد الأدنى للبيع' },
                  ]}
                  onChange={(e) => setBulkForm({ ...bulkForm, field: e.target.value as typeof bulkForm.field })}
                />
              </div>
              <div>
                <label className="text-xs font-medium text-neutral-500 block mb-1">نوع التعديل</label>
                <Select
                  value={bulkForm.mode}
                  options={[
                    { value: 'percent', label: 'نسبة %' },
                    { value: 'fixed', label: 'مبلغ ثابت' },
                  ]}
                  onChange={(e) => setBulkForm({ ...bulkForm, mode: e.target.value as typeof bulkForm.mode })}
                />
              </div>
              <div>
                <label className="text-xs font-medium text-neutral-500 block mb-1">الاتجاه</label>
                <Select
                  value={bulkForm.direction}
                  options={[
                    { value: 'increase', label: 'زيادة' },
                    { value: 'decrease', label: 'نقصان' },
                  ]}
                  onChange={(e) => setBulkForm({ ...bulkForm, direction: e.target.value as typeof bulkForm.direction })}
                />
              </div>
              <div>
                <label className="text-xs font-medium text-neutral-500 block mb-1">
                  {bulkForm.mode === 'percent' ? 'النسبة %' : 'المبلغ'}
                </label>
                <input
                  type="number"
                  min="0"
                  step={bulkForm.mode === 'percent' ? '0.1' : '0.001'}
                  value={bulkForm.value}
                  onChange={(e) => setBulkForm({ ...bulkForm, value: e.target.value })}
                  className="w-full rounded-xl border border-sand-300 bg-surface px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500/40"
                  placeholder={bulkForm.mode === 'percent' ? 'مثال: 10' : 'مثال: 0.500'}
                />
              </div>
            </div>
            <div className="flex justify-start gap-3 pt-2">
              <Button onClick={handleBulkUpdate} loading={bulkLoading}>
                <TrendingUp size={16} />
                تطبيق التعديل
              </Button>
              <Button variant="secondary" onClick={() => setBulkOpen(false)}>إلغاء</Button>
            </div>
          </div>
        </Modal>
      </div>
    </AppShell>
  );
}