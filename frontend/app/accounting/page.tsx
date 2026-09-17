'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import AppShell from '@/components/layout/AppShell';
import Card from '@/components/ui/Card';
import Button from '@/components/ui/Button';
import Table, { Th, Td, Tr } from '@/components/ui/Table';
import Input from '@/components/ui/Input';
import Select from '@/components/ui/Select';
import DateRangePicker from '@/components/ui/DateRangePicker';
import Spinner from '@/components/ui/Spinner';
import EmptyState from '@/components/ui/EmptyState';
import Badge from '@/components/ui/Badge';
import Modal from '@/components/ui/Modal';
import ConfirmDialog from '@/components/ui/ConfirmDialog';
import SearchInput from '@/components/ui/SearchInput';
import { useToast } from '@/components/ui/Toast';
import { useSettings } from '@/components/providers/SettingsProvider';
import { useUrlState } from '@/lib/useUrlState';
import { Plus, Pencil, Trash2, RotateCcw, ChevronDown, Lock } from 'lucide-react';
import {
  Account,
  AccountType,
  BalanceSheet,
  CashBox,
  CashFlow,
  ClosedPeriod,
  IncomeStatement,
  JournalEntry,
  JournalSource,
  Paginated,
  TrialBalance,
} from '@/types';
import {
  listAccounts,
  createAccount,
  updateAccount,
  deleteAccount,
  listJournalEntries,
  createJournalEntry,
  deleteJournalEntry,
  reverseJournalEntry,
  getTrialBalance,
  getIncomeStatement,
  getBalanceSheet,
  getCashFlow,
  getCashBox,
  listClosedPeriods,
  closePeriod,
} from '@/services/accounting';
import { formatCurrency, formatDate } from '@/lib/format';

type Tab = 'journal' | 'accounts' | 'trial-balance' | 'statements' | 'cashbox';
type StatementTab = 'income' | 'balance' | 'cash-flow';

const tabs: { value: Tab; label: string }[] = [
  { value: 'journal', label: 'دفتر اليومية' },
  { value: 'accounts', label: 'شجرة الحسابات' },
  { value: 'trial-balance', label: 'ميزان المراجعة' },
  { value: 'statements', label: 'القوائم المالية' },
  { value: 'cashbox', label: 'الخزينة والإقفال' },
];

const statementTabs: { value: StatementTab; label: string }[] = [
  { value: 'income', label: 'قائمة الدخل' },
  { value: 'balance', label: 'الميزانية العمومية' },
  { value: 'cash-flow', label: 'حركة النقد والبنك' },
];

const SOURCE_LABELS: Record<JournalSource, string> = {
  manual: 'يدوي',
  session: 'إغلاق وردية',
  purchase: 'الموردون',
  expense: 'مصروف',
  partner: 'الشركاء',
  closing: 'إقفال دوري',
};

const TYPE_LABELS: Record<AccountType, string> = {
  asset: 'أصل',
  liability: 'التزام',
  equity: 'حقوق ملكية',
  income: 'إيراد',
  expense: 'مصروف',
};

const TYPE_VARIANTS: Record<AccountType, 'success' | 'warning' | 'danger' | 'neutral'> = {
  asset: 'neutral',
  liability: 'warning',
  equity: 'neutral',
  income: 'success',
  expense: 'danger',
};

type SourceVariant = 'success' | 'warning' | 'danger' | 'neutral';
const SOURCE_VARIANTS: Record<JournalSource, SourceVariant> = {
  manual: 'neutral',
  session: 'success',
  purchase: 'warning',
  expense: 'danger',
  partner: 'neutral',
  closing: 'neutral',
};

interface ManualLine {
  account: number;
  debit: string;
  credit: string;
  description: string;
}

interface AccountFormState {
  code: string;
  name: string;
  type: AccountType;
  parent: number | '';
  is_active: boolean;
}

export default function AccountingPage() {
  const { toast } = useToast();
  const { settings } = useSettings();
  const pageSize = settings?.default_page_size ?? 10;

  const [activeTab, setActiveTab] = useUrlState<Tab>('tab', 'journal');
  const [statementTab, setStatementTab] = useUrlState<StatementTab>('statement', 'income');
  const [loading, setLoading] = useState(false);

  // shared date filters
  const [dateFrom, setDateFrom] = useUrlState('from', '');
  const [dateTo, setDateTo] = useUrlState('to', '');
  const today = new Date().toISOString().slice(0, 10);

  // journal
  const [entries, setEntries] = useState<Paginated<JournalEntry> | null>(null);
  const [journalFilter, setJournalFilter] = useUrlState('source', '');
  const [journalPage, setJournalPage] = useUrlState('jpage', 1);
  const [entryModalOpen, setEntryModalOpen] = useState(false);
  const [entryDate, setEntryDate] = useState(today);
  const [entryDescription, setEntryDescription] = useState('');
  const [entryLines, setEntryLines] = useState<ManualLine[]>([{ account: 0, debit: '', credit: '', description: '' }]);
  const [entrySubmitting, setEntrySubmitting] = useState(false);
  const [deletingEntry, setDeletingEntry] = useState<JournalEntry | null>(null);
  const [reversingEntry, setReversingEntry] = useState<JournalEntry | null>(null);

  // accounts tree
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [accountSearch, setAccountSearch] = useState('');
  const [accModalOpen, setAccModalOpen] = useState(false);
  const [editingAccount, setEditingAccount] = useState<Account | null>(null);
  const [accForm, setAccForm] = useState<AccountFormState>({ code: '', name: '', type: 'asset', parent: '', is_active: true });
  const [accSubmitting, setAccSubmitting] = useState(false);
  const [deletingAccount, setDeletingAccount] = useState<Account | null>(null);

  // reports
  const [trialBalance, setTrialBalance] = useState<TrialBalance | null>(null);
  const [tbDate, setTbDate] = useUrlState('tb_date', today);
  const [income, setIncome] = useState<IncomeStatement | null>(null);
  const [balanceSheet, setBalanceSheet] = useState<BalanceSheet | null>(null);
  const [cashFlow, setCashFlow] = useState<CashFlow | null>(null);

  // cashbox / closing
  const [cashBoxData, setCashBoxData] = useState<CashBox | null>(null);
  const [cashBoxDate, setCashBoxDate] = useUrlState('cashbox_date', today);
  const [closedPeriods, setClosedPeriods] = useState<ClosedPeriod[]>([]);
  const [closeDate, setCloseDate] = useState(today);
  const [closeDescription, setCloseDescription] = useState('');
  const [closeLoading, setCloseLoading] = useState(false);

  const [expandedEntry, setExpandedEntry] = useState<number | null>(null);

  const loadJournal = useCallback(() => {
    let cancelled = false;
    setLoading(true);
    const params: Record<string, string | number | undefined | null> = {
      page: journalPage,
      page_size: 100,
      source: journalFilter || undefined,
      from: dateFrom || undefined,
      to: dateTo || undefined,
    };
    listJournalEntries(params)
      .then((res) => { if (!cancelled) setEntries(res); })
      .catch((err: any) => { if (!cancelled) toast('error', err.message); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [journalPage, journalFilter, dateFrom, dateTo, toast]);

  const loadAccounts = useCallback(() => {
    let cancelled = false;
    listAccounts({ page_size: 500, search: accountSearch || undefined })
      .then((res) => { if (!cancelled) setAccounts(res.results); })
      .catch((err: any) => { if (!cancelled) toast('error', err.message); });
    return () => { cancelled = true; };
  }, [accountSearch, toast]);

  const loadCashboxAndPeriods = useCallback(() => {
    let cancelled = false;
    setLoading(true);
    Promise.all([
      getCashBox({ date: cashBoxDate || undefined }),
      listClosedPeriods(),
    ])
      .then(([cb, periods]) => {
        if (cancelled) return;
        setCashBoxData(cb);
        setClosedPeriods(periods);
      })
      .catch((err: any) => { if (!cancelled) toast('error', err.message); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [cashBoxDate, toast]);

  useEffect(() => {
    if (activeTab === 'journal') return loadJournal();
  }, [activeTab, loadJournal]);

  useEffect(() => {
    if (activeTab === 'accounts') return loadAccounts();
  }, [activeTab, loadAccounts]);

  useEffect(() => {
    if (activeTab !== 'trial-balance') return;
    let cancelled = false;
    setLoading(true);
    getTrialBalance({ to: tbDate || undefined })
      .then((res) => { if (!cancelled) setTrialBalance(res); })
      .catch((err: any) => { if (!cancelled) toast('error', err.message); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [activeTab, tbDate, toast]);

  useEffect(() => {
    if (activeTab !== 'statements') return;
    let cancelled = false;
    setLoading(true);
    const params: Record<string, string | number | undefined | null> = {
      from: dateFrom || undefined,
      to: dateTo || undefined,
    };
    let p: Promise<unknown>;
    if (statementTab === 'income') p = getIncomeStatement(params);
    else if (statementTab === 'balance') p = getBalanceSheet({ to: dateTo || undefined });
    else p = getCashFlow(params);
    p.then((res: any) => {
      if (cancelled) return;
      if (statementTab === 'income') setIncome(res);
      else if (statementTab === 'balance') setBalanceSheet(res);
      else setCashFlow(res);
    })
      .catch((err: any) => { if (!cancelled) toast('error', err.message); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [activeTab, statementTab, dateFrom, dateTo, toast]);

  useEffect(() => {
    if (activeTab === 'cashbox') return loadCashboxAndPeriods();
  }, [activeTab, loadCashboxAndPeriods]);

  const accountOptions = useMemo(
    () => accounts.sort((a, b) => a.code.localeCompare(b.code)).map((a) => ({ value: a.id, label: `${a.code} — ${a.name}` })),
    [accounts]
  );

  const entryTotals = useMemo(() => {
    let debit = 0;
    let credit = 0;
    entryLines.forEach((l) => {
      debit += parseFloat(l.debit) || 0;
      credit += parseFloat(l.credit) || 0;
    });
    return { debit, credit, balanced: Math.abs(debit - credit) < 0.01 };
  }, [entryLines]);

  const handleAddLine = () => {
    setEntryLines((prev) => [...prev, { account: 0, debit: '', credit: '', description: '' }]);
  };

  const handleRemoveLine = (idx: number) => {
    setEntryLines((prev) => (prev.length === 1 ? prev : prev.filter((_, i) => i !== idx)));
  };

  const handleLineChange = (idx: number, field: keyof ManualLine, value: string | number) => {
    setEntryLines((prev) => prev.map((l, i) => (i === idx ? { ...l, [field]: value } : l)));
  };

  const handleSaveEntry = async () => {
    if (entryLines.length === 0) {
      toast('error', 'أضف سطراً واحداً على الأقل');
      return;
    }
    if (!entryTotals.balanced) {
      toast('error', 'القيد غير متوازن — مجموع المدين لا يساوي الدائن');
      return;
    }
    if (entryLines.some((l) => !l.account)) {
      toast('error', 'اختر الحساب لكل سطر');
      return;
    }
    setEntrySubmitting(true);
    try {
      await createJournalEntry({
        date: entryDate,
        description: entryDescription,
        lines: entryLines.map((l) => ({
          account: l.account,
          debit: parseFloat(l.debit) || 0,
          credit: parseFloat(l.credit) || 0,
          description: l.description,
        })),
      });
      toast('success', 'تم تسجيل القيد بنجاح');
      setEntryModalOpen(false);
      setEntryDescription('');
      setEntryLines([{ account: 0, debit: '', credit: '', description: '' }]);
      loadJournal();
    } catch (err: any) {
      toast('error', err.message);
    } finally {
      setEntrySubmitting(false);
    }
  };

  const handleDeleteEntry = async () => {
    if (!deletingEntry) return;
    setEntrySubmitting(true);
    try {
      await deleteJournalEntry(deletingEntry.id);
      toast('success', 'تم حذف القيد');
      setDeletingEntry(null);
      loadJournal();
    } catch (err: any) {
      toast('error', err.message);
    } finally {
      setEntrySubmitting(false);
    }
  };

  const handleReverseEntry = async () => {
    if (!reversingEntry) return;
    setEntrySubmitting(true);
    try {
      await reverseJournalEntry(reversingEntry.id);
      toast('success', 'تم عكس القيد');
      setReversingEntry(null);
      loadJournal();
    } catch (err: any) {
      toast('error', err.message);
    } finally {
      setEntrySubmitting(false);
    }
  };

  const openAccountModal = (acc: Account | null) => {
    setEditingAccount(acc);
    if (acc) {
      setAccForm({ code: acc.code, name: acc.name, type: acc.type, parent: acc.parent ?? '', is_active: acc.is_active });
    } else {
      setAccForm({ code: '', name: '', type: 'asset', parent: '', is_active: true });
    }
    setAccModalOpen(true);
  };

  const handleSaveAccount = async () => {
    if (!accForm.code.trim() || !accForm.name.trim()) {
      toast('error', 'أدخل كود واسم الحساب');
      return;
    }
    setAccSubmitting(true);
    const payload: Record<string, unknown> = {
      code: accForm.code.trim(),
      name: accForm.name.trim(),
      type: accForm.type,
      is_active: accForm.is_active,
    };
    if (accForm.parent !== '') payload.parent = accForm.parent;
    try {
      if (editingAccount) {
        await updateAccount(editingAccount.id, payload);
        toast('success', 'تم تحديث الحساب');
      } else {
        await createAccount(payload);
        toast('success', 'تم إنشاء الحساب');
      }
      setAccModalOpen(false);
      loadAccounts();
    } catch (err: any) {
      toast('error', err.message);
    } finally {
      setAccSubmitting(false);
    }
  };

  const handleDeleteAccount = async () => {
    if (!deletingAccount) return;
    setAccSubmitting(true);
    try {
      await deleteAccount(deletingAccount.id);
      toast('success', 'تم حذف الحساب');
      setDeletingAccount(null);
      loadAccounts();
    } catch (err: any) {
      toast('error', err.message);
    } finally {
      setAccSubmitting(false);
    }
  };

  const handleClosePeriod = async () => {
    if (!closeDate) {
      toast('error', 'اختر تاريخ نهاية الفترة');
      return;
    }
    setCloseLoading(true);
    try {
      const res = await closePeriod(closeDate, closeDescription);
      toast('success', `تم إقفال الفترة — صافي الأرباح ${formatCurrency(res.net_profit)}`);
      setCloseDescription('');
      loadCashboxAndPeriods();
    } catch (err: any) {
      toast('error', err.message);
    } finally {
      setCloseLoading(false);
    }
  };

  const tree = useMemo(() => {
    const childrenMap = new Map<number | null, Account[]>();
    accounts.forEach((a) => {
      const key = a.parent;
      if (!childrenMap.has(key)) childrenMap.set(key, []);
      childrenMap.get(key)!.push(a);
    });
    const order = (list: Account[]) => list.sort((a, b) => a.code.localeCompare(b.code));

    const build = (parent: number | null, depth: number): { acc: Account; depth: number; hasChildren: boolean }[] => {
      const out: { acc: Account; depth: number; hasChildren: boolean }[] = [];
      const kids = order(childrenMap.get(parent) || []);
      kids.forEach((k) => {
        out.push({ acc: k, depth, hasChildren: (childrenMap.get(k.id) || []).length > 0 });
        out.push(...build(k.id, depth + 1));
      });
      return out;
    };
    return build(null, 0);
  }, [accounts]);

  return (
    <AppShell>
      <div className="space-y-6">
        {/* Filters */}
        <Card className="!p-4">
          <div className="flex flex-wrap items-end gap-4">
            {activeTab === 'journal' && (
              <>
                <DateRangePicker from={dateFrom} to={dateTo} onChangeFrom={setDateFrom} onChangeTo={setDateTo} />
                <Select
                  value={journalFilter}
                  onChange={(e) => setJournalFilter(e.target.value)}
                  options={[{ value: '', label: 'كل المصادر' }, ...(Object.entries(SOURCE_LABELS) as [JournalSource, string][]).map(([v, l]) => ({ value: v, label: l }))]}
                  className="w-full sm:w-44"
                />
                <Button variant="secondary" size="sm" onClick={() => { setDateFrom(''); setDateTo(''); setJournalFilter(''); }}>
                  مسح
                </Button>
              </>
            )}
            {activeTab === 'trial-balance' && (
              <div className="flex flex-col gap-1">
                <label className="text-xs font-medium text-neutral-500">حتى تاريخ</label>
                <input
                  type="date"
                  value={tbDate}
                  onChange={(e) => setTbDate(e.target.value)}
                  className="rounded-xl border border-sand-300 bg-surface px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500/40"
                />
              </div>
            )}
            {activeTab === 'statements' && (
              <DateRangePicker from={dateFrom} to={dateTo} onChangeFrom={setDateFrom} onChangeTo={setDateTo} />
            )}
            {activeTab === 'cashbox' && (
              <div className="flex flex-col gap-1">
                <label className="text-xs font-medium text-neutral-500">التاريخ</label>
                <input
                  type="date"
                  value={cashBoxDate}
                  onChange={(e) => setCashBoxDate(e.target.value)}
                  className="rounded-xl border border-sand-300 bg-surface px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500/40"
                />
              </div>
            )}
          </div>
        </Card>

        {/* Tabs */}
        <div className="flex flex-wrap gap-2">
          {tabs.map((t) => (
            <button
              key={t.value}
              onClick={() => setActiveTab(t.value)}
              className={`px-4 py-2 rounded-xl text-sm font-medium transition-all duration-150 ${
                activeTab === t.value
                  ? 'bg-brand-600 text-white shadow-sm'
                  : 'bg-surface text-neutral-600 border border-sand-200 hover:bg-sand-50'
              }`}
            >
              {t.label}
            </button>
          ))}
        </div>

        {/* Content */}
        <Card className="!p-0">
          {loading && activeTab !== 'accounts' ? (
            <div className="flex justify-center py-12"><Spinner size={32} /></div>
          ) : (
            <>
              {/* Journal Tab */}
              {activeTab === 'journal' && (
                <div>
                  <div className="flex flex-wrap items-center justify-between gap-3 px-4 sm:px-6 py-4 border-b border-sand-100">
                    <h3 className="text-lg font-semibold text-neutral-800">دفتر اليومية</h3>
                    <Button size="sm" onClick={() => setEntryModalOpen(true)}>
                      <Plus size={16} />
                      قيد يدوي
                    </Button>
                  </div>
                  {entries && entries.results.length === 0 ? (
                    <EmptyState title="لا توجد قيود" description="لم تُسجل أي قيود في هذه الفترة" />
                  ) : (
                    <Table>
                      <thead>
                        <tr>
                          <Th>الرقم</Th>
                          <Th>التاريخ</Th>
                          <Th>البيان</Th>
                          <Th>المصدر</Th>
                          <Th>مدين</Th>
                          <Th>دائن</Th>
                          <Th>{'\u00A0'}</Th>
                        </tr>
                      </thead>
                      <tbody>
                        {entries?.results.map((e) => (
                          <JournalEntryRow
                            key={e.id}
                            entry={e}
                            expanded={expandedEntry === e.id}
                            onToggle={() => setExpandedEntry(expandedEntry === e.id ? null : e.id)}
                            onDelete={() => setDeletingEntry(e)}
                            onReverse={() => setReversingEntry(e)}
                          />
                        ))}
                      </tbody>
                      {entries && entries.results.length > 0 && (
                        <tfoot>
                          <tr className="bg-sand-100 font-semibold">
                            <Td colSpan={4}>الإجمالي</Td>
                            <Td className="tabular-nums text-emerald-700">{formatCurrency(entries.results.reduce((s, e) => s + e.total_debit, 0))}</Td>
                            <Td className="tabular-nums text-red-600">{formatCurrency(entries.results.reduce((s, e) => s + e.total_credit, 0))}</Td>
                            <Td></Td>
                          </tr>
                        </tfoot>
                      )}
                    </Table>
                  )}
                </div>
              )}

              {/* Accounts Tab */}
              {activeTab === 'accounts' && (
                <div>
                  <div className="flex flex-wrap items-center justify-between gap-3 px-4 sm:px-6 py-4 border-b border-sand-100">
                    <h3 className="text-lg font-semibold text-neutral-800">شجرة الحسابات</h3>
                    <div className="flex items-center gap-3">
                      <SearchInput value={accountSearch} onChange={setAccountSearch} placeholder="بحث بالكود أو الاسم..." />
                      <Button size="sm" onClick={() => openAccountModal(null)}>
                        <Plus size={16} />
                        حساب جديد
                      </Button>
                    </div>
                  </div>
                  {tree.length === 0 ? (
                    <EmptyState title="لا توجد حسابات" description="اضغط حساب جديد لإضافة أول حساب" />
                  ) : (
                    <Table>
                      <thead>
                        <tr>
                          <Th>الكود</Th>
                          <Th>اسم الحساب</Th>
                          <Th>النوع</Th>
                          <Th>الحالة</Th>
                          <Th>{'\u00A0'}</Th>
                        </tr>
                      </thead>
                      <tbody>
                        {tree.map(({ acc, depth, hasChildren }) => (
                          <Tr key={acc.id}>
                            <Td style={{ paddingInlineStart: `${depth * 20 + 12}px` }}>
                              <span className="inline-flex items-center gap-1">
                                {hasChildren ? <ChevronDown size={14} className="text-neutral-400" /> : <span className="w-3.5" />}
                                <span className="tabular-nums font-medium">{acc.code}</span>
                              </span>
                            </Td>
                            <Td className="font-semibold text-neutral-800">{acc.name}</Td>
                            <Td>
                              <Badge variant={TYPE_VARIANTS[acc.type]}>{acc.type_label}</Badge>
                            </Td>
                            <Td>
                              <Badge variant={acc.is_active ? 'success' : 'danger'}>
                                {acc.is_active ? 'نشط' : 'موقوف'}
                              </Badge>
                            </Td>
                            <Td className="text-left">
                              <div className="inline-flex gap-1">
                                <button
                                  onClick={() => openAccountModal(acc)}
                                  className="p-1.5 rounded-lg hover:bg-brand-50 text-brand-600 transition-colors"
                                  title="تعديل"
                                >
                                  <Pencil size={16} />
                                </button>
                                <button
                                  onClick={() => setDeletingAccount(acc)}
                                  disabled={acc.is_system}
                                  className="p-1.5 rounded-lg hover:bg-red-50 text-red-500 transition-colors disabled:opacity-30 disabled:cursor-not-allowed"
                                  title={acc.is_system ? 'حساب نظامي' : 'حذف'}
                                >
                                  {acc.is_system ? <Lock size={16} /> : <Trash2 size={16} />}
                                </button>
                              </div>
                            </Td>
                          </Tr>
                        ))}
                      </tbody>
                    </Table>
                  )}
                </div>
              )}

              {/* Trial Balance Tab */}
              {activeTab === 'trial-balance' && (
                <div>
                  {trialBalance && trialBalance.rows.length === 0 ? (
                    <EmptyState title="لا توجد حركات" description="لا توجد أرصدة في الميزان حتى هذا التاريخ" />
                  ) : (
                    <Table>
                      <thead>
                        <tr>
                          <Th>الكود</Th>
                          <Th>الحساب</Th>
                          <Th>النوع</Th>
                          <Th>مدين</Th>
                          <Th>دائن</Th>
                        </tr>
                      </thead>
                      <tbody>
                        {trialBalance?.rows.map((r) => (
                          <Tr key={r.id}>
                            <Td className="tabular-nums font-medium">{r.code}</Td>
                            <Td className="font-semibold text-neutral-800">{r.name}</Td>
                            <Td><Badge variant={TYPE_VARIANTS[r.type]}>{r.type_label}</Badge></Td>
                            <Td className="tabular-nums text-emerald-700">{r.debit ? formatCurrency(r.debit) : ''}</Td>
                            <Td className="tabular-nums text-red-600">{r.credit ? formatCurrency(r.credit) : ''}</Td>
                          </Tr>
                        ))}
                      </tbody>
                      {trialBalance && (
                        <tfoot>
                          <tr className="bg-sand-100 font-semibold">
                            <Td colSpan={3}>الإجمالي</Td>
                            <Td className="tabular-nums text-emerald-700">{formatCurrency(trialBalance.totals.debit)}</Td>
                            <Td className="tabular-nums text-red-600">{formatCurrency(trialBalance.totals.credit)}</Td>
                          </tr>
                          <tr className={trialBalance.balanced ? 'bg-emerald-50' : 'bg-red-50'}>
                            <Td colSpan={5} className={trialBalance.balanced ? 'text-emerald-700' : 'text-red-600'}>
                              {trialBalance.balanced ? 'الميزان متوازن ✓' : 'الميزان غير متوازن — راجع القيود'}
                            </Td>
                          </tr>
                        </tfoot>
                      )}
                    </Table>
                  )}
                </div>
              )}

              {/* Statements Tab */}
              {activeTab === 'statements' && (
                <div>
                  <div className="flex flex-wrap gap-2 px-4 sm:px-6 py-4 border-b border-sand-100">
                    {statementTabs.map((t) => (
                      <button
                        key={t.value}
                        onClick={() => setStatementTab(t.value)}
                        className={`px-4 py-2 rounded-xl text-sm font-medium transition-all duration-150 ${
                          statementTab === t.value
                            ? 'bg-brand-600 text-white shadow-sm'
                            : 'bg-surface text-neutral-600 border border-sand-200 hover:bg-sand-50'
                        }`}
                      >
                        {t.label}
                      </button>
                    ))}
                  </div>
                  {statementTab === 'income' && income && (
                    <div className="p-4 sm:p-6 space-y-6 max-w-3xl">
                      <div className="space-y-2">
                        <h4 className="font-semibold text-neutral-800">الإيرادات</h4>
                        {income.income_rows.length === 0 ? (
                          <p className="text-sm text-neutral-400">لا توجد إيرادات</p>
                        ) : (
                          income.income_rows.map((r) => (
                            <div key={r.code} className="flex items-center justify-between py-1.5 border-b border-sand-100 text-sm">
                              <span className="text-neutral-700">{r.code} — {r.name}</span>
                              <span className="tabular-nums text-emerald-700">{formatCurrency(r.amount)}</span>
                            </div>
                          ))
                        )}
                        <div className="flex items-center justify-between py-1.5 font-semibold">
                          <span>إجمالي الإيرادات</span>
                          <span className="tabular-nums text-emerald-700">{formatCurrency(income.total_income)}</span>
                        </div>
                      </div>
                      <div className="space-y-2">
                        <h4 className="font-semibold text-neutral-800">المصاريف</h4>
                        {income.expense_rows.length === 0 ? (
                          <p className="text-sm text-neutral-400">لا توجد مصاريف</p>
                        ) : (
                          income.expense_rows.map((r) => (
                            <div key={r.code} className="flex items-center justify-between py-1.5 border-b border-sand-100 text-sm">
                              <span className="text-neutral-700">{r.code} — {r.name}</span>
                              <span className="tabular-nums text-red-600">{formatCurrency(r.amount)}</span>
                            </div>
                          ))
                        )}
                        <div className="flex items-center justify-between py-1.5 font-semibold">
                          <span>إجمالي المصاريف</span>
                          <span className="tabular-nums text-red-600">{formatCurrency(income.total_expenses)}</span>
                        </div>
                      </div>
                      <div className={`flex items-center justify-between px-4 py-3 rounded-xl ${income.net_profit >= 0 ? 'bg-emerald-50 text-emerald-700' : 'bg-red-50 text-red-600'}`}>
                        <span className="font-semibold">صافي الربح / الخسارة</span>
                        <span className="tabular-nums font-bold">{formatCurrency(income.net_profit)}</span>
                      </div>
                    </div>
                  )}
                  {statementTab === 'balance' && balanceSheet && (
                    <div className="p-4 sm:p-6 space-y-6 max-w-3xl">
                      <div className="space-y-2">
                        <h4 className="font-semibold text-neutral-800">الأصول</h4>
                        {balanceSheet.asset_rows.length === 0 ? (
                          <p className="text-sm text-neutral-400">لا توجد أصول</p>
                        ) : (
                          balanceSheet.asset_rows.map((r) => (
                            <div key={r.code} className="flex items-center justify-between py-1.5 border-b border-sand-100 text-sm">
                              <span className="text-neutral-700">{r.code} — {r.name}</span>
                              <span className="tabular-nums">{formatCurrency(r.amount)}</span>
                            </div>
                          ))
                        )}
                        <div className="flex items-center justify-between py-1.5 font-semibold">
                          <span>إجمالي الأصول</span>
                          <span className="tabular-nums">{formatCurrency(balanceSheet.total_assets)}</span>
                        </div>
                      </div>
                      <div className="space-y-2">
                        <h4 className="font-semibold text-neutral-800">الالتزامات</h4>
                        {balanceSheet.liability_rows.length === 0 ? (
                          <p className="text-sm text-neutral-400">لا توجد التزامات</p>
                        ) : (
                          balanceSheet.liability_rows.map((r) => (
                            <div key={r.code} className="flex items-center justify-between py-1.5 border-b border-sand-100 text-sm">
                              <span className="text-neutral-700">{r.code} — {r.name}</span>
                              <span className="tabular-nums text-red-600">{formatCurrency(r.amount)}</span>
                            </div>
                          ))
                        )}
                        <div className="flex items-center justify-between py-1.5 font-semibold">
                          <span>إجمالي الالتزامات</span>
                          <span className="tabular-nums text-red-600">{formatCurrency(balanceSheet.total_liabilities)}</span>
                        </div>
                      </div>
                      <div className="space-y-2">
                        <h4 className="font-semibold text-neutral-800">حقوق الملكية</h4>
                        {balanceSheet.equity_rows.length === 0 ? (
                          <p className="text-sm text-neutral-400">لا توجد حقوق ملكية</p>
                        ) : (
                          balanceSheet.equity_rows.map((r) => (
                            <div key={r.code} className="flex items-center justify-between py-1.5 border-b border-sand-100 text-sm">
                              <span className="text-neutral-700">{r.code} — {r.name}</span>
                              <span className="tabular-nums text-purple-700">{formatCurrency(r.amount)}</span>
                            </div>
                          ))
                        )}
                        <div className="flex items-center justify-between py-1.5 font-semibold">
                          <span>إجمالي حقوق الملكية</span>
                          <span className="tabular-nums text-purple-700">{formatCurrency(balanceSheet.total_equity)}</span>
                        </div>
                      </div>
                      <div className={`flex items-center justify-between px-4 py-3 rounded-xl ${balanceSheet.balanced ? 'bg-emerald-50 text-emerald-700' : 'bg-red-50 text-red-600'}`}>
                        <span className="font-semibold">{balanceSheet.balanced ? 'الميزانية متوازنة ✓' : 'الفرق بين الأصول والخصوم'}</span>
                        <span className="tabular-nums font-bold">{formatCurrency(balanceSheet.difference)}</span>
                      </div>
                    </div>
                  )}
                  {statementTab === 'cash-flow' && cashFlow && (
                    <div>
                      {cashFlow.rows.length === 0 ? (
                        <EmptyState title="لا توجد حركات" description="لا توجد حركات نقد أو بنك في هذه الفترة" />
                      ) : (
                        <Table>
                          <thead>
                            <tr>
                              <Th>المصدر</Th>
                              <Th>وارد</Th>
                              <Th>صادر</Th>
                              <Th>الصافي</Th>
                            </tr>
                          </thead>
                          <tbody>
                            {cashFlow.rows.map((r) => (
                              <Tr key={r.source}>
                                <Td className="font-medium">{r.label}</Td>
                                <Td className="tabular-nums text-emerald-700">{formatCurrency(r.in)}</Td>
                                <Td className="tabular-nums text-red-600">{formatCurrency(r.out)}</Td>
                                <Td className={`tabular-nums font-semibold ${r.net < 0 ? 'text-red-600' : 'text-emerald-700'}`}>{formatCurrency(r.net)}</Td>
                              </Tr>
                            ))}
                          </tbody>
                          <tfoot>
                            <tr className="bg-sand-100 font-semibold">
                              <Td>الإجمالي</Td>
                              <Td className="tabular-nums text-emerald-700">{formatCurrency(cashFlow.totals.in)}</Td>
                              <Td className="tabular-nums text-red-600">{formatCurrency(cashFlow.totals.out)}</Td>
                              <Td className={`tabular-nums ${cashFlow.totals.net < 0 ? 'text-red-600' : 'text-emerald-700'}`}>{formatCurrency(cashFlow.totals.net)}</Td>
                            </tr>
                          </tfoot>
                        </Table>
                      )}
                    </div>
                  )}
                </div>
              )}

              {/* Cashbox & Closing Tab */}
              {activeTab === 'cashbox' && (
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 p-4 sm:p-6">
                  <div className="space-y-4">
                    <Card title="خزينة اليوم" subtitle={formatDate(cashBoxDate)}>
                      {!cashBoxData ? (
                        <Spinner size={24} />
                      ) : (
                        <div className="space-y-4">
                          <div className="flex items-center justify-between px-4 py-3 bg-sand-50 rounded-xl">
                            <span className="text-sm text-neutral-600">الرصيد الافتتاحي</span>
                            <span className="tabular-nums font-semibold">{formatCurrency(cashBoxData.opening)}</span>
                          </div>
                          <Table>
                            <thead>
                              <tr>
                                <Th>المصدر</Th>
                                <Th>وارد</Th>
                                <Th>صادر</Th>
                              </tr>
                            </thead>
                            <tbody>
                              {cashBoxData.rows.map((r) => (
                                <Tr key={r.source}>
                                  <Td className="font-medium">{r.label}</Td>
                                  <Td className="tabular-nums text-emerald-700">{r.in ? formatCurrency(r.in) : ''}</Td>
                                  <Td className="tabular-nums text-red-600">{r.out ? formatCurrency(r.out) : ''}</Td>
                                </Tr>
                              ))}
                            </tbody>
                            <tfoot>
                              <tr className="bg-sand-100 font-semibold">
                                <Td>الإجمالي</Td>
                                <Td className="tabular-nums text-emerald-700">{formatCurrency(cashBoxData.totals.in)}</Td>
                                <Td className="tabular-nums text-red-600">{formatCurrency(cashBoxData.totals.out)}</Td>
                              </tr>
                            </tfoot>
                          </Table>
                          <div className="flex items-center justify-between px-4 py-3 bg-brand-50 rounded-xl">
                            <span className="text-sm font-medium text-brand-800">الرصيد الختامي</span>
                            <span className="tabular-nums font-bold text-brand-700">{formatCurrency(cashBoxData.closing)}</span>
                          </div>
                        </div>
                      )}
                    </Card>

                    <Card title="إقفال دوري" subtitle="تحويل أرباح الفترة إلى الأرباح المحتجزة">
                      <div className="space-y-3">
                        <Input label="آخر يوم في الفترة" type="date" value={closeDate} onChange={(e) => setCloseDate(e.target.value)} />
                        <Input label="الوصف (اختياري)" value={closeDescription} onChange={(e) => setCloseDescription(e.target.value)} placeholder="مثال: إقفال نهاية الشهر" />
                        <Button onClick={handleClosePeriod} loading={closeLoading} className="w-full">
                          <Lock size={16} />
                          إقفال الفترة
                        </Button>
                      </div>
                    </Card>
                  </div>

                  <Card title="سجل الفترات المغلقة" subtitle="الفترات التي تم إقفالها سابقاً">
                    {closedPeriods.length === 0 ? (
                      <EmptyState title="لا توجد فترات مغلقة" description="لم يتم إقفال أي فترة بعد" />
                    ) : (
                      <Table>
                        <thead>
                          <tr>
                            <Th>حتى تاريخ</Th>
                            <Th>الوصف</Th>
                            <Th>صافي الأرباح</Th>
                          </tr>
                        </thead>
                        <tbody>
                          {closedPeriods.map((p) => (
                            <Tr key={p.id}>
                              <Td className="tabular-nums">{formatDate(p.period_end)}</Td>
                              <Td>{p.description || '—'}</Td>
                              <Td className={`tabular-nums font-semibold ${p.net_profit >= 0 ? 'text-emerald-700' : 'text-red-600'}`}>{formatCurrency(p.net_profit)}</Td>
                            </Tr>
                          ))}
                        </tbody>
                      </Table>
                    )}
                  </Card>
                </div>
              )}
            </>
          )}
        </Card>
      </div>

      {/* Manual Entry Modal */}
      <Modal
        open={entryModalOpen}
        onClose={() => setEntryModalOpen(false)}
        title="قيد يومية يدوي"
        maxWidth="max-w-2xl"
        footer={
          <>
            <Button onClick={handleSaveEntry} loading={entrySubmitting}>
              <Plus size={16} />
              تسجيل القيد
            </Button>
            <Button variant="secondary" onClick={() => setEntryModalOpen(false)}>إلغاء</Button>
          </>
        }
      >
        <div className="space-y-4">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <Input label="التاريخ" type="date" value={entryDate} onChange={(e) => setEntryDate(e.target.value)} />
            <Input label="البيان" value={entryDescription} onChange={(e) => setEntryDescription(e.target.value)} placeholder="وصف القيد" />
          </div>
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-sm font-medium text-neutral-700">الأسطر</span>
              <Button variant="subtle" size="sm" onClick={handleAddLine}>
                <Plus size={14} />
                إضافة سطر
              </Button>
            </div>
            {entryLines.map((line, idx) => (
              <div key={idx} className="rounded-xl border border-sand-200 p-3 space-y-2">
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 items-end">
                  <div className="col-span-2 sm:col-span-2">
                    <Select
                      label={idx === 0 ? 'الحساب' : undefined}
                      value={line.account}
                      onChange={(e) => handleLineChange(idx, 'account', Number(e.target.value))}
                      options={accountOptions.map((o) => ({ value: String(o.value), label: o.label }))}
                      placeholder="اختر الحساب"
                    />
                  </div>
                  <Input
                    label={idx === 0 ? 'مدين' : undefined}
                    type="number"
                    value={line.debit}
                    onChange={(e) => handleLineChange(idx, 'debit', e.target.value)}
                    placeholder="0.00"
                  />
                  <Input
                    label={idx === 0 ? 'دائن' : undefined}
                    type="number"
                    value={line.credit}
                    onChange={(e) => handleLineChange(idx, 'credit', e.target.value)}
                    placeholder="0.00"
                  />
                </div>
                <div className="flex items-end gap-2">
                  <Input
                    label="البيان"
                    value={line.description}
                    onChange={(e) => handleLineChange(idx, 'description', e.target.value)}
                    placeholder="بيان السطر (اختياري)"
                    className="flex-1"
                  />
                  <button
                    onClick={() => handleRemoveLine(idx)}
                    className="p-2 rounded-lg hover:bg-red-50 text-red-400 transition-colors"
                    title="حذف السطر"
                  >
                    <Trash2 size={16} />
                  </button>
                </div>
              </div>
            ))}
          </div>
          <div className="flex flex-wrap items-center justify-between gap-2 px-4 py-3 rounded-xl bg-sand-50">
            <span className="text-sm text-neutral-600">الفرق</span>
            <span className={`tabular-nums font-bold ${entryTotals.balanced ? 'text-emerald-700' : 'text-red-600'}`}>
              {entryTotals.balanced ? 'متوازن ✓' : `${formatCurrency(entryTotals.debit - entryTotals.credit)}`}
            </span>
          </div>
        </div>
      </Modal>

      {/* Account Modal */}
      <Modal
        open={accModalOpen}
        onClose={() => setAccModalOpen(false)}
        title={editingAccount ? 'تعديل حساب' : 'حساب جديد'}
        footer={
          <>
            <Button onClick={handleSaveAccount} loading={accSubmitting}>
              <Plus size={16} />
              حفظ
            </Button>
            <Button variant="secondary" onClick={() => setAccModalOpen(false)}>إلغاء</Button>
          </>
        }
      >
        <div className="space-y-3">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <Input label="الكود" value={accForm.code} onChange={(e) => setAccForm({ ...accForm, code: e.target.value })} placeholder="مثال: 5202" />
            <Input label="اسم الحساب" value={accForm.name} onChange={(e) => setAccForm({ ...accForm, name: e.target.value })} placeholder="اسم الحساب" />
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <Select
              label="النوع"
              value={accForm.type}
              onChange={(e) => setAccForm({ ...accForm, type: e.target.value as AccountType })}
              options={(Object.entries(TYPE_LABELS) as [AccountType, string][]).map(([v, l]) => ({ value: v, label: l }))}
            />
            <Select
              label="الحساب الأب"
              value={accForm.parent}
              onChange={(e) => setAccForm({ ...accForm, parent: e.target.value ? Number(e.target.value) : '' })}
              options={accountOptions
                .filter((o) => !editingAccount || Number(o.value) !== editingAccount.id)
                .map((o) => ({ value: String(o.value), label: o.label }))}
              placeholder="بدون حساب أب"
            />
          </div>
          <label className="flex items-center gap-2 cursor-pointer">
            <input
              type="checkbox"
              checked={accForm.is_active}
              onChange={(e) => setAccForm({ ...accForm, is_active: e.target.checked })}
              className="w-4 h-4 accent-brand-600"
            />
            <span className="text-sm text-neutral-700">حساب نشط</span>
          </label>
        </div>
      </Modal>

      {/* Delete entry confirm */}
      <ConfirmDialog
        open={!!deletingEntry}
        title="حذف القيد"
        message={`هل تريد حذف القيد ${deletingEntry?.number}؟ لا يمكن حذف قيد تلقائي المصدر.`}
        confirmLabel="حذف"
        onClose={() => setDeletingEntry(null)}
        onConfirm={handleDeleteEntry}
      />

      {/* Reverse entry confirm */}
      <ConfirmDialog
        open={!!reversingEntry}
        title="عكس القيد"
        message={`سيتم وضع علامة إلغاء على القيد ${reversingEntry?.number}. هل تريد المتابعة؟`}
        confirmLabel="عكس"
        onClose={() => setReversingEntry(null)}
        onConfirm={handleReverseEntry}
      />

      {/* Delete account confirm */}
      <ConfirmDialog
        open={!!deletingAccount}
        title="حذف الحساب"
        message={`هل تريد حذف الحساب ${deletingAccount?.code} — ${deletingAccount?.name}؟ لن يمكن حذف حساب عليه حركات أو له حسابات فرعية.`}
        confirmLabel="حذف"
        onClose={() => setDeletingAccount(null)}
        onConfirm={handleDeleteAccount}
      />
    </AppShell>
  );
}

function JournalEntryRow({
  entry,
  expanded,
  onToggle,
  onDelete,
  onReverse,
}: {
  entry: JournalEntry;
  expanded: boolean;
  onToggle: () => void;
  onDelete: () => void;
  onReverse: () => void;
}) {
  return (
    <>
      <Tr onClick={onToggle} className="cursor-pointer">
        <Td className="tabular-nums font-medium">{entry.number}</Td>
        <Td className="tabular-nums">{formatDate(entry.date)}</Td>
        <Td>{entry.description || '—'}</Td>
        <Td>
          <Badge variant={SOURCE_VARIANTS[entry.source]}>{entry.source_label}</Badge>
          {entry.reversed_at && <span className="ml-1 inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-neutral-100 text-neutral-600">ملغى</span>}
        </Td>
        <Td className="tabular-nums text-emerald-700">{formatCurrency(entry.total_debit)}</Td>
        <Td className="tabular-nums text-red-600">{formatCurrency(entry.total_credit)}</Td>
        <Td className="text-left">
          <div className="inline-flex gap-1">
            {entry.source === 'manual' && !entry.reversed_at && (
              <>
                <button onClick={onReverse} className="p-1.5 rounded-lg hover:bg-amber-50 text-amber-600 transition-colors" title="عكس القيد">
                  <RotateCcw size={16} />
                </button>
                <button onClick={onDelete} className="p-1.5 rounded-lg hover:bg-red-50 text-red-500 transition-colors" title="حذف">
                  <Trash2 size={16} />
                </button>
              </>
            )}
            <button className={`p-1.5 rounded-lg hover:bg-sand-100 text-neutral-500 transition-colors ${expanded ? 'rotate-180' : ''}`}>
              <ChevronDown size={16} />
            </button>
          </div>
        </Td>
      </Tr>
      {expanded && (
        <tr className="bg-sand-50/70">
          <td colSpan={7} className="px-4 sm:px-6 py-3">
            <div className="space-y-1">
              {entry.lines.map((ln) => (
                <div key={ln.id} className="flex items-center justify-between gap-3 text-sm">
                  <span className="tabular-nums text-neutral-500">{ln.account_code}</span>
                  <span className="flex-1 text-neutral-700">{ln.account_name}{ln.description ? ` — ${ln.description}` : ''}</span>
                  <span className="tabular-nums w-28 text-left text-emerald-700">{ln.debit ? formatCurrency(ln.debit) : ''}</span>
                  <span className="tabular-nums w-28 text-left text-red-600">{ln.credit ? formatCurrency(ln.credit) : ''}</span>
                </div>
              ))}
            </div>
          </td>
        </tr>
      )}
    </>
  );
}