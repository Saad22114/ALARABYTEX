'use client';

import { useCallback, useEffect, useState } from 'react';
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
import { Landmark, Banknote, HandCoins, Trash2, CreditCard, TrendingUp } from 'lucide-react';
import { Branch, MachineAccountResult, MachineCollection } from '@/types';
import { getMachineAccount, createCollection, deleteCollection } from '@/services/machine';
import { listBranches } from '@/services/branches';
import { formatCurrency, formatDate } from '@/lib/format';
import { useToast } from '@/components/ui/Toast';
import { useUrlState } from '@/lib/useUrlState';

const METHODS = [
  { value: 'transfer', label: 'تحويل بنكي' },
  { value: 'cash', label: 'نقدي' },
  { value: 'other', label: 'أخرى' },
];

export default function MachineAccountPage() {
  const { toast } = useToast();
  const [data, setData] = useState<MachineAccountResult | null>(null);
  const [branches, setBranches] = useState<Branch[]>([]);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);

  const [from, setFrom] = useUrlState('from', currentMonthRange().from);
  const [to, setTo] = useUrlState('to', currentMonthRange().to);
  const [branchFilter, setBranchFilter] = useUrlState('branch', '');

  const [form, setForm] = useState({
    date: new Date().toISOString().slice(0, 10),
    amount: '',
    method: 'transfer',
    branch: '',
    reference: '',
    notes: '',
  });
  const [deleting, setDeleting] = useState<MachineCollection | null>(null);
  const [deleteLoading, setDeleteLoading] = useState(false);

  const fetchData = useCallback(() => {
    const params: Record<string, string> = { date_from: from, date_to: to };
    if (branchFilter) params.branch = branchFilter;
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
      .catch((err) => { if (!cancelled) toast('error', err.message); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [fetchData, toast]);

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
        date: form.date,
        amount,
        method: form.method,
        branch: form.branch ? Number(form.branch) : null,
        reference: form.reference,
        notes: form.notes,
      });
      toast('success', 'تم تسجيل الدفعة — سجّلتها، والمتبقي محدّث');
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

  const set = (key: string, val: string) => setForm((f) => ({ ...f, [key]: val }));

  const maxMonth = Math.max(...(data?.months || []).map((m) => Math.max(m.card_sales, m.received)), 1);

  return (
    <AppShell>
      <div className="space-y-6">
        <div className="flex items-center gap-3">
          <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-brand-600 text-white">
            <CreditCard size={22} />
          </div>
          <div>
            <h1 className="text-xl font-bold">حساب الماكينة</h1>
            <p className="text-sm text-neutral-500">مبيعات البطاقة مقابل الدفعات الواردة — لتعرف كم باقي لك عند شركة الدفع</p>
          </div>
        </div>

        <Card className="!p-4">
          <div className="flex flex-wrap items-end gap-4">
            <DateRangeToolbar from={from} to={to} onChange={(f, t) => { setFrom(f); setTo(t); }} />
            <Select
              value={branchFilter}
              onChange={(e) => setBranchFilter(e.target.value)}
              options={[{ value: '', label: 'كل الفروع' }, ...branches.map((b) => ({ value: b.id, label: b.name }))]}
              className="w-full sm:w-48"
            />
          </div>
        </Card>

        {loading ? (
          <div className="flex justify-center py-16"><Spinner size={36} /></div>
        ) : !data ? (
          <EmptyState title="تعذر التحميل" description="لم نتمكن من جلب بيانات حساب الماكينة" />
        ) : (
          <>
            {/* بطاقات الملخص */}
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
              <Card className="!p-4">
                <div className="flex items-center justify-between">
                  <div className="text-xs text-neutral-500 mb-1">مبيعات البطاقة (الفترة)</div>
                  <Banknote size={18} className="text-brand-500" />
                </div>
                <div className="text-xl font-bold tabular-nums text-brand-700">{formatCurrency(data.totals.card_sales)}</div>
                <div className="text-xs text-neutral-400 mt-1">هذا الشهر: {formatCurrency(data.month.card_sales)}</div>
              </Card>
              <Card className="!p-4">
                <div className="flex items-center justify-between">
                  <div className="text-xs text-neutral-500 mb-1">الدفعات المستلمة (وصلني)</div>
                  <Landmark size={18} className="text-emerald-500" />
                </div>
                <div className="text-xl font-bold tabular-nums text-emerald-700">{formatCurrency(data.totals.received)}</div>
                <div className="text-xs text-neutral-400 mt-1">هذا الشهر: {formatCurrency(data.month.received)}</div>
              </Card>
              <Card className="!p-4">
                <div className="flex items-center justify-between">
                  <div className="text-xs text-neutral-500 mb-1">المتبقي المستحق (يجب أن يصل)</div>
                  <HandCoins size={18} className="text-amber-500" />
                </div>
                <div className={`text-2xl font-bold tabular-nums ${data.totals.balance < 0 ? 'text-red-600' : 'text-amber-600'}`}>
                  {formatCurrency(data.totals.balance)}
                </div>
                <div className="text-xs text-neutral-400 mt-1">مبيعات البطاقة − الدفعات الواردة</div>
              </Card>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
              {/* تسجيل دفعة */}
              <Card title="«وصلني كذا» — تسجيل دفعة واردة" className="lg:col-span-1">
                <form onSubmit={handleSubmit} className="space-y-3">
                  <Input label="المبلغ الواصل" type="number" min="0" step="0.01" value={form.amount} onChange={(e) => set('amount', e.target.value)} placeholder="0.00" />
                  <div className="grid grid-cols-2 gap-3">
                    <Input label="التاريخ" type="date" value={form.date} onChange={(e) => set('date', e.target.value)} />
                    <Select label="الطريقة" value={form.method} onChange={(e) => set('method', e.target.value)} options={METHODS} />
                  </div>
                  <Select
                    label="الفرع"
                    value={form.branch}
                    onChange={(e) => set('branch', e.target.value)}
                    options={[{ value: '', label: 'الحساب الكلي (كل الفروع)' }, ...branches.map((b) => ({ value: b.id, label: b.name }))]}
                  />
                  <Input label="مرجع التحويل / رقم العملية (اختياري)" value={form.reference} onChange={(e) => set('reference', e.target.value)} placeholder="REF-..." />
                  <Input label="ملاحظات (اختياري)" value={form.notes} onChange={(e) => set('notes', e.target.value)} placeholder="ملاحظات..." />
                  <Button type="submit" loading={submitting} className="w-full">
                    <HandCoins size={18} />
                    سجّل الدفعة
                  </Button>
                </form>
              </Card>

              {/* الدفعات الأخيرة */}
              <Card title="آخر الدفعات الواردة" className="lg:col-span-2">
                {data.recent_collections.length === 0 ? (
                  <EmptyState title="لا توجد دفعات" description="سجّل أول دفعة واردة من «وصلني كذا»" />
                ) : (
                  <Table>
                    <thead>
                      <tr>
                        <Th>التاريخ</Th>
                        <Th>المبلغ</Th>
                        <Th>الطريقة</Th>
                        <Th>الفرع</Th>
                        <Th>المرجع</Th>
                        <Th>حذف</Th>
                      </tr>
                    </thead>
                    <tbody>
                      {data.recent_collections.map((c) => (
                        <Tr key={c.id}>
                          <Td>{formatDate(c.date)}</Td>
                          <Td className="tabular-nums font-medium text-emerald-700">{formatCurrency(c.amount)}</Td>
                          <Td>{c.method_label}</Td>
                          <Td>{c.branch_name || 'الكلي'}</Td>
                          <Td className="font-mono text-xs">{c.reference || '-'}</Td>
                          <Td>
                            <button onClick={() => setDeleting(c)} className="p-1.5 rounded-lg hover:bg-red-50 text-red-500 dark:hover:bg-red-500/15 dark:text-red-400 transition-colors">
                              <Trash2 size={15} />
                            </button>
                          </Td>
                        </Tr>
                      ))}
                    </tbody>
                  </Table>
                )}
              </Card>
            </div>

            {/* الاتجاه الشهري */}
            {data.months.length > 0 && (
              <Card title="الاتجاه الشهري">
                <div className="h-44 flex items-end gap-2 overflow-x-auto pb-1">
                  {data.months.map((m) => (
                    <div key={m.month} className="flex flex-col items-center gap-1 min-w-[40px] flex-1">
                      <div className="flex items-end gap-1 h-28">
                        <div
                          title={`مبيعات ${formatCurrency(m.card_sales)}`}
                          className="w-3 rounded-t bg-brand-500/80 hover:bg-brand-600 transition-colors"
                          style={{ height: `${Math.max((m.card_sales / maxMonth) * 100, 1)}%` }}
                        />
                        <div
                          title={`وارد ${formatCurrency(m.received)}`}
                          className="w-3 rounded-t bg-emerald-500/80 hover:bg-emerald-600 transition-colors"
                          style={{ height: `${Math.max((m.received / maxMonth) * 100, 1)}%` }}
                        />
                      </div>
                      <div className="text-[10px] text-neutral-500">{formatDate(`${m.month}-01`).slice(0, 7)}</div>
                    </div>
                  ))}
                </div>
                <div className="flex items-center gap-4 text-xs text-neutral-500 mt-2">
                  <span className="inline-flex items-center gap-1.5"><span className="h-2.5 w-2.5 rounded-sm bg-brand-500/80 inline-block" /> مبيعات بطاقة</span>
                  <span className="inline-flex items-center gap-1.5"><span className="h-2.5 w-2.5 rounded-sm bg-emerald-500/80 inline-block" /> دفعات واردة</span>
                  <span className="inline-flex items-center gap-1"><TrendingUp size={13} /> آخر {data.months.length} شهراً داخل الفترة</span>
                </div>
              </Card>
            )}
          </>
        )}

        <ConfirmDialog
          open={!!deleting}
          title="حذف الدفعة"
          message="هل أنت متأكد من حذف هذه الدفعة الواردة؟ سيتغير رصيد الماكينة المستحق."
          confirmLabel="حذف"
          loading={deleteLoading}
          onConfirm={handleDelete}
          onClose={() => setDeleting(null)}
        />
      </div>
    </AppShell>
  );
}