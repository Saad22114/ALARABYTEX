'use client';

import { useState, useEffect } from 'react';
import AppShell from '@/components/layout/AppShell';
import Card from '@/components/ui/Card';
import Button from '@/components/ui/Button';
import Table, { Th, Td, Tr } from '@/components/ui/Table';
import Modal from '@/components/ui/Modal';
import Input from '@/components/ui/Input';
import Textarea from '@/components/ui/Textarea';
import Badge from '@/components/ui/Badge';
import Spinner from '@/components/ui/Spinner';
import EmptyState from '@/components/ui/EmptyState';
import ConfirmDialog from '@/components/ui/ConfirmDialog';
import Switch from '@/components/ui/Switch';
import {
  Plus, Trash2, Check, Sun, Moon, Palette, Printer, Tags, ImagePlus,
} from 'lucide-react';
import { ExpenseCategory, ThemesControl } from '@/types';
import { listExpenseCategories, createExpenseCategory, deleteExpenseCategory } from '@/services/expenses';
import { getThemesControl, updateThemesControl, logoUrl, uploadLogo, removeLogo } from '@/services/settings';
import { useToast } from '@/components/ui/Toast';
import { useTheme } from '@/components/providers/ThemeProvider';
import { useFonts } from '@/components/providers/FontProvider';
import { FONT_PRESETS, FONT_SCALE_OPTIONS, THEME_PRESETS } from '@/lib/themes';

const DEFAULT_THEME_OPTIONS = THEME_PRESETS.map((p) => ({ value: p.id, label: p.swatch }));

const TABS = [
  { key: 'appearance', label: 'المظهر', icon: Palette },
  { key: 'print', label: 'الطباعة', icon: Printer },
  { key: 'categories', label: 'تصنيفات المصاريف', icon: Tags },
];

export default function ThemesPage() {
  const { toast } = useToast();
  const { theme, setTheme, dark, toggleDark } = useTheme();
  const { font, setFont, fontScale, setFontScale } = useFonts();

  const [tab, setTab] = useState('appearance');

  const [control, setControl] = useState<ThemesControl | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [printForm, setPrintForm] = useState({ receipt_footer: '', invoice_notes: '', receipt_show_tax: false, receipt_show_phone: true });
  const [savingPrint, setSavingPrint] = useState(false);

  const [categories, setCategories] = useState<ExpenseCategory[]>([]);
  const [categoriesLoading, setCategoriesLoading] = useState(true);
  const [addOpen, setAddOpen] = useState(false);
  const [catName, setCatName] = useState('');
  const [catCode, setCatCode] = useState('');
  const [catLoading, setCatLoading] = useState(false);
  const [deletingCat, setDeletingCat] = useState<ExpenseCategory | null>(null);
  const [deleteLoading, setDeleteLoading] = useState(false);
  const [logoUploading, setLogoUploading] = useState(false);

  useEffect(() => {
    let cancelled = false;
    getThemesControl()
      .then((res) => {
        if (cancelled) return;
        setControl(res);
        setPrintForm({
          receipt_footer: res.receipt_footer || '',
          invoice_notes: res.invoice_notes || '',
          receipt_show_tax: res.receipt_show_tax,
          receipt_show_phone: res.receipt_show_phone,
        });
      })
      .catch((err) => {
        if (!cancelled) setError(err?.message || 'حدث خطأ أثناء تحميل القسم');
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => { cancelled = true; };
  }, []);

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

  const handleThemeSelect = (id: string) => {
    setTheme(id);
    updateThemesControl({ default_theme: id }).catch((err) => toast('error', err.message));
    toast('success', 'تم تغيير المظهر بنجاح');
  };

  const handleFontSelect = (id: string) => {
    setFont(id);
    updateThemesControl({ font_family: id }).catch((err) => toast('error', err.message));
    toast('success', 'تم تغيير نوع الخط بنجاح');
  };

  const handleScaleSelect = (scale: number) => {
    setFontScale(scale);
    toast('success', 'تم ضبط حجم الخط');
  };

  const handleLogoChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    if (file.size > 2 * 1024 * 1024) {
      toast('error', 'حجم الصورة يجب ألا يتجاوز 2 ميجابايت');
      return;
    }
    setLogoUploading(true);
    try {
      await uploadLogo(file);
      const fresh = await getThemesControl();
      setControl(fresh);
      toast('success', 'تم حفظ الشعار بنجاح');
    } catch (err: any) {
      toast('error', err.message);
    } finally {
      setLogoUploading(false);
      e.target.value = '';
    }
  };

  const handleLogoDelete = async () => {
    setLogoUploading(true);
    try {
      await removeLogo();
      const fresh = await getThemesControl();
      setControl(fresh);
      toast('success', 'تم حذف الشعار بنجاح');
    } catch (err: any) {
      toast('error', err.message);
    } finally {
      setLogoUploading(false);
    }
  };

  const handleSavePrint = async () => {
    setSavingPrint(true);
    try {
      await updateThemesControl({
        receipt_footer: printForm.receipt_footer,
        invoice_notes: printForm.invoice_notes,
        receipt_show_tax: printForm.receipt_show_tax,
        receipt_show_phone: printForm.receipt_show_phone,
      });
      toast('success', 'تم حفظ إعدادات الطباعة بنجاح');
    } catch (err: any) {
      toast('error', err.message);
    } finally {
      setSavingPrint(false);
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

  if (loading && !control) {
    return (
      <AppShell>
        <div className="flex items-center justify-center py-20">
          <Spinner size={40} />
        </div>
      </AppShell>
    );
  }

  if (error && !control) {
    return (
      <AppShell>
        <div className="text-center py-20 text-neutral-400">
          <p>{error}</p>
        </div>
      </AppShell>
    );
  }

  return (
    <AppShell>
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <h1 className="text-2xl font-bold">الثيمات والتحكم</h1>
        </div>

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

        {tab === 'appearance' && (
          <>
            <Card title="شعار الموقع" subtitle="صورة تُعرض في الشريط الجانبي وفوق إيصالات الطباعة وفي صفحة تسجيل الدخول">
              <div className="flex items-start gap-6">
                <div className="w-28 h-28 rounded-2xl border-2 border-sand-200 bg-surface flex items-center justify-center overflow-hidden">
                  {logoUrl(control?.logo) ? (
                    <img src={logoUrl(control?.logo)} alt="شعار الموقع" className="w-full h-full object-contain p-2" />
                  ) : (
                    <ImagePlus size={32} className="text-neutral-300" />
                  )}
                </div>
                <div className="space-y-2 max-w-md">
                  <p className="text-sm text-neutral-600 leading-relaxed">
                    ارفع صورة شعارك وسيتم حفظها تلقائياً وتظهر في كل النظام (صيغ مدعومة: PNG، JPG، WEBP، SVG).
                  </p>
                  <div className="flex flex-wrap items-center gap-2">
                    <input
                      id="logo-upload"
                      type="file"
                      accept="image/png,image/jpeg,image/webp,image/svg+xml,image/gif"
                      className="hidden"
                      onChange={handleLogoChange}
                    />
                    <Button variant="primary" onClick={() => document.getElementById('logo-upload')?.click()} disabled={logoUploading}>
                      {logoUploading ? 'جارٍ الحفظ...' : 'رفع شعار'}
                    </Button>
                    {control?.logo && (
                      <Button variant="danger" onClick={handleLogoDelete} disabled={logoUploading}>
                        حذف الشعار
                      </Button>
                    )}
                  </div>
                </div>
              </div>
            </Card>

            <Card title="المظهر" subtitle="اختر لون النظام — يُحفظ كإعداد عام وللمتصفح">
              <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 max-w-3xl">
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
                      <span className="w-8 h-8 rounded-full" style={{ backgroundColor: preset.swatch }} />
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
              <p className="text-xs text-neutral-400 mt-3">اختيارك يُحفظ الآن في إعدادات النظام (لجميع الأجهزة) وفي المتصفح الحالي.</p>
            </Card>

            <Card title="نوع الخط" subtitle="اختر خط النظام — يُحفظ كإعداد عام وللمتصفح">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 max-w-3xl">
                {FONT_PRESETS.map((preset) => {
                  const active = font === preset.id;
                  return (
                    <button
                      key={preset.id}
                      onClick={() => handleFontSelect(preset.id)}
                      className={`relative flex flex-col items-start gap-2 p-4 rounded-xl border transition-all duration-150 ${
                        active
                          ? 'border-brand-600 ring-2 ring-brand-200 bg-brand-50'
                          : 'border-sand-200 hover:border-sand-300 bg-surface'
                      }`}
                    >
                      <span className="text-base font-semibold text-neutral-800" style={{ fontFamily: `var(--font-${preset.id})` }}>
                        {preset.name}
                      </span>
                      <span className="text-sm text-neutral-500" style={{ fontFamily: `var(--font-${preset.id})` }}>
                        نص تجريبي للخط — آية الشركة والحسابات 123
                      </span>
                      {active && (
                        <span className="absolute top-2 left-2 w-5 h-5 rounded-full bg-brand-600 text-white flex items-center justify-center">
                          <Check size={12} />
                        </span>
                      )}
                    </button>
                  );
                })}
              </div>
            </Card>

            <Card title="حجم الخط" subtitle="تكبير أو تصغير الخط لجهازك أنت فقط — لا يؤثر على بقية المستخدمين">
              <div className="flex gap-2 max-w-md">
                {FONT_SCALE_OPTIONS.map((opt) => {
                  const active = fontScale === opt.value;
                  return (
                    <button
                      key={opt.value}
                      type="button"
                      onClick={() => handleScaleSelect(opt.value)}
                      className={`flex items-center justify-center flex-1 py-2.5 px-3 rounded-xl border text-sm font-medium transition-all duration-150 ${
                        active
                          ? 'border-brand-600 ring-2 ring-brand-200 bg-brand-50 text-brand-700'
                          : 'border-sand-200 bg-surface text-neutral-600'
                      }`}
                    >
                      {opt.label}
                    </button>
                  );
                })}
              </div>
              <p className="text-xs text-neutral-400 mt-3">تُحفظ على متصفحك فقط — كل مستخدم يرى حجمه الخاص.</p>
            </Card>

            <Card title="الوضع الليلي" subtitle="المظهر الفاتح أو الداكن">
              <div className="flex gap-2 max-w-md">
                <button
                  type="button"
                  onClick={() => dark && toggleDark()}
                  className={`flex items-center justify-center flex-1 gap-2 py-2.5 px-4 rounded-xl border text-sm font-medium transition-all duration-150 ${
                    !dark
                      ? 'border-brand-600 ring-2 ring-brand-200 bg-brand-50 text-brand-700'
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
                      ? 'border-brand-600 ring-2 ring-brand-200 bg-brand-50 text-brand-700'
                      : 'border-sand-200 bg-surface text-neutral-600'
                  }`}
                >
                  <Moon size={16} />
                  ليلي
                </button>
              </div>
              <p className="text-xs text-neutral-400 mt-3">الوضع الليلي يُحفظ على المتصفح الحالي فقط.</p>
            </Card>

            <Card title="المظهر الافتراضي عند فتح النظام" subtitle="يُطبق على الأجهزة الجديدة التي لم تختار مظهراً بعد">
              <div className="grid grid-cols-2 sm:grid-cols-5 gap-2 max-w-xl">
                {DEFAULT_THEME_OPTIONS.map((opt) => {
                  const active = (control?.default_theme || 'green') === opt.value;
                  return (
                    <button
                      key={opt.value}
                      type="button"
                      onClick={() => updateThemesControl({ default_theme: opt.value }).then(() => toast('success', 'تم حفظ المظهر الافتراضي')).catch((e) => toast('error', e.message))}
                      className={`flex flex-col items-center gap-2 p-3 rounded-xl border transition-all duration-150 ${
                        active ? 'border-brand-600 ring-2 ring-brand-200' : 'border-sand-200 hover:border-sand-300'
                      }`}
                    >
                      <span className="w-8 h-8 rounded-full" style={{ backgroundColor: opt.label }} />
                      <span className="text-xs font-medium text-neutral-600">{opt.value}</span>
                      {active && <Check size={12} className="text-brand-600" />}
                    </button>
                  );
                })}
              </div>
            </Card>
          </>
        )}

        {tab === 'print' && (
          <Card title="إعدادات الطباعة" subtitle="النصوص والمعلومات التي تظهر على الفواتير المطبوعة">
            <div className="space-y-4 max-w-2xl">
              <Textarea
                label="تذييل الفواتير"
                value={printForm.receipt_footer}
                onChange={(e) => setPrintForm({ ...printForm, receipt_footer: e.target.value })}
                placeholder="مثال: شكراً لتعاملكم معنا — البضاعة المباعة لا تُرد بعد الاستلام"
                rows={3}
              />
              <p className="text-xs text-neutral-400">
                سوف يظهر هذا النص أسفل الفواتير المطبوعة (تسليم/نقل/مبيعات).
              </p>
              <Textarea
                label="ملاحظات الفاتورة"
                value={printForm.invoice_notes}
                onChange={(e) => setPrintForm({ ...printForm, invoice_notes: e.target.value })}
                placeholder="مثال: تُسلم البضاعة المرفقة حسب المواصفات المتفق عليها"
                rows={3}
              />
              <p className="text-xs text-neutral-400 -mt-2">
                نص اختياري يظهر أعلى خانتي التوقيع في الفاتورة لتصبح فاتورة رسمية.
              </p>
              <div className="flex items-center justify-between py-2">
                <div>
                  <p className="text-sm font-medium text-neutral-700">إظهار الضريبة في الإيصال المطبوع</p>
                  <p className="text-xs text-neutral-500 mt-0.5">
                    يُضاف سطر ضريبة ({control?.tax_rate ?? 0}%) إلى إجمالي الإيصال المطبوع (بدون تغيير المبيعات المحاسبية)
                  </p>
                </div>
                <Switch
                  checked={printForm.receipt_show_tax}
                  onChange={(v) => setPrintForm({ ...printForm, receipt_show_tax: v })}
                />
              </div>
              <div className="flex items-center justify-between py-2">
                <div>
                  <p className="text-sm font-medium text-neutral-700">إظهار رقم الهاتف في الإيصال المطبوع</p>
                  <p className="text-xs text-neutral-500 mt-0.5">
                    عرض رقم هاتف النشاط مع بيانات التواصل في الطباعة
                  </p>
                </div>
                <Switch
                  checked={printForm.receipt_show_phone}
                  onChange={(v) => setPrintForm({ ...printForm, receipt_show_phone: v })}
                />
              </div>
              <div className="flex gap-3">
                <Button onClick={handleSavePrint} loading={savingPrint}>حفظ</Button>
              </div>
            </div>
          </Card>
        )}

        {tab === 'categories' && (
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
        )}

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
      </div>
    </AppShell>
  );
}