'use client';

import Select from '@/components/ui/Select';
import Input from '@/components/ui/Input';
import Button from '@/components/ui/Button';
import { X, Plus } from 'lucide-react';
import { Fabric, Warehouse, Branch } from '@/types';
import { formatCurrency, formatNumber } from '@/lib/format';

export interface LedgerItemRow {
  key: number;
  fabric: number | '';
  quantity_yards: string;
  rolls: string;
  unit_price: string;
  destType: '' | 'warehouse' | 'branch';
  destId: number | '';
}

interface LedgerItemsFieldsProps {
  fabrics: Fabric[];
  items: LedgerItemRow[];
  onChange: (items: LedgerItemRow[]) => void;
  destinations?: { warehouses: Warehouse[]; branches: Branch[] };
  destinationLabel?: string;
}

export function newLedgerItemRow(key: number): LedgerItemRow {
  return { key, fabric: '', quantity_yards: '', rolls: '', unit_price: '', destType: '', destId: '' };
}

export function ledgerItemsTotal(items: LedgerItemRow[]): number {
  return items.reduce((sum, r) => sum + (Number(r.quantity_yards) || 0) * (Number(r.unit_price) || 0), 0);
}

export function rowTotal(r: LedgerItemRow): number {
  return (Number(r.quantity_yards) || 0) * (Number(r.unit_price) || 0);
}

const round2 = (n: number) => Math.round(n * 100) / 100;

export default function LedgerItemsFields({ fabrics, items, onChange, destinations, destinationLabel }: LedgerItemsFieldsProps) {
  const yardsPerRoll = (fabricId: number | ''): number => {
    if (fabricId === '') return 0;
    const f = fabrics.find((x) => x.id === fabricId);
    const v = f?.yards_per_roll;
    return v != null && Number(v) > 0 ? Number(v) : 0;
  };

  const destOptions = destinations
    ? [
        { value: '', label: 'بدون وجهة (لا يُورَّد)' },
        ...destinations.warehouses.map((w) => ({ value: `w:${w.id}`, label: `مخزن: ${w.name}` })),
        ...destinations.branches.map((b) => ({ value: `b:${b.id}`, label: `فرع: ${b.name}` })),
      ]
    : [];

  const setRowDest = (key: number, raw: string) => {
    const [kind, idStr] = raw.split(':');
    onChange(
      items.map((r) =>
        r.key === key
          ? { ...r, destType: (kind === 'w' || kind === 'b' ? kind : '') as '' | 'warehouse' | 'branch', destId: idStr ? Number(idStr) : '' }
          : r
      )
    );
  };

  const applyToAll = (raw: string) => {
    const [kind, idStr] = raw.split(':');
    const destType = (kind === 'w' ? 'warehouse' : kind === 'b' ? 'branch' : '') as '' | 'warehouse' | 'branch';
    const destId = idStr ? Number(idStr) : '';
    onChange(items.map((r) => ({ ...r, destType, destId })));
  };

  const updateRow = (key: number, patch: Partial<LedgerItemRow>) => {
    onChange(
      items.map((r) => {
        if (r.key !== key) return r;
        const next = { ...r, ...patch };
        const ypr = yardsPerRoll(next.fabric);
        if (ypr > 0) {
          const rolls = Number(next.rolls) || 0;
          const yards = Number(next.quantity_yards) || 0;
          const rollsEdited = 'rolls' in patch;
          const yardsEdited = 'quantity_yards' in patch;
          if ((rollsEdited || 'fabric' in patch) && rolls > 0) {
            next.quantity_yards = String(round2(rolls * ypr));
          }
          if ((yardsEdited || 'fabric' in patch) && yards > 0) {
            next.rolls = String(round2(yards / ypr));
          }
        }
        return next;
      })
    );
  };

  const removeRow = (key: number) => {
    onChange(items.filter((r) => r.key !== key));
  };

  const addRow = () => {
    const nextKey = items.length ? Math.max(...items.map((r) => r.key)) + 1 : 1;
    onChange([...items, newLedgerItemRow(nextKey)]);
  };

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <span className="text-sm font-medium text-neutral-700">الأصناف</span>
        <Button type="button" variant="subtle" size="sm" onClick={addRow}>
          <Plus size={14} />
          إضافة صنف
        </Button>
      </div>

      {destinations && (
        <div className="flex flex-col sm:flex-row sm:items-center gap-3 rounded-xl border border-dashed border-sand-300 bg-sand-50/50 p-3">
          <Select
            label={destinationLabel || 'وجهة التوريد (اختياري)'}
            value=""
            onChange={(e) => applyToAll(e.target.value)}
            options={[{ value: '', label: 'تطبيق وجهة واحدة على جميع البنود...' }, { value: 'none:d', label: 'بدون وجهة (لا يُورَّد)' }, ...destOptions.slice(1)]}
          />
          <p className="text-xs text-neutral-500 sm:max-w-[260px]">
            تُطبق على كل البنود، ويمكن تغيير وجهة كل بند على حدة بعد ذلك. البند بدون وجهة لا يُضاف للمخزون.
          </p>
        </div>
      )}

      {items.length === 0 ? (
        <p className="text-xs text-neutral-400 py-2">لم تتم إضافة أي أصناف بعد.</p>
      ) : (
        items.map((r, i) => (
          <div key={r.key} className="border border-sand-200 rounded-xl p-4 space-y-3">
            <div className="flex items-center justify-between gap-2">
              <span className="text-xs font-medium text-neutral-500">صنف {i + 1}</span>
              <button
                type="button"
                onClick={() => removeRow(r.key)}
                className="p-1.5 rounded-lg hover:bg-red-50 text-red-500 dark:hover:bg-red-500/15 dark:text-red-400 transition-colors"
              >
                <X size={16} />
              </button>
            </div>
            <Select
              label="القماش"
              value={r.fabric}
              onChange={(e) => updateRow(r.key, { fabric: e.target.value ? Number(e.target.value) : '' })}
              options={fabrics.map((f) => ({ value: f.id, label: f.code ? `${f.code} - ${f.name}` : f.name }))}
              placeholder="اختر القماش"
            />
            {yardsPerRoll(r.fabric) > 0 ? (
              <p className="text-xs text-emerald-600 dark:text-emerald-400">
                يُحسب بينهما تلقائياً: 1 طاقة = {formatNumber(yardsPerRoll(r.fabric))} ياردة
              </p>
            ) : (
              <p className="text-xs text-neutral-400">لم يُحدد لهذا القماش معامل طاقة — أدخل الكميتين يدوياً</p>
            )}
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
              <Input
                label="الكمية بالياردة"
                type="number"
                step="0.01"
                min="0"
                value={r.quantity_yards}
                onChange={(e) => updateRow(r.key, { quantity_yards: e.target.value })}
                placeholder=""
              />
              <Input
                label="عدد الطاقات"
                type="number"
                step="0.01"
                min="0"
                value={r.rolls}
                onChange={(e) => updateRow(r.key, { rolls: e.target.value })}
                placeholder="اختياري"
              />
              <Input
                label="سعر الياردة"
                type="number"
                step="0.01"
                min="0"
                value={r.unit_price}
                onChange={(e) => updateRow(r.key, { unit_price: e.target.value })}
                placeholder=""
              />
            </div>
            {destinations && (
              <Select
                label="وجهة توريد هذا البند (اختياري)"
                value={r.destType ? `${r.destType}:${r.destId}` : ''}
                onChange={(e) => setRowDest(r.key, e.target.value)}
                options={destOptions}
              />
            )}
            <div className="flex items-center justify-between text-sm">
              <span className="text-neutral-500">الإجمالي</span>
              <span className="font-semibold text-neutral-800 tabular-nums">{formatCurrency(rowTotal(r))}</span>
            </div>
          </div>
        ))
      )}
    </div>
  );
}