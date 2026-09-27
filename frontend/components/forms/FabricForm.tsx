'use client';

import { useState, useEffect } from 'react';
import Input from '@/components/ui/Input';
import Select from '@/components/ui/Select';
import Textarea from '@/components/ui/Textarea';
import Button from '@/components/ui/Button';
import { listSuppliers } from '@/services/suppliers';
import { listBranches, listBranchPrices, upsertBranchPrices, deleteBranchPrice, BranchPriceUpsertItem } from '@/services/branches';
import { listFabrics } from '@/services/fabrics';
import { Branch, Fabric, FabricUnit, Supplier } from '@/types';
import { useSettings } from '@/components/providers/SettingsProvider';

const UNIT_OPTIONS = [
  { value: 'yard', label: 'ياردة' },
  { value: 'roll', label: 'طاقة' },
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

/** عدد الياردات في القطعة الواحدة — يحوّل سعر القطعة إلى سعر بيع الياردة. */
const PIECE_YARDS = 3.5;

interface FabricFormProps {
  initial?: Partial<Fabric>;
  onSubmit: (data: Partial<Fabric>) => Promise<Fabric>;
  onCancel: () => void;
}

/** أسعار بيع قماش في فرع معيّن — كل حقول التسعير والهوامش لكل فرع على حدة. */
interface BranchPriceForm {
  id?: number;
  sale_price_yard: string;
  min_sale_yard: string;
  sale_price_roll: string;
  min_sale_roll: string;
  piece_price: string;
}

const emptyBranchPrice = (): BranchPriceForm => ({
  sale_price_yard: '',
  min_sale_yard: '',
  sale_price_roll: '',
  min_sale_roll: '',
  piece_price: '',
});

export default function FabricForm({ initial, onSubmit, onCancel }: FabricFormProps) {
  const { settings } = useSettings();
  const minSalePercent = settings?.min_sale_percent != null ? Number(settings.min_sale_percent) : 15;
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
    min_stock: '',
    yards_per_roll: '',
    description: '',
    is_active: true,
    allow_roll_sale: true,
  });
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(false);
  const [suppliers, setSuppliers] = useState<Supplier[]>([]);
  const [branches, setBranches] = useState<Branch[]>([]);
  const [rollOverrides, setRollOverrides] = useState<Record<string, string>>({});
  const [branchPricing, setBranchPricing] = useState<Record<string, BranchPriceForm>>({});
  /** الفروع التي عُدِّل حدّها الأدنى يدوياً — تتوقف التعبئة التلقائية لها وحدها. */
  const [manualMinBranches, setManualMinBranches] = useState<Set<number>>(new Set());

  const markMinManual = (branchId: number) =>
    setManualMinBranches((prev) => {
      if (prev.has(branchId)) return prev;
      const next = new Set(prev);
      next.add(branchId);
      return next;
    });
  const [fabrics, setFabrics] = useState<Fabric[]>([]);
  const [importSource, setImportSource] = useState('');
  const [importedName, setImportedName] = useState('');

  useEffect(() => {
    let cancelled = false;
    listFabrics({ page_size: 300 })
      .then((res) => { if (!cancelled) setFabrics(res.results); })
      .catch(() => {});
    return () => { cancelled = true; };
  }, []);

  const fillFromFabric = (f: Fabric, copyIdentity: boolean) => {
    const identity = copyIdentity
      ? { name: f.name || '', code: f.code || '', barcode: f.barcode || '' }
      : { barcode: f.barcode || '' };
    setForm((prev) => ({
      ...prev,
      ...identity,
      unit: f.unit || 'yard',
      fabric_type: f.fabric_type || '',
      color: f.color || '',
      composition: f.composition || '',
      width_cm: f.width_cm != null ? String(f.width_cm) : '',
      weight_gsm: f.weight_gsm != null ? String(f.weight_gsm) : '',
      origin: f.origin || '',
      manufacturer: f.manufacturer || '',
      supplier: f.supplier != null ? String(f.supplier) : '',
      purchase_price: f.purchase_price != null ? String(f.purchase_price) : '',
      min_stock: f.min_stock != null ? String(f.min_stock) : '',
      yards_per_roll: f.yards_per_roll != null ? String(f.yards_per_roll) : '',
      description: f.description || '',
      is_active: f.is_active !== false,
      allow_roll_sale: f.allow_roll_sale !== false,
    }));
    const overrides: Record<string, string> = {};
    for (const [k, v] of Object.entries(f.roll_sale_overrides || {})) {
      overrides[k] = v ? 'true' : 'false';
    }
    setRollOverrides(overrides);
  };

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
        min_stock: initial.min_stock != null ? String(initial.min_stock) : '',
        yards_per_roll: initial.yards_per_roll != null ? String(initial.yards_per_roll) : '',
        description: initial.description || '',
        is_active: !!initial.is_active,
        allow_roll_sale: initial.allow_roll_sale !== false,
      });
      const overrides: Record<string, string> = {};
      for (const [k, v] of Object.entries(initial.roll_sale_overrides || {})) {
        overrides[k] = v ? 'true' : 'false';
      }
      setRollOverrides(overrides);
    }
  }, [initial]);

  useEffect(() => {
    let cancelled = false;
    listBranches({ page_size: 100 })
      .then((res) => { if (!cancelled) setBranches(res.results); })
      .catch(() => setBranches([]));
    return () => { cancelled = true; };
  }, []);

  useEffect(() => {
    let cancelled = false;
    listSuppliers({ page_size: 100 })
      .then((res) => setSuppliers(res.results))
      .catch(() => setSuppliers([]));
    return () => { cancelled = true; };
  }, []);

  useEffect(() => {
    if (!initial?.id) { setBranchPricing({}); setManualMinBranches(new Set()); return; }
    let cancelled = false;
    setManualMinBranches(new Set());
    listBranchPrices({ fabric: initial.id, page_size: 100 })
      .then((res) => {
        if (cancelled) return;
        const map: Record<string, BranchPriceForm> = {};
        for (const p of res.results) {
          map[String(p.branch)] = {
            id: p.id,
            sale_price_yard: p.sale_price_yard ? String(p.sale_price_yard) : '',
            min_sale_yard: p.min_sale_yard ? String(p.min_sale_yard) : '',
            sale_price_roll: p.sale_price_roll != null ? String(p.sale_price_roll) : '',
            min_sale_roll: p.min_sale_roll != null ? String(p.min_sale_roll) : '',
            piece_price: p.piece_price != null ? String(p.piece_price) : '',
          };
        }
        setBranchPricing(map);
      })
      .catch(() => {});
    return () => { cancelled = true; };
  }, [initial?.id]);

  const num = (v: string) => (v === '' ? null : Number(v));

  const validate = () => {
    const e: Record<string, string> = {};
    if (!form.name.trim()) e.name = 'اسم القماش مطلوب';
    if (!form.code.trim()) e.code = 'الكود مطلوب';

    const name = form.name.trim().toLowerCase();
    const code = form.code.trim().toLowerCase();
    const barcode = form.barcode.trim();
    const duplicate = fabrics.find((f) => {
      if (f.id === initial?.id) return false;
      const sameName = name && f.name.trim().toLowerCase() === name;
      const sameCode = code && f.code.trim().toLowerCase() === code;
      const sameBarcode = barcode && f.barcode.trim() === barcode;
      return sameName || sameCode || sameBarcode;
    });
    if (duplicate) {
      const fields: string[] = [];
      if (name && duplicate.name.trim().toLowerCase() === name) fields.push('الاسم');
      if (code && duplicate.code.trim().toLowerCase() === code) fields.push('الكود');
      if (barcode && duplicate.barcode.trim() === barcode) fields.push('الباركود');
      e.duplicate = `يوجد قماش «${duplicate.name}» بنفس ${fields.join(' و')} — نفس القماش موجود بالفعل ولا يمكن الحفظ. غيّر ${fields.join(' و')} ثم أعد المحاولة.`;
    }
    // تحقق من أسعار الفروع المنفصلة (كل فرع له تسعيره الكامل)
    for (const branch of branches) {
      const bf = branchPricing[String(branch.id)];
      if (!bf) continue;
      const by = bf.sale_price_yard.trim() === '' ? null : Number(bf.sale_price_yard);
      const my = bf.min_sale_yard.trim() === '' ? null : Number(bf.min_sale_yard);
      const br = bf.sale_price_roll.trim() === '' ? null : Number(bf.sale_price_roll);
      const mr = bf.min_sale_roll.trim() === '' ? null : Number(bf.min_sale_roll);
      const pc = bf.piece_price.trim() === '' ? null : Number(bf.piece_price);
      const ypr = num(form.yards_per_roll);
      const autoRoll = br == null && by != null && ypr != null && ypr > 0 ? Number((by * ypr).toFixed(3)) : null;
      const autoMinRoll = mr == null && my != null && ypr != null && ypr > 0 ? Number((my * ypr).toFixed(3)) : null;
      if (by != null && by < 0) e[`bp_${branch.id}_yard`] = 'لا يمكن أن تكون سالبة';
      if (my != null && my < 0) e[`bp_${branch.id}_miny`] = 'لا يمكن أن تكون سالبة';
      if (br != null && br < 0) e[`bp_${branch.id}_roll`] = 'لا يمكن أن تكون سالبة';
      if (mr != null && mr < 0) e[`bp_${branch.id}_minr`] = 'لا يمكن أن تكون سالبة';
      if (pc != null && pc < 0) e[`bp_${branch.id}_piece`] = 'لا يمكن أن تكون سالبة';
      if (my != null && by != null && my > by)
        e[`bp_${branch.id}_miny`] = 'الحد الأدنى لا يمكن أن يتجاوز سعر البيع';
      const sRollEff = br ?? autoRoll;
      const mRollEff = mr ?? autoMinRoll;
      if (mRollEff != null && sRollEff != null && mRollEff > sRollEff)
        e[`bp_${branch.id}_minr`] = 'الحد الأدنى لا يمكن أن يتجاوز سعر البيع';
    }
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
      min_stock: num(form.min_stock) ?? 0,
      yards_per_roll: num(form.yards_per_roll),
      description: form.description.trim(),
      is_active: form.is_active,
      allow_roll_sale: form.allow_roll_sale,
    };
    const overrides: Record<string, boolean> = {};
    for (const branch of branches) {
      const val = rollOverrides[String(branch.id)];
      if (val === 'true') overrides[String(branch.id)] = true;
      else if (val === 'false') overrides[String(branch.id)] = false;
    }
    payload.roll_sale_overrides = overrides;
    setLoading(true);
    try {
      const saved = await onSubmit(payload);
      await saveBranchPrices(saved);
    } finally {
      setLoading(false);
    }
  };

  /** حفظ/تحديث/حذف أسعار الفروع للقماش المحفوظ (سعر البيع/الحد الأدنى/سعر القطعة لكل فرع منفصلاً). */
  const saveBranchPrices = async (saved: Fabric) => {
    const toUpsert: BranchPriceUpsertItem[] = [];
    const toDelete: number[] = [];
    for (const branch of branches) {
      const bf = branchPricing[String(branch.id)];
      if (!bf) continue;
      const hasAny =
        bf.sale_price_yard.trim() !== '' ||
        bf.min_sale_yard.trim() !== '' ||
        bf.sale_price_roll.trim() !== '' ||
        bf.min_sale_roll.trim() !== '' ||
        bf.piece_price.trim() !== '';
      if (!hasAny) {
        if (bf.id) toDelete.push(bf.id);
        continue;
      }
      toUpsert.push({
        branch: branch.id,
        sale_price_yard: bf.sale_price_yard.trim() === '' ? 0 : Number(bf.sale_price_yard),
        min_sale_yard: bf.min_sale_yard.trim() === '' ? 0 : Number(bf.min_sale_yard),
        sale_price_roll: bf.sale_price_roll.trim() === '' ? null : Number(bf.sale_price_roll),
        min_sale_roll: bf.min_sale_roll.trim() === '' ? null : Number(bf.min_sale_roll),
        piece_price: bf.piece_price.trim() === '' ? null : Number(bf.piece_price),
      });
    }
    if (toUpsert.length > 0) {
      await upsertBranchPrices(saved.id, toUpsert);
    }
    for (const id of toDelete) {
      await deleteBranchPrice(id);
    }
  };

  const set = (key: string, val: string | boolean) => setForm((f) => ({ ...f, [key]: val }));

  /** الحد الأدنى التلقائي للفرع = نسبة الإعدادات (افتراضياً 15%) من سعر بيع الياردة. */
  const branchMinForYard = (yardValue: string): string => {
    const yard = Number(yardValue);
    if (!Number.isFinite(yard) || yard <= 0 || minSalePercent <= 0) return '';
    return String(Number((yard * (minSalePercent / 100)).toFixed(3)));
  };

  /** كتابة سعر بيع الياردة لفرع يحدّث الحد الأدنى تلقائياً بنسبة الإعدادات — إلا إذا عُدِّل يدوياً لهذا الفرع. */
  const setBranchYard = (branchId: number, value: string) => {
    setBranchPricing((prev) => {
      const key = String(branchId);
      const cur = prev[key] || emptyBranchPrice();
      const next = { ...cur, sale_price_yard: value };
      if (!manualMinBranches.has(branchId)) {
        next.min_sale_yard = branchMinForYard(value);
      }
      return { ...prev, [key]: next };
    });
  };

  /** كتابة سعر القطعة لفرع يملأ سعر بيع الياردة لهذا الفرع تلقائياً (قطعة ÷ 3.5) ويحدّث الحد الأدنى — ويبقيان قابلين للتعديل بعده. */
  const setBranchPiecePrice = (branchId: number, value: string) => {
    setBranchPricing((prev) => {
      const key = String(branchId);
      const cur = prev[key] || emptyBranchPrice();
      const next = { ...cur, piece_price: value };
      const piece = value === '' ? null : Number(value);
      if (piece != null && Number.isFinite(piece) && piece > 0) {
        const yardStr = String(Number((piece / PIECE_YARDS).toFixed(3)));
        next.sale_price_yard = yardStr;
        if (!manualMinBranches.has(branchId)) {
          next.min_sale_yard = branchMinForYard(yardStr);
        }
      }
      return { ...prev, [key]: next };
    });
  };

  const sectionTitle = (title: string) => (
    <h3 className="text-sm font-bold text-brand-700 border-b border-sand-200 pb-2">{title}</h3>
  );

  return (
    <form onSubmit={handleSubmit} className="space-y-6">
      {errors.duplicate && (
        <div className="rounded-xl bg-red-50 border border-red-300 text-red-700 px-4 py-3 text-sm font-medium" role="alert">
          {errors.duplicate}
        </div>
      )}
      {sectionTitle('استيراد سريع')}
      <Select
        label="انسخ بيانات قماش موجود"
        value={importSource}
        onChange={(e) => {
          const id = e.target.value;
          setImportSource(id);
          const f = fabrics.find((x) => String(x.id) === id);
          if (f) {
            fillFromFabric(f, !initial?.id);
            setImportedName(f.name);
          }
        }}
        options={[{ value: '', label: 'اختر قماشاً لنسخ بياناته...' }, ...fabrics.filter((f) => f.id !== initial?.id).map((f) => ({ value: String(f.id), label: `${f.name}${f.code ? ` (${f.code})` : ''}` }))]}
        placeholder="اختر قماشاً لنسخ بياناته..."
      />
      {importedName && (
        <p className="text-xs text-emerald-600">
          {initial?.id
            ? `تم استيراد بيانات «${importedName}» — تُستبدل بيانات المواصفات والتسعير مع بقاء الاسم والكود الحاليين.`
            : `تم استيراد جميع بيانات «${importedName}» — غيّر الاسم والكود ليتناسبا مع القماش المطلوب ثم أكمل الحفظ.`}
        </p>
      )}

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
        <Input label="تكلفة الشراء (للياردة) — موحّدة لكل الفروع" type="number" step="0.001" min="0" value={form.purchase_price} onChange={(e) => set('purchase_price', e.target.value)} placeholder="" />
        <Input label="ياردات الطاقة الواحدة" type="number" step="0.001" min="0" value={form.yards_per_roll} onChange={(e) => set('yards_per_roll', e.target.value)} placeholder="مثال: 25" />
      </div>
      <p className="text-xs text-neutral-400 -mt-2">
        سعر الشراء وتقسيم الطاقة موحّدان لكل الفروع. أما أسعار البيع والحدود الدنيا والهوامش فيتم تحديدها لكل فرع أدناه —
        كل فرع يبيع بسعره الخاص مع كل مميزات التسعير (سعر القطعة، سعر الياردة، الطاقة، الحدود، الحسابات التلقائية والربح).
      </p>

      {sectionTitle('التسعير والهوامش لكل فرع')}
      {branches.length === 0 && (
        <div className="rounded-xl bg-sand-50 border border-sand-200 px-4 py-3 text-sm text-neutral-500">
          لا توجد فروع مسجلة — أضف فرعاً أولاً من صفحة الفروع ثم عُد لتحديد سعر كل فرع.
        </div>
      )}
      {branches.map((branch) => {
        const bf = branchPricing[String(branch.id)] || emptyBranchPrice();
        const setBf = (patch: Partial<BranchPriceForm>) =>
          setBranchPricing((prev) => ({
            ...prev,
            [String(branch.id)]: { ...(prev[String(branch.id)] || emptyBranchPrice()), ...patch },
          }));
        const by = bf.sale_price_yard.trim() === '' ? null : Number(bf.sale_price_yard);
        const my = bf.min_sale_yard.trim() === '' ? null : Number(bf.min_sale_yard);
        const br = bf.sale_price_roll.trim() === '' ? null : Number(bf.sale_price_roll);
        const mr = bf.min_sale_roll.trim() === '' ? null : Number(bf.min_sale_roll);
        const ypr = num(form.yards_per_roll);
        const autoRoll = br == null && by != null && ypr != null && ypr > 0 ? Number((by * ypr).toFixed(3)) : null;
        const autoMinRoll = mr == null && my != null && ypr != null && ypr > 0 ? Number((my * ypr).toFixed(3)) : null;
        const bCost = num(form.purchase_price) ?? 0;
        const profitY = by != null && by > 0 ? by - bCost : null;
        const margin = by != null && by > 0 ? ((by - bCost) / by) * 100 : null;
        const effRoll = br ?? autoRoll;
        const profitR = effRoll != null && ypr != null && ypr > 0 ? effRoll - bCost * ypr : null;
        return (
          <div key={branch.id} className="rounded-xl bg-sand-50 border border-sand-200 p-4 space-y-4">
            <div className="flex items-center justify-between">
              <h4 className="text-sm font-bold text-neutral-800">{branch.name}</h4>
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div className="space-y-1.5">
                <Input label="سعر القطعة" type="number" step="0.001" min="0" value={bf.piece_price} onChange={(e) => setBranchPiecePrice(branch.id, e.target.value)} error={errors[`bp_${branch.id}_piece`]} placeholder="مثال: 70" />
                <p className="text-xs text-neutral-400">يُقسَم تلقائياً على 3.5 ليملأ سعر بيع الياردة بهذا الفرع — ويمكن تعديله بعده.</p>
              </div>
              <Input label="سعر بيع الياردة" type="number" step="0.001" min="0" value={bf.sale_price_yard} onChange={(e) => setBranchYard(branch.id, e.target.value)} error={errors[`bp_${branch.id}_yard`]} placeholder="" />
              <div className="space-y-1.5">
                <Input label="الحد الأدنى لسعر بيع الياردة" type="number" step="0.001" min="0" value={bf.min_sale_yard} onChange={(e) => { setBf({ min_sale_yard: e.target.value }); markMinManual(branch.id); }} error={errors[`bp_${branch.id}_miny`]} placeholder="" />
                <p className="text-xs text-neutral-400">يُحدَّث تلقائياً مع كل تعديل للسعر بنسبة {minSalePercent}% من سعر بيع الياردة — التعديل اليدوي يوقف التعبئة التلقائية لهذا الفرع.</p>
              </div>
              <Input label="سعر بيع الطاقة" type="number" step="0.001" min="0" value={bf.sale_price_roll} onChange={(e) => setBf({ sale_price_roll: e.target.value })} error={errors[`bp_${branch.id}_roll`]} placeholder="اتركه للحساب التلقائي" />
              <Input label="الحد الأدنى لسعر بيع الطاقة" type="number" step="0.001" min="0" value={bf.min_sale_roll} onChange={(e) => setBf({ min_sale_roll: e.target.value })} error={errors[`bp_${branch.id}_minr`]} placeholder="اتركه للحساب التلقائي" />
            </div>
            {(autoRoll != null || autoMinRoll != null || profitY != null || profitR != null || margin != null) && (
              <div className="rounded-xl bg-white border border-sand-200 divide-y divide-sand-200 overflow-hidden">
                {autoRoll != null && (
                  <div className="px-4 py-2.5 flex items-center justify-between text-sm">
                    <span className="text-neutral-600">سعر بيع الطاقة (تلقائي)</span>
                    <span className="font-bold text-brand-700">{autoRoll.toFixed(3)}</span>
                  </div>
                )}
                {autoMinRoll != null && (
                  <div className="px-4 py-2.5 flex items-center justify-between text-sm">
                    <span className="text-neutral-600">الحد الأدنى لسعر الطاقة (تلقائي)</span>
                    <span className="font-bold text-brand-700">{autoMinRoll.toFixed(3)}</span>
                  </div>
                )}
                {profitR != null && (
                  <div className="px-4 py-2.5 flex items-center justify-between text-sm">
                    <span className="text-neutral-600">الربح المتوقع بالطاقة (بيع − شراء)</span>
                    <span className={`font-bold ${profitR >= 0 ? 'text-emerald-600' : 'text-red-500'}`}>
                      {profitR.toFixed(3)}
                    </span>
                  </div>
                )}
                {profitY != null && (
                  <div className="px-4 py-2.5 flex items-center justify-between text-sm">
                    <span className="text-neutral-600">الربح المتوقع باليارد (بيع − شراء)</span>
                    <span className={`font-bold ${profitY >= 0 ? 'text-emerald-600' : 'text-red-500'}`}>
                      {profitY.toFixed(3)}
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
          </div>
        );
      })}

      {sectionTitle('المخزون والتنبيهات')}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <Input label="الحد الأدنى للمخزون" type="number" step="0.01" min="0" value={form.min_stock} onChange={(e) => set('min_stock', e.target.value)} placeholder="مثال: 100" />
      </div>
      <p className="text-xs text-neutral-400 -mt-2">
        عند تسجيل الأصناف تُحسب الياردات من الطاقات والعكس تلقائياً لضمان الاتساق، ويُحظر البيع بأقل من الحد الأدنى المحدد.
      </p>
      <Textarea label="الوصف" value={form.description} onChange={(e) => set('description', e.target.value)} placeholder="وصف القماش..." rows={3} />
      <label className="flex items-center gap-3 cursor-pointer">
        <input type="checkbox" checked={form.is_active} onChange={(e) => set('is_active', e.target.checked)} className="w-4 h-4 accent-brand-600" />
        <span className="text-sm font-medium text-neutral-700">نشط</span>
      </label>
      <label className="flex items-center gap-3 cursor-pointer">
        <input type="checkbox" checked={form.allow_roll_sale} onChange={(e) => set('allow_roll_sale', e.target.checked)} className="w-4 h-4 accent-brand-600" />
        <span className="text-sm font-medium text-neutral-700">السماح بالبيع بالطاقة</span>
      </label>
      <p className="text-xs text-neutral-400 -mt-2">
        {form.allow_roll_sale
          ? 'يمكن بيع هذا القماش بالطاقة (اللفة) في ورديات البيع.'
          : 'يُمنع بيع هذا القماش بالطاقة وتبقى البيع بالياردات متاحة فقط.'}
      </p>

      {sectionTitle('السماح بالبيع بالطاقة حسب الفرع')}
      <div className="rounded-xl bg-sand-50 border border-sand-200 divide-y divide-sand-200">
        {branches.length === 0 && (
          <div className="px-4 py-3 text-sm text-neutral-500">لا توجد فروع مسجلة.</div>
        )}
        {branches.map((branch) => (
          <div key={branch.id} className="px-4 py-2.5 flex items-center justify-between gap-3">
            <div className="min-w-0">
              <span className="text-sm font-medium text-neutral-700 block truncate">{branch.name}</span>
              <span className={`text-xs ${rollOverrides[String(branch.id)] ? 'text-brand-600' : 'text-neutral-400'}`}>
                {rollOverrides[String(branch.id)] === 'true'
                  ? 'يُباع بالطاقة في هذا الفرع إذا توفر السعر'
                  : rollOverrides[String(branch.id)] === 'false'
                    ? 'يُمنع البيع بالطاقة في هذا الفرع'
                    : 'يتبع الإعداد العام — «السماح بالبيع بالطاقة»'}
              </span>
            </div>
            <select
              className="shrink-0 rounded-lg border border-sand-300 bg-white px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
              value={rollOverrides[String(branch.id)] || ''}
              onChange={(e) => setRollOverrides((prev) => ({ ...prev, [String(branch.id)]: e.target.value }))}
              aria-label={`بيع الطاقة لفرع ${branch.name}`}
            >
              <option value="">تبع افتراضي</option>
              <option value="true">مسموح</option>
              <option value="false">ممنوع</option>
            </select>
          </div>
        ))}
      </div>
      <p className="text-xs text-neutral-400 -mt-2">
        تحكم في بيع الطاقة (اللفة) لكل فرع على حدة؛ «تبع افتراضي» يجعل الفرع يسير مع الإعداد العام أعلاه.
      </p>
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