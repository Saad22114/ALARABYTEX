'use client';

import { useState, useEffect, useCallback, useMemo } from 'react';
import AppShell from '@/components/layout/AppShell';
import Card from '@/components/ui/Card';
import Button from '@/components/ui/Button';
import Table, { Th, Td, Tr } from '@/components/ui/Table';
import Input from '@/components/ui/Input';
import Select from '@/components/ui/Select';
import Textarea from '@/components/ui/Textarea';
import Switch from '@/components/ui/Switch';
import SearchInput from '@/components/ui/SearchInput';
import Pagination from '@/components/ui/Pagination';
import Modal from '@/components/ui/Modal';
import ConfirmDialog from '@/components/ui/ConfirmDialog';
import Badge from '@/components/ui/Badge';
import EmptyState from '@/components/ui/EmptyState';
import Spinner from '@/components/ui/Spinner';
import {
  Plus, ClipboardCheck, CheckCircle2, Ban, EyeOff, Trash2, PackagePlus,
} from 'lucide-react';
import {
  StockCount,
  StockCountListItem,
  Paginated,
  Warehouse,
  CountItem,
  CountStatus,
  CountSummary,
  Fabric,
  Employee,
} from '@/types';
import {
  listCounts, createCount, getCount, updateCountItems, postCount, cancelCount,
  addCountFabric, removeCountItem, listWarehouses,
} from '@/services/warehouses';
import { listFabrics } from '@/services/fabrics';
import { listEmployees } from '@/services/employees';
import { API_URL, downloadBlob } from '@/services/api';
import { useToast } from '@/components/ui/Toast';
import { useSettings } from '@/components/providers/SettingsProvider';
import { useUrlState } from '@/lib/useUrlState';
import { formatNumber } from '@/lib/format';
import {
  countedDifference, dirtyFabrics as computeDirty, progressPercent,
  rowStatus, ROW_STATUS_LABEL, type DraftMap,
} from '@/lib/counts';

const STATUS_VARIANT: Record<CountStatus, 'success' | 'warning' | 'danger' | 'neutral'> = {
  open: 'warning',
  posted: 'success',
  cancelled: 'neutral',
};

/** القيم المُدخلة للصفوف: نصٌّ ليُحفظ كما رُسم، لا رقمٌ يفقد الفراغَ معناه. */
type Draft = DraftMap;

function emptyDraft(item: Pick<CountItem, 'counted_yards' | 'note'>) {
  return {
    yards:
      item.counted_yards === null || item.counted_yards === undefined
        ? ''
        : String(item.counted_yards),
    note: item.note || '',
  };
}

function draftOf(count: StockCount): Draft {
  return count.items.reduce<Draft>((acc, item) => {
    acc[item.fabric] = emptyDraft(item);
    return acc;
  }, {});
}

function ProgressBar({ summary }: { summary: CountSummary }) {
  const pct = progressPercent(summary);
  return (
    <div className="min-w-[120px]">
      <div className="h-2 rounded-full bg-sand-200 overflow-hidden" role="progressbar" aria-valuenow={pct} aria-valuemin={0} aria-valuemax={100}>
        <div className={`h-full rounded-full transition-all ${pct === 100 ? 'bg-emerald-500' : 'bg-brand-500'}`} style={{ width: `${pct}%` }} />
      </div>
      <p className="text-xs text-neutral-500 mt-1 tabular-nums">
        {formatNumber(summary.counted)} من {formatNumber(summary.items)}
        {summary.pending > 0 && <span className="text-neutral-400"> — بقي {formatNumber(summary.pending)}</span>}
      </p>
    </div>
  );
}

function VarianceBadge({ summary }: { summary: CountSummary }) {
  if (summary.variances === 0) {
    return <span className="text-xs text-neutral-400">لا فروق</span>;
  }
  return (
    <Badge variant="warning">
      {formatNumber(summary.variances)} صنف — {summary.net_yards > 0 ? '+' : ''}{formatNumber(summary.net_yards)} ياردة
    </Badge>
  );
}

function NewCountForm({
  warehouses,
  employees,
  onSubmit,
  loading,
}: {
  warehouses: Warehouse[];
  employees: Employee[];
  onSubmit: (d: { warehouse: number; date: string; notes: string; blind: boolean; counted_by: number | null }) => void;
  loading: boolean;
}) {
  const [warehouse, setWarehouse] = useState<number | undefined>(warehouses[0]?.id);
  const [date, setDate] = useState(new Date().toISOString().slice(0, 10));
  const [notes, setNotes] = useState('');
  const [counter, setCounter] = useState<number | ''>('');
  // الجرد المغلق هو ما يجعل الجرد جرداً. من يفتح جلسة يريد عدّاً لا مطابقة،
  // والرصيدُ الدفتري أمام عين العدّاد يجعله يعدّ ليصل إليه لا ليقيس ما رآه.
  const [blind, setBlind] = useState(true);

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        if (!warehouse) return;
        onSubmit({ warehouse, date, notes, blind, counted_by: counter === '' ? null : Number(counter) });
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
      <div>
        <label className="block text-sm font-medium text-neutral-700 mb-1">العدّاد</label>
        <Select
          value={counter}
          onChange={(e) => setCounter(e.target.value === '' ? '' : Number(e.target.value))}
          options={[{ value: '', label: 'غير محدّد' }, ...employees.map((e) => ({ value: e.id, label: e.name }))]}
        />
        <p className="text-xs text-neutral-400 mt-1">جردٌ بلا اسم يعني عملياً: لا أحد مسؤول عنه.</p>
      </div>
      <div className="rounded-xl border border-sand-200 bg-sand-50 p-4">
        <div className="flex items-start justify-between gap-4">
          <div className="min-w-0">
            <label className="block text-sm font-semibold text-neutral-800">جرد مغلق</label>
            <p className="text-xs text-neutral-600 mt-1 leading-relaxed">
              يُخفى الرصيد الدفتري عن العدّاد حتى ينتهي، فيقيس ما على الرفّ بلا
              مرجع. يكشفه النظام للمراجع بعد النشر. أطفئه إن أردت جرداً مفتوحاً
              يرى فيه العدّاد الفرق وهو يعدّ.
            </p>
          </div>
          <Switch checked={blind} onChange={setBlind} aria-label="جرد مغلق" />
        </div>
      </div>
      <div>
        <label className="block text-sm font-medium text-neutral-700 mb-1">ملاحظات</label>
        <Textarea value={notes} onChange={(e) => setNotes(e.target.value)} rows={2} placeholder="سبب فتح الجرد، أو أي توضيح" />
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
  const [data, setData] = useState<Paginated<StockCountListItem> | null>(null);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useUrlState('page', 1);
  const [modalOpen, setModalOpen] = useState(false);
  const [formLoading, setFormLoading] = useState(false);
  const [warehouses, setWarehouses] = useState<Warehouse[]>([]);
  const [employees, setEmployees] = useState<Employee[]>([]);

  const [working, setWorking] = useState<StockCount | null>(null);
  const [draft, setDraft] = useState<Draft>({});
  const [loadingCount, setLoadingCount] = useState(false);
  const [saveLoading, setSaveLoading] = useState(false);
  const [filter, setFilter] = useState('');
  const [fabrics, setFabrics] = useState<Fabric[]>([]);
  const [pickFabric, setPickFabric] = useState<number | ''>('');
  const [lineLoading, setLineLoading] = useState(false);
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
  }, [page, pageSize, toast]);

  useEffect(() => fetchData(), [fetchData]);

  useEffect(() => {
    listWarehouses({ page_size: 100 })
      .then((r) => setWarehouses(r.results.filter((w) => w.is_active)))
      .catch(() => {});
    listEmployees({ page_size: 200 })
      .then((r) => setEmployees(r.results.filter((e) => e.is_active)))
      .catch(() => {});
    listFabrics({ page_size: 300 })
      .then((r) => setFabrics(r.results.filter((f) => f.is_active)))
      .catch(() => {});
  }, []);

  const totalPages = data ? Math.ceil(data.count / pageSize) : 1;

  const handleCreate = async (d: { warehouse: number; date: string; notes: string; blind: boolean; counted_by: number | null }) => {
    setFormLoading(true);
    try {
      const r = await createCount(d);
      toast('success', `تم بدء جلسة الجرد ${r.number}`);
      setModalOpen(false);
      fetchData();
      openWork(r);
    } catch (err: any) {
      toast('error', err.message);
    } finally {
      setFormLoading(false);
    }
  };

  /** يفتح الجلسة على الشاشة: القائمة لا تحمل أصنافها، فالتفصيل يُطلب وحده. */
  const openWork = async (row: StockCountListItem | StockCount) => {
    setLoadingCount(true);
    setFilter('');
    try {
      const full = 'items' in row && Array.isArray((row as StockCount).items)
        ? (row as StockCount)
        : await getCount(row.id);
      setWorking(full);
      setDraft(draftOf(full));
    } catch (err: any) {
      toast('error', err.message);
    } finally {
      setLoadingCount(false);
    }
  };

  /**
   * دمج الحقول يخلط الجديدَ بالقديم: `{ ...old, ...patch }` يجعل قيمةً
   * فارغةً في `patch` تسقط ما كان محفوظاً. الفراغُ هنا معناه «امسح» في
   * حقل السبب، و«لم يُعدّ» في حقل الرصيد — وكلاهما مقصود.
   */
  const setCell = (fabric: number, patch: Partial<{ yards: string; note: string }>) =>
    setDraft((prev) => ({ ...prev, [fabric]: { ...(prev[fabric] || { yards: '', note: '' }), ...patch } }));

  const dirty = useMemo(
    () => (working ? computeDirty(working.items, draft) : []),
    [working, draft],
  );

  const updateWorking = async () => {
    if (!working) return;
    if (dirty.length === 0) {
      toast('info', 'لا تغييرات لحفظها');
      return;
    }
    setSaveLoading(true);
    try {
      const items = dirty.map((fabric) => {
        const cell = draft[fabric];
        const yards = cell?.yards.trim() ?? '';
        return {
          fabric,
          // السطر الفارغ «لم يُعدّ» لا «رصيده صفر»؛这也是 سبب تمرير نص.
          counted_yards: yards === '' ? null : Number(yards),
          note: cell?.note ?? '',
        };
      });
      await updateCountItems(working.id, items);
      const fresh = await getCount(working.id);
      setWorking(fresh);
      setDraft(draftOf(fresh));
      toast('success', `تم حفظ ${items.length} سطر`);
      fetchData();
    } catch (err: any) {
      toast('error', err.message);
    } finally {
      setSaveLoading(false);
    }
  };

  const runAddFabric = async () => {
    if (!working || pickFabric === '') return;
    setLineLoading(true);
    try {
      const fresh = await addCountFabric(working.id, Number(pickFabric));
      setWorking(fresh);
      setDraft(draftOf(fresh));
      setPickFabric('');
      toast('success', 'أُضيف القماش إلى الجرد');
      fetchData();
    } catch (err: any) {
      toast('error', err.message);
    } finally {
      setLineLoading(false);
    }
  };

  const runRemoveItem = async (item: CountItem) => {
    if (!working) return;
    setLineLoading(true);
    try {
      const fresh = await removeCountItem(working.id, item.id);
      setWorking(fresh);
      setDraft(draftOf(fresh));
      toast('success', 'أُزيل السطر');
      fetchData();
    } catch (err: any) {
      toast('error', err.message);
    } finally {
      setLineLoading(false);
    }
  };

  const runExport = async () => {
    if (!working) return;
    try {
      await downloadBlob(`${API_URL}/warehouses/counts/${working.id}/export/`, 'جرد.xlsx');
    } catch (err: any) {
      toast('error', err.message);
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

  const visibleItems = useMemo(() => {
    if (!working) return [];
    const needle = filter.trim();
    if (!needle) return working.items;
    return working.items.filter((item) =>
      item.fabric_name.includes(needle) || (item.fabric_code || '').toLowerCase().includes(needle.toLowerCase()),
    );
  }, [working, filter]);

  const addableFabrics = useMemo(() => {
    if (!working) return [];
    const present = new Set(working.items.map((i) => i.fabric));
    return fabrics.filter((f) => !present.has(f.id));
  }, [fabrics, working]);

  return (
    <AppShell>
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-xl font-bold text-neutral-800">جرد المخزون</h1>
            <p className="text-sm text-neutral-500">
              جردٌ مغلق يقيس ما على الرفّ بلا أن يرى الدفتر، ثم يكشف الفرق للمراجعة بعد النشر
            </p>
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
                    <Th>العدّاد</Th>
                    <Th>التقدّم</Th>
                    <Th>الفروق</Th>
                    <Th>الحالة</Th>
                    <Th>إجراءات</Th>
                  </tr>
                </thead>
                <tbody>
                  {data.results.map((c) => (
                    <Tr key={c.id}>
                      <Td>
                        <span className="font-mono text-xs bg-sand-100 px-2 py-1 rounded" dir="ltr">{c.number}</span>
                        {c.blind && (
                          <span className="inline-flex items-center gap-1 text-[11px] text-neutral-500 mr-2" title="جرد مغلق: الرصيد الدفتري مخفيّ أثناء العدّ">
                            <EyeOff size={12} />
                            مغلق
                          </span>
                        )}
                      </Td>
                      <Td>{c.warehouse_name}</Td>
                      <Td className="tabular-nums">{c.date}</Td>
                      <Td>{c.counted_by_name || <span className="text-neutral-400">—</span>}</Td>
                      <Td><ProgressBar summary={c.summary} /></Td>
                      <Td>
                        <VarianceBadge summary={c.summary} />
                        {c.summary.value !== 0 && (
                          <p className="text-[11px] text-neutral-400 mt-0.5 tabular-nums">
                            بقيمة {formatNumber(c.summary.value)}
                          </p>
                        )}
                      </Td>
                      <Td><Badge variant={STATUS_VARIANT[c.status]}>{c.status_label}</Badge></Td>
                      <Td>
                        <div className="flex gap-1">
                          {c.status === 'open' ? (
                            <>
                              <button onClick={() => openWork(c)} className="p-2 rounded-lg text-brand-600 hover:bg-brand-50" title="إدخال الرصيد الفعلي">
                                <ClipboardCheck size={16} />
                              </button>
                              <button onClick={() => setConfirm({ count: { ...c, items: [] }, type: 'post' })} className="p-2 rounded-lg text-emerald-600 hover:bg-emerald-50" title="نشر الجرد">
                                <CheckCircle2 size={16} />
                              </button>
                              <button onClick={() => setConfirm({ count: { ...c, items: [] }, type: 'cancel' })} className="p-2 rounded-lg text-neutral-500 hover:bg-red-50 hover:text-red-600" title="إلغاء">
                                <Ban size={16} />
                              </button>
                            </>
                          ) : (
                            <button onClick={() => openWork(c)} className="p-2 rounded-lg text-brand-600 hover:bg-brand-50" title="عرض الجرد">
                              <ClipboardCheck size={16} />
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

      <Modal open={modalOpen} onClose={() => setModalOpen(false)} title="بدء جلسة جرد">
        <NewCountForm warehouses={warehouses} employees={employees} onSubmit={handleCreate} loading={formLoading} />
      </Modal>

      <Modal
        open={!!working || loadingCount}
        onClose={() => { if (!loadingCount) { setWorking(null); setDraft({}); } }}
        title={working ? `جرد ${working.number} — ${working.warehouse_name}` : ''}
        maxWidth="max-w-5xl"
      >
        {loadingCount && !working ? (
          <div className="flex justify-center py-12"><Spinner size={32} /></div>
        ) : working && (
          <div className="space-y-4">
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
              <Tile label="أصناف الجلسة" value={formatNumber(working.summary.items)} />
              <Tile label="مُرصد" value={formatNumber(working.summary.counted)} tone={working.summary.complete ? 'good' : 'plain'} />
              <Tile label="بقي" value={formatNumber(working.summary.pending)} tone={working.summary.pending ? 'warn' : 'plain'} />
              <Tile
                label="صافي الفروق"
                value={`${working.summary.net_yards > 0 ? '+' : ''}${formatNumber(working.summary.net_yards)}`}
                sub={`${formatNumber(working.summary.variances)} صنف · بقيمة ${formatNumber(working.summary.value)}`}
                tone={working.summary.variances ? 'warn' : 'plain'}
              />
            </div>

            <div className="flex items-center gap-3 flex-wrap">
              <div className="flex-1 min-w-[200px]">
                <SearchInput value={filter} onChange={setFilter} placeholder="بحث باسم القماش أو كوده" />
              </div>
              <Button variant="secondary" size="sm" onClick={runExport}>تصدير ورقة الجرد</Button>
            </div>

            {working.blind && (
              <p className="text-xs text-neutral-500 bg-sand-50 rounded-xl p-3">
                هذا جردٌ مغلق: الرصيد الدفتري والفرق مخفيّان حتى النشر. الفرق يظهر للمراجع
                في حركة المخزون وفي ورقة الفروق بعد النشر.
              </p>
            )}

            {working.status === 'open' && addableFabrics.length > 0 && (
              <div className="flex items-end gap-2 p-3 rounded-xl border border-dashed border-sand-300 bg-sand-50">
                <div className="flex-1">
                  <label className="block text-sm font-medium text-neutral-700 mb-1">
                    قماشٌ وُجد على الرفّ ولا يشمله الجرد
                  </label>
                  <Select
                    value={pickFabric}
                    onChange={(e) => setPickFabric(e.target.value === '' ? '' : Number(e.target.value))}
                    options={[{ value: '', label: 'اختر القماش...' }, ...addableFabrics.map((f) => ({ value: f.id, label: f.code ? `${f.name} (${f.code})` : f.name }))]}
                  />
                </div>
                <Button onClick={runAddFabric} disabled={pickFabric === ''} loading={lineLoading}>
                  <PackagePlus size={16} />
                  أضف سطراً
                </Button>
              </div>
            )}

            <div className="border border-sand-200 rounded-xl overflow-hidden">
              <Table>
                <thead>
                  <tr>
                    <Th>القماش</Th>
                    <Th>الرصيد الدفتري</Th>
                    <Th>الرصيد المرصود</Th>
                    <Th>الفرق</Th>
                    <Th>الحالة</Th>
                    <Th>سبب الفرق</Th>
                    {working.status === 'open' && <Th><span className="sr-only">حذف</span></Th>}
                  </tr>
                </thead>
                <tbody>
                  {visibleItems.length === 0 ? (
                    <Tr>
                      <Td>لا نتائج</Td>
                    </Tr>
                  ) : (
                    visibleItems.map((it: CountItem) => {
                      const cell = draft[it.fabric];
                      const diff = countedDifference(it, cell?.yards);
                      const status = rowStatus(it, cell?.yards);
                      const editable = working.status === 'open';
                      return (
                        <Tr key={it.id}>
                          <Td>
                            <span className="font-medium">{it.fabric_name}</span>
                            {it.fabric_code && (
                              <span className="font-mono text-[11px] text-neutral-400 mr-2" dir="ltr">{it.fabric_code}</span>
                            )}
                          </Td>
                          <Td className="tabular-nums">
                            {it.system_yards === undefined ? (
                              <span className="text-neutral-400" title="مخفيّ في الجرد المغلق">— مخفيّ</span>
                            ) : (
                              formatNumber(Number(it.system_yards))
                            )}
                          </Td>
                          <Td width={140}>
                            <Input
                              type="number"
                              min={0}
                              step="0.01"
                              disabled={!editable}
                              value={cell?.yards ?? ''}
                              onChange={(e) => setCell(it.fabric, { yards: e.target.value })}
                              placeholder="الفعلي"
                            />
                          </Td>
                          <Td>
                            {diff === null ? (
                              <span className="text-neutral-400">—</span>
                            ) : (
                              <span className={`tabular-nums font-medium ${diff > 0 ? 'text-emerald-700' : diff < 0 ? 'text-red-600' : 'text-neutral-400'}`}>
                                {diff > 0 ? '+' : ''}{formatNumber(diff)}
                              </span>
                            )}
                          </Td>
                          <Td>
                            {status === 'variance' ? (
                              <Badge variant="warning">{ROW_STATUS_LABEL.variance}</Badge>
                            ) : (
                              <span className="text-xs text-neutral-400">{ROW_STATUS_LABEL[status]}</span>
                            )}
                          </Td>
                          <Td width={200}>
                            <Input
                              disabled={!editable}
                              value={cell?.note ?? ''}
                              onChange={(e) => setCell(it.fabric, { note: e.target.value })}
                              placeholder="قصاصة، تلف، خطأ إدخال..."
                            />
                          </Td>
                          {working.status === 'open' && (
                            <Td>
                              <button
                                onClick={() => runRemoveItem(it)}
                                disabled={lineLoading}
                                className="p-2 rounded-lg text-neutral-400 hover:bg-red-50 hover:text-red-600 disabled:opacity-40"
                                title="أزل هذا السطر من الجرد"
                              >
                                <Trash2 size={16} />
                              </button>
                            </Td>
                          )}
                        </Tr>
                      );
                    })
                  )}
                </tbody>
              </Table>
            </div>

            <div className="flex justify-end gap-3">
              <Button variant="secondary" onClick={() => { setWorking(null); setDraft({}); }}>إغلاق</Button>
              {working.status === 'open' && (
                <>
                  <Button variant="ghost" onClick={() => setConfirm({ count: working, type: 'cancel' })}>إلغاء الجلسة</Button>
                  <Button onClick={updateWorking} loading={saveLoading} disabled={dirty.length === 0}>
                    <CheckCircle2 size={16} />
                    حفظ {dirty.length > 0 ? `(${dirty.length})` : ''}
                  </Button>
                  <Button variant="secondary" onClick={() => setConfirm({ count: working, type: 'post' })} disabled={!working.summary.complete}>
                    نشر الجرد
                  </Button>
                </>
              )}
            </div>
            {working.status === 'open' && !working.summary.complete && (
              <p className="text-xs text-amber-700 bg-amber-50 rounded-xl p-3 text-center">
                لا يمكن النشر قبل رصد كل الأصناف: بقي {formatNumber(working.summary.pending)} بلا رصد.
              </p>
            )}
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

function Tile({
  label,
  value,
  sub,
  tone,
}: {
  label: string;
  value: string;
  sub?: string;
  tone?: 'plain' | 'good' | 'warn';
}) {
  const color =
    tone === 'good' ? 'text-emerald-700' : tone === 'warn' ? 'text-amber-700' : 'text-neutral-800';
  return (
    <div className="rounded-xl border border-sand-200 bg-surface p-3">
      <p className="text-xs text-neutral-500">{label}</p>
      <p className={`text-lg font-bold tabular-nums ${color}`}>{value}</p>
      {sub && <p className="text-[11px] text-neutral-400 tabular-nums">{sub}</p>}
    </div>
  );
}