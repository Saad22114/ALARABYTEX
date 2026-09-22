'use client';

import { useState, useEffect, useRef } from 'react';
import AppShell from '@/components/layout/AppShell';
import Card from '@/components/ui/Card';
import Button from '@/components/ui/Button';
import Table, { Th, Td, Tr } from '@/components/ui/Table';
import Modal from '@/components/ui/Modal';
import Input from '@/components/ui/Input';
import Select from '@/components/ui/Select';
import Badge from '@/components/ui/Badge';
import Spinner from '@/components/ui/Spinner';
import EmptyState from '@/components/ui/EmptyState';
import ConfirmDialog from '@/components/ui/ConfirmDialog';
import Switch from '@/components/ui/Switch';
import {
  Plus, Trash2, Download, Upload, RotateCcw, Pencil, Check,
  Store, Coins, SlidersHorizontal, LayoutGrid, Database, Info, Wallet,
} from 'lucide-react';
import { ExpenseCategory, ExpenseBudget, Branch, AppSection } from '@/types';
import { listExpenseCategories, listExpenseBudgets, createExpenseBudget, updateExpenseBudget, deleteExpenseBudget } from '@/services/expenses';
import { listBranches } from '@/services/branches';
import { backupUrl, restoreSettings, resetData, getAutoBackups, runAutoBackup, autoBackupDownloadUrl, AutoBackupInfo } from '@/services/settings';
import { getSectionsInfo } from '@/services/sections';
import { API_URL } from '@/services/api';
import { useToast } from '@/components/ui/Toast';
import { useSettings } from '@/components/providers/SettingsProvider';
import { useUrlState } from '@/lib/useUrlState';
import { formatCurrency } from '@/lib/format';

const PERIOD_OPTIONS = [
  { value: 'today', label: 'اليوم' },
  { value: 'week', label: 'هذا الأسبوع' },
  { value: 'month', label: 'هذا الشهر' },
];

const PAGE_SIZE_OPTIONS = [
  { value: 5, label: '5' },
  { value: 10, label: '10' },
  { value: 20, label: '20' },
  { value: 50, label: '50' },
];

const DECIMAL_OPTIONS = [0, 1, 2, 3, 4].map((d) => ({ value: d, label: String(d) }));

const CUTOFF_HOUR_OPTIONS = [0, 1, 2, 3, 4, 5, 6, 7].map((h) => ({ value: h, label: `${h}:00` }));

const CURRENCY_POSITION_OPTIONS = [
  { value: 'after', label: 'بعد المبلغ (43 ر.ع)' },
  { value: 'before', label: 'قبل المبلغ (ر.ع 43)' },
];

const TAX_RATE_OPTIONS = [
  { value: 0, label: 'بدون ضريبة (0%)' },
  { value: 5, label: '5%' },
  { value: 10, label: '10%' },
  { value: 15, label: '15%' },
  { value: 23, label: '23%' },
];

const DEFAULT_PAYMENT_OPTIONS = [
  { value: 'cash', label: 'كاش' },
  { value: 'transfer', label: 'تحويل' },
  { value: 'card', label: 'ماكينة' },
];

const DATE_FORMAT_OPTIONS = [
  { value: 'YYYY-MM-DD', label: '2026-09-13' },
  { value: 'DD-MM-YYYY', label: '13-09-2026' },
  { value: 'DD/MM/YYYY', label: '13/09/2026' },
  { value: 'MM-DD-YYYY', label: '09-13-2026' },
];

const TABS = [
  { key: 'business', label: 'النشاط', icon: Store },
  { key: 'currency', label: 'العملة والتنسيق', icon: Coins },
  { key: 'prefs', label: 'التفضيلات والمخزون', icon: SlidersHorizontal },
  { key: 'sections', label: 'أقسام القائمة', icon: LayoutGrid },
  { key: 'budgets', label: 'الميزانيات', icon: Wallet },
  { key: 'data', label: 'إدارة البيانات', icon: Database },
  { key: 'system', label: 'بيانات النظام', icon: Info },
];

export default function SettingsPage() {
  const { toast } = useToast();
  const { settings, loading, error, updateSettings, refreshSettings } = useSettings();

  const [tab, setTab] = useUrlState('tab', 'business');

  const [savingBusiness, setSavingBusiness] = useState(false);
  const [savingCurrency, setSavingCurrency] = useState(false);
  const [savingPrefs, setSavingPrefs] = useState(false);
  const [savingSections, setSavingSections] = useState(false);

  const [businessForm, setBusinessForm] = useState({
    business_name: '',
    trade_name: '',
    commercial_registration: '',
    business_phone: '',
    business_address: '',
    tax_number: '',
    business_email: '',
    invoice_prefix: '',
    tax_rate: 0,
  });
  const [currencyForm, setCurrencyForm] = useState({
    currency_symbol: 'ر.ع',
    currency_code: 'OMR',
    decimal_places: 2,
    date_format: 'YYYY-MM-DD',
    currency_position: 'after' as 'after' | 'before',
  });
  const [prefsForm, setPrefsForm] = useState<{
    default_period: 'today' | 'week' | 'month';
    default_page_size: number;
    low_stock_threshold: number;
    low_stock_alert_enabled: boolean;
    session_warn_hours: number;
    session_danger_hours: number;
    default_payment_method: 'cash' | 'transfer' | 'card';
    discount_max_percent: number;
    previous_day_cutoff_hour: number;
  }>({
    default_period: 'today',
    default_page_size: 10,
    low_stock_threshold: 50,
    low_stock_alert_enabled: true,
    session_warn_hours: 2,
    session_danger_hours: 4,
    default_payment_method: 'transfer',
    discount_max_percent: 100,
    previous_day_cutoff_hour: 2,
  });
  const [hiddenSections, setHiddenSections] = useState<string[]>([]);

  useEffect(() => {
    if (settings) {
      setBusinessForm({
        business_name: settings.business_name || '',
        trade_name: settings.trade_name || '',
        commercial_registration: settings.commercial_registration || '',
        business_phone: settings.business_phone || '',
        business_address: settings.business_address || '',
        tax_number: settings.tax_number || '',
        business_email: settings.business_email || '',
        invoice_prefix: settings.invoice_prefix || '',
        tax_rate: Number(settings.tax_rate ?? 0),
      });
      setCurrencyForm({
        currency_symbol: settings.currency_symbol || 'ر.ع',
        currency_code: settings.currency_code || 'OMR',
        decimal_places: settings.decimal_places ?? 2,
        date_format: settings.date_format || 'YYYY-MM-DD',
        currency_position: settings.currency_position || 'after',
      });
      setPrefsForm({
        default_period: settings.default_period || 'today',
        default_page_size: settings.default_page_size ?? 10,
        low_stock_threshold: Number(settings.low_stock_threshold ?? 50),
        low_stock_alert_enabled: settings.low_stock_alert_enabled,
        session_warn_hours: settings.session_warn_hours ?? 2,
        session_danger_hours: settings.session_danger_hours ?? 4,
        default_payment_method: settings.default_payment_method || 'transfer',
        discount_max_percent: Number(settings.discount_max_percent ?? 100),
        previous_day_cutoff_hour: settings.previous_day_cutoff_hour ?? 2,
      });
      setHiddenSections(settings.hidden_sections || []);
    }
  }, [settings]);

  const [sections, setSections] = useState<AppSection[]>([]);

  useEffect(() => {
    let cancelled = false;
    getSectionsInfo()
      .then((res) => { if (!cancelled) setSections(res.sections); })
      .catch(() => {});
    return () => { cancelled = true; };
  }, []);

  const [restoring, setRestoring] = useState(false);
  const [resetting, setResetting] = useState(false);
  const [resetOpen, setResetOpen] = useState(false);
  const [backupPassword, setBackupPassword] = useState('');
  const [savingPassword, setSavingPassword] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [autoBackupInfo, setAutoBackupInfo] = useState<AutoBackupInfo | null>(null);
  const [autoBackupEnabled, setAutoBackupEnabled] = useState(false);
  const [autoBackupTime, setAutoBackupTime] = useState('');
  const [autoBackupEveryHours, setAutoBackupEveryHours] = useState(0);
  const [autoBackupLoading, setAutoBackupLoading] = useState(false);
  const [runningNow, setRunningNow] = useState(false);

  const [categories, setCategories] = useState<ExpenseCategory[]>([]);
  const [categoriesLoading, setCategoriesLoading] = useState(true);

  const [budgets, setBudgets] = useState<ExpenseBudget[]>([]);
  const [budgetsLoading, setBudgetsLoading] = useState(true);
  const [addBudgetOpen, setAddBudgetOpen] = useState(false);
  const [editBudget, setEditBudget] = useState<ExpenseBudget | null>(null);
  const [budgetBranch, setBudgetBranch] = useState('');
  const [budgetCategory, setBudgetCategory] = useState('');
  const [budgetMonth, setBudgetMonth] = useState<string>(() => new Date().toISOString().slice(0, 7));
  const [budgetAmount, setBudgetAmount] = useState<number>(0);
  const [budgetSaving, setBudgetSaving] = useState(false);
  const [deletingBudget, setDeletingBudget] = useState<ExpenseBudget | null>(null);
  const [deleteBudgetLoading, setDeleteBudgetLoading] = useState(false);
  const [budgetBranches, setBudgetBranches] = useState<Branch[]>([]);

  const fetchCategories = () => {
    let cancelled = false;
    setCategoriesLoading(true);
    listExpenseCategories({ page_size: 200 })
      .then((res) => { if (!cancelled) setCategories(res.results); })
      .catch((err) => { if (!cancelled) toast('error', err.message); })
      .finally(() => { if (!cancelled) setCategoriesLoading(false); });
    return () => { cancelled = true; };
  };

  useEffect(() => fetchCategories(), []);

  const fetchBudgetBranches = () => {
    let cancelled = false;
    listBranches({ page_size: 200 }).then((res) => {
      if (!cancelled) setBudgetBranches(res.results.filter((b) => b.is_active));
    });
    return () => { cancelled = true; };
  };
  const fetchBudgets = () => {
    let cancelled = false;
    setBudgetsLoading(true);
    listExpenseBudgets({ page_size: 200 })
      .then((res) => { if (!cancelled) setBudgets(res.results); })
      .catch((err) => { if (!cancelled) toast('error', err.message); })
      .finally(() => { if (!cancelled) setBudgetsLoading(false); });
    return () => { cancelled = true; };
  };
  useEffect(() => fetchBudgetBranches(), []);
  useEffect(() => fetchBudgets(), []);

  const fetchAutoBackups = () => {
    getAutoBackups()
      .then((info) => setAutoBackupInfo(info))
      .catch(() => {});
  };
  useEffect(() => { fetchAutoBackups(); }, []);
  useEffect(() => {
    if (settings) {
      setAutoBackupEnabled(!!settings.auto_backup_enabled);
      setAutoBackupTime(settings.auto_backup_time || '');
      setAutoBackupEveryHours(Number(settings.auto_backup_every_hours || 0));
    }
  }, [settings]);

  const handleSaveAutoBackup = async () => {
    setAutoBackupLoading(true);
    try {
      const patch: any = {
        auto_backup_enabled: autoBackupEnabled,
        auto_backup_time: autoBackupTime || null,
        auto_backup_every_hours: autoBackupEveryHours,
      };
      await updateSettings(patch);
      toast('success', 'تم حفظ إعدادات النسخ التلقائي بنجاح');
    } catch (err: any) {
      toast('error', err.message);
    } finally {
      setAutoBackupLoading(false);
    }
  };

  const handleRunAutoBackupNow = async () => {
    setRunningNow(true);
    try {
      await runAutoBackup();
      toast('success', 'تم إنشاء نسخة احتياطية الآن');
      fetchAutoBackups();
    } catch (err: any) {
      toast('error', err.message);
    } finally {
      setRunningNow(false);
    }
  };

  const handleSaveBusiness = async () => {
    setSavingBusiness(true);
    try {
      await updateSettings({ ...businessForm });
      toast('success', 'تم حفظ معلومات النشاط بنجاح');
    } catch (err: any) {
      toast('error', err.message);
    } finally {
      setSavingBusiness(false);
    }
  };

  const handleSaveCurrency = async () => {
    setSavingCurrency(true);
    try {
      await updateSettings({
        currency_symbol: currencyForm.currency_symbol,
        currency_code: currencyForm.currency_code,
        decimal_places: currencyForm.decimal_places,
        date_format: currencyForm.date_format,
        currency_position: currencyForm.currency_position,
      });
      toast('success', 'تم حفظ إعدادات العملة والتنسيق بنجاح');
    } catch (err: any) {
      toast('error', err.message);
    } finally {
      setSavingCurrency(false);
    }
  };

  const handleSavePrefs = async () => {
    setSavingPrefs(true);
    try {
      await updateSettings(prefsForm);
      toast('success', 'تم حفظ التفضيلات بنجاح');
    } catch (err: any) {
      toast('error', err.message);
    } finally {
      setSavingPrefs(false);
    }
  };

  const handleSaveSections = async () => {
    setSavingSections(true);
    try {
      await updateSettings({ hidden_sections: hiddenSections });
      toast('success', 'تم حفظ إظهار/إخفاء الأقسام بنجاح');
    } catch (err: any) {
      toast('error', err.message);
    } finally {
      setSavingSections(false);
    }
  };

  const toggleSection = (key: string) => {
    setHiddenSections((prev) => (prev.includes(key) ? prev.filter((k) => k !== key) : [...prev, key]));
  };

  const handleBackup = () => {
    const a = document.createElement('a');
    a.href = backupUrl();
    a.download = 'backup.json';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
  };

  const handleRestoreFile = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    e.target.value = '';
    if (!file) return;
    setRestoring(true);
    try {
      const text = await file.text();
      JSON.parse(text);
      await restoreSettings({ content: text });
      toast('success', 'تم استيراد النسخة الاحتياطية بنجاح');
      refreshSettings();
    } catch (err: any) {
      toast('error', err.message || 'فشل استيراد النسخة الاحتياطية');
    } finally {
      setRestoring(false);
    }
  };

  const handleSavePassword = async () => {
    setSavingPassword(true);
    try {
      await updateSettings({ backup_password: backupPassword });
      toast('success', backupPassword ? 'تم حفظ كلمة مرور النسخة الاحتياطية' : 'تم إلغاء تشفير النسخة الاحتياطية');
      setBackupPassword('');
      refreshSettings();
    } catch (err: any) {
      toast('error', err.message || 'فشل حفظ كلمة المرور');
    } finally {
      setSavingPassword(false);
    }
  };

  const handleReset = async () => {
    setResetting(true);
    try {
      await resetData({ confirm: true, scope: 'transactions' });
      toast('success', 'تمت إعادة ضبط البيانات بنجاح');
      setResetOpen(false);
      refreshSettings();
    } catch (err: any) {
      toast('error', err.message);
    } finally {
      setResetting(false);
    }
  };

  const openAddBudget = () => {
    setEditBudget(null);
    setBudgetBranch('');
    setBudgetCategory('');
    setBudgetMonth(new Date().toISOString().slice(0, 7));
    setBudgetAmount(0);
    setAddBudgetOpen(true);
  };

  const handleSaveBudget = async () => {
    if (!budgetBranch || !budgetCategory || !budgetAmount || budgetAmount <= 0) {
      toast('error', 'اختر الفرع والتصنيف وأدخل قيمة صحيحة');
      return;
    }
    if (!budgetMonth) {
      toast('error', 'حدد الشهر');
      return;
    }
    setBudgetSaving(true);
    const monthValue = `${budgetMonth}-01`;
    const payload = {
      branch: Number(budgetBranch),
      category: Number(budgetCategory),
      month: monthValue,
      amount: budgetAmount,
    };
    try {
      if (editBudget) {
        await updateExpenseBudget(editBudget.id, payload);
        toast('success', 'تم تحديث الميزانية بنجاح');
      } else {
        await createExpenseBudget(payload);
        toast('success', 'تمت إضافة الميزانية بنجاح');
      }
      setAddBudgetOpen(false);
      fetchBudgets();
    } catch (err: any) {
      toast('error', err.message);
    } finally {
      setBudgetSaving(false);
    }
  };

  const handleDeleteBudget = async () => {
    if (!deletingBudget) return;
    setDeleteBudgetLoading(true);
    try {
      await deleteExpenseBudget(deletingBudget.id);
      toast('success', 'تم حذف الميزانية بنجاح');
      setDeletingBudget(null);
      fetchBudgets();
    } catch (err: any) {
      toast('error', err.message);
    } finally {
      setDeleteBudgetLoading(false);
    }
  };

  if (loading && !settings) {
    return (
      <AppShell>
        <div className="flex items-center justify-center py-20">
          <Spinner size={40} />
        </div>
      </AppShell>
    );
  }

  if (error && !settings) {
    return (
      <AppShell>
        <div className="text-center py-20 text-neutral-400">
          <p>حدث خطأ أثناء تحميل الإعدادات</p>
          <Button variant="secondary" className="mt-4" onClick={() => refreshSettings()}>
            إعادة المحاولة
          </Button>
        </div>
      </AppShell>
    );
  }

  return (
    <AppShell>
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <h1 className="text-2xl font-bold">الإعدادات</h1>
        </div>

        {/* Tab bar */}
        <div className="overflow-x-auto rounded-xl border border-sand-300 bg-surface">
          <div className="flex min-w-max">
            {TABS.map((t) => {
              const Icon = t.icon;
              const active = tab === t.key;
              return (
                <button
                  key={t.key}
                  type="button"
                  onClick={() => setTab(t.key)}
                  className={`flex items-center gap-2 px-4 sm:px-5 py-3 text-sm font-medium transition-colors border-l last:border-l-0 border-sand-200 ${
                    active ? 'bg-brand-600 text-white' : 'text-neutral-600 hover:bg-sand-100'
                  }`}
                >
                  <Icon size={16} />
                  <span className="hidden sm:inline">{t.label}</span>
                </button>
              );
            })}
          </div>
        </div>

        {tab === 'business' && (
          <Card title="معلومات النشاط" subtitle="البيانات الأساسية للمنشأة وبيانات التواصل">
            <div className="space-y-4 max-w-2xl">
              <div className="grid sm:grid-cols-2 gap-4">
                <Input
                  label="اسم النشاط"
                  value={businessForm.business_name}
                  onChange={(e) => setBusinessForm({ ...businessForm, business_name: e.target.value })}
                />
                <Input
                  label="رقم الهاتف"
                  value={businessForm.business_phone}
                  onChange={(e) => setBusinessForm({ ...businessForm, business_phone: e.target.value })}
                />
              </div>
              <div className="grid sm:grid-cols-2 gap-4">
                <Input
                  label="الاسم التجاري (اسم السجل التجاري)"
                  value={businessForm.trade_name}
                  onChange={(e) => setBusinessForm({ ...businessForm, trade_name: e.target.value })}
                  placeholder="يظهر في الفاتورة أسفل اسم النشاط"
                />
                <Input
                  label="رقم السجل التجاري"
                  value={businessForm.commercial_registration}
                  onChange={(e) => setBusinessForm({ ...businessForm, commercial_registration: e.target.value })}
                  placeholder="رقم السجل/الترخيص"
                />
              </div>
              <div className="grid sm:grid-cols-2 gap-4">
                <Input
                  label="العنوان"
                  value={businessForm.business_address}
                  onChange={(e) => setBusinessForm({ ...businessForm, business_address: e.target.value })}
                />
                <Input
                  label="البريد الإلكتروني"
                  type="email"
                  value={businessForm.business_email}
                  onChange={(e) => setBusinessForm({ ...businessForm, business_email: e.target.value })}
                  placeholder="info@example.com"
                />
              </div>
              <Input
                label="الرقم الضريبي"
                value={businessForm.tax_number}
                onChange={(e) => setBusinessForm({ ...businessForm, tax_number: e.target.value })}
              />
              <div className="grid sm:grid-cols-2 gap-4">
                <Input
                  label="برفكس أرقام الإيصالات"
                  value={businessForm.invoice_prefix}
                  onChange={(e) => setBusinessForm({ ...businessForm, invoice_prefix: e.target.value })}
                  placeholder="مثال: INV-"
                />
                <Select
                  label="نسبة الضريبة المضافة"
                  value={businessForm.tax_rate}
                  options={TAX_RATE_OPTIONS}
                  onChange={(e) => setBusinessForm({ ...businessForm, tax_rate: Number(e.target.value) })}
                />
              </div>
              <p className="text-xs text-neutral-400 -mt-2">
                الضريبة تُحسب على إجمالي الإيصال عند تفعيل «إظهار الضريبة في الطباعة». يُكتب البرفكس + رقم الإيصال أسفل اسم النشاط.
              </p>
              <div className="flex gap-3">
                <Button onClick={handleSaveBusiness} loading={savingBusiness}>حفظ</Button>
              </div>
            </div>
          </Card>
        )}

        {tab === 'currency' && (
          <Card title="العملة والتنسيق" subtitle="كيفية عرض المبالغ والتياردةيخ في النظام">
            <div className="space-y-4 max-w-2xl">
              <div className="grid sm:grid-cols-2 gap-4">
                <Input
                  label="رمز العملة"
                  value={currencyForm.currency_symbol}
                  onChange={(e) => setCurrencyForm({ ...currencyForm, currency_symbol: e.target.value })}
                />
                <Input
                  label="كود العملة"
                  value={currencyForm.currency_code}
                  onChange={(e) => setCurrencyForm({ ...currencyForm, currency_code: e.target.value })}
                />
              </div>
              <div className="grid sm:grid-cols-2 gap-4">
                <Select
                  label="عدد الخانات العشرية"
                  value={currencyForm.decimal_places}
                  options={DECIMAL_OPTIONS}
                  onChange={(e) => setCurrencyForm({ ...currencyForm, decimal_places: Number(e.target.value) })}
                />
                <Select
                  label="صيغة التاريخ"
                  value={currencyForm.date_format}
                  options={DATE_FORMAT_OPTIONS}
                  onChange={(e) => setCurrencyForm({ ...currencyForm, date_format: e.target.value })}
                />
              </div>
              <div className="grid sm:grid-cols-2 gap-4">
                <Select
                  label="موضع رمز العملة"
                  value={currencyForm.currency_position}
                  options={CURRENCY_POSITION_OPTIONS}
                  onChange={(e) => setCurrencyForm({ ...currencyForm, currency_position: e.target.value as 'after' | 'before' })}
                />
                <Select
                  label="ساعة بداية اليوم المحاسبي"
                  value={prefsForm.previous_day_cutoff_hour}
                  options={CUTOFF_HOUR_OPTIONS}
                  onChange={(e) => setPrefsForm({ ...prefsForm, previous_day_cutoff_hour: Number(e.target.value) })}
                />
              </div>
              <p className="text-xs text-neutral-400 -mt-2">
                البيع المسجل قبل «ساعة بداية اليوم المحاسبي» يُحتسب للتاريخ السابق — افتراضياً 2:00 صباحاً.
              </p>
              <div className="rounded-xl bg-sand-50 border border-sand-200 px-4 py-3 text-sm text-neutral-600">
                <p className="font-medium mb-1">معاينة:</p>
                <p className="tabular-nums">12,345.67 {currencyForm.currency_symbol} — تاريخ اليوم: {new Date().toISOString().slice(0, 10)}</p>
              </div>
              <div className="flex gap-3">
                <Button onClick={handleSaveCurrency} loading={savingCurrency}>حفظ</Button>
              </div>
            </div>
          </Card>
        )}

        {tab === 'prefs' && (
          <Card title="التفضيلات والمخزون" subtitle="الإعدادات الافتراضية وسياسة المخزون">
            <div className="space-y-4 max-w-2xl">
              <div className="grid sm:grid-cols-2 gap-4">
                <Select
                  label="الفترة الافتراضية (لوحة التحكم والمبيعات)"
                  value={prefsForm.default_period}
                  options={PERIOD_OPTIONS}
                  onChange={(e) => setPrefsForm({ ...prefsForm, default_period: e.target.value as 'today' | 'week' | 'month' })}
                />
                <Select
                  label="عدد الصفوف الافتراضي في الجداول"
                  value={prefsForm.default_page_size}
                  options={PAGE_SIZE_OPTIONS}
                  onChange={(e) => setPrefsForm({ ...prefsForm, default_page_size: Number(e.target.value) })}
                />
              </div>
              <Input
                label="حد تنبيه المخزون المنخفض (ياردات)"
                type="number"
                min="0"
                step="1"
                value={prefsForm.low_stock_threshold}
                onChange={(e) => setPrefsForm({ ...prefsForm, low_stock_threshold: Number(e.target.value) })}
              />
              <p className="text-xs text-neutral-400 -mt-2">تنبيه عند وصول رصيد القماش إلى هذا الحد أو أقل.</p>
              <div className="flex items-center justify-between py-2">
                <div>
                  <p className="text-sm font-medium text-neutral-700">تفعيل تنبيهات المخزون المنخفض</p>
                  <p className="text-xs text-neutral-500 mt-0.5">
                    إظهار الأقمشة التي وصل رصيدها إلى حد التنبيه في لوحة التحكم وجرس التنبيهات
                  </p>
                </div>
                <Switch
                  checked={prefsForm.low_stock_alert_enabled}
                  onChange={(v) => setPrefsForm({ ...prefsForm, low_stock_alert_enabled: v })}
                />
              </div>
              <div className="grid sm:grid-cols-2 gap-4">
                <Input
                  label="تنبيه مدة الوردية (ساعات)"
                  type="number"
                  min="1"
                  max="24"
                  step="1"
                  value={prefsForm.session_warn_hours}
                  onChange={(e) => setPrefsForm({ ...prefsForm, session_warn_hours: Number(e.target.value) })}
                />
                <Input
                  label="تحذير الوردية الطويلة (ساعات)"
                  type="number"
                  min="1"
                  max="72"
                  step="1"
                  value={prefsForm.session_danger_hours}
                  onChange={(e) => setPrefsForm({ ...prefsForm, session_danger_hours: Number(e.target.value) })}
                />
              </div>
              <p className="text-xs text-neutral-400 -mt-2">
                بعد أول عدد ساعات تظهر شارة تحذير على الوردية المفتوحة، وبعد الثاني تظهر شارة حمراء.
              </p>
              <div className="grid sm:grid-cols-2 gap-4">
                <Select
                  label="طريقة الدفع الافتراضية"
                  value={prefsForm.default_payment_method}
                  options={DEFAULT_PAYMENT_OPTIONS}
                  onChange={(e) => setPrefsForm({ ...prefsForm, default_payment_method: e.target.value as 'cash' | 'transfer' | 'card' })}
                />
                <Input
                  label="أقصى خصم مسموح (%)"
                  type="number"
                  min="0"
                  max="100"
                  step="1"
                  value={prefsForm.discount_max_percent}
                  onChange={(e) => setPrefsForm({ ...prefsForm, discount_max_percent: Number(e.target.value) })}
                />
              </div>
              <p className="text-xs text-neutral-400 -mt-2">
                الحد الأقصى لخصم البند كنسبة من إجماليه — 100 تعني بدون حد.
              </p>
              <div className="flex gap-3">
                <Button onClick={handleSavePrefs} loading={savingPrefs}>حفظ</Button>
              </div>
            </div>
          </Card>
        )}

        {tab === 'sections' && (
          <Card title="إظهار/إخفاء أقسام القائمة" subtitle="اختر الأقسام التي تظهر في القائمة الجانبية لجميع المستخدمين">
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2 max-w-4xl">
              {(sections.length ? sections : [
                { key: 'dashboard', label: 'الرئيسية', fixed: true },
                { key: 'branches', label: 'الفروع', fixed: false },
                { key: 'suppliers', label: 'الموردون', fixed: false },
                { key: 'customers', label: 'الزبائن', fixed: false },
                { key: 'partners', label: 'الشركاء', fixed: false },
                { key: 'fabrics', label: 'الأقمشة', fixed: false },
                { key: 'sales', label: 'المبيعات', fixed: false },
                { key: 'sessions', label: 'ورديات البيع', fixed: false },
                { key: 'employees', label: 'الموظفون', fixed: false },
                { key: 'warehouses', label: 'المخازن', fixed: false },
                { key: 'expenses', label: 'المصاريف', fixed: false },
                { key: 'reports', label: 'التقارير', fixed: false },
                { key: 'accounting', label: 'المحاسبة', fixed: false },
                { key: 'messages', label: 'التواصل', fixed: false },
                { key: 'themes', label: 'الثيمات والتحكم', fixed: false },
                { key: 'settings', label: 'الإعدادات', fixed: true },
              ] as AppSection[]).map((sec) => {
                const checked = sec.fixed || !hiddenSections.includes(sec.key);
                return (
                  <label
                    key={sec.key}
                    className={`flex items-center gap-3 p-3 rounded-xl border transition-colors ${
                      checked ? 'border-sand-300 bg-surface' : 'border-sand-200 bg-sand-50'
                    }`}
                  >
                    <input
                      type="checkbox"
                      checked={checked}
                      disabled={sec.fixed}
                      onChange={() => toggleSection(sec.key)}
                      className="w-4 h-4 accent-brand-600"
                    />
                    <span className={`text-sm font-medium ${sec.fixed ? 'text-neutral-400' : 'text-neutral-700'}`}>
                      {sec.label}
                    </span>
                    {sec.fixed && <Badge variant="neutral">دائمًا ظاهرة</Badge>}
                  </label>
                );
              })}
            </div>
            <div className="mt-4">
              <Button onClick={handleSaveSections} loading={savingSections}>حفظ</Button>
            </div>
          </Card>
        )}

        {tab === 'budgets' && (
          <Card
            title="الميزانيات الشهرية"
            subtitle="تحديد ميزانية كل فرع/تصنيف شهرياً ثم قياس نسبة الاستهلاك في تقارير المصاريف"
            action={
              <Button size="sm" onClick={() => { setEditBudget(null); setBudgetBranch(''); setBudgetCategory(''); setBudgetAmount(0); setBudgetMonth(new Date().toISOString().slice(0, 7)); setAddBudgetOpen(true); }}>
                <Plus size={16} />
                إضافة ميزانية
              </Button>
            }
          >
            {budgetsLoading ? (
              <div className="flex justify-center py-8"><Spinner size={28} /></div>
            ) : budgets.length === 0 ? (
              <EmptyState title="لا توجد ميزانيات" description="أضف ميزانية لكل فرع/تصنيف للمقارنة مع المصروف الفعلي" />
            ) : (
              <Table>
                <thead>
                  <tr>
                    <Th>الشهر</Th>
                    <Th>الفرع</Th>
                    <Th>التصنيف</Th>
                    <Th>قيمة الميزانية</Th>
                    <Th>إجراءات</Th>
                  </tr>
                </thead>
                <tbody>
                  {budgets.map((b) => (
                    <Tr key={b.id}>
                      <Td className="tabular-nums">{b.month.slice(0, 7)}</Td>
                      <Td className="font-medium">{b.branch_name}</Td>
                      <Td>{b.category_name}</Td>
                      <Td className="tabular-nums font-medium">{formatCurrency(b.amount)}</Td>
                      <Td>
                        <div className="flex items-center gap-2">
                          <button onClick={() => { setEditBudget(b); setBudgetBranch(String(b.branch)); setBudgetCategory(String(b.category)); setBudgetAmount(b.amount); setBudgetMonth(b.month.slice(0, 7)); setAddBudgetOpen(true); }} className="p-1.5 rounded-lg hover:bg-amber-50 text-amber-600 dark:hover:bg-amber-500/15 dark:text-amber-400 transition-colors">
                            <Pencil size={16} />
                          </button>
                          <button onClick={() => setDeletingBudget(b)} className="p-1.5 rounded-lg hover:bg-red-50 text-red-500 dark:hover:bg-red-500/15 dark:text-red-400 transition-colors">
                            <Trash2 size={16} />
                          </button>
                        </div>
                      </Td>
                    </Tr>
                  ))}
                </tbody>
              </Table>
            )}
          </Card>
        )}

        {tab === 'data' && (
          <Card title="إدارة البيانات" subtitle="النسخ الاحتياطي والاستعادة وإعادة الضبط">
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div className="p-4 bg-sand-50 rounded-xl flex flex-col items-start gap-3">
                <p className="text-sm font-medium text-neutral-700">تصدير نسخة احتياطية</p>
                <p className="text-xs text-neutral-500">تنزيل جميع بيانات النظام كملف JSON (الفرع، الموظفون، الزبائن، الأقمشة والمخزون، المبيعات، المصاريف، المحاسبة، الرسائل، الشعار والإعدادات).</p>
                <Button variant="secondary" onClick={handleBackup}>
                  <Download size={16} />
                  تصدير نسخة احتياطية
                </Button>
              </div>
              <div className="p-4 bg-sand-50 rounded-xl flex flex-col items-start gap-3">
                <p className="text-sm font-medium text-neutral-700">استيراد نسخة</p>
                <p className="text-xs text-neutral-500">استبدال البيانات الحالية من ملف نسخة احتياطية.</p>
                <Button variant="secondary" loading={restoring} onClick={() => fileInputRef.current?.click()}>
                  <Upload size={16} />
                  استيراد نسخة
                </Button>
                <input
                  ref={fileInputRef}
                  type="file"
                  accept=".json"
                  className="hidden"
                  onChange={handleRestoreFile}
                />
              </div>
              <div className="p-4 bg-sand-50 rounded-xl flex flex-col items-start gap-3">
                <p className="text-sm font-medium text-neutral-700">إعادة الضبط</p>
                <p className="text-xs text-neutral-500">حذف جميع معاملات (مبيعات ومصاريف) النظام.</p>
                <Button variant="danger" onClick={() => setResetOpen(true)}>
                  <RotateCcw size={16} />
                  إعادة الضبط
                </Button>
              </div>
            </div>

            <div className="mt-6 p-4 bg-sand-50 rounded-xl">
              <div className="flex items-center justify-between mb-1">
                <p className="text-sm font-medium text-neutral-700">كلمة مرور تشفير النسخة الاحتياطية</p>
                <Badge variant={settings?.has_backup_password ? 'success' : 'neutral'}>
                  {settings?.has_backup_password ? 'مُشفّرة' : 'بدون تشفير'}
                </Badge>
              </div>
              <p className="text-xs text-neutral-500 mb-3">
                عند ضبط كلمة مرور تُصدَّر النسخة الاحتياطية مشفّرة تلقائياً، وتُطلب الكلمة نفسها للاستعادة.
                اتركها فارغة لإلغاء التشفير.
              </p>
              <div className="flex flex-col sm:flex-row items-start sm:items-end gap-3">
                <div className="w-full sm:max-w-xs">
                  <Input
                    type="password"
                    placeholder={settings?.has_backup_password ? 'أدخل كلمة مرور جديدة' : 'كلمة المرور'}
                    value={backupPassword}
                    onChange={(e) => setBackupPassword(e.target.value)}
                  />
                </div>
                <Button onClick={handleSavePassword} loading={savingPassword}>
                  <Check size={16} />
                  حفظ كلمة المرور
                </Button>
              </div>
            </div>
          <div className="mt-6 p-4 bg-sand-50 rounded-xl">
              <div className="flex items-center justify-between mb-1">
                <p className="text-sm font-medium text-neutral-700">النسخ الاحتياطي التلقائي</p>
                <Switch checked={autoBackupEnabled} onChange={setAutoBackupEnabled} />
              </div>
              <p className="text-xs text-neutral-500 mb-3">
                عند التفعيل تُنشأ نسخة احتياطية تلقائياً في مجلد النسخ الاحتياطية. حدد موعداً يومياً (الوقت) أو
                نسخة دورية كل عدة ساعات (أو كليهما معاً). لتشغيلها تلقائياً أنشئ مهمة مجدولة على الخادم تشغّل
                <span className="font-mono text-[11px] bg-sand-100 px-1.5 py-0.5 rounded mx-1" dir="ltr">python manage.py auto_backup</span>
                بشكل متكرر.
              </p>
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                <div>
                  <label className="text-xs font-medium text-neutral-500 block mb-1">وقت يومي (اختياري)</label>
                  <input
                    type="time"
                    value={autoBackupTime}
                    onChange={(e) => setAutoBackupTime(e.target.value)}
                    className="w-full rounded-xl border border-sand-300 bg-surface px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500/40"
                  />
                </div>
                <div>
                  <label className="text-xs font-medium text-neutral-500 block mb-1">كل (ساعة)</label>
                  <input
                    type="number"
                    min="0"
                    max="720"
                    value={autoBackupEveryHours}
                    onChange={(e) => setAutoBackupEveryHours(Math.max(0, Number(e.target.value)))}
                    className="w-full rounded-xl border border-sand-300 bg-surface px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500/40"
                  />
                  <p className="text-[11px] text-neutral-400 mt-1">0 = إيقاف الفاصل الزمني</p>
                </div>
                <div className="flex items-end">
                  <Button variant="secondary" onClick={handleSaveAutoBackup} loading={autoBackupLoading}>
                    <Check size={16} />
                    حفظ الإعدادات
                  </Button>
                </div>
              </div>

              <div className="mt-4 flex flex-wrap items-center gap-3">
                <Button variant="secondary" onClick={handleRunAutoBackupNow} loading={runningNow}>
                  <Download size={16} />
                  إنشاء نسخة الآن
                </Button>
                {autoBackupInfo?.last_auto_backup_path && (
                  <span className="text-xs text-neutral-500">
                    آخر نسخة تلقائية:{' '}
                    <span className="font-mono" dir="ltr">{autoBackupInfo.last_auto_backup_path}</span>
                    {' '}({autoBackupInfo.last_auto_backup_at ? new Date(autoBackupInfo.last_auto_backup_at).toLocaleString('ar') : '—'})
                  </span>
                )}
              </div>

              {autoBackupInfo?.files?.length ? (
                <div className="mt-4 overflow-x-auto">
                  <Table>
                    <thead>
                      <tr>
                        <Th>الملف</Th>
                        <Th>الحجم</Th>
                        <Th>التاريخ</Th>
                        <Th>تنزيل</Th>
                      </tr>
                    </thead>
                    <tbody>
                      {autoBackupInfo.files.slice(0, 10).map((f) => (
                        <Tr key={f.name}>
                          <Td>
                            <span className="font-mono text-xs" dir="ltr">{f.name}</span>
                          </Td>
                          <Td>{(f.size / 1024).toFixed(1)} KB</Td>
                          <Td>{new Date(f.modified).toLocaleString('ar')}</Td>
                          <Td className="text-left">
                            <a
                              href={autoBackupDownloadUrl(f.name)}
                              download={f.name}
                              className="inline-flex items-center gap-1 text-brand-600 hover:text-brand-700 text-sm font-medium"
                            >
                              <Download size={14} />
                              تحميل
                            </a>
                          </Td>
                        </Tr>
                      ))}
                    </tbody>
                  </Table>
                </div>
              ) : (
                <p className="text-xs text-neutral-400 mt-3">لا توجد نسخ تلقائية بعد.</p>
              )}
            </div>
          </Card>
        )}

        {tab === 'system' && (
          <Card title="بيانات النظام">
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
              <div className="p-4 bg-sand-50 rounded-xl">
                <p className="text-xs text-neutral-400 mb-1">النسخة</p>
                <p className="font-semibold text-neutral-800">1.0.0</p>
              </div>
              <div className="p-4 bg-sand-50 rounded-xl">
                <p className="text-xs text-neutral-400 mb-1">الاسم التجاري</p>
                <p className="font-semibold text-neutral-800">{settings?.trade_name || '—'}</p>
              </div>
              <div className="p-4 bg-sand-50 rounded-xl">
                <p className="text-xs text-neutral-400 mb-1">رقم السجل التجاري</p>
                <p className="font-semibold text-neutral-800">{settings?.commercial_registration || '—'}</p>
              </div>
              <div className="p-4 bg-sand-50 rounded-xl">
                <p className="text-xs text-neutral-400 mb-1">وحدة العملة</p>
                <p className="font-semibold text-neutral-800">
                  {settings?.currency_symbol || 'ر.ع'} ({settings?.currency_code || 'OMR'})
                </p>
              </div>
              <div className="p-4 bg-sand-50 rounded-xl">
                <p className="text-xs text-neutral-400 mb-1">رابط API</p>
                <p className="font-mono text-xs text-neutral-600 break-all" dir="ltr">{API_URL}</p>
              </div>
              <div className="p-4 bg-sand-50 rounded-xl">
                <p className="text-xs text-neutral-400 mb-1">صيغة التاريخ</p>
                <p className="font-semibold text-neutral-800">{settings?.date_format || 'YYYY-MM-DD'}</p>
              </div>
              <div className="p-4 bg-sand-50 rounded-xl">
                <p className="text-xs text-neutral-400 mb-1">المظهر الافتراضي</p>
                <p className="font-semibold text-neutral-800">{settings?.default_theme || 'green'}</p>
              </div>
              <div className="p-4 bg-sand-50 rounded-xl">
                <p className="text-xs text-neutral-400 mb-1">حد تنبيه المخزون</p>
                <p className="font-semibold text-neutral-800">{Number(settings?.low_stock_threshold ?? 50)} ياردة</p>
              </div>
              <div className="p-4 bg-sand-50 rounded-xl">
                <p className="text-xs text-neutral-400 mb-1">نسبة الضريبة</p>
                <p className="font-semibold text-neutral-800">{Number(settings?.tax_rate ?? 0)}%</p>
              </div>
              <div className="p-4 bg-sand-50 rounded-xl">
                <p className="text-xs text-neutral-400 mb-1">برفكس الإيصالات</p>
                <p className="font-semibold text-neutral-800">{settings?.invoice_prefix || '—'}</p>
              </div>
              <div className="p-4 bg-sand-50 rounded-xl">
                <p className="text-xs text-neutral-400 mb-1">بداية اليوم المحاسبي</p>
                <p className="font-semibold text-neutral-800">{settings?.previous_day_cutoff_hour ?? 2}:00</p>
              </div>
              <div className="p-4 bg-sand-50 rounded-xl">
                <p className="text-xs text-neutral-400 mb-1">أقصى خصم للبند</p>
                <p className="font-semibold text-neutral-800">{Number(settings?.discount_max_percent ?? 100)}%</p>
              </div>
              <div className="p-4 bg-sand-50 rounded-xl">
                <p className="text-xs text-neutral-400 mb-1">طريقة الدفع الافتراضية</p>
                <p className="font-semibold text-neutral-800">{settings?.default_payment_method === 'card' ? 'ماكينة' : settings?.default_payment_method === 'transfer' ? 'تحويل' : 'كاش'}</p>
              </div>
            </div>
          </Card>
        )}

        <ConfirmDialog
          open={resetOpen}
          onClose={() => setResetOpen(false)}
          onConfirm={handleReset}
          loading={resetting}
          title="تأكيد إعادة الضبط"
          confirmLabel="إعادة الضبط"
          message="سيتم حذف جميع المبيعات والمصاريف نهائيًا. لا يمكن التراجع عن هذا الإجراء. هل أنت متأكد من المتابعة؟"
        />

        <Modal open={addBudgetOpen} onClose={() => setAddBudgetOpen(false)} title={editBudget ? 'تعديل الميزانية' : 'إضافة ميزانية جديدة'} maxWidth="max-w-lg">
          <div className="space-y-4">
            <Select
              label="الفرع"
              value={budgetBranch}
              onChange={(e) => setBudgetBranch(e.target.value)}
              options={[{ value: '', label: 'اختر الفرع' }, ...budgetBranches.map((b) => ({ value: String(b.id), label: b.name }))]}
            />
            <Select
              label="التصنيف"
              value={budgetCategory}
              onChange={(e) => setBudgetCategory(e.target.value)}
              options={[{ value: '', label: 'اختر التصنيف' }, ...categories.map((c) => ({ value: String(c.id), label: c.name }))]}
            />
            <div className="flex flex-col gap-1">
              <label className="text-xs font-medium text-neutral-500">الشهر</label>
              <input
                type="month"
                value={budgetMonth}
                onChange={(e) => setBudgetMonth(e.target.value)}
                className="rounded-xl border border-sand-300 bg-surface px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500/40"
              />
            </div>
            <Input
              label="قيمة الميزانية"
              type="number"
              min="0"
              step="1"
              value={budgetAmount}
              onChange={(e) => setBudgetAmount(Number(e.target.value))}
            />
            <div className="flex justify-start gap-3 pt-2">
              <Button onClick={handleSaveBudget} loading={budgetSaving}>{editBudget ? 'تحديث' : 'إضافة'}</Button>
              <Button variant="secondary" onClick={() => setAddBudgetOpen(false)}>إلغاء</Button>
            </div>
          </div>
        </Modal>

        <ConfirmDialog
          open={!!deletingBudget}
          onClose={() => setDeletingBudget(null)}
          onConfirm={handleDeleteBudget}
          loading={deleteBudgetLoading}
          message={`هل أنت متأكد من حذف ميزانية "${deletingBudget?.category_name} — ${deletingBudget?.branch_name}" (${deletingBudget?.month?.slice(0, 7)})؟`}
        />
      </div>
    </AppShell>
  );
}
