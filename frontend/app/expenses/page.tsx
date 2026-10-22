'use client';

import { useState, useEffect, useMemo, useCallback } from 'react';
import AppShell from '@/components/layout/AppShell';
import Card from '@/components/ui/Card';
import Button from '@/components/ui/Button';
import Table, { Th, Td, Tr } from '@/components/ui/Table';
import SearchInput from '@/components/ui/SearchInput';
import Select from '@/components/ui/Select';
import DateRangeToolbar, { currentMonthRange } from '@/components/ui/DateRangeToolbar';
import Pagination from '@/components/ui/Pagination';
import Modal from '@/components/ui/Modal';
import ConfirmDialog from '@/components/ui/ConfirmDialog';
import ExpenseForm from '@/components/forms/ExpenseForm';
import CategoriesPanel from '@/components/expenses/CategoriesPanel';
import EmptyState from '@/components/ui/EmptyState';
import Spinner from '@/components/ui/Spinner';
import { Plus, Pencil, Trash2, RefreshCw, Download, Receipt, Tags, Eye, FileText } from 'lucide-react';
import { Expense, Branch, ExpenseCategory, Paginated } from '@/types';
import { listExpenses, getExpenseSummary, createExpense, updateExpense, deleteExpense, listExpenseCategories, runRecurringExpenses, getExpenseReceipt, ExpenseSummary } from '@/services/expenses';
import { listBranches } from '@/services/branches';
import { formatCurrency, formatDate } from '@/lib/format';
import { counted } from '@/lib/arabic';
import { downloadCsv, csvFilename } from '@/lib/csv';
import { useAutoRefresh } from '@/lib/useAutoRefresh';
import { PAYMENT_METHODS_MAP } from '@/lib/constants';
import { useToast } from '@/components/ui/Toast';
import { useSettings } from '@/components/providers/SettingsProvider';
import { useUrlState } from '@/lib/useUrlState';
import { useDefaultEmployeeBranch } from '@/lib/useDefaultEmployeeBranch';

/** تبويبا القسم: المصاريف نفسها، وتصنيفاتها التي وُلدت منها. */
const TABS = [
  { key: 'list' as const, label: 'المصاريف', icon: Receipt },
  { key: 'categories' as const, label: 'التصنيفات', icon: Tags },
];

export default function ExpensesPage() {
  const { toast } = useToast();
  const { settings } = useSettings();
  const pageSize = settings?.default_page_size ?? 10;
  const [data, setData] = useState<Paginated<Expense> | null>(null);
  const [branches, setBranches] = useState<Branch[]>([]);
  const [categories, setCategories] = useState<ExpenseCategory[]>([]);
  const [loading, setLoading] = useState(true);
  const [summaryLoading, setSummaryLoading] = useState(true);
  const [search, setSearch] = useUrlState('q', '');
  const [filterBranch, setFilterBranch] = useUrlState('branch', '');
  useDefaultEmployeeBranch(setFilterBranch);
  const [filterCategory, setFilterCategory] = useUrlState('category', '');
  const [tab, setTab] = useUrlState<'list' | 'categories'>('wtab', 'list');
  const [dateFrom, setDateFrom] = useUrlState('from', currentMonthRange().from);
  const [dateTo, setDateTo] = useUrlState('to', currentMonthRange().to);
  const [page, setPage] = useUrlState('page', 1);
  const [modalOpen, setModalOpen] = useState(false);
  const [editing, setEditing] = useState<Expense | null>(null);
  const [deleting, setDeleting] = useState<Expense | null>(null);
  const [deleteLoading, setDeleteLoading] = useState(false);
  const [recurringLoading, setRecurringLoading] = useState(false);
  const [receiptPreview, setReceiptPreview] = useState<{ expense: Expense; image: string } | null>(null);
  const [filteredSummary, setFilteredSummary] = useState<ExpenseSummary | null>(null);
  const [monthlySummary, setMonthlySummary] = useState<ExpenseSummary | null>(null);
  const [monthlySummaryLoading, setMonthlySummaryLoading] = useState(true);
  const [summaryOpen, setSummaryOpen] = useState(false);
  const [selectedExpenses, setSelectedExpenses] = useState<Record<number, number>>({});
  const monthRange = useMemo(() => currentMonthRange(), []);

  const handleViewReceipt = async (expense: Expense) => {
    try {
      const result = await getExpenseReceipt(expense.id);
      setReceiptPreview({ expense, image: result.image });
    } catch (err: any) {
      toast('error', err.message);
    }
  };

  const handleRunRecurring = async () => {
    setRecurringLoading(true);
    try {
      const res = await runRecurringExpenses();
      toast('success', res.count > 0 ? `تم ترحيل ${counted(res.count, 'مصروف متكرر', 'مصروفان متكرران', 'مصروفات متكررة')}` : 'لا توجد مصاريف مستحقة للترحيل');
      fetchData();
      fetchMonthlySummary();
    } catch (err: any) {
      toast('error', err.message);
    } finally {
      setRecurringLoading(false);
    }
  };

  useEffect(() => {
    let cancelled = false;
    Promise.all([
      listBranches({ page_size: 100 }),
      listExpenseCategories({ page_size: 200 }),
    ]).then(([b, c]) => {
      if (!cancelled) {
        setBranches(b.results.filter((br) => br.is_active));
        setCategories(c.results);
      }
    });
    return () => { cancelled = true; };
  }, []);

  const editBranches = useMemo(() => {
    if (!editing || branches.some((b) => b.id === editing.branch)) return branches;
    return [...branches, {
      id: editing.branch,
      name: editing.branch_name || 'فرع (موقوف)',
      code: '',
      phone: '',
      address: '',
      city: '',
      notes: '',
      is_active: false,
      sales_count: 0,
      expenses_count: 0,
      monthly_sales_target: 0,
      monthly_sales: 0,
      monthly_expenses: 0,
      target_progress_pct: 0,
      created_at: '',
      updated_at: '',
    }];
  }, [branches, editing]);

  const fetchData = useCallback(() => {
    let cancelled = false;
    setLoading(true);
    setSummaryLoading(true);
    const filters: Record<string, string | number | undefined | null> = {
      search: search || undefined,
      branch: filterBranch || undefined,
      category: filterCategory || undefined,
      date_from: dateFrom || undefined,
      date_to: dateTo || undefined,
    };
    listExpenses({ ...filters, page, page_size: pageSize })
      .then(async (res) => {
        if (cancelled) return;
        setData(res);
        try {
          const summary = await getExpenseSummary(filters);
          if (!cancelled) {
            setFilteredSummary(summary);
            setSummaryLoading(false);
          }
        } catch {
          if (!cancelled) {
            setFilteredSummary(null);
            setSummaryLoading(false);
          }
        }
      })
      .catch((err) => {
        if (!cancelled) {
          setSummaryLoading(false);
          toast('error', err.message);
        }
      })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [page, pageSize, search, filterBranch, filterCategory, dateFrom, dateTo, toast]);

  useEffect(() => fetchData(), [fetchData]);

  const fetchMonthlySummary = useCallback(() => {
    let cancelled = false;
    setMonthlySummaryLoading(true);
    getExpenseSummary({
      date_from: monthRange.from,
      date_to: monthRange.to,
      branch: filterBranch || undefined,
    })
      .then((summary) => { if (!cancelled) setMonthlySummary(summary); })
      .catch(() => { if (!cancelled) setMonthlySummary(null); })
      .finally(() => { if (!cancelled) setMonthlySummaryLoading(false); });
    return () => { cancelled = true; };
  }, [filterBranch, monthRange]);

  useEffect(() => fetchMonthlySummary(), [fetchMonthlySummary]);
  useAutoRefresh(useCallback(() => {
    fetchData();
    fetchMonthlySummary();
  }, [fetchData, fetchMonthlySummary]));

  const totalPages = data ? Math.ceil(data.count / pageSize) : 1;
  const selectedExpenseTotal = useMemo(
    () => Object.values(selectedExpenses).reduce((total, amount) => total + amount, 0),
    [selectedExpenses]
  );
  const allVisibleSelected = Boolean(data?.results.length && data.results.every((expense) => selectedExpenses[expense.id] !== undefined));

  const toggleExpense = (expense: Expense) => {
    setSelectedExpenses((current) => {
      const next = { ...current };
      if (next[expense.id] !== undefined) delete next[expense.id];
      else next[expense.id] = Number(expense.amount) || 0;
      return next;
    });
  };

  const toggleVisibleExpenses = () => {
    setSelectedExpenses((current) => {
      const next = { ...current };
      if (allVisibleSelected) data?.results.forEach((expense) => { delete next[expense.id]; });
      else data?.results.forEach((expense) => { next[expense.id] = Number(expense.amount) || 0; });
      return next;
    });
  };

  const clearSelection = () => setSelectedExpenses({});

  const handleCreate = async (d: Partial<Expense>) => {
    await createExpense(d);
    clearSelection();
    toast('success', 'تم تسجيل المصروف بنجاح');
    setModalOpen(false);
    fetchData();
    fetchMonthlySummary();
  };

  const handleUpdate = async (d: Partial<Expense>) => {
    if (!editing) return;
    await updateExpense(editing.id, d);
    clearSelection();
    toast('success', 'تم تحديث المصروف بنجاح');
    setEditing(null);
    fetchData();
    fetchMonthlySummary();
  };

  const handleDelete = async () => {
    if (!deleting) return;
    setDeleteLoading(true);
    try {
      await deleteExpense(deleting.id);
      clearSelection();
      toast('success', 'تم حذف المصروف بنجاح');
      setDeleting(null);
      fetchData();
      fetchMonthlySummary();
    } catch (err: any) {
      toast('error', err.message);
    } finally {
      setDeleteLoading(false);
    }
  };

  /**
   * يصدّر المصاريف داخل الفترة والفرع الحاليين.
   *
   * نطلب `page_size` كبيراً بدل `data` المعروض، فالصفحة مقسّمة إلى صفحات
   * والمستخدم يتوقع ملفاً بكل مصاريفه لا بما ظهر على الشاشة فقط.
   */
  const handleExport = async () => {
    try {
      const res = await listExpenses({
        page_size: 100000,
        branch: filterBranch || undefined,
        date_from: dateFrom || undefined,
        date_to: dateTo || undefined,
      });
      downloadCsv(csvFilename('expenses'), [
        { header: 'التاريخ', value: (e: Expense) => e.date },
        { header: 'الفرع', value: (e: Expense) => e.branch_name || '' },
        { header: 'التصنيف', value: (e: Expense) => e.category_name || '' },
        { header: 'البيان', value: (e: Expense) => e.description },
        { header: 'المبلغ', value: (e: Expense) => e.amount },
        { header: 'طريقة الدفع', value: (e: Expense) => PAYMENT_METHODS_MAP[e.payment_method] || e.payment_method },
        { header: 'متكررة', value: (e: Expense) => (e.is_recurring ? 'نعم' : 'لا') },
        { header: 'ملاحظات', value: (e: Expense) => e.notes || '' },
      ], res.results);
      toast('success', `تم تصدير ${counted(res.results.length, 'مصروف', 'مصروفان', 'مصروفات')}`);
    } catch (err: any) {
      toast('error', err.message);
    }
  };

  return (
    <AppShell>
      <div className="space-y-6">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex flex-wrap items-center gap-3">
            <Button onClick={() => setModalOpen(true)}>
              <Plus size={18} />
              تسجيل مصروف
            </Button>
            <Button variant="subtle" onClick={handleExport}>
              <Download size={18} />
              تصدير CSV
            </Button>
            <Button variant="secondary" onClick={handleRunRecurring} loading={recurringLoading}>
              <RefreshCw size={18} />
              ترحيل المتكررة
            </Button>
            {tab === 'list' && (
              <Button variant="secondary" onClick={() => setSummaryOpen(true)}>
                <FileText size={18} />
                ملخص الفترة
              </Button>
            )}
          </div>
          <div className="flex items-center gap-1 rounded-xl border border-sand-200 bg-surface p-1">
            {TABS.map((t) => (
              <button
                key={t.key}
                onClick={() => setTab(t.key)}
                className={`inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-sm font-medium transition-colors ${
                  tab === t.key
                    ? 'bg-brand-600 text-white shadow-sm'
                    : 'text-neutral-600 hover:bg-sand-50'
                }`}
              >
                <t.icon size={15} />
                {t.label}
              </button>
            ))}
          </div>
        </div>

        {tab === 'categories' ? (
          <CategoriesPanel />
        ) : (
          <>
        <Card className="!p-4">
          <div className="flex flex-wrap items-end gap-4">
            <div className="flex-1 min-w-[200px]">
              <SearchInput value={search} onChange={(v) => { clearSelection(); setSearch(v); setPage(1); }} placeholder="بحث في المصاريف..." />
            </div>
            <Select
              value={filterBranch}
              onChange={(e) => { clearSelection(); setFilterBranch(e.target.value); setPage(1); }}
              options={[{ value: '', label: 'كل الفروع' }, ...branches.map((b) => ({ value: b.id, label: b.name }))]}
              className="w-full sm:w-48"
            />
            <Select
              value={filterCategory}
              onChange={(e) => { clearSelection(); setFilterCategory(e.target.value); setPage(1); }}
              options={[{ value: '', label: 'كل التصنيفات' }, ...categories.map((c) => ({ value: c.id, label: c.name }))]}
              className="w-full sm:w-48"
            />
            <DateRangeToolbar
              from={dateFrom}
              to={dateTo}
              onChange={(f, t) => { clearSelection(); setDateFrom(f); setDateTo(t); setPage(1); }}
            />
          </div>
        </Card>

        <div className="grid gap-3 sm:grid-cols-2">
          <Card className="!p-4">
            <div className="text-sm text-neutral-500">إجمالي المصاريف حسب الفلتر</div>
            <div className="mt-1 text-xl font-bold tabular-nums">{summaryLoading ? 'جارٍ الحساب…' : formatCurrency(filteredSummary?.total || 0)}</div>
            <div className="mt-1 text-xs text-neutral-400">{summaryLoading ? ' ' : `${filteredSummary?.count || 0} مصروف · يشمل كل الصفحات`}</div>
          </Card>
          <Card className="!p-4">
            <div className="flex items-start justify-between gap-2">
              <div>
                <div className="text-sm text-neutral-500">إجمالي المصاريف المحددة</div>
                <div className="mt-1 text-xl font-bold tabular-nums">{formatCurrency(selectedExpenseTotal)}</div>
                <div className="mt-1 text-xs text-neutral-400">{Object.keys(selectedExpenses).length} مصروف محدد، ويمكن التحديد من صفحات مختلفة</div>
              </div>
              {Object.keys(selectedExpenses).length > 0 && <Button size="sm" variant="ghost" onClick={clearSelection}>مسح التحديد</Button>}
            </div>
          </Card>
        </div>

        <Card className="!p-4">
          <div className="mb-4 flex flex-wrap items-start justify-between gap-2">
            <div>
              <h2 className="font-semibold text-neutral-800">ملخص الشهر الحالي حسب نوع المصروف</h2>
              <p className="mt-1 text-xs text-neutral-500">
                {formatDate(monthRange.from)} – {formatDate(monthRange.to)} · {filterBranch ? branches.find((branch) => String(branch.id) === filterBranch)?.name || 'الفرع المحدد' : 'كل الفروع'}
              </p>
            </div>
            <div className="text-left">
              <div className="text-xs text-neutral-500">الإجمالي الشهري</div>
              <div className="text-lg font-bold tabular-nums">{monthlySummaryLoading ? 'جارٍ الحساب…' : formatCurrency(monthlySummary?.total || 0)}</div>
            </div>
          </div>
          {monthlySummaryLoading ? (
            <div className="flex justify-center py-5"><Spinner size={24} /></div>
          ) : !monthlySummary || monthlySummary.categories.length === 0 ? (
            <p className="rounded-lg bg-sand-50 p-4 text-center text-sm text-neutral-500">لا توجد مصاريف مسجلة لهذا الشهر.</p>
          ) : (
            <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
              {monthlySummary.categories.map((category) => (
                <div key={category.category ?? 'uncategorized'} className="flex items-center justify-between gap-3 rounded-lg border border-sand-200 p-3">
                  <div>
                    <div className="text-sm font-medium text-neutral-700">{category.category_name}</div>
                    <div className="mt-0.5 text-xs text-neutral-400">{category.count} مصروف</div>
                  </div>
                  <div className="font-semibold tabular-nums text-neutral-800">{formatCurrency(category.total)}</div>
                </div>
              ))}
            </div>
          )}
        </Card>

        <Card>
          {loading ? (
            <div className="flex justify-center py-12"><Spinner size={32} /></div>
          ) : !data || data.results.length === 0 ? (
            <EmptyState title="لا توجد مصاريف" description="لم يتم تسجيل أي مصاريف بعد" />
          ) : (
            <>
              <Table>
                <thead>
                  <tr>
                    <Th className="w-10"><input type="checkbox" checked={allVisibleSelected} onChange={toggleVisibleExpenses} aria-label="تحديد كل مصاريف الصفحة" /></Th>
                    <Th>التاريخ</Th>
                    <Th>الفرع</Th>
                    <Th>نوع المصروف</Th>
                    <Th>المبلغ</Th>
                    <Th>طريقة الدفع</Th>
                    <Th>الوصف</Th>
                    <Th>الفاتورة</Th>
                    <Th>ملاحظات</Th>
                    <Th>التكرار</Th>
                    <Th>إجراءات</Th>
                  </tr>
                </thead>
                <tbody>
                  {data.results.map((e) => (
                    <Tr key={e.id}>
                      <Td><input type="checkbox" checked={selectedExpenses[e.id] !== undefined} onChange={() => toggleExpense(e)} aria-label={`تحديد مصروف ${e.description || e.id}`} /></Td>
                      <Td>{formatDate(e.date)}</Td>
                      <Td className="font-medium">{e.branch_name}</Td>
                      <Td>{e.category_name}</Td>
                      <Td className="tabular-nums font-medium">{formatCurrency(e.amount)}</Td>
                      <Td>{PAYMENT_METHODS_MAP[e.payment_method] || e.payment_method}</Td>
                      <Td className="max-w-[200px] truncate" title={e.description || undefined}>{e.description || '-'}</Td>
                      <Td>
                        {e.has_receipt_image ? (
                          <button onClick={() => void handleViewReceipt(e)} className="p-1.5 rounded-lg text-brand-600 hover:bg-brand-50" title="عرض صورة الفاتورة" aria-label={`عرض فاتورة المصروف ${e.id}`}>
                            <Eye size={16} />
                          </button>
                        ) : <span className="text-neutral-300">—</span>}
                      </Td>
                      <Td className="max-w-[180px] truncate text-neutral-500" title={e.notes || undefined}>
                        {e.notes || '-'}
                      </Td>
                      <Td>
                        {e.is_recurring ? (
                          <div className="flex flex-col gap-0.5">
                            <span className="inline-flex w-fit items-center gap-1 rounded-full bg-brand-50 text-brand-700 dark:bg-brand-950/40 dark:text-brand-300 px-2 py-0.5 text-xs font-medium">
                              <RefreshCw size={11} className="inline" />
                              {e.recur_frequency === 'weekly' ? 'أسبوعي' : 'شهري'}
                            </span>
                            {e.next_run_date && (
                              <span className="text-[11px] text-neutral-500">القادم: {formatDate(e.next_run_date)}</span>
                            )}
                          </div>
                        ) : e.origin ? (
                          <span className="text-[11px] text-neutral-400">نسخة متكررة</span>
                        ) : (
                          <span className="text-neutral-400">-</span>
                        )}
                      </Td>
                      <Td>
                        <div className="flex items-center gap-2">
                          <button onClick={() => setEditing(e)} className="p-1.5 rounded-lg hover:bg-amber-50 text-amber-600 dark:hover:bg-amber-500/15 dark:text-amber-400 transition-colors">
                            <Pencil size={16} />
                          </button>
                          <button onClick={() => setDeleting(e)} className="p-1.5 rounded-lg hover:bg-red-50 text-red-500 dark:hover:bg-red-500/15 dark:text-red-400 transition-colors">
                            <Trash2 size={16} />
                          </button>
                        </div>
                      </Td>
                    </Tr>
                  ))}
                </tbody>
              </Table>
              <Pagination page={page} totalPages={totalPages} onChange={setPage} count={data.count} pageSize={pageSize} />
            </>
          )}
        </Card>
          </>
        )}

        <Modal open={modalOpen} onClose={() => setModalOpen(false)} title="تسجيل مصروف جديد" maxWidth="max-w-2xl">
          <ExpenseForm branches={branches} categories={categories} onSubmit={handleCreate} onCancel={() => setModalOpen(false)} />
        </Modal>

        <Modal open={summaryOpen} onClose={() => setSummaryOpen(false)} title="ملخص المصاريف حسب نوع المصروف" maxWidth="max-w-2xl">
          <div className="space-y-4">
            <div className="rounded-xl bg-brand-50 p-4 dark:bg-brand-950/30">
              <div className="text-sm text-neutral-500">إجمالي الفترة المفلترة · {summaryLoading ? 'جارٍ الحساب' : `${filteredSummary?.count || 0} مصروف`}</div>
              <div className="mt-1 text-2xl font-bold tabular-nums">{summaryLoading ? 'جارٍ الحساب…' : formatCurrency(filteredSummary?.total || 0)}</div>
            </div>
            {summaryLoading ? (
              <div className="py-6"><Spinner size={28} /></div>
            ) : !filteredSummary || filteredSummary.categories.length === 0 ? (
              <EmptyState title="لا توجد مصاريف في الفترة" description="غيّر الفترة أو الفلاتر لعرض الملخص" />
            ) : (
              <div className="divide-y divide-sand-100 rounded-xl border border-sand-200">
                {filteredSummary.categories.map((category) => (
                  <div key={category.category ?? 'uncategorized'} className="flex items-center justify-between gap-4 p-3">
                    <div>
                      <div className="font-medium">{category.category_name}</div>
                      <div className="text-xs text-neutral-500">{category.count} مصروف</div>
                    </div>
                    <div className="font-semibold tabular-nums">{formatCurrency(category.total)}</div>
                  </div>
                ))}
              </div>
            )}
            <Button variant="ghost" onClick={() => setSummaryOpen(false)}>إغلاق</Button>
          </div>
        </Modal>

        <Modal open={!!editing} onClose={() => setEditing(null)} title="تعديل المصروف" maxWidth="max-w-2xl">
          {editing && <ExpenseForm initial={editing} branches={editBranches} categories={categories} onSubmit={handleUpdate} onCancel={() => setEditing(null)} />}
        </Modal>

        <Modal open={!!receiptPreview} onClose={() => setReceiptPreview(null)} title={`فاتورة المصروف${receiptPreview ? ` · ${formatDate(receiptPreview.expense.date)}` : ''}`} maxWidth="max-w-3xl">
          {receiptPreview && (
            <div className="flex max-h-[75vh] justify-center overflow-auto rounded-xl bg-sand-50 p-2">
              <img src={receiptPreview.image} alt="صورة فاتورة المصروف" className="h-auto max-h-[70vh] max-w-full object-contain" />
            </div>
          )}
        </Modal>

        <ConfirmDialog
          open={!!deleting}
          onClose={() => setDeleting(null)}
          onConfirm={handleDelete}
          loading={deleteLoading}
          message="هل أنت متأكد من حذف هذا المصروف؟ لا يمكن التراجع عن هذا الإجراء."
        />
      </div>
    </AppShell>
  );
}
