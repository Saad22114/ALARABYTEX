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
import { Plus, Trash2, Download, Upload, RotateCcw, Check, Sun, Moon } from 'lucide-react';
import { ExpenseCategory } from '@/types';
import { listExpenseCategories, createExpenseCategory, deleteExpenseCategory } from '@/services/expenses';
import { backupUrl, restoreSettings, resetData } from '@/services/settings';
import { API_URL } from '@/services/api';
import { useToast } from '@/components/ui/Toast';
import { useSettings } from '@/components/providers/SettingsProvider';
import { useTheme } from '@/components/providers/ThemeProvider';
import { THEME_PRESETS } from '@/lib/themes';

const SECTION_OPTIONS = [
  { key: 'dashboard', label: 'الرئيسية', fixed: true },
  { key: 'branches', label: 'الفروع', fixed: false },
  { key: 'suppliers', label: 'الموردون', fixed: false },
  { key: 'partners', label: 'الشركاء', fixed: false },
  { key: 'fabrics', label: 'الأقمشة', fixed: false },
  { key: 'sales', label: 'المبيعات', fixed: false },
  { key: 'warehouses', label: 'المخازن', fixed: false },
  { key: 'expenses', label: 'المصاريف', fixed: false },
  { key: 'reports', label: 'التقارير', fixed: false },
  { key: 'settings', label: 'الإعدادات', fixed: true },
];

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

export default function SettingsPage() {
  const { toast } = useToast();
  const { settings, loading, error, updateSettings, refreshSettings } = useSettings();
  const { theme, setTheme, dark, toggleDark } = useTheme();

  const [savingBusiness, setSavingBusiness] = useState(false);
  const [savingCurrency, setSavingCurrency] = useState(false);
  const [savingPrefs, setSavingPrefs] = useState(false);
  const [savingSections, setSavingSections] = useState(false);

  const [businessForm, setBusinessForm] = useState({
    business_name: '',
    business_phone: '',
    business_address: '',
    tax_number: '',
  });
  const [currencyForm, setCurrencyForm] = useState({
    currency_symbol: 'ر.ع',
    currency_code: 'OMR',
    decimal_places: 2,
  });
  const [prefsForm, setPrefsForm] = useState<{ default_period: 'today' | 'week' | 'month'; default_page_size: number; allow_negative_stock: boolean }>({
    default_period: 'today',
    default_page_size: 10,
    allow_negative_stock: false,
  });
  const [hiddenSections, setHiddenSections] = useState<string[]>([]);

  useEffect(() => {
    if (settings) {
      setBusinessForm({
        business_name: settings.business_name || '',
        business_phone: settings.business_phone || '',
        business_address: settings.business_address || '',
        tax_number: settings.tax_number || '',
      });
      setCurrencyForm({
        currency_symbol: settings.currency_symbol || 'ر.ع',
        currency_code: settings.currency_code || 'OMR',
        decimal_places: settings.decimal_places ?? 2,
      });
      setPrefsForm({
        default_period: settings.default_period || 'today',
        default_page_size: settings.default_page_size ?? 10,
        allow_negative_stock: settings.allow_negative_stock,
      });
      setHiddenSections(settings.hidden_sections || []);
    }
  }, [settings]);

  const [restoring, setRestoring] = useState(false);
  const [resetting, setResetting] = useState(false);
  const [resetOpen, setResetOpen] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [categories, setCategories] = useState<ExpenseCategory[]>([]);
  const [categoriesLoading, setCategoriesLoading] = useState(true);
  const [addOpen, setAddOpen] = useState(false);
  const [catName, setCatName] = useState('');
  const [catCode, setCatCode] = useState('');
  const [catLoading, setCatLoading] = useState(false);
  const [deletingCat, setDeletingCat] = useState<ExpenseCategory | null>(null);
  const [deleteLoading, setDeleteLoading] = useState(false);

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
      });
      toast('success', 'تم حفظ إعدادات العملة بنجاح');
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

  const handleThemeSelect = (id: string) => {
    setTheme(id);
    toast('success', 'تم تغيير المظهر بنجاح');
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
      const parsed = JSON.parse(text);
      await restoreSettings(parsed);
      toast('success', 'تم استيراد النسخة الاحتياطية بنجاح');
      refreshSettings();
    } catch (err: any) {
      toast('error', err.message || 'فشل استيراد النسخة الاحتياطية');
    } finally {
      setRestoring(false);
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

  const handleAdd = async () => {
    if (!catName.trim()) {
      toast('error', 'اسم التصنيف مطلوب');
      return;
    }
    setCatLoading(true);
    try {
      await createExpenseCategory({ name: catName, code: catCode });
      toast('success', 'تمت إضافة التصنيف بنجاح');
      setCatName('');
      setCatCode('');
      setAddOpen(false);
      fetchCategories();
    } catch (err: any) {
      toast('error', err.message);
    } finally {
      setCatLoading(false);
    }
  };

  const handleDelete = async () => {
    if (!deletingCat) return;
    setDeleteLoading(true);
    try {
      await deleteExpenseCategory(deletingCat.id);
      toast('success', 'تم حذف التصنيف بنجاح');
      setDeletingCat(null);
      fetchCategories();
    } catch (err: any) {
      toast('error', err.message);
    } finally {
      setDeleteLoading(false);
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
        {/* Appearance (1) + Business Info (2) */}
        <div className="grid md:grid-cols-2 gap-6">
          <Card title="المظهر" subtitle="اختر لون النظام">
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
              {THEME_PRESETS.map((preset) => {
                const active = theme === preset.id;
                return (
                  <button
                    key={preset.id}
                    onClick={() => handleThemeSelect(preset.id)}
                    className={`relative flex flex-col items-start gap-2 p-3 rounded-xl border transition-all duration-150 ${
                      active
                        ? 'border-brand-600 ring-2 ring-brand-200 bg-brand-50'
                        : 'border-sand-200 hover:border-sand-300 bg-surface'
                    }`}
                  >
                    <span
                      className="w-8 h-8 rounded-full"
                      style={{ backgroundColor: preset.swatch }}
                    />
                    <span className="text-sm font-medium text-neutral-700">{preset.name}</span>
                    {active && (
                      <span className="absolute top-2 left-2 w-5 h-5 rounded-full bg-brand-600 text-white flex items-center justify-center">
                        <Check size={12} />
                      </span>
                    )}
                  </button>
                );
              })}
            </div>
            <p className="text-xs text-neutral-400 mt-3">يُحفظ المظهر على مستوى المتصفح (localStorage).</p>
            <div className="mt-4 pt-4 border-t border-sand-100">
              <p className="text-sm font-medium text-neutral-700 mb-2">الوضع الليلي</p>
              <div className="flex gap-2">
                <button
                  type="button"
                  onClick={() => dark && toggleDark()}
                  className={`flex items-center justify-center flex-1 gap-2 py-2.5 px-4 rounded-xl border text-sm font-medium transition-all duration-150 ${
                    !dark
                      ? 'border-brand-600 ring-2 ring-brand-200 bg-brand-50 text-brand-700 dark:bg-brand-500/15 dark:text-brand-300 dark:ring-brand-500/30'
                      : 'border-sand-200 bg-surface text-neutral-600'
                  }`}
                >
                  <Sun size={16} />
                  نهاري
                </button>
                <button
                  type="button"
                  onClick={() => !dark && toggleDark()}
                  className={`flex items-center justify-center flex-1 gap-2 py-2.5 px-4 rounded-xl border text-sm font-medium transition-all duration-150 ${
                    dark
                      ? 'border-brand-600 ring-2 ring-brand-200 bg-brand-50 text-brand-700 dark:bg-brand-500/15 dark:text-brand-300 dark:ring-brand-500/30'
                      : 'border-sand-200 bg-surface text-neutral-600'
                  }`}
                >
                  <Moon size={16} />
                  ليلي
                </button>
              </div>
            </div>
          </Card>

          <Card title="معلومات النشاط" subtitle="البيانات الأساسية للمنشأة">
            <div className="space-y-4">
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
              <Input
                label="العنوان"
                value={businessForm.business_address}
                onChange={(e) => setBusinessForm({ ...businessForm, business_address: e.target.value })}
              />
              <Input
                label="الرقم الضريبي"
                value={businessForm.tax_number}
                onChange={(e) => setBusinessForm({ ...businessForm, tax_number: e.target.value })}
              />
              <div className="flex justify-start">
                <Button onClick={handleSaveBusiness} loading={savingBusiness}>حفظ</Button>
              </div>
            </div>
          </Card>
        </div>

        {/* Currency (3) + Preferences (4) + Sections (5) */}
        <div className="grid md:grid-cols-2 gap-6">
          <Card title="العملة والتنسيق" subtitle="كيفية عرض المبالغ في النظام">
            <div className="space-y-4">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
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
              <Select
                label="عدد الخانات العشرية"
                value={currencyForm.decimal_places}
                options={DECIMAL_OPTIONS}
                onChange={(e) => setCurrencyForm({ ...currencyForm, decimal_places: Number(e.target.value) })}
              />
              <div className="flex justify-start">
                <Button onClick={handleSaveCurrency} loading={savingCurrency}>حفظ</Button>
              </div>
            </div>
          </Card>

          <Card title="التفضيلات" subtitle="الإعدادات الافتراضية للنظام">
            <div className="space-y-4">
              <Select
                label="الفترة الافتراضية للوحة التحكم"
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
              <div className="flex items-center justify-between py-2">
                <div>
                  <p className="text-sm font-medium text-neutral-700">السماح بالرصيد السالب</p>
                  <p className="text-xs text-neutral-500 mt-0.5">
                    السماح بتسجيل مبيعات تتجاوز المخزون المتاح وخصمه حتى لو أصبح الرصيد سالباً
                  </p>
                </div>
                <Switch
                  checked={prefsForm.allow_negative_stock}
                  onChange={(v) => setPrefsForm({ ...prefsForm, allow_negative_stock: v })}
                />
              </div>
              <div className="flex justify-start">
                <Button onClick={handleSavePrefs} loading={savingPrefs}>حفظ</Button>
              </div>
            </div>
          </Card>

          <Card title="إظهار/إخفاء الأقسام" subtitle="اختر الأقسام التي تظهر في القائمة الجانبية" className="md:col-span-2">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
              {SECTION_OPTIONS.map((sec) => {
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
            <div className="flex justify-start mt-4">
              <Button onClick={handleSaveSections} loading={savingSections}>حفظ</Button>
            </div>
          </Card>
        </div>

        {/* Data Management (6) */}
        <Card title="إدارة البيانات" subtitle="النسخ الاحتياطي والاستعادة وإعادة الضبط">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="p-4 bg-sand-50 rounded-xl flex flex-col items-start gap-3">
              <p className="text-sm font-medium text-neutral-700">تصدير نسخة احتياطية</p>
              <p className="text-xs text-neutral-500">تنزيل جميع بيانات النظام كملف JSON.</p>
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
        </Card>

        {/* Expense Categories (7) */}
        <Card
          title="تصنيفات المصاريف"
          action={
            <Button size="sm" onClick={() => setAddOpen(true)}>
              <Plus size={16} />
              إضافة تصنيف
            </Button>
          }
        >
          {categoriesLoading ? (
            <div className="flex justify-center py-8"><Spinner size={28} /></div>
          ) : categories.length === 0 ? (
            <EmptyState title="لا توجد تصنيفات" />
          ) : (
            <Table>
              <thead>
                <tr>
                  <Th>الاسم</Th>
                  <Th>الكود</Th>
                  <Th>النوع</Th>
                  <Th>عدد المصاريف</Th>
                  <Th>إجراءات</Th>
                </tr>
              </thead>
              <tbody>
                {categories.map((c) => (
                  <Tr key={c.id}>
                    <Td className="font-medium">{c.name}</Td>
                    <Td><span className="font-mono text-xs bg-sand-100 px-2 py-1 rounded">{c.code || '-'}</span></Td>
                    <Td>
                      <Badge variant={c.is_system ? 'neutral' : 'success'}>
                        {c.is_system ? 'نظامي' : 'مخصص'}
                      </Badge>
                    </Td>
                    <Td className="tabular-nums">{c.expense_count}</Td>
                    <Td>
                      {!c.is_system && (
                        <button onClick={() => setDeletingCat(c)} className="p-1.5 rounded-lg hover:bg-red-50 text-red-500 dark:hover:bg-red-500/15 dark:text-red-400 transition-colors">
                          <Trash2 size={16} />
                        </button>
                      )}
                    </Td>
                  </Tr>
                ))}
              </tbody>
            </Table>
          )}
        </Card>

        {/* System Info (8) */}
        <Card title="بيانات النظام">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            <div className="p-4 bg-sand-50 rounded-xl">
              <p className="text-xs text-neutral-400 mb-1">النسخة</p>
              <p className="font-semibold text-neutral-800">1.0.0</p>
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
          </div>
        </Card>

        {/* Add Category Modal */}
        <Modal open={addOpen} onClose={() => setAddOpen(false)} title="إضافة تصنيف جديد">
          <div className="space-y-4">
            <Input
              label="اسم التصنيف"
              value={catName}
              onChange={(e) => setCatName(e.target.value)}
              placeholder="اسم التصنيف"
            />
            <Input
              label="الكود (اختياري)"
              value={catCode}
              onChange={(e) => setCatCode(e.target.value)}
              placeholder="مثال: CAT-001"
            />
            <div className="flex justify-start gap-3 pt-2">
              <Button onClick={handleAdd} loading={catLoading}>إضافة</Button>
              <Button variant="secondary" onClick={() => setAddOpen(false)}>إلغاء</Button>
            </div>
          </div>
        </Modal>

        <ConfirmDialog
          open={!!deletingCat}
          onClose={() => setDeletingCat(null)}
          onConfirm={handleDelete}
          loading={deleteLoading}
          message={`هل أنت متأكد من حذف تصنيف "${deletingCat?.name}"؟`}
        />

        <ConfirmDialog
          open={resetOpen}
          onClose={() => setResetOpen(false)}
          onConfirm={handleReset}
          loading={resetting}
          title="تأكيد إعادة الضبط"
          confirmLabel="إعادة الضبط"
          message="سيتم حذف جميع المبيعات والمصاريف نهائيًا. لا يمكن التراجع عن هذا الإجراء. هل أنت متأكد من المتابعة؟"
        />
      </div>
    </AppShell>
  );
}