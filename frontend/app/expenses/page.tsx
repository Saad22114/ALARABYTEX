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
import { Plus, Pencil, Trash2, RefreshCw, Download, Receipt, Tags } from 'lucide-react';
import { Expense, Branch, ExpenseCategory, Paginated } from '@/types';
import { listExpenses, createExpense, updateExpense, deleteExpense, listExpenseCategories, runRecurringExpenses } from '@/services/expenses';
import { listBranches } from '@/services/branches';
import { formatCurrency, formatDate } from '@/lib/format';
import { downloadCsv, csvFilename } from '@/lib/csv';
import { PAYMENT_METHODS_MAP } from '@/lib/constants';
import { useToast } from '@/components/ui/Toast';
import { useSettings } from '@/components/providers/SettingsProvider';
import { useUrlState } from '@/lib/useUrlState';

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
  const [search, setSearch] = useUrlState('q', '');
  const [filterBranch, setFilterBranch] = useUrlState('branch', '');
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

  const handleRunRecurring = async () => {
    setRecurringLoading(true);
    try {
      const res = await runRecurringExpenses();
      toast('success', res.count > 0 ? `تم ترحيل ${res.count} مصروف متكرر` : 'لا توجد مصاريف مستحقة للترحيل');
      fetchData();
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
    const params: Record<string, string | number | undefined | null> = {
      page,
      page_size: pageSize,
      search: search || undefined,
      branch: filterBranch || undefined,
      category: filterCategory || undefined,
      date_from: dateFrom || undefined,
      date_to: dateTo || undefined,
    };
    listExpenses(params)
      .then((res) => { if (!cancelled) setData(res); })
      .catch((err) => { if (!cancelled) toast('error', err.message); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [page, pageSize, search, filterBranch, filterCategory, dateFrom, dateTo, toast]);

  useEffect(() => fetchData(), [fetchData]);

  const totalPages = data ? Math.ceil(data.count / pageSize) : 1;

  const handleCreate = async (d: Partial<Expense>) => {
    await createExpense(d);
    toast('success', 'تم تسجيل المصروف بنجاح');
    setModalOpen(false);
    fetchData();
  };

  const handleUpdate = async (d: Partial<Expense>) => {
    if (!editing) return;
    await updateExpense(editing.id, d);
    toast('success', 'تم تحديث المصروف بنجاح');
    setEditing(null);
    fetchData();
  };

  const handleDelete = async () => {
    if (!deleting) return;
    setDeleteLoading(true);
    try {
      await deleteExpense(deleting.id);
      toast('success', 'تم حذف المصروف بنجاح');
      setDeleting(null);
      fetchData();
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
      toast('success', `تم تصدير ${res.results.length} مصروف`);
    } catch (err: any) {
      toast('error', err.message);
    }
  };

  return (
    <AppShell>
      <div className="space-y-6">
        <div className="flex items-center justify-between gap-3">
          <div className="flex items-center gap-3">
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
              <SearchInput value={search} onChange={(v) => { setSearch(v); setPage(1); }} placeholder="بحث في المصاريف..." />
            </div>
            <Select
              value={filterBranch}
              onChange={(e) => { setFilterBranch(e.target.value); setPage(1); }}
              options={[{ value: '', label: 'كل الفروع' }, ...branches.map((b) => ({ value: b.id, label: b.name }))]}
              className="w-full sm:w-48"
            />
            <Select
              value={filterCategory}
              onChange={(e) => { setFilterCategory(e.target.value); setPage(1); }}
              options={[{ value: '', label: 'كل التصنيفات' }, ...categories.map((c) => ({ value: c.id, label: c.name }))]}
              className="w-full sm:w-48"
            />
            <DateRangeToolbar
              from={dateFrom}
              to={dateTo}
              onChange={(f, t) => { setDateFrom(f); setDateTo(t); setPage(1); }}
            />
          </div>
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
                    <Th>التاريخ</Th>
                    <Th>الفرع</Th>
                    <Th>نوع المصروف</Th>
                    <Th>المبلغ</Th>
                    <Th>طريقة الدفع</Th>
                    <Th>الوصف</Th>
                    <Th>ملاحظات</Th>
                    <Th>التكرار</Th>
                    <Th>إجراءات</Th>
                  </tr>
                </thead>
                <tbody>
                  {data.results.map((e) => (
                    <Tr key={e.id}>
                      <Td>{formatDate(e.date)}</Td>
                      <Td className="font-medium">{e.branch_name}</Td>
                      <Td>{e.category_name}</Td>
                      <Td className="tabular-nums font-medium">{formatCurrency(e.amount)}</Td>
                      <Td>{PAYMENT_METHODS_MAP[e.payment_method] || e.payment_method}</Td>
                      <Td className="max-w-[200px] truncate" title={e.description || undefined}>{e.description || '-'}</Td>
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

        <Modal open={!!editing} onClose={() => setEditing(null)} title="تعديل المصروف" maxWidth="max-w-2xl">
          {editing && <ExpenseForm initial={editing} branches={editBranches} categories={categories} onSubmit={handleUpdate} onCancel={() => setEditing(null)} />}
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
