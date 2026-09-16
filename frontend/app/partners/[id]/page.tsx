'use client';

import { useState, useEffect, useMemo } from 'react';
import { useParams } from 'next/navigation';
import Link from 'next/link';
import AppShell from '@/components/layout/AppShell';
import Card from '@/components/ui/Card';
import Button from '@/components/ui/Button';
import Table, { Th, Td, Tr } from '@/components/ui/Table';
import DateRangeToolbar, { currentMonthRange } from '@/components/ui/DateRangeToolbar';
import Badge from '@/components/ui/Badge';
import EmptyState from '@/components/ui/EmptyState';
import Spinner from '@/components/ui/Spinner';
import Modal from '@/components/ui/Modal';
import Select from '@/components/ui/Select';
import Input from '@/components/ui/Input';
import Textarea from '@/components/ui/Textarea';
import StatCard from '@/components/ui/StatCard';
import {
  ArrowRight, Download, TrendingUp, TrendingDown, Scale, Wallet,
  Plus, Percent, Users, Sparkles, FileText,
} from 'lucide-react';
import { PartnerMovementsResult, PartnerDistributionResult, PartnerOperationType, PartnerPaymentMethod } from '@/types';
import { getPartnerMovements, getPartnerDistribution, createPartnerOperation } from '@/services/partners';
import { API_URL } from '@/services/api';
import { formatCurrency, formatDate } from '@/lib/format';
import { useToast } from '@/components/ui/Toast';

const OPERATION_TYPE_OPTIONS = [
  { value: 'support', label: 'دعم (إيداع)' },
  { value: 'withdraw', label: 'سحب' },
];

const PAYMENT_METHOD_OPTIONS = [
  { value: 'cash', label: 'كاش' },
  { value: 'transfer', label: 'تحويل بنكي' },
];

type Tab = 'statement' | 'distribution';

const TABS: { value: Tab; label: string; icon: React.ReactNode }[] = [
  { value: 'statement', label: 'كشف الحساب', icon: <FileText size={16} /> },
  { value: 'distribution', label: 'التوزيع والنسب', icon: <Percent size={16} /> },
];

export default function PartnerDetailPage() {
  const params = useParams();
  const id = Number(params.id);
  const { toast } = useToast();

  const [data, setData] = useState<PartnerMovementsResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState<Tab>('statement');
  const [distribution, setDistribution] = useState<PartnerDistributionResult | null>(null);
  const [distributionLoading, setDistributionLoading] = useState(false);

  const [dateFrom, setDateFrom] = useState(() => currentMonthRange().from);
  const [dateTo, setDateTo] = useState(() => currentMonthRange().to);

  const [opModalOpen, setOpModalOpen] = useState(false);
  const [opType, setOpType] = useState<PartnerOperationType>('support');
  const [opPayment, setOpPayment] = useState<PartnerPaymentMethod>('cash');
  const [opDate, setOpDate] = useState('');
  const [opAmount, setOpAmount] = useState('');
  const [opReason, setOpReason] = useState('');
  const [opNotes, setOpNotes] = useState('');
  const [opSaving, setOpSaving] = useState(false);

  useEffect(() => {
    if (!opModalOpen) return;
    setOpDate(new Date().toISOString().slice(0, 10));
  }, [opModalOpen]);

  const fetchData = (from: string, to: string) => {
    let cancelled = false;
    setLoading(true);
    getPartnerMovements(id, {
      date_from: from || undefined,
      date_to: to || undefined,
    })
      .then((res) => { if (!cancelled) setData(res); })
      .catch((err) => { if (!cancelled) toast('error', err.message); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  };

  const fetchDistribution = () => {
    let cancelled = false;
    setDistributionLoading(true);
    getPartnerDistribution()
      .then((res) => { if (!cancelled) setDistribution(res); })
      .catch((err) => { if (!cancelled) toast('error', err.message); })
      .finally(() => { if (!cancelled) setDistributionLoading(false); });
    return () => { cancelled = true; };
  };

  useEffect(() => fetchData(dateFrom, dateTo), [id]);

  useEffect(() => {
    if (tab === 'distribution') return fetchDistribution();
  }, [tab, id]);

  const currentItem = distribution?.items.find((it) => it.id === id) || null;

  const buildExportUrl = () => {
    const p = new URLSearchParams();
    if (dateFrom) p.append('date_from', dateFrom);
    if (dateTo) p.append('date_to', dateTo);
    p.append('export', 'xlsx');
    return `${API_URL}/partners/${id}/movements/?${p.toString()}`;
  };

  const distributionExportUrl = `${API_URL}/partners/distribution/?export=xlsx`;

  const isCurrent = (otherId: number) => otherId === id;

  const handleCreateOperation = async () => {
    const amount = parseFloat(opAmount);
    if (!opDate || !amount || amount <= 0) {
      toast('error', 'يرجى إدخال التاريخ ومبلغ صحيح أكبر من صفر');
      return;
    }
    setOpSaving(true);
    try {
      await createPartnerOperation({
        partner: id,
        date: opDate,
        operation_type: opType,
        payment_method: opPayment,
        amount,
        reason: opReason,
        notes: opNotes,
      });
      toast('success', 'تم تسجيل العملية على حساب الشريك');
      setOpModalOpen(false);
      setOpAmount('');
      setOpReason('');
      setOpNotes('');
      fetchData(dateFrom, dateTo);
      fetchDistribution();
    } catch (err: any) {
      toast('error', err.message);
    } finally {
      setOpSaving(false);
    }
  };

  const openOpModal = () => {
    setOpType('support');
    setOpPayment('cash');
    setOpDate(new Date().toISOString().slice(0, 10));
    setOpAmount('');
    setOpReason('');
    setOpNotes('');
    setOpModalOpen(true);
  };

  return (
    <AppShell>
      <div className="space-y-6">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <Link href="/partners" className="flex items-center gap-1 text-sm text-neutral-500 hover:text-brand-600 transition-colors">
              <ArrowRight size={16} />
              الشركاء
            </Link>
            <h1 className="text-2xl font-bold">
              {tab === 'statement' ? 'كشف حساب الشريك: ' : 'توزيع الأرباح والنسب — '}
              <span className="text-brand-600">{data?.partner.name || '...'}</span>
            </h1>
          </div>
          <div className="flex items-center gap-2">
            <Button variant="secondary" onClick={openOpModal}>
              <Plus size={16} />
              تسجيل عملية
            </Button>
            {tab === 'statement' ? (
              <a href={buildExportUrl()} className="inline-flex items-center gap-2 rounded-xl bg-surface px-5 py-2.5 text-sm font-medium text-neutral-700 border border-sand-300 hover:bg-sand-50 transition-all">
                <Download size={16} />
                تصدير الكشف (Excel)
              </a>
            ) : (
              <a href={distributionExportUrl} target="_blank" rel="noreferrer" className="inline-flex items-center gap-2 rounded-xl bg-surface px-5 py-2.5 text-sm font-medium text-neutral-700 border border-sand-300 hover:bg-sand-50 transition-all">
                <Download size={16} />
                تصدير التوزيع (Excel)
              </a>
            )}
          </div>
        </div>

        <Card>
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div className="flex items-center gap-4">
              <span className="flex h-12 w-12 items-center justify-center rounded-full bg-brand-50 text-xl font-bold text-brand-700">
                {data?.partner.name.charAt(0) || '?'}
              </span>
              <div>
                <div className="font-semibold">{data?.partner.name || '...'}</div>
                <Badge variant={data?.partner.is_active ? 'success' : 'neutral'}>
                  {data?.partner.is_active ? 'شريك نشط' : 'موقوف'} · النسبة {data?.partner.share_percent}%
                </Badge>
              </div>
            </div>
            <div className="flex gap-2">
              {TABS.map((t) => (
                <button
                  key={t.value}
                  onClick={() => setTab(t.value)}
                  className={`inline-flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-medium transition-all duration-150 ${
                    tab === t.value
                      ? 'bg-brand-600 text-white shadow-sm'
                      : 'bg-surface text-neutral-600 border border-sand-200 hover:bg-sand-50'
                  }`}
                >
                  {t.icon}
                  {t.label}
                </button>
              ))}
            </div>
          </div>
        </Card>

        {tab === 'statement' && (
          <div className="space-y-4">
            <Card className="!p-4">
              <DateRangeToolbar from={dateFrom} to={dateTo} onChange={(f, t) => { setDateFrom(f); setDateTo(t); fetchData(f, t); }} />
            </Card>

            {data && (
              <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-4">
                <StatCard icon={<Wallet size={20} />} label="الرصيد الافتتاحي" value={formatCurrency(data.opening_balance)} sub="قبل بداية الفترة" />
                <StatCard icon={<TrendingUp size={20} />} iconBg="bg-emerald-50 text-emerald-600" label="الدعم في الفترة" value={formatCurrency(data.totals.total_support)} />
                <StatCard icon={<TrendingDown size={20} />} iconBg="bg-red-50 text-red-600" label="السحب في الفترة" value={formatCurrency(data.totals.total_withdraw)} />
                <StatCard
                  icon={<Scale size={20} />}
                  iconBg={data.totals.net < 0 ? 'bg-red-50 text-red-600' : 'bg-emerald-50 text-emerald-600'}
                  label="صافي الفترة"
                  value={formatCurrency(data.totals.net)}
                />
                <StatCard
                  icon={<Wallet size={20} />}
                  iconBg={data.closing_balance < 0 ? 'bg-red-50 text-red-600' : 'bg-brand-50 text-brand-600'}
                  label="الرصيد الختامي"
                  value={formatCurrency(data.closing_balance)}
                  sub="رصيد الشريك بعد الفترة"
                />
              </div>
            )}

            <Card title={`حركة الحساب — ${data?.movements.length ?? 0} حركة`}>
              {loading ? (
                <div className="flex justify-center py-12"><Spinner size={32} /></div>
              ) : !data || data.movements.length === 0 ? (
                <EmptyState title="لا توجد حركات" description="لم تُسجل أي حركات في هذه الفترة على حساب هذا الشريك" />
              ) : (
                <Table>
                  <thead>
                    <tr>
                      <Th>التاريخ</Th>
                      <Th>رقم العملية</Th>
                      <Th>النوع</Th>
                      <Th>طريقة الدفع</Th>
                      <Th>المبلغ</Th>
                      <Th>الرصيد الجاري</Th>
                      <Th>السبب</Th>
                      <Th>ملاحظات</Th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.movements.map((m) => (
                      <Tr key={m.id}>
                        <Td>{formatDate(m.date)}</Td>
                        <Td className="tabular-nums font-medium">{m.number}</Td>
                        <Td>
                          <Badge variant={m.movement_type === 'support' ? 'success' : 'danger'}>
                            {m.movement_type_label}
                          </Badge>
                        </Td>
                        <Td>
                          <Badge variant={m.payment_method === 'cash' ? 'neutral' : 'warning'}>
                            {m.payment_method_label}
                          </Badge>
                        </Td>
                        <Td className="tabular-nums font-medium">
                          <span className={m.movement_type === 'support' ? 'text-emerald-600' : 'text-red-500'}>
                            {formatCurrency(m.amount)}
                          </span>
                        </Td>
                        <Td className="tabular-nums">{formatCurrency(m.running_balance)}</Td>
                        <Td className="max-w-[180px] truncate">{m.reason || '-'}</Td>
                        <Td className="max-w-[160px] truncate">{m.notes || '-'}</Td>
                      </Tr>
                    ))}
                  </tbody>
                </Table>
              )}
            </Card>
          </div>
        )}

        {tab === 'distribution' && (
          <div className="space-y-4">
            {distributionLoading && distribution === null ? (
              <Card><div className="flex justify-center py-12"><Spinner size={32} /></div></Card>
            ) : distribution ? (
              <>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                  <StatCard icon={<Scale size={20} />} iconBg="bg-emerald-50 text-emerald-600" label="إجمالي صافي رأس المال" value={formatCurrency(distribution.total_net)} />
                  <StatCard icon={<Users size={20} />} label="نسبة مشاركة الشريك" value={currentItem ? `${currentItem.share_percent}%` : '-'} sub={data?.partner.name} />
                  <StatCard icon={<Wallet size={20} />} label="رصيده الفعلي" value={currentItem ? formatCurrency(currentItem.actual_net) : '-'} sub="الدعم − السحب" />
                  <StatCard
                    icon={currentItem && currentItem.difference >= 0 ? <TrendingUp size={20} /> : <TrendingDown size={20} />}
                    iconBg={currentItem && currentItem.difference < 0 ? 'bg-red-50 text-red-600' : 'bg-brand-50 text-brand-600'}
                    label="النصيب النظري"
                    value={currentItem ? formatCurrency(currentItem.theoretical_share) : '-'}
                    sub="صافي رأس المال × النسبة"
                  />
                </div>

                <Card className="!p-5">
                  <div className="flex flex-wrap items-center justify-between gap-3">
                    <div className="flex items-center gap-3">
                      <span className="flex h-10 w-10 items-center justify-center rounded-full bg-brand-50 text-lg font-bold text-brand-700">
                        {data?.partner.name.charAt(0) || '?'}
                      </span>
                      <div>
                        <div className="font-semibold">{data?.partner.name}</div>
                        <div className="text-xs text-neutral-500">حالة الشريك مقارنة بنصيبه النظري</div>
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      {currentItem ? (
                        Math.abs(currentItem.difference) < 0.005 ? (
                          <Badge variant="success">رصيده مطابق لنسبته</Badge>
                        ) : currentItem.difference > 0 ? (
                          <Badge variant="warning">أقل من نصيبه بـ {formatCurrency(currentItem.difference)}</Badge>
                        ) : (
                          <Badge variant="danger">أعلى من نصيبه بـ {formatCurrency(Math.abs(currentItem.difference))}</Badge>
                        )
                      ) : null}
                    </div>
                  </div>
                  {currentItem && Math.abs(currentItem.theoretical_share) > 0 && (
                    <div className="mt-4">
                      <div className="mb-1 flex items-center justify-between text-xs text-neutral-500">
                        <span>الرصيد الفعلي نسبةً إلى النصيب النظري</span>
                        <span className="tabular-nums">
                          {formatCurrency(currentItem.actual_net)} / {formatCurrency(currentItem.theoretical_share)}
                        </span>
                      </div>
                      <div className="h-2 rounded-full bg-sand-100 overflow-hidden">
                        <div
                          className={`h-full rounded-full ${currentItem.difference < 0 ? 'bg-red-400' : 'bg-brand-500'}`}
                          style={{ width: `${Math.min(Math.abs(currentItem.theoretical_share) > 0 ? (Math.abs(currentItem.actual_net) / Math.abs(currentItem.theoretical_share)) * 100 : 0, 100)}%` }}
                        />
                      </div>
                    </div>
                  )}
                </Card>

                <Card title={`توزيع الأرباح على جميع الشركاء (${distribution.items.length})`}>
                  {distribution.items.length === 0 ? (
                    <EmptyState title="لا يوجد شركاء نشطون" description="أضف شركاء نشطين لعرض توزيع الأرباح" />
                  ) : (
                    <Table>
                      <thead>
                        <tr>
                          <Th>الشريك</Th>
                          <Th>نسبة المشاركة</Th>
                          <Th>الصافي الفعلي</Th>
                          <Th>النصيب النظري</Th>
                          <Th>الفرق</Th>
                          <Th>الحالة</Th>
                        </tr>
                      </thead>
                      <tbody>
                        {distribution.items.map((it) => (
                          <Tr key={it.id} className={isCurrent(it.id) ? 'bg-brand-50/50' : ''}>
                            <Td className="font-medium">
                              <span className="inline-flex items-center gap-2">
                                {it.name}
                                {isCurrent(it.id) && <Badge variant="neutral">هذا الشريك</Badge>}
                              </span>
                            </Td>
                            <Td className="tabular-nums">{it.share_percent}%</Td>
                            <Td className="tabular-nums">{formatCurrency(it.actual_net)}</Td>
                            <Td className="tabular-nums">{formatCurrency(it.theoretical_share)}</Td>
                            <Td className={`tabular-nums font-medium ${it.difference > 0.005 ? 'text-amber-600' : it.difference < -0.005 ? 'text-red-500' : ''}`}>
                              {it.difference > 0.005 ? '+' : ''}{formatCurrency(it.difference)}
                            </Td>
                            <Td>
                              {Math.abs(it.difference) < 0.005 ? (
                                <Badge variant="success">مطابق لنسبته</Badge>
                              ) : it.difference > 0 ? (
                                <Badge variant="warning">أقل من نصيبه</Badge>
                              ) : (
                                <Badge variant="danger">أعلى من نصيبه</Badge>
                              )}
                            </Td>
                          </Tr>
                        ))}
                      </tbody>
                    </Table>
                  )}
                </Card>

                <Card className="!p-4">
                  <p className="flex items-start gap-2 text-sm text-neutral-500">
                    <Sparkles size={16} className="mt-0.5 text-brand-500 shrink-0" />
                    «النصيب النظري» = إجمالي صافي رأس المال × نسبة مشاركة الشريك ÷ 100. سجّل عمليات دعم أو سحب لهذا الشريك من زر
                    «تسجيل عملية» لتقريب رصيده من نصيبه النظري.
                  </p>
                </Card>
              </>
            ) : null}
          </div>
        )}

        <Modal open={opModalOpen} onClose={() => setOpModalOpen(false)} title={`تسجيل عملية — ${data?.partner.name || ''}`} maxWidth="max-w-lg">
          <div className="space-y-4">
            <div className="rounded-xl border border-brand-200 bg-brand-50 px-4 py-3 text-sm text-brand-800">
              تُسجَّل العملية على الشريك المحدد فقط: دعم يزيد رصيده، وسحب يخصمه من رصيده.
            </div>
            <div className="grid grid-cols-2 gap-4">
              <Select
                label="نوع العملية"
                value={opType}
                onChange={(e) => setOpType(e.target.value as PartnerOperationType)}
                options={OPERATION_TYPE_OPTIONS}
              />
              <Select
                label="طريقة الدفع"
                value={opPayment}
                onChange={(e) => setOpPayment(e.target.value as PartnerPaymentMethod)}
                options={PAYMENT_METHOD_OPTIONS}
              />
            </div>
            <div className="grid grid-cols-2 gap-4">
              <Input label="التاريخ" type="date" value={opDate} onChange={(e) => setOpDate(e.target.value)} />
              <Input
                label="المبلغ"
                type="number"
                min="0"
                step="0.01"
                value={opAmount}
                onChange={(e) => setOpAmount(e.target.value)}
                placeholder=""
              />
            </div>
            <Input
              label="السبب"
              value={opReason}
              onChange={(e) => setOpReason(e.target.value)}
              placeholder="مثال: دعم رأس المال / سحب أرباح..."
            />
            <Textarea
              label="ملاحظات"
              value={opNotes}
              onChange={(e) => setOpNotes(e.target.value)}
              placeholder="ملاحظات اختيارية..."
            />
            <div className="flex items-center justify-end gap-2 pt-2">
              <Button variant="secondary" onClick={() => setOpModalOpen(false)}>إلغاء</Button>
              <Button onClick={handleCreateOperation} loading={opSaving}>تسجيل العملية</Button>
            </div>
          </div>
        </Modal>
      </div>
    </AppShell>
  );
}