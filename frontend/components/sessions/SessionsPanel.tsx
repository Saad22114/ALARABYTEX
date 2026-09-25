'use client';

import { useState, useEffect, useMemo, useCallback } from 'react';
import Card from '@/components/ui/Card';
import Button from '@/components/ui/Button';
import Table, { Th, Td, Tr } from '@/components/ui/Table';
import Select from '@/components/ui/Select';
import Input from '@/components/ui/Input';
import QuantityQuickPicks from '@/components/sessions/QuantityQuickPicks';
import FinalAmountInput from '@/components/sessions/FinalAmountInput';
import Modal from '@/components/ui/Modal';
import ConfirmDialog from '@/components/ui/ConfirmDialog';
import EmptyState from '@/components/ui/EmptyState';
import Spinner from '@/components/ui/Spinner';
import Badge from '@/components/ui/Badge';
import StatCard from '@/components/ui/StatCard';
import { Plus, Trash2, Pencil, LogIn, CircleDollarSign, RefreshCcw, Users, Package, Layers, Eye, Search, Move, TriangleAlert, Printer, FileText, Undo2 } from 'lucide-react';
import {
  SaleSession, Employee, Fabric, Branch, SessionSaleItem,
  SessionSaleType, SessionPaymentMethod, SessionCardType, SaleSessionSummary, SaleStockResult,
} from '@/types';
import {
  listEmployees,
  listSaleSessions,
  openSaleSession,
  addSessionItem,
  addSessionItems,
  removeSessionItem,
  closeSaleSession,
  deleteSaleSession,
  getSaleSessionSummary,
} from '@/services/sessions';
import { listFabrics } from '@/services/fabrics';
import { listBranches } from '@/services/branches';
import { getSaleStock } from '@/services/sales';
import SessionItemEditModal from '@/components/sessions/SessionItemEditModal';
import SessionDetailsModal from '@/components/sessions/SessionDetailsModal';
import SessionEditModal from '@/components/sessions/SessionEditModal';
import CloseSessionModal from '@/components/sessions/CloseSessionModal';
import MoveItemModal from '@/components/sessions/MoveItemModal';
import SessionCustomerInvoiceModal from '@/components/sessions/SessionCustomerInvoiceModal';
import CustomerSalesReturnModal from '@/components/sessions/CustomerSalesReturnModal';
import CustomerPicker from '@/components/sessions/CustomerPicker';
import { saveContact } from '@/lib/customerContacts';
import { ensureCustomer } from '@/lib/registerCustomer';
import { rollSaleAllowed } from '@/lib/fabrics';
import { useSettings } from '@/components/providers/SettingsProvider';
import { useAuth } from '@/components/providers/AuthProvider';
import { toEmployee } from '@/lib/sessionEmployee';
import { formatCurrency, formatDate, formatNumber } from '@/lib/format';
import { todayISO } from '@/lib/date';
import { printSessionReceipt } from '@/lib/receipt';
import { useToast } from '@/components/ui/Toast';
import Link from 'next/link';

const PAYMENT_OPTIONS = [
  { value: 'cash', label: 'كاش' },
  { value: 'transfer', label: 'تحويل' },
  { value: 'card', label: 'ماكينة' },
];

const CARD_TYPE_OPTIONS = [
  { value: 'credit', label: 'إئتماني / Credit' },
  { value: 'debit', label: 'خصم مباشر / Debit' },
];

interface ItemForm {
  fabric: number | null;
  sale_type: SessionSaleType;
  quantity: string;
  unit_price: string;
  discount: string;
  payment_method: SessionPaymentMethod;
  card_type: SessionCardType | '';
}

const emptyItemForm = (payment?: SessionPaymentMethod): ItemForm => ({ fabric: null, sale_type: 'yard', quantity: '3.5', unit_price: '', discount: '', payment_method: payment || 'cash', card_type: '' });

const defaultQuantityForType = (saleType: SessionSaleType): string => (saleType === 'roll' ? '1' : '3.5');

type SessionSortKey = 'newest' | 'oldest' | 'total' | 'employee';

const SORT_OPTIONS: { value: SessionSortKey; label: string }[] = [
  { value: 'newest', label: 'الأحدث فتحاً' },
  { value: 'oldest', label: 'الأقدم مدةً' },
  { value: 'total', label: 'الأعلى مبيعات' },
  { value: 'employee', label: 'باسم الموظف' },
];

const SALE_GROUP_COLORS = [
  'bg-brand-50 text-brand-700 border-brand-200',
  'bg-emerald-50 text-emerald-700 border-emerald-200',
  'bg-amber-50 text-amber-700 border-amber-200',
  'bg-sky-50 text-sky-700 border-sky-200',
  'bg-violet-50 text-violet-700 border-violet-200',
  'bg-rose-50 text-rose-700 border-rose-200',
];

function saleGroupBadges(items: SessionSaleItem[]): Map<string, { num: number; cls: string }> {
  const map = new Map<string, { num: number; cls: string }>();
  let i = 1;
  for (const it of items) {
    const g = it.sale_group || `single-${it.id}`;
    if (!map.has(g)) {
      map.set(g, { num: i, cls: SALE_GROUP_COLORS[(i - 1) % SALE_GROUP_COLORS.length] });
      i += 1;
    }
  }
  return map;
}

function elapsedText(minutes: number | null): string {
  if (minutes == null) return '';
  const m = Math.max(0, minutes);
  if (m < 60) return `منذ ${formatNumber(m)} دقيقة`;
  const h = Math.floor(m / 60);
  const r = m % 60;
  return r === 0 ? `منذ ${formatNumber(h)} ساعة` : `منذ ${formatNumber(h)} ساعة و ${formatNumber(r)} دقيقة`;
}

export default function SessionsPanel({ onChanged, onSaleGenerated }: { onChanged?: () => void; onSaleGenerated?: (session: SaleSession) => void }) {
  const { toast } = useToast();
  const { settings } = useSettings();
  const { session } = useAuth();
  const me = session?.employee;
  const isManager = Boolean(me && (me.role === 'admin' || me.role === 'supervisor'));

  const [employees, setEmployees] = useState<Employee[]>([]);
  const [fabrics, setFabrics] = useState<Fabric[]>([]);
  const [branches, setBranches] = useState<Branch[]>([]);
  const [sessions, setSessions] = useState<SaleSession[]>([]);
  const [summary, setSummary] = useState<SaleSessionSummary | null>(null);
  const [stock, setStock] = useState<SaleStockResult | null>(null);
  const [loading, setLoading] = useState(true);

  const [branchFilter, setBranchFilter] = useState('');
  const [search, setSearch] = useState('');
  const [sortBy, setSortBy] = useState<SessionSortKey>('newest');
  const [tick, setTick] = useState(() => Date.now());
  const [openingEmp, setOpeningEmp] = useState<number | null>(null);
  const [openingDate, setOpeningDate] = useState<string>(() => todayISO());
  const [opening, setOpening] = useState(false);
  const [selectedId, setSelectedId] = useState<number | null>(null);

  const [lines, setLines] = useState<ItemForm[]>(() => [emptyItemForm(settings?.default_payment_method)]);
  const [adding, setAdding] = useState(false);
  const [addOpen, setAddOpen] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [checked, setChecked] = useState<Set<number>>(new Set());
  const [invoiceSel, setInvoiceSel] = useState<number[] | null>(null);
  const [custName, setCustName] = useState('');
  const [custPhone, setCustPhone] = useState('');

  const [closing, setClosing] = useState<SaleSession | null>(null);
  const [closeLoading, setCloseLoading] = useState(false);
  const [movingItem, setMovingItem] = useState<{ session: SaleSession; item: SessionSaleItem } | null>(null);
  const [editingItem, setEditingItem] = useState<{ session: SaleSession; item: SessionSaleItem } | null>(null);
  const [viewing, setViewing] = useState<SaleSession | null>(null);
  const [editingSession, setEditingSession] = useState<SaleSession | null>(null);
  const [deletingSession, setDeletingSession] = useState<SaleSession | null>(null);
  const [deleteSessionLoading, setDeleteSessionLoading] = useState(false);
  const [deletingItem, setDeletingItem] = useState<SessionSaleItem | null>(null);
  const [deleteItemLoading, setDeleteItemLoading] = useState(false);
  const [customerSalesOpen, setCustomerSalesOpen] = useState(false);

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
    if (isManager) {
      listEmployees({ page_size: 100 })
        .then((res) => { if (!cancelled) setEmployees(res.results); })
        .catch(() => {});
    } else if (me) {
      setEmployees([toEmployee(me)]);
      setOpeningEmp((cur) => cur ?? me.id);
    }
    listFabrics({ page_size: 100 })
      .then((res) => { if (!cancelled) setFabrics(res.results); })
      .catch(() => {});
    listBranches({ page_size: 100 })
      .then((res) => { if (!cancelled) setBranches(res.results.filter((b) => b.is_active)); })
      .catch(() => {});
    return () => { cancelled = true; };
  }, [isManager, me]);

  useEffect(() => {
    if (!isManager && me?.branch) {
      setBranchFilter(String(me.branch));
    }
  }, [isManager, me?.branch]);

  useEffect(() => {
    const id = setInterval(() => {
      fetchSessions(true);
      fetchSummary();
    }, 60000);
    return () => clearInterval(id);
  }, [fetchSessions, fetchSummary]);

  const selected = useMemo(() => sessions.find((s) => s.id === selectedId) || null, [sessions, selectedId]);

  const saleFabrics = useMemo(
    () =>
      [...fabrics].sort((a, b) => {
        const diff = (b.sold_count ?? 0) - (a.sold_count ?? 0);
        if (diff !== 0) return diff;
        return a.name.localeCompare(b.name, 'ar');
      }),
    [fabrics],
  );

  useEffect(() => {
    setChecked(new Set());
  }, [selectedId]);

  useEffect(() => {
    const id = setInterval(() => setTick(Date.now()), 30000);
    return () => clearInterval(id);
  }, []);

  const liveMinutes = (s: SaleSession) => Math.floor((tick - new Date(s.opened_at).getTime()) / 60000);
  /** تاريخ الوردية المحاسبي إن كان مختلفاً عن يوم الفتح الفعلي (وردية بتاريخ سابق). */
  const backdatedLabel = (s: SaleSession): string | null => {
    if (!s.session_date) return null;
    const openedDay = new Date(s.opened_at);
    const openedISO = `${openedDay.getFullYear()}-${String(openedDay.getMonth() + 1).padStart(2, '0')}-${String(openedDay.getDate()).padStart(2, '0')}`;
    return s.session_date === openedISO ? null : formatDate(s.session_date);
  };
  const warnMinutes = (settings?.session_warn_hours ?? 2) * 60;
  const dangerMinutes = (settings?.session_danger_hours ?? 4) * 60;
  const agingLevel = (m: number) => (m >= dangerMinutes ? 'danger' : m >= warnMinutes ? 'warn' : 'ok');

  const filteredSessions = useMemo(() => {
    const q = search.trim().toLowerCase();
    const list = q
      ? sessions.filter(
          (s) =>
            s.employee_name.toLowerCase().includes(q) ||
            s.branch_name.toLowerCase().includes(q) ||
            String(s.id).includes(q)
        )
      : [...sessions];
    const sorted = [...list];
    switch (sortBy) {
      case 'employee':
        sorted.sort((a, b) => a.employee_name.localeCompare(b.employee_name, 'ar'));
        break;
      case 'total':
        sorted.sort((a, b) => b.totals.total - a.totals.total);
        break;
      case 'oldest':
        sorted.sort((a, b) => liveMinutes(b) - liveMinutes(a));
        break;
      default:
        sorted.sort((a, b) => liveMinutes(a) - liveMinutes(b));
    }
    return sorted;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sessions, search, sortBy]);

  const paymentParts = [
    { label: 'كاش', value: selected?.totals.cash ?? 0, cls: 'bg-emerald-500' },
    { label: 'تحويل', value: selected?.totals.transfer ?? 0, cls: 'bg-neutral-400' },
    { label: 'ماكينة', value: selected?.totals.card ?? 0, cls: 'bg-amber-500' },
  ];
  const paymentTotal = paymentParts.reduce((acc, p) => acc + p.value, 0);
  const paymentBar = paymentParts.filter((p) => p.value > 0).map((p) => ({
    ...p,
    pct: paymentTotal > 0 ? (p.value / paymentTotal) * 100 : 0,
  }));
  const selectedDiscount = selected?.items.reduce((acc, it) => acc + (it.discount_amount || 0), 0) ?? 0;

  useEffect(() => {
    let cancelled = false;
    if (!selected) { setStock(null); return; }
    getSaleStock(selected.branch)
      .then((res) => { if (!cancelled) setStock(res); })
      .catch(() => { if (!cancelled) setStock(null); });
    return () => { cancelled = true; };
  }, [selected]);

  const fabricAutoPrice = (line: ItemForm): number => {
    const fabric = fabrics.find((f) => f.id === line.fabric);
    if (!fabric) return 0;
    const base = Number(fabric.sale_price_yard) || 0;
    if (line.sale_type === 'roll') {
      if (fabric.sale_price_roll != null) return Number(fabric.sale_price_roll) || 0;
      return base * (Number(fabric.yards_per_roll) || 0);
    }
    return base;
  };

  const lineCalc = (line: ItemForm) => {
    const stockYards = line.fabric != null ? stock?.items.find((i) => i.fabric === line.fabric)?.yards : undefined;
    const pendingYards =
      line.fabric != null && selected
        ? selected.items
            .filter((i) => i.fabric === line.fabric)
            .reduce((s, i) => s + (i.yards_effective || 0), 0)
        : 0;
    const availableYards = stockYards === undefined ? undefined : Math.max(0, stockYards - pendingYards);
    const selectedFabric = line.fabric != null ? fabrics.find((f) => f.id === line.fabric) : undefined;
    const yardsPerRoll = Number(selectedFabric?.yards_per_roll) || 0;
    const availableUnit =
      availableYards === undefined
        ? null
        : line.sale_type === 'roll'
          ? yardsPerRoll > 0
            ? availableYards / yardsPerRoll
            : null
          : availableYards;
    const rollAllowed = rollSaleAllowed(selectedFabric, selected?.branch);
    const quantityNum = parseFloat(line.quantity);
    const priceNum = line.unit_price !== '' && !isNaN(parseFloat(line.unit_price)) ? parseFloat(line.unit_price) : 0;
    const subtotal = line.quantity.trim() !== '' && quantityNum > 0 && priceNum >= 0 ? quantityNum * priceNum : null;
    const discountNum = line.discount.trim() !== '' && !isNaN(parseFloat(line.discount)) ? parseFloat(line.discount) : 0;
    const netTotal = subtotal != null ? Math.max(0, subtotal - discountNum) : null;
    const discountExceeds = subtotal != null && discountNum > subtotal;
    const quantityExceeds = availableUnit !== null && !isNaN(quantityNum) && quantityNum > availableUnit;
    const feePercent =
      line.payment_method === 'card'
        ? line.card_type === 'debit'
          ? Number(settings?.card_debit_fee_percent ?? 0)
          : Number(settings?.card_credit_fee_percent ?? 0)
        : 0;
    const cardFee = netTotal != null && feePercent > 0 ? Math.round(netTotal * feePercent) / 100 : 0;
    const netAfterFee = netTotal != null ? netTotal - cardFee : null;
    return { selectedFabric, availableUnit, rollAllowed, quantityNum, priceNum, subtotal, discountNum, netTotal, netAfterFee, feePercent, cardFee, discountExceeds, quantityExceeds };
  };

  const linesTotal = lines.reduce((sum, l) => {
    const c = lineCalc(l);
    return sum + (c.netAfterFee ?? 0);
  }, 0);

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
    if (!openingDate) {
      toast('error', 'حدد تاريخ الوردية');
      return;
    }
    if (openingDate > todayISO()) {
      toast('error', 'لا يمكن فتح وردية بتاريخ مستقبلي');
      return;
    }
    setOpening(true);
    try {
      const s = await openSaleSession(openingEmp, openingDate);
      const dateLabel = openingDate === todayISO() ? 'اليوم' : `بتاريخ ${formatDate(openingDate)}`;
      toast('success', s.reopened ? `تم إعادة فتح وردية ${dateLabel} للموظف ${s.employee_name}` : `تمت فتح الوردية ${dateLabel} للموظف ${s.employee_name}`);
      if (isManager) setOpeningEmp(null);
      setOpeningDate(todayISO());
      fetchSessions();
      fetchSummary();
      setSelectedId(s.id);
    } catch (err: any) {
      toast('error', err.message);
    } finally {
      setOpening(false);
    }
  };

  const changeFabricOrType = (idx: number, patch: Partial<ItemForm>) => {
    setLines((cur) =>
      cur.map((line, i) => {
        if (i !== idx) return line;
        const next = { ...line, ...patch };
        const candidate = fabrics.find((f) => f.id === next.fabric);
        if (candidate && !rollSaleAllowed(candidate, selected?.branch) && next.sale_type === 'roll') {
          next.sale_type = 'yard';
        }
        if ('sale_type' in patch && patch.sale_type) {
          next.quantity = defaultQuantityForType(next.sale_type);
        }
        if (candidate) {
          const base = Number(candidate.sale_price_yard) || 0;
          let price = base;
          if (next.sale_type === 'roll') {
            price = candidate.sale_price_roll != null ? (Number(candidate.sale_price_roll) || 0) : base * (Number(candidate.yards_per_roll) || 0);
          }
          next.unit_price = price > 0 ? String(price) : '';
        }
        return next;
      })
    );
  };

  const addLine = () => {
    const first = lines[0];
    const payment = first?.payment_method || 'cash';
    setLines((cur) => [...cur, { ...emptyItemForm(payment), card_type: first?.card_type || '' }]);
  };

  const removeLine = (idx: number) => {
    setLines((cur) => (cur.length > 1 ? cur.filter((_, i) => i !== idx) : [{ ...emptyItemForm(cur[0]?.payment_method || 'cash'), card_type: cur[0]?.card_type || '' }]));
  };

  const updateLine = (idx: number, patch: Partial<ItemForm>) => {
    setLines((cur) => cur.map((line, i) => (i === idx ? { ...line, ...patch } : line)));
  };

  const handleAddItem = async () => {
    if (!selected) return;
    for (const line of lines) {
      if (!line.fabric) {
        toast('error', 'اختر القماش لكل الأصناف قبل الإضافة');
        return;
      }
      const quantity = parseFloat(line.quantity);
      const price = parseFloat(line.unit_price);
      if (!quantity || quantity <= 0) {
        toast('error', 'أدخل كمية صحيحة أكبر من صفر لكل الأصناف');
        return;
      }
      if (isNaN(price) || price <= 0) {
        toast('error', 'لا يمكن حفظ البيعة بدون سعر — أدخل سعر الوحدة لكل الأصناف');
        return;
      }
      const calc = lineCalc(line);
      if (calc.discountNum > (calc.subtotal ?? 0)) {
        toast('error', 'قيمة الخصم أكبر من إجمالي أحد الأصناف');
        return;
      }
      if (line.sale_type === 'roll') {
        const fabric = fabrics.find((f) => f.id === line.fabric);
        if (fabric && !fabric.yards_per_roll) {
          toast('error', `القماش «${fabric.name}» لا توجد له ياردات الطاقة`);
          return;
        }
      }
      if (line.fabric && stock) {
        const entry = stock.items.find((i) => i.fabric === line.fabric);
        const pending = selected.items
          .filter((i) => i.fabric === line.fabric)
          .reduce((s, i) => s + (i.yards_effective || 0), 0);
        const avail = Math.max(0, (entry ? entry.yards : 0) - pending);
        const need = line.sale_type === 'roll'
          ? quantity * (Number(fabrics.find((f) => f.id === line.fabric)?.yards_per_roll) || 0)
          : quantity;
        if (avail <= 0) {
          toast('error', `قماش من الأصناف غير متوفر في مخزون الفرع`);
          return;
        }
        if (need > avail) {
          toast('error', `الكمية غير متوفرة في مخزون الفرع — المتوفر ${formatNumber(avail)} ياردة فقط بعد بنود الوردية المعلقة`);
          return;
        }
      }
    }
    setAdding(true);
    try {
      const payload = lines.map((line) => {
        const calc = lineCalc(line);
        return {
          fabric: line.fabric as number,
          sale_type: line.sale_type,
          quantity: parseFloat(line.quantity),
          unit_price: parseFloat(line.unit_price),
          discount_amount: calc.discountNum,
          payment_method: line.payment_method,
          card_type: line.payment_method === 'card' ? ((line.card_type || '') as SessionCardType | '') : '',
          customer_name: custName.trim(),
          customer_phone: custPhone.trim(),
        };
      });
      const created = await addSessionItems(selected.id, payload);
      toast('success', `تمت إضافة ${created.length > 1 ? `${created.length} أصناف` : 'البند'} — المجموع ${formatCurrency(linesTotal)}`);
      if (custPhone.trim()) {
        saveContact(custPhone, custName);
        void ensureCustomer(custName, custPhone, selected.branch);
      }
      setLines([emptyItemForm(payload[0]?.payment_method || 'cash')]);
      setCustName('');
      setCustPhone('');
      fetchSessions();
      fetchSummary();
    } catch (err: any) {
      toast('error', err.message);
    } finally {
      setAdding(false);
    }
  };

  const handleRemoveItem = async () => {
    if (!selected || !deletingItem) return;
    setDeleteItemLoading(true);
    try {
      await removeSessionItem(selected.id, deletingItem.id);
      toast('success', 'تم حذف البيع');
      setDeletingItem(null);
      fetchSessions();
      fetchSummary();
      onChanged?.();
    } catch (err: any) {
      toast('error', err.message);
    } finally {
      setDeleteItemLoading(false);
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
      onSaleGenerated?.(s);
    } catch (err: any) {
      toast('error', err.message);
    } finally {
      setCloseLoading(false);
    }
  };

  const handlePrint = () => {
    if (!selected) return;
    const ok = printSessionReceipt(selected, settings || null, 'إيصال وردية بيع');
    if (!ok) toast('error', 'الرجاء السماح بالنوافذ المنبثقة للطباعة');
  };

  const handleDeleteSession = async () => {
    if (!deletingSession) return;
    setDeleteSessionLoading(true);
    try {
      await deleteSaleSession(deletingSession.id);
      toast('success', 'تم حذف الوردية');
      setDeletingSession(null);
      fetchSessions();
      fetchSummary();
      onChanged?.();
    } catch (err: any) {
      toast('error', err.message);
    } finally {
      setDeleteSessionLoading(false);
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
        <div className="flex flex-wrap items-center gap-2">
          <Button variant="secondary" onClick={() => setCustomerSalesOpen(true)}>
            <Undo2 size={16} />
            بحث زبون واسترجاع
          </Button>
          <Button variant="secondary" onClick={manualRefresh} loading={refreshing}>
            <RefreshCcw size={16} />
            تحديث الآن
          </Button>
        </div>
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
          value={summary ? `${formatNumber(summary.yards)} وار` : '—'}
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
            {isManager ? (
              <>
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
              </>
            ) : (
              <>
                <label className="block text-sm font-medium text-neutral-700 mb-1.5">فتح وردية باسمك</label>
                <div className="rounded-xl border border-sand-300 px-4 py-2.5 text-sm text-neutral-800">
                  {me?.name || ''}{me?.branch_name ? ` — ${me.branch_name}` : ''}
                </div>
              </>
            )}
          </div>
          <div className="w-full sm:w-auto sm:min-w-[180px]">
            <Input
              label="تاريخ الوردية"
              type="date"
              value={openingDate}
              max={todayISO()}
              onChange={(e) => setOpeningDate(e.target.value)}
            />
          </div>
          <Button onClick={handleOpen} loading={opening} disabled={isManager && employees.length === 0}>
            <LogIn size={18} />
            فتح وردية
          </Button>
        </div>
      </Card>

      <Card>
        <div className="border-b border-sand-200 px-4 py-3 flex flex-wrap items-center justify-between gap-2">
          <h2 className="font-semibold">الورديات المفتوحة ({filteredSessions.length})</h2>
          <div className="flex flex-wrap items-center gap-2">
            <div className="relative">
              <Search size={14} className="absolute right-3 top-1/2 -translate-y-1/2 text-neutral-400 pointer-events-none" />
              <input
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                dir="rtl"
                placeholder="بحث بالموظف أو الفرع..."
                className="w-52 rounded-xl border border-sand-300 bg-surface pr-8 pl-3 py-2 text-sm placeholder:text-neutral-400 focus:border-brand-500 focus:ring-2 focus:ring-brand-100 outline-none transition-colors"
              />
            </div>
            <Select
              value={sortBy}
              onChange={(e) => setSortBy(e.target.value as SessionSortKey)}
              options={SORT_OPTIONS}
              className="w-44"
            />
            <Select
              value={branchFilter}
              onChange={(e) => setBranchFilter(e.target.value)}
              options={[{ value: '', label: 'كل الفروع' }, ...branches.map((b) => ({ value: b.id, label: b.name }))]}
              className="w-44"
            />
          </div>
        </div>
        {loading ? (
          <div className="flex justify-center py-12"><Spinner size={32} /></div>
        ) : sessions.length === 0 ? (
          <EmptyState
            title="لا توجد ورديات مفتوحة"
            description="افتح وردية لموظف من القسم أعلاه لبدء تسجيل بيوعات الوردية"
          />
        ) : filteredSessions.length === 0 ? (
          <EmptyState
            title="لا توجد نتائج مطابقة"
            description="جرّب تغيير كلمة البحث أو خيارات الترتيب"
          />
        ) : (
          <div className="grid gap-3 p-4 sm:grid-cols-2 lg:grid-cols-3">
            {filteredSessions.map((s) => {
              const live = liveMinutes(s);
              const aging = agingLevel(live);
              return (
              <div
                key={s.id}
                onClick={() => setSelectedId(s.id)}
                className={`text-right rounded-xl border p-4 transition-colors cursor-pointer ${
                  selectedId === s.id
                    ? 'border-brand-500 ring-2 ring-brand-100'
                    : 'border-sand-300 hover:border-brand-300'
                } ${aging === 'danger' ? 'border-red-200' : aging === 'warn' ? 'border-amber-200' : ''}`}
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="font-semibold">{s.employee_name}</span>
                  <span className="flex items-center gap-1.5">
                    <Badge variant="success">مفتوحة</Badge>
                    {aging === 'warn' && (
                      <Badge variant="warning"><TriangleAlert size={11} /> ساعتان</Badge>
                    )}
                    {aging === 'danger' && (
                      <Badge variant="danger"><TriangleAlert size={11} /> طويلة</Badge>
                    )}
                  </span>
                </div>
                <div className="mt-1 text-sm text-neutral-500">{s.branch_name}</div>
                <div className="mt-2 text-xs text-neutral-400">
                  فُتحت {formatDate(s.opened_at)} {new Date(s.opened_at).toLocaleTimeString('ar-EG-u-nu-latn', { hour: '2-digit', minute: '2-digit' })} • {elapsedText(live)}
                </div>
                {backdatedLabel(s) && (
                  <div className="mt-1.5">
                    <Badge variant="warning">تاريخ الوردية: {backdatedLabel(s)}</Badge>
                  </div>
                )}
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
                <div className="mt-3 flex items-center gap-1.5 border-t border-sand-100 pt-3" onClick={(e) => e.stopPropagation()}>
                  <button onClick={() => setViewing(s)} className="flex items-center gap-1 px-2 py-1 rounded-lg text-xs font-medium text-sky-600 hover:bg-sky-50 dark:text-sky-400 dark:hover:bg-sky-500/15 transition-colors" title="مشاهدة الوردية">
                    <Eye size={14} />
                    مشاهدة
                  </button>
                  <button onClick={() => setEditingSession(s)} className="flex items-center gap-1 px-2 py-1 rounded-lg text-xs font-medium text-amber-600 hover:bg-amber-50 dark:text-amber-400 dark:hover:bg-amber-500/15 transition-colors" title="تعديل الوردية">
                    <Pencil size={14} />
                    تعديل
                  </button>
                  <button onClick={() => setDeletingSession(s)} className="flex items-center gap-1 px-2 py-1 rounded-lg text-xs font-medium text-red-500 hover:bg-red-50 dark:text-red-400 dark:hover:bg-red-500/15 transition-colors" title="حذف الوردية">
                    <Trash2 size={14} />
                    حذف
                  </button>
                </div>
              </div>
              );
            })}
          </div>
        )}
      </Card>

      {selected && (
        <Card className="!p-5 space-y-5">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <h2 className="font-semibold">وردية {selected.employee_name} — {selected.branch_name}</h2>
              <p className="text-sm text-neutral-500">
                فُتحت {formatDate(selected.opened_at)} {new Date(selected.opened_at).toLocaleTimeString('ar-EG-u-nu-latn', { hour: '2-digit', minute: '2-digit' })} • {elapsedText(liveMinutes(selected))}
              </p>
              {backdatedLabel(selected) && (
                <p className="mt-1 text-sm font-medium text-amber-700">
                  تُسجَّل مبيعات هذه الوردية بتاريخ {backdatedLabel(selected)}
                </p>
              )}
              {selectedDiscount > 0 && (
                <p className="text-xs text-red-500 mt-1">إجمالي الخصومات المطبقة: {formatCurrency(selectedDiscount)}</p>
              )}
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <Button onClick={() => { setLines([emptyItemForm(settings?.default_payment_method)]); setAddOpen(true); }}>
                <Plus size={18} />
                إضافة بيع
              </Button>
              {selected.items.length > 0 && (
                <Button variant="secondary" onClick={handlePrint}>
                  <Printer size={18} />
                  طباعة الإيصال
                </Button>
              )}
              <Button variant="danger" onClick={() => setClosing(selected)}>
                <CircleDollarSign size={18} />
                إغلاق الوردية وتسجيل البيع
              </Button>
            </div>
          </div>

          {selected.items.length === 0 ? (
            <EmptyState title="لا توجد بنود بعد" description="اضغط «إضافة بيع» لإضافة أول بند" />
          ) : (
            <>
              <div className="overflow-x-auto">
                <Table>
                  <thead>
                    <tr>
                      <Th>
                        <input
                          type="checkbox"
                          className="h-4 w-4 rounded border-sand-300 accent-brand-600"
                          checked={selected.items.length > 0 && selected.items.every((i) => checked.has(i.id))}
                          onChange={(e) =>
                            setChecked(e.target.checked ? new Set(selected.items.map((i) => i.id)) : new Set())
                          }
                          title="تحديد كل البنود"
                        />
                      </Th>
                      <Th>القماش</Th>
                      <Th>النوع</Th>
                      <Th>الكمية</Th>
                      <Th>البيعة</Th>
                      <Th>الزبون</Th>
                      <Th>سعر الوحدة</Th>
                      <Th>الخصم</Th>
                      <Th>طريقة الدفع</Th>
                      <Th>الإجمالي</Th>
                      <Th>تاريخ البيع</Th>
                      <Th>{''}</Th>
                    </tr>
                  </thead>
                  <tbody>
                    {selected.items.map((item) => (
                      <Tr key={item.id}>
                        <Td>
                          <input
                            type="checkbox"
                            disabled={item.is_returned}
                            className={`h-4 w-4 rounded border-sand-300 accent-brand-600 ${item.is_returned ? 'opacity-40 cursor-not-allowed' : ''}`}
                            checked={checked.has(item.id)}
                            onChange={(e) => {
                              const next = new Set(checked);
                              if (e.target.checked) next.add(item.id);
                              else next.delete(item.id);
                              setChecked(next);
                            }}
                          />
                        </Td>
                        <Td className="font-medium">
                          <span className="flex flex-wrap items-center gap-1.5">
                            {item.fabric_name}
                            {item.is_returned && <Badge variant="danger">مسترجع</Badge>}
                          </span>
                          {item.is_returned && (
                            <span className="block text-[11px] text-red-400 mt-0.5">{item.return_reason || 'بدون سبب'}</span>
                          )}
                        </Td>
                        <Td><Badge variant="neutral">{item.sale_type_label}</Badge></Td>
                        <Td className="tabular-nums">{item.quantity} {item.sale_type === 'roll' ? 'طاقة' : 'يارد'}</Td>
                        <Td>
                          <span
                            onClick={() => {
                              const g = item.sale_group || `single-${item.id}`;
                              const ids = selected.items.filter((i) => (i.sale_group || `single-${i.id}`) === g).map((i) => i.id);
                              setChecked((prev) => {
                                const next = new Set(prev);
                                ids.forEach((id) => next.add(id));
                                return next;
                              });
                            }}
                            title="تحديد كل بنود هذه البيعة للفاتورة"
                            className={`inline-flex cursor-pointer items-center rounded-full border px-2 py-0.5 text-[11px] font-bold select-none transition-transform hover:scale-105 ${
                              saleGroupBadges(selected.items).get(item.sale_group || `single-${item.id}`)?.cls ?? 'bg-neutral-100 text-neutral-400 border-neutral-200'
                            }`}
                          >
                            بيعة {saleGroupBadges(selected.items).get(item.sale_group || `single-${item.id}`)?.num ?? ''}
                          </span>
                        </Td>
                        <Td className="tabular-nums text-neutral-500">
                          {item.customer_name ? <span className="block font-medium text-neutral-700">{item.customer_name}</span> : null}
                          {item.customer_phone ? item.customer_phone : <span className="text-neutral-300">—</span>}
                        </Td>
                        <Td className="tabular-nums">{formatCurrency(item.unit_price)}</Td>
                        <Td className={`tabular-nums ${item.discount_amount > 0 ? 'text-red-500' : 'text-neutral-400'}`}>
                          {item.discount_amount > 0 ? formatCurrency(item.discount_amount) : '—'}
                        </Td>
                        <Td>
                          <Badge variant={item.payment_method === 'card' ? 'warning' : item.payment_method === 'transfer' ? 'neutral' : 'success'}>
                            {item.payment_method === 'card' ? (item.card_type_label ? `ماكينة (${item.card_type_label})` : 'ماكينة') : item.payment_method_label}
                          </Badge>
                        </Td>
                        <Td
                          className="tabular-nums font-semibold"
                          title={
                            item.payment_method === 'card' && item.card_fee_amount > 0
                              ? `رسوم الماكينة: ${formatCurrency(item.card_fee_amount)} — الصافي: ${formatCurrency(item.net_total)}`
                              : undefined
                          }
                        >
                          {formatCurrency(item.payment_method === 'card' && item.net_total > 0 ? item.net_total : item.total)}
                          {item.payment_method === 'card' && item.card_fee_amount > 0 && (
                            <span className="block text-[10px] font-normal text-neutral-400">صافي بعد رسوم {formatCurrency(item.card_fee_amount)}</span>
                          )}
                        </Td>
                        <Td className="tabular-nums text-sm text-neutral-500">{formatDate(item.sale_date)}</Td>
                        <Td>
                          <div className="flex items-center gap-1.5">
                            <button onClick={() => setMovingItem({ session: selected, item })} disabled={item.is_returned} title={item.is_returned ? 'لا يمكن نقل بند مسترجع' : 'نقل البند إلى وردية أخرى'} className="p-1.5 rounded-lg hover:bg-sky-50 text-sky-600 dark:hover:bg-sky-500/15 dark:text-sky-400 transition-colors disabled:opacity-30 disabled:cursor-not-allowed">
                              <Move size={15} />
                            </button>
                            <button onClick={() => setEditingItem({ session: selected, item })} disabled={item.is_returned} title={item.is_returned ? 'لا يمكن تعديل بند مسترجع' : 'تعديل البيع'} className="p-1.5 rounded-lg hover:bg-amber-50 text-amber-600 dark:hover:bg-amber-500/15 dark:text-amber-400 transition-colors disabled:opacity-30 disabled:cursor-not-allowed">
                              <Pencil size={15} />
                            </button>
                            <button onClick={() => setDeletingItem(item)} disabled={item.is_returned} title={item.is_returned ? 'لا يمكن حذف بند مسترجع' : 'حذف البيع'} className="p-1.5 rounded-lg hover:bg-red-50 text-red-500 dark:hover:bg-red-500/15 dark:text-red-400 transition-colors disabled:opacity-30 disabled:cursor-not-allowed">
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
                <span className="flex flex-wrap items-center gap-2 text-sm">
                  <Badge variant="success">كاش {formatCurrency(selected.totals.cash)}</Badge>
                  <Badge variant="neutral">تحويل {formatCurrency(selected.totals.transfer)}</Badge>
                  <Badge variant="warning">ماكينة {formatCurrency(selected.totals.card)}</Badge>
                  <Badge variant="neutral">{formatNumber(selected.totals.yards)} ياردة</Badge>
                </span>
                <span className="flex flex-wrap items-center gap-2">
                  {(() => {
                    const selList = selected.items.filter((i) => checked.has(i.id));
                    const selTotal = selList.reduce((s, i) => s + Number(i.total), 0);
                    return (
                      <>
                        {selList.length > 0 && (
                          <Badge variant="neutral">
                            المحدد: {selList.length}/{selected.items.length} — {formatCurrency(selTotal)}
                          </Badge>
                        )}
                        <Button onClick={() => setInvoiceSel(selList.map((i) => i.id))} disabled={selList.length === 0}>
                          <FileText size={18} />
                          فاتورة الزبون
                        </Button>
                      </>
                    );
                  })()}
                  <span className="text-lg font-bold tabular-nums">{formatCurrency(selected.totals.total)}</span>
                </span>
              </div>

              {paymentBar.length > 0 && (
                <div className="rounded-xl border border-sand-200 p-3">
                  <div className="flex h-3 w-full overflow-hidden rounded-full bg-sand-200">
                    {paymentBar.map((p) => (
                      <div key={p.label} className={`${p.cls} h-full`} style={{ width: `${p.pct}%` }} title={`${p.label}: ${formatCurrency(p.value)}`} />
                    ))}
                  </div>
                  <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-neutral-500">
                    {paymentBar.map((p) => (
                      <span key={p.label} className="flex items-center gap-1.5">
                        <span className={`inline-block h-2.5 w-2.5 rounded-full ${p.cls}`} />
                        {p.label} {formatCurrency(p.value)} ({formatNumber(p.pct)}%)
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </>
          )}
        </Card>
      )}

      <Modal
        open={addOpen}
        onClose={() => setAddOpen(false)}
        title={`إضافة بيع — ${selected ? `${selected.employee_name} · ${selected.branch_name}` : ''}`}
        maxWidth="max-w-3xl"
        footer={
          <>
            <Button onClick={handleAddItem} loading={adding}>
              <Plus size={18} />
              إضافة البيع
            </Button>
            <Button variant="ghost" onClick={() => setAddOpen(false)}>
              إغلاق
            </Button>
          </>
        }
      >
        <div className="space-y-4">
          <CustomerPicker
            name={custName}
            onChangeName={setCustName}
            phone={custPhone}
            onChangePhone={setCustPhone}
            compact
          />

          <div className="space-y-3">
            {lines.map((line, idx) => {
              const calc = lineCalc(line);
              const overStock = calc.quantityExceeds;
              return (
                <div key={idx} className="rounded-xl border border-sand-300 bg-surface p-4 space-y-4">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-semibold text-neutral-500">الصنف {idx + 1}</span>
                    <Button
                      variant="ghost"
                      size="sm"
                      className="!h-7 !w-7 !p-0 !text-red-500"
                      onClick={() => removeLine(idx)}
                      title="حذف الصنف"
                    >
                      <Trash2 size={15} />
                    </Button>
                  </div>
                  <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                    <Select
                      label="القماش"
                      value={line.fabric ?? ''}
                      onChange={(e) => changeFabricOrType(idx, { fabric: Number(e.target.value) })}
                      options={saleFabrics.map((f) => ({ value: f.id, label: `${f.name} — ي: ${formatNumber(f.sale_price_yard)}${f.sale_price_roll_display ? ` / ط: ${formatNumber(f.sale_price_roll_display)}` : ''}` }))}
                      placeholder="اختر القماش"
                    />
                    <div>
                      <label className="block text-sm font-medium text-neutral-700 mb-1.5">نوع البيع</label>
                      <div className="flex rounded-xl border border-sand-300 overflow-hidden">
                        <button
                          type="button"
                          onClick={() => changeFabricOrType(idx, { sale_type: 'yard' })}
                          className={`flex-1 py-2.5 text-sm font-medium transition-colors ${line.sale_type === 'yard' ? 'bg-brand-600 text-white' : 'bg-surface text-neutral-600 hover:bg-sand-100'}`}
                        >
                          ياردة
                        </button>
                        <button
                          type="button"
                          onClick={() => changeFabricOrType(idx, { sale_type: 'roll' })}
                          disabled={!calc.rollAllowed}
                          title={calc.rollAllowed ? 'بيع بالطاقة' : 'البيع بالطاقة غير مسموح لهذا القماش في هذا الفرع'}
                          className={`flex-1 py-2.5 text-sm font-medium transition-colors ${
                            !calc.rollAllowed
                              ? 'bg-surface text-neutral-300 cursor-not-allowed'
                              : line.sale_type === 'roll'
                                ? 'bg-brand-600 text-white'
                                : 'bg-surface text-neutral-600 hover:bg-sand-100'
                          }`}
                        >
                          طاقة (بالطاقة)
                        </button>
                      </div>
                    </div>
                    {idx === 0 && (
                      <Select
                        label="طريقة الدفع (تُطبَّق على كل أصناف هذه البيعة)"
                        value={line.payment_method}
                        onChange={(e) => {
                          const v = e.target.value as SessionPaymentMethod;
                          setLines((cur) => cur.map((l) => ({ ...l, payment_method: v, card_type: v === 'card' ? (l.card_type || 'credit') : '' })));
                        }}
                        options={PAYMENT_OPTIONS}
                      />
                    )}
                    {idx === 0 && line.payment_method === 'card' && (
                      <div>
                        <label className="block text-sm font-medium text-neutral-700 mb-1.5">نوع الماكينة (تُطبَّق على كل الأصناف)</label>
                        <div className="flex rounded-xl border border-sand-300 overflow-hidden">
                          {CARD_TYPE_OPTIONS.map((opt) => (
                            <button
                              key={opt.value}
                              type="button"
                              onClick={() => setLines((cur) => cur.map((l) => ({ ...l, card_type: opt.value as SessionCardType })))}
                              className={`flex-1 py-2.5 text-sm font-medium transition-colors ${line.card_type === opt.value ? 'bg-brand-600 text-white' : 'bg-surface text-neutral-600 hover:bg-sand-100'}`}
                            >
                              {opt.label}
                            </button>
                          ))}
                        </div>
                        <p className="text-xs text-neutral-400 mt-1">عمولة الماكينة {calc.feePercent}% — يُسجَّل صافي المبيعات بعد خصمها</p>
                      </div>
                    )}
                    <div>
                      <Input
                        label={line.sale_type === 'roll' ? 'عدد الطاقات' : 'الكمية (ياردات)'}
                        type="number"
                        min="0"
                        step={line.sale_type === 'roll' ? '1' : '0.25'}
                        value={line.quantity}
                        onChange={(e) => updateLine(idx, { quantity: e.target.value })}
                        placeholder=""
                        className={overStock ? 'border-red-400 ring-2 ring-red-200' : ''}
                      />
                      {line.sale_type === 'yard' && (
                        <QuantityQuickPicks value={line.quantity} onPick={(q) => updateLine(idx, { quantity: q })} />
                      )}
                    </div>
                    <Input
                      label="سعر الوحدة"
                      type="number"
                      min="0"
                      step="0.1"
                      value={line.unit_price}
                      onChange={(e) => updateLine(idx, { unit_price: e.target.value })}
                      placeholder={String(fabricAutoPrice(line))}
                    />
                    <Input
                      label="قيمة الخصم"
                      type="number"
                      min="0"
                      step="0.01"
                      value={line.discount}
                      onChange={(e) => updateLine(idx, { discount: e.target.value })}
                      placeholder=""
                    />
                    <FinalAmountInput
                      subtotal={calc.subtotal}
                      discount={line.discount}
                      onDiscountChange={(d) => updateLine(idx, { discount: d })}
                    />
                  </div>

                  <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl bg-sand-50 border border-sand-200 px-4 py-2.5">
                    <span className="text-sm text-neutral-600">
                      إجمالي الصنف ({line.sale_type === 'roll' ? `${line.quantity || '0'} طاقة × ${formatCurrency(calc.priceNum)}` : `${line.quantity || '0'} ياردة × ${formatCurrency(calc.priceNum)}`})
                      {calc.discountNum > 0 ? ` - خصم ${formatCurrency(calc.discountNum)}` : ''}:
                    </span>
                    <span className={`text-lg font-bold tabular-nums ${calc.discountExceeds ? 'text-red-500' : 'text-brand-700'}`}>
                      {calc.netTotal != null ? formatCurrency(calc.netTotal) : '—'}
                    </span>
                  </div>
                  {line.payment_method === 'card' && calc.cardFee > 0 && calc.netAfterFee != null && (
                    <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl bg-amber-50 border border-amber-200 px-4 py-2">
                      <span className="text-xs text-neutral-600">
                        عمولة الماكينة {calc.feePercent}% ({line.card_type === 'debit' ? 'خصم مباشر / Debit' : 'إئتماني / Credit'}):
                      </span>
                      <span className="text-xs font-semibold text-red-600 tabular-nums">- {formatCurrency(calc.cardFee)}</span>
                      <span className="text-sm font-bold text-brand-700 tabular-nums">الصافي: {formatCurrency(calc.netAfterFee)}</span>
                    </div>
                  )}

                  {stock && calc.availableUnit !== null && (
                    <p className={`text-xs ${overStock ? 'text-red-500 font-medium' : 'text-neutral-400'}`}>
                      المتوفر في مخزون الفرع ({stock.warehouse_name}): {formatNumber(calc.availableUnit)} {line.sale_type === 'roll' ? 'طاقة' : 'ياردة'}
                      {overStock ? ' — الكمية تتجاوز المتوفر' : ''}
                    </p>
                  )}
                  {calc.selectedFabric && line.sale_type === 'roll' && !calc.selectedFabric.yards_per_roll && (
                    <p className="text-xs text-amber-600 font-medium">هذا القماش لا يملك ياردات الطاقة — لا يمكن بيعه بالطاقة</p>
                  )}
                  {calc.selectedFabric && !calc.rollAllowed && (
                    <p className="text-xs text-amber-600 font-medium">البيع بالطاقة لهذا القماش غير متوفر في هذا الفرع</p>
                  )}
                </div>
              );
            })}
          </div>

          <Button variant="secondary" onClick={addLine}>
            <Plus size={16} />
            إضافة صنف آخر
          </Button>

          <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl bg-sand-50 border border-sand-200 px-4 py-3">
            <span className="text-sm text-neutral-600">إجمالي البيعة (المجموع الموحد):</span>
            <span className="text-xl font-bold tabular-nums text-brand-700">{formatCurrency(linesTotal)}</span>
          </div>
          {lines.some((l) => l.payment_method === 'card') && (
            <p className="text-xs text-amber-600">
              عند الدفع بالماكينة يُسجَّل الصافي بعد خصم عمولة الماكينة — صافي البيعة: {formatCurrency(linesTotal)}
            </p>
          )}

          <div className="space-y-1.5">
            <p className="text-xs text-neutral-400">
              يمكن إضافة أكثر من صنف في البيعة الواحدة بزر «إضافة صنف آخر» — تُضاف الأصناف معاً في عملية واحدة وتصبح بيعة واحدة بمجموع موحد. السعر التلقائي يُؤخذ من ملف القماش (ياردات × سعر الياردة = سعر الطاقة) — لا يمكن البيع بأقل من الحد الأدنى المحدد لكل قماش.
            </p>
          </div>
        </div>
      </Modal>

      <SessionCustomerInvoiceModal
        open={invoiceSel !== null}
        onClose={() => setInvoiceSel(null)}
        session={selected}
        itemIds={invoiceSel ?? []}
        settings={settings}
      />

      <CloseSessionModal
        open={!!closing}
        session={closing}
        loading={closeLoading}
        onClose={() => setClosing(null)}
        onConfirm={handleClose}
      />

      <MoveItemModal
        open={!!movingItem}
        session={movingItem?.session ?? null}
        item={movingItem?.item ?? null}
        sessions={sessions}
        onClose={() => setMovingItem(null)}
        onMoved={() => {
          fetchSessions();
          fetchSummary();
          onChanged?.();
        }}
      />

      <SessionItemEditModal
        open={!!editingItem}
        session={editingItem?.session ?? null}
        item={editingItem?.item ?? null}
        fabrics={saleFabrics}
        onClose={() => setEditingItem(null)}
        onSaved={() => {
          fetchSessions();
          fetchSummary();
          onChanged?.();
        }}
      />

      <SessionDetailsModal
        open={!!viewing}
        session={viewing}
        onClose={() => setViewing(null)}
      />

      <SessionEditModal
        open={!!editingSession}
        session={editingSession}
        employees={isManager ? employees : me ? [toEmployee(me)] : []}
        branches={branches}
        onClose={() => setEditingSession(null)}
        onSaved={() => {
          fetchSessions();
          fetchSummary();
        }}
      />

      <ConfirmDialog
        open={!!deletingItem}
        onClose={() => setDeletingItem(null)}
        onConfirm={handleRemoveItem}
        loading={deleteItemLoading}
        title="حذف البيع"
        confirmLabel="حذف البيع"
        message={
          deletingItem
            ? `هل أنت متأكد من حذف هذا البيع (${deletingItem.fabric_name} — ${deletingItem.quantity} ${deletingItem.sale_type === 'roll' ? 'طاقة' : 'يارد'} — ${formatCurrency(Number(deletingItem.total))})؟ سيتم إلغاء البيعة وترجيع الكمية إلى المخزون.`
            : ''
        }
      />

      <ConfirmDialog
        open={!!deletingSession}
        onClose={() => setDeletingSession(null)}
        onConfirm={handleDeleteSession}
        loading={deleteSessionLoading}
        title="حذف الوردية"
        confirmLabel="حذف الوردية"
        message={
          deletingSession
            ? `هل أنت متأكد من حذف وردية ${deletingSession.employee_name} (${deletingSession.items.length} بند — إجمالي ${formatCurrency(deletingSession.totals.total)})؟ سيتم إلغاء الوردية وبنودها.`
            : ''
        }
      />

      <CustomerSalesReturnModal
        open={customerSalesOpen}
        onClose={() => setCustomerSalesOpen(false)}
        onChanged={() => {
          fetchSessions();
          fetchSummary();
          onChanged?.();
        }}
      />
    </div>
  );
}