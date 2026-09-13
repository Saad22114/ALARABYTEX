'use client';

import { useState, useEffect, useMemo } from 'react';
import Input from '@/components/ui/Input';
import Select from '@/components/ui/Select';
import Textarea from '@/components/ui/Textarea';
import Button from '@/components/ui/Button';
import { listSuppliers } from '@/services/suppliers';
import { Fabric, FabricUnit, Supplier } from '@/types';

const UNIT_OPTIONS = [
  { value: 'yard', label: 'ياردة' },
  { value: 'meter', label: 'متر' },
  { value: 'roll', label: 'لفة' },
];

const FABRIC_TYPE_OPTIONS = [
  { value: 'منسوج', label: 'منسوج' },
  { value: 'قطن', label: 'قطن' },
  { value: 'صوف', label: 'صوف' },
  { value: 'حرير', label: 'حرير' },
  { value: 'بوليستر', label: 'بوليستر' },
  { value: 'مخمل', label: 'مخمل' },
  { value: 'ساتان', label: 'ساتان' },
  { value: 'جينز', label: 'جينز' },
  { value: 'أخرى', label: 'أخرى' },
];

interface FabricFormProps {
  initial?: Partial<Fabric>;
  onSubmit: (data: Partial<Fabric>) => Promise<void>;
  onCancel: () => void;
}

export default function FabricForm({ initial, onSubmit, onCancel }: FabricFormProps) {
  const [form, setForm] = useState({
    name: '',
    code: '',
    barcode: '',
    unit: 'yard' as FabricUnit,
    fabric_type: '',
    color: '',
    composition: '',
    width_cm: '',
    weight_gsm: '',
    origin: '',
    manufacturer: '',
    supplier: '',
    purchase_price: '',
    sale_price_yard: '',
    sale_price_roll: '',
    min_sale_yard: '',
    min_sale_roll: '',
    min_stock: '',
    yards_per_roll: '',
    description: '',
    is_active: true,
  });
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(false);
  const [suppliers, setSuppliers] = useState<Supplier[]>([]);

  useEffect(() => {
    if (initial) {
      setForm({
        name: initial.name || '',
        code: initial.code || '',
        barcode: initial.barcode || '',
        unit: initial.unit || 'yard',
        fabric_type: initial.fabric_type || '',
        color: initial.color || '',
        composition: initial.composition || '',
        width_cm: initial.width_cm != null ? String(initial.width_cm) : '',
        weight_gsm: initial.weight_gsm != null ? String(initial.weight_gsm) : '',
        origin: initial.origin || '',
        manufacturer: initial.manufacturer || '',
        supplier: initial.supplier != null ? String(initial.supplier) : '',
        purchase_price: initial.purchase_price !== undefined ? String(initial.purchase_price) : '',
        sale_price_yard: initial.sale_price_yard !== undefined ? String(initial.sale_price_yard) : '',
        sale_price_roll: initial.sale_price_roll != null ? String(initial.sale_price_roll) : '',
        min_sale_yard: initial.min_sale_yard !== undefined ? String(initial.min_sale_yard) : '',
        min_sale_roll: initial.min_sale_roll != null ? String(initial.min_sale_roll) : '',
        min_stock: initial.min_stock != null ? String(initial.min_stock) : '',
        yards_per_roll: initial.yards_per_roll != null ? String(initial.yards_per_roll) : '',
        description: initial.description || '',
        is_active: !!initial.is_active,
      });
    }
  }, [initial]);

  useEffect(() => {
    listSuppliers({ page_size: 100 })
      .then((res) => setSuppliers(res.results))
      .catch(() => setSuppliers([]));
  }, []);

  const num = (v: string) => (v === '' ? null : Number(v));

  const autoSaleRoll = useMemo(() => {
    if (num(form.sale_price_roll) != null) return null;
    const yard = num(form.sale_price_yard);
    const ypr = num(form.yards_per_roll);
    if (yard == null || ypr == null || ypr <= 0) return null;
    return Number((yard * ypr).toFixed(3));
  }, [form.sale_price_yard, form.sale_price_roll, form.yards_per_roll]);

  const autoMinRoll = useMemo(() => {
    if (num(form.min_sale_roll) != null) return null;
    const minYard = num(form.min_sale_yard);
    const ypr = num(form.yards_per_roll);
    if (minYard == null || ypr == null || ypr <= 0) return null;
    return Number((minYard * ypr).toFixed(3));
  }, [form.min_sale_yard, form.min_sale_roll, form.yards_per_roll]);

  const cost = num(form.purchase_price) ?? 0;
  const sale = num(form.sale_price_yard) ?? 0;
  const profit = sale > 0 ? sale - cost : null;
  const margin = sale > 0 ? ((sale - cost) / sale) * 100 : null;

  const validate = () => {
    const e: Record<string, string> = {};
    if (!form.name.trim()) e.name = 'اسم القماش مطلوب';
    if (!form.code.trim()) e.code = 'الكود مطلوب';
    const sYard = num(form.sale_price_yard);
    const mYard = num(form.min_sale_yard);
    if (mYard != null && sYard != null && mYard > sYard)
      e.min_sale_yard = 'الحد الأدنى لا يمكن أن يتجاوز سعر البيع';
    const sRoll = num(form.sale_price_roll) ?? autoSaleRoll;
    const mRoll = num(form.min_sale_roll) ?? autoMinRoll;
    if (mRoll != null && sRoll != null && mRoll > sRoll)
      e.min_sale_roll = 'الحد الأدنى لا يمكن أن يتجاوز سعر البيع';
    setErrors(e);
    return Object.keys(e).length === 0;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!validate()) return;
    const payload: Partial<Fabric> = {
      name: form.name.trim(),
      code: form.code.trim(),
      barcode: form.barcode.trim(),
      unit: form.unit,
      fabric_type: form.fabric_type.trim(),
      color: form.color.trim(),
      composition: form.composition.trim(),
      width_cm: num(form.width_cm),
      weight_gsm: num(form.weight_gsm),
      origin: form.origin.trim(),
      manufacturer: form.manufacturer.trim(),
      supplier: form.supplier ? Number(form.supplier) : null,
      purchase_price: num(form.purchase_price) ?? 0,
      sale_price_yard: num(form.sale_price_yard) ?? 0,
      sale_price_roll: num(form.sale_price_roll),
      min_sale_yard: num(form.min_sale_yard) ?? 0,
      min_sale_roll: num(form.min_sale_roll),
      min_stock: num(form.min_stock) ?? 0,
      yards_per_roll: num(form.yards_per_roll),
      description: form.description.trim(),
      is_active: form.is_active,
    };
    setLoading(true);
    try {
      await onSubmit(payload);
    } finally {
      setLoading(false);
    }
  };

  const set = (key: string, val: string | boolean) => setForm((f) => ({ ...f, [key]: val }));

  const sectionTitle = (title: string) => (
    <h3 className="text-sm font-bold text-brand-700 border-b border-sand-200 pb-2">{title}</h3>
  );

  return (
    <form onSubmit={handleSubmit} className="space-y-6">
      {sectionTitle('البيانات الأساسية')}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <Input label="اسم القماش" value={form.name} onChange={(e) => set('name', e.target.value)} error={errors.name} placeholder="اسم القماش" />
        <Input label="الكود" value={form.code} onChange={(e) => set('code', e.target.value)} error={errors.code} placeholder="مثال: FAB-001" />
        <Input label="الباركود" value={form.barcode} onChange={(e) => set('barcode', e.target.value)} placeholder="6281..." />
        <Select label="الوحدة" value={form.unit} onChange={(e) => set('unit', e.target.value as FabricUnit)} options={UNIT_OPTIONS} />
        <Select label="نوع القماش" value={form.fabric_type} onChange={(e) => set('fabric_type', e.target.value)} options={FABRIC_TYPE_OPTIONS} placeholder="اختر النوع..." />
        <Input label="بلد المنشأ" value={form.origin} onChange={(e) => set('origin', e.target.value)} placeholder="مثال: الصين" />
      </div>

      {sectionTitle('المواصفات الفنية')}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <Input label="اللون" value={form.color} onChange={(e) => set('color', e.target.value)} placeholder="مثال: أزرق" />
        <Input label="التركيبة" value={form.composition} onChange={(e) => set('composition', e.target.value)} placeholder="مثال: قطن 100%" />
        <Input label="العرض (سم)" type="number" step="0.1" min="0" value={form.width_cm} onChange={(e) => set('width_cm', e.target.value)} placeholder="مثال: 150" />
        <Input label="الوزن (جم/م²)" type="number" step="1" min="0" value={form.weight_gsm} onChange={(e) => set('weight_gsm', e.target.value)} placeholder="مثال: 240" />
        <Input label="الشركة المصنعة" value={form.manufacturer} onChange={(e) => set('manufacturer', e.target.value)} placeholder="اسم الشركة المصنعة" />
        <Select label="المورد الأساسي" value={form.supplier} onChange={(e) => set('supplier', e.target.value)} options={suppliers.map((s) => ({ value: s.id, label: s.name }))} placeholder="اختر المورد..." />
      </div>

      {sectionTitle('التسعير والهوامش')}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <Input label="تكلفة الشراء (للياردة)" type="number" step="0.001" min="0" value={form.purchase_price} onChange={(e) => set('purchase_price', e.target.value)} placeholder="0.000" />
        <Input label="سعر بيع الياردة" type="number" step="0.001" min="0" value={form.sale_price_yard} onChange={(e) => set('sale_price_yard', e.target.value)} placeholder="0.000" />
        <Input label="الحد الأدنى لسعر بيع الياردة" type="number" step="0.001" min="0" value={form.min_sale_yard} onChange={(e) => set('min_sale_yard', e.target.value)} error={errors.min_sale_yard} placeholder="0.000" />
        <Input label="سعر بيع اللفة" type="number" step="0.001" min="0" value={form.sale_price_roll} onChange={(e) => set('sale_price_roll', e.target.value)} placeholder="اتركه فارغاً للحساب التلقائي" />
        <Input label="الحد الأدنى لسعر بيع اللفة" type="number" step="0.001" min="0" value={form.min_sale_roll} onChange={(e) => set('min_sale_roll', e.target.value)} error={errors.min_sale_roll} placeholder="اتركه فارغاً للحساب التلقائي" />
        <Input label="ياردات اللفة الواحدة" type="number" step="0.001" min="0" value={form.yards_per_roll} onChange={(e) => set('yards_per_roll', e.target.value)} placeholder="مثال: 25" />
      </div>

      {(autoSaleRoll != null || autoMinRoll != null || profit != null) && (
        <div className="rounded-xl bg-sand-50 border border-sand-200 divide-y divide-sand-200">
          {autoSaleRoll != null && (
            <div className="px-4 py-2.5 flex items-center justify-between text-sm">
              <span className="text-neutral-600">سعر بيع اللفة (تلقائي)</span>
              <span className="font-bold text-brand-700">{autoSaleRoll.toFixed(3)}</span>
            </div>
          )}
          {autoMinRoll != null && (
            <div className="px-4 py-2.5 flex items-center justify-between text-sm">
              <span className="text-neutral-600">الحد الأدنى لسعر اللفة (تلقائي)</span>
              <span className="font-bold text-brand-700">{autoMinRoll.toFixed(3)}</span>
            </div>
          )}
          {profit != null && (
            <div className="px-4 py-2.5 flex items-center justify-between text-sm">
              <span className="text-neutral-600">الربح المتوقع باليارد (بيع − شراء)</span>
              <span className={`font-bold ${profit >= 0 ? 'text-emerald-600' : 'text-red-500'}`}>
                {profit.toFixed(3)}
              </span>
            </div>
          )}
          {margin != null && (
            <div className="px-4 py-2.5 flex items-center justify-between text-sm">
              <span className="text-neutral-600">هامش الربح</span>
              <span className={`font-bold ${margin >= 0 ? 'text-emerald-600' : 'text-red-500'}`}>
                {margin.toFixed(1)}%
              </span>
            </div>
          )}
        </div>
      )}

      {sectionTitle('المخزون والتنبيهات')}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <Input label="الحد الأدنى للمخزون" type="number" step="0.01" min="0" value={form.min_stock} onChange={(e) => set('min_stock', e.target.value)} placeholder="مثال: 100" />
      </div>
      <p className="text-xs text-neutral-400 -mt-2">
        عند تسجيل الأصناف تُحسب الياردات من اللفات والعكس تلقائياً لضمان الاتساق، ويُحظر البيع بأقل من الحد الأدنى المحدد.
      </p>
      <Textarea label="الوصف" value={form.description} onChange={(e) => set('description', e.target.value)} placeholder="وصف القماش..." rows={3} />
      <label className="flex items-center gap-3 cursor-pointer">
        <input type="checkbox" checked={form.is_active} onChange={(e) => set('is_active', e.target.checked)} className="w-4 h-4 accent-brand-600" />
        <span className="text-sm font-medium text-neutral-700">نشط</span>
      </label>
      <div className="flex justify-start gap-3 pt-2">
        <Button type="submit" loading={loading}>
          {initial?.id ? 'تحديث' : 'إضافة'}
        </Button>
        <Button type="button" variant="secondary" onClick={onCancel}>
          إلغاء
        </Button>
      </div>
    </form>
  );
}