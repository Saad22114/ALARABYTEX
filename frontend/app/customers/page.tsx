'use client';

import { useState, useEffect, useCallback, useMemo } from 'react';
import AppShell from '@/components/layout/AppShell';
import Card from '@/components/ui/Card';
import Button from '@/components/ui/Button';
import Table, { Th, Td, Tr } from '@/components/ui/Table';
import SearchInput from '@/components/ui/SearchInput';
import Pagination from '@/components/ui/Pagination';
import Modal from '@/components/ui/Modal';
import ConfirmDialog from '@/components/ui/ConfirmDialog';
import CustomerForm from '@/components/forms/CustomerForm';
import EmptyState from '@/components/ui/EmptyState';
import Spinner from '@/components/ui/Spinner';
import Badge from '@/components/ui/Badge';
import Select from '@/components/ui/Select';
import StatCard from '@/components/ui/StatCard';
import DateRangeToolbar, { currentMonthRange } from '@/components/ui/DateRangeToolbar';
import { Plus, Pencil, Trash2, UserX, UserCheck, Users, UserPlus, Phone, MessageCircle, Search as SearchIcon, Printer, Download } from 'lucide-react';
import { Customer, CustomersSummary, Paginated, Branch, CustomerSalesResult, SaleSession } from '@/types';
import {
  listCustomers, createCustomer, updateCustomer, deleteCustomer,
  getCustomersSummary, lookupCustomer,
} from '@/services/customers';
import { listBranches } from '@/services/branches';
import { getCustomerSales, getSaleSession } from '@/services/sessions';
import { formatDate, formatCurrency } from '@/lib/format';
import { downloadCsv, csvFilename } from '@/lib/csv';
import { useToast } from '@/components/ui/Toast';
import { useSettings } from '@/components/providers/SettingsProvider';
import { useUrlState } from '@/lib/useUrlState';
import SessionCustomerInvoiceModal from '@/components/sessions/SessionCustomerInvoiceModal';

/**
 * «السعر الأعلى» ليس عموداً في جدول الزبائن، بل مجموعُ مشتريات الزبون في جدول
 * البنود. ولهذا المفتاحُ المختار اسمٌ يُترجمه الخادم إلى ذلك المجموع، ولهذا
 * يُحفَظ في العنوان وحده فيمضي معه الانتقالُ إلى زبونٍ آخر بلا إعادة اختيار.
 */
const SORT_OPTIONS = [
  { value: '', label: 'الترتيب: الاسم' },
  { value: 'newest', label: 'الأحدث أولاً' },
  { value: 'oldest', label: 'الأقدم أولاً' },
  { value: 'top', label: 'السعر الأعلى أولاً' },
  { value: 'bottom', label: 'السعر الأقل أولاً' },
];

export default function CustomersPage() {
  const { toast } = useToast();
  const { settings } = useSettings();
  const pageSize = settings?.default_page_size ?? 10;
  const [data, setData] = useState<Paginated<Customer> | null>(null);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useUrlState('q', '');
  const [page, setPage] = useUrlState('page', 1);
  const [filterBranch, setFilterBranch] = useUrlState('branch', '');
  const [dateFrom, setDateFrom] = useUrlState('from', currentMonthRange().from);
  const [dateTo, setDateTo] = useUrlState('to', currentMonthRange().to);
  // «الكل» رايةٌ مستقلّةٌ لا تاريخان فارغان. فراغُ التاريخين يُحذف من العنوان
  // عند التحديث فيعود الشهر الجاري، فتنقرض الرايةُ بلا سبب.
  const [allTime, setAllTime] = useUrlState('all', '0');
  const noDates = allTime === '1';
  const [sort, setSort] = useUrlState('sort', '');
  const [summary, setSummary] = useState<CustomersSummary | null>(null);
  const [branches, setBranches] = useState<Branch[]>([]);
  const [modalOpen, setModalOpen] = useState(false);
  const [editing, setEditing] = useState<Customer | null>(null);
  const [deleting, setDeleting] = useState<Customer | null>(null);
  const [deleteLoading, setDeleteLoading] = useState(false);
  const [togglingId, setTogglingId] = useState<number | null>(null);
  const [phoneSearch, setPhoneSearch] = useState('');
  const [phoneLoading, setPhoneLoading] = useState(false);
  const [phoneHints, setPhoneHints] = useState<Customer[]>([]);
  const [hintsOpen, setHintsOpen] = useState(false);
  const [customerSales, setCustomerSales] = useState<CustomerSalesResult | null>(null);
  const [phoneMiss, setPhoneMiss] = useState<string | null>(null);
  const [invoiceSession, setInvoiceSession] = useState<SaleSession | null>(null);
  const [invoiceItemIds, setInvoiceItemIds] = useState<number[]>([]);
  const [invoiceOpen, setInvoiceOpen] = useState(false);

  /**
   * استعلامٌ واحدٌ يبني القائمةَ ويُبنى عليه التصدير.
   *
   * كان التصدير يسألُ الخادم من جديد بمعطياتٍ لا شيءَ منها مما يراه
   * المستخدم: لا بحثٌ ولا فرعٌ ولا تاريخان ولا ترتيب. فالملفّ كان يصلُ
   * أبجدياً وكاملاً دائماً، من أيّ شاشةٍ صُدِّر منها — فلا يُعرف الخطأُ
   * فيه حتى لا تُطابق الأرقام.
   */
  const listParams = useMemo(
    (): Record<string, string | number | undefined | null> => ({
      search: search || undefined,
      branch: filterBranch || undefined,
      ordering: sort || undefined,
      date_from: noDates ? undefined : dateFrom || undefined,
      date_to: noDates ? undefined : dateTo || undefined,
    }),
    [search, filterBranch, sort, dateFrom, dateTo, noDates]
  );

  const fetchData = useCallback(() => {
    let cancelled = false;
    setLoading(true);
    const params = { ...listParams, page, page_size: pageSize };
    listCustomers(params)
      .then((res) => { if (!cancelled) setData(res); })
      .catch((err) => { if (!cancelled) toast('error', err.message); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [page, pageSize, listParams, toast]);

  useEffect(() => fetchData(), [fetchData]);

  useEffect(() => {
    getCustomersSummary({
      branch: filterBranch || undefined,
      date_from: noDates ? undefined : dateFrom || undefined,
      date_to: noDates ? undefined : dateTo || undefined,
    })
      .then(setSummary)
      .catch(() => setSummary(null));
  }, [filterBranch, dateFrom, dateTo, noDates]);

  useEffect(() => {
    listBranches({ page_size: 200 }).then((res) => setBranches(res.results)).catch(() => {});
  }, []);

  const totalPages = data ? Math.ceil(data.count / pageSize) : 1;

  const handleCreate = async (d: Partial<Customer>) => {
    await createCustomer(d);
    toast('success', 'تمت إضافة الزبون بنجاح');
    setModalOpen(false);
    fetchData();
  };

  const handleUpdate = async (d: Partial<Customer>) => {
    if (!editing) return;
    await updateCustomer(editing.id, d);
    toast('success', 'تم تحديث الزبون بنجاح');
    setEditing(null);
    fetchData();
  };

  const handleDelete = async () => {
    if (!deleting) return;
    setDeleteLoading(true);
    try {
      await deleteCustomer(deleting.id);
      toast('success', 'تم حذف الزبون بنجاح');
      setDeleting(null);
      fetchData();
    } catch (err: any) {
      toast('error', err.message);
    } finally {
      setDeleteLoading(false);
    }
  };

  const toggleActive = async (c: Customer) => {
    setTogglingId(c.id);
    try {
      await updateCustomer(c.id, { is_active: !c.is_active });
      toast('success', c.is_active ? 'تم تعطيل الزبون' : 'تم تفعيل الزبون');
      fetchData();
    } catch (err: any) {
      toast('error', err.message);
    } finally {
      setTogglingId(null);
    }
  };

  /**
   * رقمٌ خطأ لا يجيب «لا نتائج» أبداً.
   *
   * رقمان يبدوان واحداً: زبونٌ مسجَّل بلا مشتريات، ورقمٌ لا وجود له.
   * الأول يُعالَج بأن يعدّ المتعاملون رصيده، والثاني بأن يُسجَّل أو
   * يُصحَّح. وجدولٌ فارغٌ لا يفرق بينهما، فيظنّ الموظف أنّ الزبون
   * موجودٌ بلا مبيعات وهو في الحقيقة رقمٌ أخطأ فيه — فيُطالب زبوناً
   * غيره بدينٍ عليه.
   */
  /**
   * ما يكتبه الموظف يُقرأ قبل أن يُكمل.
   *
   * الموظفُ يتذكّر نصفَ رقمٍ ويكتبه، ثم ينتظر. فإذا انتظر ضغطةَ «بحث» لأظهر
   * جواباً، صار الحقلُ عقبةً بينه وبين الزبون. فنبحثُ فورَ الكتابة، بعد أن
   * يتوقّف القلمُ لحظة، فيرى المتشابهَ وهو لا يزال ينوي.
   *
   * ثلاثةُ أرقامٍ حدٌّ أدنى: رقمان يطابقان نصفَ كلِّ الأرقام، فيصير الجدولُ
   * كلُّه ولا يبقى «المتشابه» متشاهاً. وما دون ثلاثة أرقام لا نرسمُ قائمةً
   * أبداً، لأنّه لا سؤالَ فيه.
   */
  useEffect(() => {
    const digits = phoneSearch.replace(/\D/g, '');
    if (digits.length < 3) {
      setPhoneHints([]);
      setHintsOpen(false);
      return;
    }
    let cancelled = false;
    const timer = setTimeout(() => {
      listCustomers({ search: digits, page_size: 8, page: 1 })
        .then((res) => {
          if (cancelled) return;
          setPhoneHints(res.results);
          setHintsOpen(true);
        })
        .catch(() => { if (!cancelled) setPhoneHints([]); });
    }, 250);
    return () => { cancelled = true; clearTimeout(timer); };
  }, [phoneSearch]);

  /** الضغطُ على مقترحٍ يملأ الرقم كاملاً ويطلب كشف مبيعاته — لا يتركه معلَّقاً. */
  const chooseHint = (customer: Customer) => {
    setPhoneSearch(customer.phone || '');
    setHintsOpen(false);
    setTimeout(() => { void handlePhoneSearch(customer.phone || ''); }, 0);
  };

  const handlePhoneSearch = async (forced?: string) => {
    const phone = (forced ?? phoneSearch).trim();
    if (!phone) return;
    setPhoneLoading(true);
    setCustomerSales(null);
    setPhoneMiss(null);
    try {
      const res = await getCustomerSales(phone);
      if (res.items.length === 0) {
        const found = await lookupCustomer(phone);
        setPhoneMiss(
          found.found
            ? `${found.customer?.name} مسجَّل بهذا الرقم وليس له مشتريات مسجّلة`
            : `لا يوجد زبون مسجَّل بالرقم ${phone}`,
        );
        return;
      }
      setCustomerSales(res);
    } catch (err: any) {
      toast('error', err.message);
    } finally {
      setPhoneLoading(false);
    }
  };

  const handleInvoice = async (sessionId: number, itemIds: number[]) => {
    try {
      const session = await getSaleSession(sessionId);
      setInvoiceSession(session);
      setInvoiceItemIds(itemIds);
      setInvoiceOpen(true);
    } catch (err: any) {
      toast('error', err.message);
    }
  };

  /**
   * يصدّر كلّ ما تعرضه الشاشة، لا الصفحة المعروضة فقط.
   *
   * ومعه البحثُ والفرعُ والتاريخان والترتيبُ الذي يراه الموظف فوق.
   * ولو صدّرنا `data` الحالي لانتفقت الصفحاتُ مع ما يراه على الشاشة.
   */
  const handleExport = async () => {
    try {
      const res = await listCustomers({ ...listParams, page_size: 100000 });
      downloadCsv(csvFilename('customers'), [
        { header: 'الاسم', value: (c: Customer) => c.name },
        { header: 'الهاتف', value: (c: Customer) => c.phone },
        { header: 'العنوان', value: (c: Customer) => c.address },
        { header: 'الحالة', value: (c: Customer) => (c.is_active ? 'نشط' : 'معطل') },
        { header: 'عدد المشتريات', value: (c: Customer) => c.purchase_count ?? 0 },
        { header: 'إجمالي المشتريات', value: (c: Customer) => c.purchase_total ?? 0 },
        { header: 'آخر شراء', value: (c: Customer) => c.last_purchase_date || '' },
      ], res.results);
      const filtered = Boolean(search || filterBranch || sort || !noDates);
      toast(
        'success',
        filtered
          ? `تم تصدير ${res.results.length} زبوناً ممّا تعرضه الشاشة`
          : `تم تصدير ${res.results.length} زبون`
      );
    } catch (err: any) {
      toast('error', err.message);
    }
  };

  return (
    <AppShell>
      <div className="space-y-6">
        <div className="flex flex-wrap items-center gap-3">
          <DateRangeToolbar
            from={dateFrom}
            to={dateTo}
            onChange={(f, t) => { setAllTime('0'); setDateFrom(f); setDateTo(t); setPage(1); }}
            allowAll
            allActive={noDates}
            onSelectAll={() => { setAllTime('1'); setPage(1); }}
          />
          <Select
            value={filterBranch}
            onChange={(e) => { setFilterBranch(e.target.value); setPage(1); }}
            options={[{ value: '', label: 'كل الفروع' }, ...branches.map((b) => ({ value: String(b.id), label: b.name }))]}
            className="w-full sm:w-48"
          />
          <Select
            value={sort}
            onChange={(e) => { setSort(e.target.value); setPage(1); }}
            options={SORT_OPTIONS}
            className="w-full sm:w-52"
          />
        </div>

        {summary && (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            <StatCard icon={<Users size={22} />} label="إجمالي الزبائن" value={summary.total_customers} sub={`${summary.active_count} نشط`} />
            <StatCard icon={<UserCheck size={22} />} iconBg="bg-emerald-50 text-emerald-600" label="الزبائن النشطون" value={summary.active_count} />
            <StatCard icon={<UserPlus size={22} />} iconBg="bg-amber-50 text-amber-600" label="الجدد في الفترة" value={summary.new_count} />
            <StatCard icon={<Phone size={22} />} iconBg="bg-indigo-50 text-indigo-600" label="لديهم رقم هاتف" value={summary.with_phone_count} />
          </div>
        )}

        <Card title="بحث الزبون بالهاتف" subtitle="اكتب جزءاً من الرقم فيظهر المتشابه فوراً — ثم اضغط بحث لعرض كل مبيعاته وإمكانية عمل فاتورة">
          <div className="flex gap-2 flex-wrap items-end">
            <div className="flex-1 min-w-[200px] relative">
              <label className="block text-sm font-medium text-neutral-700 mb-1">رقم الهاتف</label>
              <div className="flex gap-2">
                <input
                  type="tel"
                  value={phoneSearch}
                  onChange={(e) => { setPhoneSearch(e.target.value); setHintsOpen(true); }}
                  onKeyDown={(e) => e.key === 'Enter' && handlePhoneSearch()}
                  onBlur={() => setTimeout(() => setHintsOpen(false), 150)}
                  placeholder="أدخل رقم الهاتف"
                  className="w-full rounded-lg border border-neutral-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-400"
                />
                <Button onClick={() => handlePhoneSearch()} loading={phoneLoading} disabled={!phoneSearch.trim()}>
                  <SearchIcon size={16} />
                  بحث
                </Button>
              </div>
              {hintsOpen && phoneHints.length > 0 && (
                <ul className="absolute z-20 mt-1 w-full rounded-xl border border-sand-200 bg-surface shadow-lg overflow-hidden">
                  {phoneHints.map((c) => (
                    <li key={c.id}>
                      <button
                        type="button"
                        onMouseDown={(e) => e.preventDefault()}
                        onClick={() => chooseHint(c)}
                        className="flex w-full items-center justify-between gap-3 px-3 py-2 text-right text-sm hover:bg-sand-50"
                      >
                        <span className="font-medium text-neutral-800 truncate">{c.name}</span>
                        <span dir="ltr" className="text-neutral-500 tabular-nums">{c.phone}</span>
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </div>
          {phoneMiss && (
            <p className="mt-4 rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
              {phoneMiss}
            </p>
          )}
          {customerSales && (
            <div className="mt-4 space-y-4">
              <div className="flex flex-wrap gap-4 text-sm">
                <span>الهاتف: <b>{customerSales.phone}</b></span>
                <span>العدد: <b>{customerSales.totals.count}</b> بيعة</span>
                <span>المبلغ: <b>{formatCurrency(customerSales.totals.total)}</b></span>
                <span>الياردات: <b>{customerSales.totals.yards}</b></span>
              </div>
              {(() => {
                const sessions = new Map<number, typeof customerSales.items>();
                for (const item of customerSales.items) {
                  const list = sessions.get(item.session_id);
                  if (list) list.push(item); else sessions.set(item.session_id, [item]);
                }
                return Array.from(sessions.entries()).map(([sid, items]) => {
                  const first = items[0];
                  const openItems = items.filter((i) => !i.is_returned);
                  return (
                    <div key={sid} className="border rounded-lg p-3 bg-surface">
                      <div className="flex flex-wrap items-center justify-between gap-2 text-sm mb-2">
                        <span>
                          الوردية #{sid} — <b>{first.session_status_label}</b>
                        </span>
                        <Button size="sm" variant="subtle" onClick={() => handleInvoice(sid, items.map((i) => i.id))}>
                          <Printer size={14} /> فاتورة
                        </Button>
                      </div>
                      <div className="text-xs text-neutral-500 space-y-1">
                        {openItems.slice(0, 5).map((i) => (
                          <div key={i.id}>
                            {i.fabric_name} — {i.yards_effective ?? i.quantity} يارد — {formatCurrency(i.total)}
                          </div>
                        ))}
                        {openItems.length > 5 && <div>...و{openItems.length - 5} بنود أخرى</div>}
                      </div>
                    </div>
                  );
                });
              })()}
            </div>
          )}
        </Card>

        <div className="flex items-center justify-between gap-3">
          <SearchInput value={search} onChange={(v) => { setSearch(v); setPage(1); }} />
          <div className="flex gap-2">
            <Button variant="subtle" onClick={handleExport}>
              <Download size={18} />
              تصدير CSV
            </Button>
            <Button onClick={() => setModalOpen(true)}>
              <Plus size={18} />
              إضافة زبون
            </Button>
          </div>
        </div>

        <Card>
          {loading ? (
            <div className="flex justify-center py-12"><Spinner size={32} /></div>
          ) : !data || data.results.length === 0 ? (
            search.trim() ? (
              <EmptyState
                title={`لا يوجد زبون يطابق «${search.trim()}»`}
                description="لا يوجد زبون مسجَّل بهذا الاسم أو الرقم ضمن نطاق التواريخ المختار — جرّب «الكل» لترى الزبائن كلهم، أو أضِفه إن كان جديداً."
              />
            ) : (
              <EmptyState title="لا يوجد زبائن" description="لم يتم تسجيل أي زبون بعد — سيتم تسجيل الزبائن تلقائياً عند كتابة الاسم والهاتف في نقطة البيع أو في الفاتورة" />
            )
          ) : (
            <>
              <Table>
                <thead>
                  <tr>
                    <Th>اسم الزبون</Th>
                    <Th>رقم الهاتف</Th>
                    <Th>إجمالي المشتريات</Th>
                    <Th>آخر شراء</Th>
                    <Th>البريد الإلكتروني</Th>
                    <Th>الفرع</Th>
                    <Th>ملاحظات</Th>
                    <Th>الحالة</Th>
                    <Th>تاريخ التسجيل</Th>
                    <Th>إجراءات</Th>
                  </tr>
                </thead>
                <tbody>
                  {data.results.map((c) => (
                    <Tr key={c.id}>
                      <Td className="font-medium">{c.name}</Td>
                      <Td>
                        <div className="flex items-center gap-2">
                          <span dir="ltr" className="text-left">{c.phone || '-'}</span>
                          {c.phone ? (
                            <a
                              href={`https://wa.me/968${c.phone.replace(/[^\d]/g, '')}`}
                              target="_blank"
                              rel="noreferrer"
                              className="p-1 rounded-lg hover:bg-emerald-50 text-emerald-600 transition-colors"
                              title="تواصل عبر واتساب"
                            >
                              <MessageCircle size={15} />
                            </a>
                          ) : null}
                        </div>
                      </Td>
                      <Td className="text-sm tabular-nums">
                        {c.purchase_count ? (
                          <span className="block">{formatCurrency(c.purchase_total ?? 0)}</span>
                        ) : (
                          <span className="text-xs text-neutral-400">بدون مشتريات</span>
                        )}
                      </Td>
                      <Td className="text-sm">{c.last_purchase_date ? formatDate(c.last_purchase_date) : '-'}</Td>
                      <Td>{c.email || '-'}</Td>
                      <Td>{c.branch_name || '-'}</Td>
                      <Td className="max-w-[200px] truncate">{c.notes || '-'}</Td>
                      <Td>
                        <Badge variant={c.is_active ? 'success' : 'neutral'}>
                          {c.is_active ? 'نشط' : 'موقوف'}
                        </Badge>
                      </Td>
                      <Td>{formatDate(c.created_at)}</Td>
                      <Td>
                        <div className="flex items-center gap-2">
                          <button onClick={() => setEditing(c)} className="p-1.5 rounded-lg hover:bg-amber-50 text-amber-600 dark:hover:bg-amber-500/15 dark:text-amber-400 transition-colors" title="تعديل">
                            <Pencil size={16} />
                          </button>
                          <button onClick={() => toggleActive(c)} disabled={togglingId === c.id} className="p-1.5 rounded-lg hover:bg-brand-50 text-brand-600 transition-colors disabled:opacity-50" title={c.is_active ? 'تعطيل' : 'تفعيل'}>
                            {c.is_active ? <UserX size={16} /> : <UserCheck size={16} />}
                          </button>
                          <button onClick={() => setDeleting(c)} className="p-1.5 rounded-lg hover:bg-red-50 text-red-500 dark:hover:bg-red-500/15 dark:text-red-400 transition-colors" title="حذف">
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

        <Modal open={modalOpen} onClose={() => setModalOpen(false)} title="إضافة زبون جديد" maxWidth="max-w-2xl">
          <CustomerForm defaultBranch={filterBranch ? Number(filterBranch) : null} onSubmit={handleCreate} onCancel={() => setModalOpen(false)} />
        </Modal>

        <Modal open={!!editing} onClose={() => setEditing(null)} title="تعديل الزبون" maxWidth="max-w-2xl">
          {editing && <CustomerForm initial={editing} onSubmit={handleUpdate} onCancel={() => setEditing(null)} />}
        </Modal>

        <ConfirmDialog
          open={!!deleting}
          onClose={() => setDeleting(null)}
          onConfirm={handleDelete}
          loading={deleteLoading}
          message={`هل أنت متأكد من حذف الزبون "${deleting?.name}"؟ لا يمكن التراجع عن هذا الإجراء.`}
        />
        <SessionCustomerInvoiceModal
          open={invoiceOpen}
          onClose={() => setInvoiceOpen(false)}
          session={invoiceSession}
          itemIds={invoiceItemIds}
          settings={settings}
        />
      </div>
    </AppShell>
  );
}