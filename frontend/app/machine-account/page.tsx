'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import { useAutoRefresh } from '@/lib/useAutoRefresh';
import AppShell from '@/components/layout/AppShell';
import Card from '@/components/ui/Card';
import Spinner from '@/components/ui/Spinner';
import Button from '@/components/ui/Button';
import Input from '@/components/ui/Input';
import Select from '@/components/ui/Select';
import Table, { Th, Td, Tr } from '@/components/ui/Table';
import EmptyState from '@/components/ui/EmptyState';
import ConfirmDialog from '@/components/ui/ConfirmDialog';
import DateRangeToolbar, { currentMonthRange } from '@/components/ui/DateRangeToolbar';
import {
  Landmark,
  HandCoins,
  Trash2,
  CreditCard,
  Building2,
  TrendingUp,
  Download,
  Wallet,
  ArrowRightLeft,
} from 'lucide-react';
import {
  Branch,
  MachineAccountResult,
  MachineCollection,
  SettlementAccount,
  SettlementAccountKey,
  SettlementFigures,
  SETTLEMENT_ACCOUNTS,
} from '@/types';
import {
  getMachineAccount,
  createCollection,
  deleteCollection,
  listAllCollections,
  transferToBank,
} from '@/services/machine';
import { listBranches } from '@/services/branches';
import { formatCurrency, formatDate } from '@/lib/format';
import { counted } from '@/lib/arabic';
import { downloadCsv, csvFilename } from '@/lib/csv';
import { useToast } from '@/components/ui/Toast';
import { useUrlState } from '@/lib/useUrlState';

const METHODS = [
  { value: 'transfer', label: 'تحويل بنكي' },
  { value: 'cash', label: 'نقدي' },
  { value: 'other', label: 'أخرى' },
];

/** tab === 'all' يعرض الحسابين معاً، وما عداه يعرض حساباً واحداً. */
type AccountTab = 'all' | SettlementAccountKey;

const TABS: { value: AccountTab; label: string }[] = [
  { value: 'all', label: 'كل الحسابات' },
  { value: 'machine', label: 'حساب الماكينة' },
  { value: 'bank', label: 'حساب البنك' },
];

const EMPTY: SettlementFigures = { sales: 0, received: 0, balance: 0 };

const ACCOUNT_META: Record<
  SettlementAccountKey,
  { label: string; short: string; icon: typeof CreditCard; accent: string; bar: string }
> = {
  machine: {
    label: 'حساب الماكينة',
    short: 'ماكينة',
    icon: CreditCard,
    accent: 'text-brand-600',
    bar: 'bg-brand-500',
  },
  bank: {
    label: 'حساب البنك',
    short: 'بنك',
    icon: Building2,
    accent: 'text-sky-600',
    bar: 'bg-sky-500',
  },
};

export default function MachineAccountPage() {
  const { toast } = useToast();
  const [data, setData] = useState<MachineAccountResult | null>(null);
  const [branches, setBranches] = useState<Branch[]>([]);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [exporting, setExporting] = useState(false);

  const [from, setFrom] = useUrlState('from', currentMonthRange().from);
  const [to, setTo] = useUrlState('to', currentMonthRange().to);
  const [branchFilter, setBranchFilter] = useUrlState('branch', '');
  const [tab, setTab] = useState<AccountTab>('all');

  const [form, setForm] = useState({
    account: 'machine' as SettlementAccountKey,
    date: new Date().toISOString().slice(0, 10),
    amount: '',
    method: 'transfer',
    branch: '',
    reference: '',
    notes: '',
  });
  const [deleting, setDeleting] = useState<MachineCollection | null>(null);
  const [deleteLoading, setDeleteLoading] = useState(false);
  const [transfer, setTransfer] = useState({
    open: false,
    amount: '',
    date: new Date().toISOString().slice(0, 10),
    branch: '',
    reference: '',
    notes: '',
  });
  const [transferLoading, setTransferLoading] = useState(false);

  const fetchData = useCallback(() => {
    const params: Record<string, string> = { date_from: from, date_to: to };
    if (branchFilter) params.branch = branchFilter;
    // بلا `account`: نريد الحسابين دائماً حتى يبدّل التبويب بلا إعادة جلب.
    return getMachineAccount(params);
  }, [from, to, branchFilter]);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    Promise.all([fetchData(), listBranches({ page_size: 100 })])
      .then(([acc, b]) => {
        if (cancelled) return;
        setData(acc);
        setBranches(b.results.filter((br) => br.is_active));
      })
      .catch((err) => {
        if (!cancelled) toast('error', err.message);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [fetchData, toast]);

  useAutoRefresh(useCallback(() => fetchData().then(setData), [fetchData]));

  // الحسابات المعروضة في التبويب الحالي، بالترتيب الثابت.
  const visibleKeys: SettlementAccountKey[] =
    tab === 'all' ? [...SETTLEMENT_ACCOUNTS] : [tab];

  const accountOf = useCallback(
    (key: SettlementAccountKey): SettlementAccount =>
      data?.accounts?.[key] || { ...EMPTY, label: ACCOUNT_META[key].label, hint: '' },
    [data]
  );

  /**
   * ما في الماكينة فعلاً أمّا رصيدُ البطاقة المعروض في البطاقة.
   *
   * الأول متراكمٌ من أوّل يومٍ، والثاني محسوبٌ للفترة المعروضة. وأولاهما هو
   * الذي يحدُّ التحويل — ولولاه لاستطاع الموظف أن يحوّل مالَ العام الماضي مرّتين.
   */
  const machineAvailable = data?.transferable ?? 0;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const amount = parseFloat(form.amount);
    if (!amount || amount <= 0) {
      toast('error', 'أدخل المبلغ المستلم');
      return;
    }
    setSubmitting(true);
    try {
      await createCollection({
        account: form.account,
        date: form.date,
        amount,
        method: form.method,
        branch: form.branch ? Number(form.branch) : null,
        reference: form.reference,
        notes: form.notes,
      });
      toast('success', 'تم تسجيل الدفعة — الرصيد محدّث');
      setForm((f) => ({ ...f, amount: '', reference: '', notes: '' }));
      fetchData().then(setData);
    } catch (err: any) {
      toast('error', err.message);
    } finally {
      setSubmitting(false);
    }
  };

  const handleDelete = async () => {
    if (!deleting) return;
    setDeleteLoading(true);
    try {
      await deleteCollection(deleting.id);
      toast('success', 'تم حذف الدفعة');
      setDeleting(null);
      fetchData().then(setData);
    } catch (err: any) {
      toast('error', err.message);
    } finally {
      setDeleteLoading(false);
    }
  };

  /** يعبّئ استمارة «وصلني كذا» بالمتبقي المستحق على الحساب. */
  const suggestSettlement = (key: SettlementAccountKey) => {
    const balance = accountOf(key).balance;
    if (balance <= 0) {
      toast('info', `لا يوجد متبقٍ على ${ACCOUNT_META[key].label} في هذه الفترة`);
      return;
    }
    setForm((f) => ({ ...f, account: key, amount: balance.toFixed(2), method: 'transfer' }));
    toast('info', `عبّأنا المبلغ بالمتبقي على ${ACCOUNT_META[key].label} — عدّل التاريخ والمرجع ثم سجّل`);
  };

  /** يُعبّئ استمارة التحويل ببقية رصيد الماكينة، ويقول للزائر إن لم يكن هناك رصيد. */
  const openTransfer = () => {
    const available = machineAvailable;
    if (available <= 0) {
      toast('info', 'لا يوجد في الماكينة مبلغٌ غير مُودَع يمكن تحويله');
      return;
    }
    setTransfer((t) => ({
      ...t,
      open: true,
      amount: available.toFixed(2),
      branch: branchFilter,
    }));
  };

  const handleTransfer = async (e: React.FormEvent) => {
    e.preventDefault();
    const amount = parseFloat(transfer.amount);
    if (!amount || amount <= 0) {
      toast('error', 'أدخل المبلغ المحوَّل');
      return;
    }
    setTransferLoading(true);
    try {
      const res = await transferToBank({
        amount,
        date: transfer.date,
        branch: transfer.branch ? Number(transfer.branch) : null,
        reference: transfer.reference,
        notes: transfer.notes,
      });
      toast(
        'success',
        `تم تحويل ${formatCurrency(res.transferred)} — المتبقّي في الماكينة ${formatCurrency(res.machine_remaining)}`
      );
      setTransfer((t) => ({ ...t, open: false, amount: '', reference: '', notes: '' }));
      fetchData().then(setData);
    } catch (err: any) {
      toast('error', err.message);
    } finally {
      setTransferLoading(false);
    }
  };

  const handleExport = async () => {
    setExporting(true);
    try {
      const params: Record<string, string> = { date_from: from, date_to: to };
      if (branchFilter) params.branch = branchFilter;
      if (tab !== 'all') params.account = tab;
      // كل السجلات لا الصفحة المعروضة
      const rows = await listAllCollections(params);
      if (rows.length === 0) {
        toast('info', 'لا توجد دفعات في هذه الفترة لتصديرها');
        return;
      }
      downloadCsv(csvFilename('التسويات المالية', from), [
        { header: 'التاريخ', value: (r) => r.date },
        { header: 'الحساب', value: (r) => r.account_label },
        { header: 'المبلغ', value: (r) => r.amount },
        { header: 'الطريقة', value: (r) => r.method_label },
        { header: 'الفرع', value: (r) => r.branch_name || 'الحساب الكلي' },
        { header: 'المرجع', value: (r) => r.reference },
        { header: 'ملاحظات', value: (r) => r.notes },
      ], rows);
      toast('success', `تم تصدير ${counted(rows.length, 'دفعة', 'دفعتان', 'دفعات')}`);
    } catch (err: any) {
      toast('error', err.message);
    } finally {
      setExporting(false);
    }
  };

  const set = (key: string, val: string) => setForm((f) => ({ ...f, [key]: val }));

  // أعلى قيمة في الاتجاه = مقياس الأعمدة
  const maxMonth = useMemo(() => {
    const rows = data?.months || [];
    return Math.max(
      ...rows.flatMap((m) =>
        Object.values(m.accounts || {}).flatMap((f) => [f.sales, f.received])
      ),
      1
    );
  }, [data]);

  const visibleCollections = useMemo(() => {
    const rows = data?.recent_collections || [];
    return tab === 'all' ? rows : rows.filter((c) => c.account === tab);
  }, [data, tab]);

  return (
    <AppShell>
      <div className="space-y-6">
        <div className="flex items-center gap-3">
          <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-brand-600 text-white">
            <Landmark size={22} />
          </div>
          <div>
            <h1 className="text-xl font-bold">التسويات المالية</h1>
            <p className="text-sm text-neutral-500">
              حساب الماكينة (مبيعات البطاقة) وحساب البنك (مبيعات التحويل) — لتعرف كم
              باقي لك عند كل جهة
            </p>
          </div>
        </div>

        <Card className="!p-4">
          <div className="flex flex-wrap items-end gap-4">
            <DateRangeToolbar
              from={from}
              to={to}
              onChange={(f, t) => {
                setFrom(f);
                setTo(t);
              }}
            />
            <Select
              value={branchFilter}
              onChange={(e) => setBranchFilter(e.target.value)}
              options={[
                { value: '', label: 'كل الفروع' },
                ...branches.map((b) => ({ value: b.id, label: b.name })),
              ]}
              className="w-full sm:w-48"
            />
            <Button variant="secondary" onClick={handleExport} loading={exporting}>
              <Download size={16} />
              تصدير CSV
            </Button>
          </div>
        </Card>

        {/* تبويب الحساب */}
        <div className="flex flex-wrap gap-2">
          {TABS.map((t) => (
            <button
              key={t.value}
              onClick={() => setTab(t.value)}
              className={`px-4 py-2 rounded-xl text-sm font-medium transition-all duration-150 ${
                tab === t.value
                  ? 'bg-brand-600 text-white shadow-sm'
                  : 'bg-surface text-neutral-600 border border-sand-200 hover:bg-sand-50'
              }`}
            >
              {t.label}
            </button>
          ))}
        </div>

        {loading ? (
          <div className="flex justify-center py-16">
            <Spinner size={36} />
          </div>
        ) : !data ? (
          <EmptyState title="تعذر التحميل" description="لم نتمكن من جلب بيانات حسابات التسوية" />
        ) : (
          <>
            {/* بطاقات الحسابات — بطاقة لكل حساب، وبطاقة مجمّعة في تبويب «الكل» */}
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
              {visibleKeys.map((key) => {
                const meta = ACCOUNT_META[key];
                const Icon = meta.icon;
                const acc = accountOf(key);
                const month = data.month?.[key] || EMPTY;
                const settled =
                  acc.sales > 0 ? Math.min(100, Math.round((acc.received / acc.sales) * 100)) : 0;
                return (
                  <Card key={key} className="!p-4">
                    <div className="flex items-start justify-between gap-2">
                      <div>
                        <div className="flex items-center gap-1.5 text-xs font-medium text-neutral-500 mb-1">
                          <Icon size={15} className={meta.accent} />
                          {meta.label}
                        </div>
                        <div
                          className={`text-2xl font-bold tabular-nums ${
                            acc.balance < 0 ? 'text-red-600' : 'text-neutral-800'
                          }`}
                        >
                          {formatCurrency(acc.balance)}
                        </div>
                        <div className="text-[11px] text-neutral-400 mt-0.5">
                          {acc.balance < 0 ? 'دفعة أكثر من المبيعات' : 'متبقٍّ بانتظار التحصيل'}
                        </div>
                      </div>
                    </div>

                    {/* نسبة التسوية: كم من مبيعات الفترة وصل فعلياً */}
                    <div className="mt-3">
                      <div className="h-1.5 w-full rounded-full bg-sand-100 dark:bg-white/10 overflow-hidden">
                        <div
                          className={`h-full rounded-full ${meta.bar} transition-all duration-300`}
                          style={{ width: `${settled}%` }}
                        />
                      </div>
                      <div className="flex justify-between text-[11px] text-neutral-400 mt-1">
                        <span>مبيعات {formatCurrency(acc.sales)}</span>
                        <span>وصلني {formatCurrency(acc.received)} ({settled}%)</span>
                      </div>
                    </div>

                    <div className="mt-2 text-[11px] text-neutral-400">
                      هذا الشهر: مبيعات {formatCurrency(month.sales)} — وصلني{' '}
                      {formatCurrency(month.received)}
                    </div>

                    <Button
                      variant="secondary"
                      className="mt-3 w-full"
                      onClick={() => suggestSettlement(key)}
                    >
                      <HandCoins size={16} />
                      اقترح تسجيل التسوية
                    </Button>
                  </Card>
                );
              })}

              {tab === 'all' && (
                <Card className="!p-4 sm:col-span-2 lg:col-span-1">
                  <div className="flex items-center justify-between">
                    <div className="text-xs text-neutral-500 mb-1">إجمالي المتبقّي (كل الحسابات)</div>
                    <Wallet size={18} className="text-amber-500" />
                  </div>
                  <div
                    className={`text-2xl font-bold tabular-nums ${
                      data.combined.balance < 0 ? 'text-red-600' : 'text-amber-600'
                    }`}
                  >
                    {formatCurrency(data.combined.balance)}
                  </div>
                  <div className="text-[11px] text-neutral-400 mt-0.5">
                    الإجمالي المحسوب من الفترة {formatDate(data.start_date)} إلى{' '}
                    {formatDate(data.end_date)}
                  </div>
                  <dl className="mt-3 space-y-1 text-xs">
                    <div className="flex justify-between">
                      <dt className="text-neutral-500">مبيعات البطاقة + التحويل</dt>
                      <dd className="tabular-nums font-medium">
                        {formatCurrency(data.combined.sales)}
                      </dd>
                    </div>
                    <div className="flex justify-between">
                      <dt className="text-neutral-500">الدفعات الواردة</dt>
                      <dd className="tabular-nums font-medium text-emerald-700">
                        {formatCurrency(data.combined.received)}
                      </dd>
                    </div>
                  </dl>
                </Card>
              )}
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
              {/* تحويل من الماكينة إلى البنك */}
              <Card
                title="«تحويل من الماكينة إلى البنك»"
                className="lg:col-span-1"
              >
                <div className="rounded-xl bg-sky-50 dark:bg-sky-500/10 px-3 py-2 text-xs text-sky-800 dark:text-sky-200">
                  في الماكينة الآن مبلغٌ غير مُودَع قدره{' '}
                  <b className="tabular-nums">{formatCurrency(machineAvailable)}</b>
                  {!transfer.open && machineAvailable > 0 && (
                    <Button
                      variant="secondary"
                      className="mt-3 w-full"
                      onClick={openTransfer}
                    >
                      <ArrowRightLeft size={16} />
                      حوِّل مبلغاً إلى البنك
                    </Button>
                  )}
                </div>

                {transfer.open ? (
                  <form onSubmit={handleTransfer} className="mt-3 space-y-3">
                    <Input
                      label="المبلغ المحوَّل إلى البنك"
                      type="number"
                      min="0"
                      step="0.01"
                      value={transfer.amount}
                      onChange={(e) => setTransfer((t) => ({ ...t, amount: e.target.value }))}
                      placeholder="0.00"
                    />
                    <div className="grid grid-cols-2 gap-3">
                      <Input
                        label="التاريخ"
                        type="date"
                        value={transfer.date}
                        onChange={(e) => setTransfer((t) => ({ ...t, date: e.target.value }))}
                      />
                      <Select
                        label="الفرع"
                        value={transfer.branch}
                        onChange={(e) => setTransfer((t) => ({ ...t, branch: e.target.value }))}
                        options={[
                          { value: '', label: 'الحساب الكلّي' },
                          ...branches.map((b) => ({ value: b.id, label: b.name })),
                        ]}
                      />
                    </div>
                    <Input
                      label="رقم الحوالة (اختياري)"
                      value={transfer.reference}
                      onChange={(e) => setTransfer((t) => ({ ...t, reference: e.target.value }))}
                      placeholder="TRF-..."
                    />
                    <Input
                      label="ملاحظات (اختياري)"
                      value={transfer.notes}
                      onChange={(e) => setTransfer((t) => ({ ...t, notes: e.target.value }))}
                      placeholder="ملاحظات..."
                    />
                    <div className="flex gap-2">
                      <Button type="submit" loading={transferLoading} className="flex-1">
                        <ArrowRightLeft size={16} />
                        تأكيد التحويل
                      </Button>
                      <Button
                        type="button"
                        variant="subtle"
                        onClick={() => setTransfer((t) => ({ ...t, open: false }))}
                      >
                        إلغاء
                      </Button>
                    </div>
                    <p className="text-[11px] text-neutral-400 leading-relaxed">
                      التحويلُ يخرج المال من الماكينة ويدخل البنك، ولا يُقبل إلا بقدر ما
                      فيها فعلاً — فالمبلغُ الأكبر يُرفض قبل أن يُسجَّل.
                    </p>
                  </form>
                ) : (
                  <p className="text-[11px] text-neutral-400 leading-relaxed mt-3">
                    الصيغةُ أعلاه تُسجّل إيداعاً يخرج من الماكينة — وهو ما تحتاجه حين
                    تحمل ماكينةُ البطاقة مالاً ثم تُودَع في البنك.
                  </p>
                )}
              </Card>

              {/* تسجيل دفعة */}
              <Card title="«وصلني كذا» — تسجيل دفعة واردة" className="lg:col-span-1">
                <form onSubmit={handleSubmit} className="space-y-3">
                  <Select
                    label="الحساب الذي سدّدته"
                    value={form.account}
                    onChange={(e) => set('account', e.target.value)}
                    options={SETTLEMENT_ACCOUNTS.map((k) => ({
                      value: k,
                      label: ACCOUNT_META[k].label,
                    }))}
                  />
                  <Input
                    label="المبلغ الواصل"
                    type="number"
                    min="0"
                    step="0.01"
                    value={form.amount}
                    onChange={(e) => set('amount', e.target.value)}
                    placeholder="0.00"
                  />
                  <div className="grid grid-cols-2 gap-3">
                    <Input
                      label="التاريخ"
                      type="date"
                      value={form.date}
                      onChange={(e) => set('date', e.target.value)}
                    />
                    <Select
                      label="الطريقة"
                      value={form.method}
                      onChange={(e) => set('method', e.target.value)}
                      options={METHODS}
                    />
                  </div>
                  <Select
                    label="الفرع"
                    value={form.branch}
                    onChange={(e) => set('branch', e.target.value)}
                    options={[
                      { value: '', label: 'الحساب الكلي (كل الفروع)' },
                      ...branches.map((b) => ({ value: b.id, label: b.name })),
                    ]}
                  />
                  <Input
                    label="مرجع التحويل / رقم العملية (اختياري)"
                    value={form.reference}
                    onChange={(e) => set('reference', e.target.value)}
                    placeholder="REF-..."
                  />
                  <Input
                    label="ملاحظات (اختياري)"
                    value={form.notes}
                    onChange={(e) => set('notes', e.target.value)}
                    placeholder="ملاحظات..."
                  />
                  <Button type="submit" loading={submitting} className="w-full">
                    <HandCoins size={18} />
                    سجّل الدفعة
                  </Button>
                  <p className="text-[11px] text-neutral-400 leading-relaxed">
                    «الطريقة» تصف كيف وصلت الدفعة، و«الحساب» أي جهة سدّدتها — دفعة
                    تحويل بنكي قد تسدّد حساب الماكينة.
                  </p>
                </form>
              </Card>

              {/* الدفعات الأخيرة */}
              <Card
                title={
                  tab === 'all'
                    ? 'آخر الدفعات الواردة'
                    : `آخر دفعات ${ACCOUNT_META[tab].label}`
                }
                className="lg:col-span-2"
              >
                {visibleCollections.length === 0 ? (
                  <EmptyState
                    title="لا توجد دفعات"
                    description="سجّل أول دفعة واردة من «وصلني كذا»"
                  />
                ) : (
                  <Table>
                    <thead>
                      <tr>
                        <Th>التاريخ</Th>
                        {tab === 'all' && <Th>الحساب</Th>}
                        <Th>المبلغ</Th>
                        <Th>الطريقة</Th>
                        <Th>الفرع</Th>
                        <Th>المرجع</Th>
                        <Th>حذف</Th>
                      </tr>
                    </thead>
                    <tbody>
                      {visibleCollections.map((c) => (
                        <Tr key={c.id}>
                          <Td>{formatDate(c.date)}</Td>
                          {tab === 'all' && <Td>{c.account_label}</Td>}
                          <Td className="tabular-nums font-medium text-emerald-700">
                            {formatCurrency(c.amount)}
                          </Td>
                          <Td>{c.method_label}</Td>
                          <Td>{c.branch_name || 'الكلي'}</Td>
                          <Td className="font-mono text-xs">{c.reference || '-'}</Td>
                          <Td>
                            <button
                              onClick={() => setDeleting(c)}
                              className="p-1.5 rounded-lg hover:bg-red-50 text-red-500 dark:hover:bg-red-500/15 dark:text-red-400 transition-colors"
                            >
                              <Trash2 size={15} />
                            </button>
                          </Td>
                        </Tr>
                      ))}
                    </tbody>
                  </Table>
                )}
                {data.recent_collections.length >= 20 && (
                  <p className="text-[11px] text-neutral-400 mt-2">
                    يُعرض أحدث 20 دفعة — صدّر CSV أو ضيّق الفترة لرؤية الباقي.
                  </p>
                )}
              </Card>
            </div>

            {/* الاتجاه الشهري */}
            {data.months.length > 0 && (
              <Card title="الاتجاه الشهري">
                <div className="h-44 flex items-end gap-2 overflow-x-auto pb-1">
                  {data.months.map((m) => {
                    const perKey = visibleKeys.map((k) => m.accounts?.[k] || EMPTY);
                    return (
                      <div
                        key={m.month}
                        className="flex flex-col items-center gap-1 min-w-[52px] flex-1"
                      >
                        <div className="flex items-end gap-1 h-28">
                          {perKey.map((f, i) => {
                            const key = visibleKeys[i];
                            return (
                              <div key={key} className="flex items-end gap-0.5 h-full">
                                <div
                                  title={`${ACCOUNT_META[key].short} — مبيعات ${formatCurrency(f.sales)}`}
                                  className={`w-3 rounded-t ${ACCOUNT_META[key].bar} opacity-80 transition-all`}
                                  style={{ height: `${Math.max((f.sales / maxMonth) * 100, 1)}%` }}
                                />
                                <div
                                  title={`${ACCOUNT_META[key].short} — وصلني ${formatCurrency(f.received)}`}
                                  className="w-3 rounded-t bg-emerald-500/80 hover:bg-emerald-600 transition-colors"
                                  style={{ height: `${Math.max((f.received / maxMonth) * 100, 1)}%` }}
                                />
                              </div>
                            );
                          })}
                        </div>
                        <div className="text-[10px] text-neutral-500">
                          {formatDate(`${m.month}-01`).slice(0, 7)}
                        </div>
                      </div>
                    );
                  })}
                </div>
                <div className="flex flex-wrap items-center gap-4 text-xs text-neutral-500 mt-2">
                  {visibleKeys.map((k) => (
                    <span key={k} className="inline-flex items-center gap-1.5">
                      <span className={`h-2.5 w-2.5 rounded-sm ${ACCOUNT_META[k].bar} opacity-80 inline-block`} />{' '}
                      مبيعات {ACCOUNT_META[k].short}
                    </span>
                  ))}
                  <span className="inline-flex items-center gap-1.5">
                    <span className="h-2.5 w-2.5 rounded-sm bg-emerald-500/80 inline-block" /> دفعات واردة
                  </span>
                  <span className="inline-flex items-center gap-1">
                    <TrendingUp size={13} /> آخر {data.months.length} شهراً داخل الفترة
                  </span>
                </div>
              </Card>
            )}

            <p className="text-[11px] text-neutral-400 leading-relaxed">
              الرصيد = مبيعات الفترة − الدفعات المستلمة لها. النقدية تُستلم فوراً فلا
              تدخل حساب تسوية، وأي دفعة بلا فرع تُحسب على الحساب الكلي.
            </p>
          </>
        )}

        <ConfirmDialog
          open={!!deleting}
          title="حذف الدفعة"
          message="هل أنت متأكد من حذف هذه الدفعة الواردة؟ سيتغيّر رصيد الحساب المستحق."
          confirmLabel="حذف"
          loading={deleteLoading}
          onConfirm={handleDelete}
          onClose={() => setDeleting(null)}
        />
      </div>
    </AppShell>
  );
}
