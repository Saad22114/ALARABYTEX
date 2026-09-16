'use client';

import { useState, useEffect } from 'react';
import Card from '@/components/ui/Card';
import Button from '@/components/ui/Button';
import Input from '@/components/ui/Input';
import Select from '@/components/ui/Select';
import Table, { Th, Td, Tr } from '@/components/ui/Table';
import Modal from '@/components/ui/Modal';
import ConfirmDialog from '@/components/ui/ConfirmDialog';
import EmptyState from '@/components/ui/EmptyState';
import Spinner from '@/components/ui/Spinner';
import Badge from '@/components/ui/Badge';
import { Plus, Pencil, Trash2, Tags } from 'lucide-react';
import { Fabric, FabricBranchPrice } from '@/types';
import {
  listBranchPrices, createBranchPrice, updateBranchPrice, deleteBranchPrice,
} from '@/services/branches';
import { listFabrics } from '@/services/fabrics';
import { useToast } from '@/components/ui/Toast';

interface BranchPricingPanelProps {
  branchId: number;
}

interface PriceForm {
  fabric: string;
  sale_price_yard: string;
  sale_price_roll: string;
  min_sale_yard: string;
  min_sale_roll: string;
}

export default function BranchPricingPanel({ branchId }: BranchPricingPanelProps) {
  const { toast } = useToast();
  const [prices, setPrices] = useState<FabricBranchPrice[]>([]);
  const [loading, setLoading] = useState(true);
  const [modalOpen, setModalOpen] = useState(false);
  const [editing, setEditing] = useState<FabricBranchPrice | null>(null);
  const [fabrics, setFabrics] = useState<Fabric[]>([]);
  const [deleting, setDeleting] = useState<FabricBranchPrice | null>(null);
  const [deleteLoading, setDeleteLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [form, setForm] = useState<PriceForm>({
    fabric: '',
    sale_price_yard: '',
    sale_price_roll: '',
    min_sale_yard: '',
    min_sale_roll: '',
  });

  const fetchPrices = () => {
    let cancelled = false;
    setLoading(true);
    listBranchPrices({ branch: branchId, page_size: 100 })
      .then((res) => { if (!cancelled) setPrices(res.results); })
      .catch((err) => { if (!cancelled) toast('error', err.message); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  };

  useEffect(() => fetchPrices(), [branchId]);

  useEffect(() => {
    if (modalOpen && fabrics.length === 0) {
      listFabrics({ page_size: 100 }).then((res) => setFabrics(res.results)).catch(() => undefined);
    }
  }, [modalOpen]);

  const openAdd = () => {
    setEditing(null);
    setErrors({});
    setForm({ fabric: '', sale_price_yard: '', sale_price_roll: '', min_sale_yard: '', min_sale_roll: '' });
    setModalOpen(true);
  };

  const openEdit = (p: FabricBranchPrice) => {
    setEditing(p);
    setErrors({});
    setForm({
      fabric: String(p.fabric),
      sale_price_yard: p.sale_price_yard ? String(p.sale_price_yard) : '',
      sale_price_roll: p.sale_price_roll != null ? String(p.sale_price_roll) : '',
      min_sale_yard: p.min_sale_yard ? String(p.min_sale_yard) : '',
      min_sale_roll: p.min_sale_roll != null ? String(p.min_sale_roll) : '',
    });
    setModalOpen(true);
  };

  const pricedFabricIds = new Set(prices.map((p) => p.fabric));
  const availableFabrics = editing
    ? fabrics
    : fabrics.filter((f) => !pricedFabricIds.has(f.id));

  const handleSave = async () => {
    const e: Record<string, string> = {};
    if (!form.fabric) e.fabric = 'اختر القماش';
    if (Number(form.sale_price_yard) < 0) e.sale_price_yard = 'لا يمكن أن تكون سالبة';
    if (form.sale_price_roll !== '' && Number(form.sale_price_roll) < 0) e.sale_price_roll = 'لا يمكن أن تكون سالبة';
    if (Number(form.min_sale_yard) < 0) e.min_sale_yard = 'لا يمكن أن تكون سالبة';
    if (form.min_sale_roll !== '' && Number(form.min_sale_roll) < 0) e.min_sale_roll = 'لا يمكن أن تكون سالبة';
    setErrors(e);
    if (Object.keys(e).length > 0) return;

    setSaving(true);
    const payload = {
      branch: branchId,
      fabric: Number(form.fabric),
      sale_price_yard: form.sale_price_yard === '' ? 0 : Number(form.sale_price_yard),
      sale_price_roll: form.sale_price_roll === '' ? null : Number(form.sale_price_roll),
      min_sale_yard: form.min_sale_yard === '' ? 0 : Number(form.min_sale_yard),
      min_sale_roll: form.min_sale_roll === '' ? null : Number(form.min_sale_roll),
    };
    try {
      if (editing) {
        await updateBranchPrice(editing.id, payload);
        toast('success', 'تم تحديث سعر الفرع');
      } else {
        await createBranchPrice(payload);
        toast('success', 'تمت إضافة سعر الفرع');
      }
      setModalOpen(false);
      fetchPrices();
    } catch (err: any) {
      toast('error', err.message);
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async () => {
    if (!deleting) return;
    setDeleteLoading(true);
    try {
      await deleteBranchPrice(deleting.id);
      toast('success', 'تم حذف سعر الفرع');
      setDeleting(null);
      fetchPrices();
    } catch (err: any) {
      toast('error', err.message);
    } finally {
      setDeleteLoading(false);
    }
  };

  return (
    <Card
      title={prices[0]?.branch_name ? `أسعار بيع فرع «${prices[0].branch_name}»` : 'أسعار بيع الفرع'}
      subtitle="تشمل هذه الأسعار على الأسعار العامة — تُستخدم تلقائياً في ورديات البيع"
      action={
        <Button onClick={openAdd} size="sm">
          <Plus size={16} />
          إضافة سعر
        </Button>
      }
    >
      {loading ? (
        <div className="flex justify-center py-12"><Spinner size={32} /></div>
      ) : prices.length === 0 ? (
        <EmptyState
          icon={<Tags size={40} />}
          title="لا توجد أسعار خاصة"
          description="أسعار بيع هذا الفرع تستخدم الأسعار العامة من ملف الأقمشة"
        />
      ) : (
        <div className="overflow-x-auto">
          <Table>
            <thead>
              <tr>
                <Th>القماش</Th>
                <Th>السعر الجاري</Th>
                <Th>سعر الفرع/ياردة</Th>
                <Th>سعر الفرع/لفة</Th>
                <Th>الحد الأدنى/ياردة</Th>
                <Th>الحد الأدنى/لفة</Th>
                <Th>إجراءات</Th>
              </tr>
            </thead>
            <tbody>
              {prices.map((p) => (
                <Tr key={p.id}>
                  <Td>
                    <div className="font-medium">{p.fabric_name}</div>
                    <div className="text-xs text-neutral-400 font-mono">{p.fabric_code}</div>
                  </Td>
                  <Td>
                    <div className="tabular-nums">{p.global_sale_price_yard || 0}</div>
                    <div className="text-xs text-neutral-400">يارد/لفة: {p.global_sale_price_roll ?? '—'}</div>
                  </Td>
                  <Td>
                    <Badge variant={p.sale_price_yard ? 'neutral' : 'danger'}>
                      {p.sale_price_yard ? p.sale_price_yard : 'العام'}
                    </Badge>
                  </Td>
                  <Td>{p.sale_price_roll != null ? p.sale_price_roll : '—'}</Td>
                  <Td>{p.min_sale_yard || '—'}</Td>
                  <Td>{p.min_sale_roll != null ? p.min_sale_roll : '—'}</Td>
                  <Td>
                    <div className="flex items-center gap-2">
                      <button onClick={() => openEdit(p)} className="p-1.5 rounded-lg hover:bg-amber-50 text-amber-600 dark:hover:bg-amber-500/15 dark:text-amber-400 transition-colors" aria-label="تعديل">
                        <Pencil size={16} />
                      </button>
                      <button onClick={() => setDeleting(p)} className="p-1.5 rounded-lg hover:bg-red-50 text-red-500 dark:hover:bg-red-500/15 dark:text-red-400 transition-colors" aria-label="حذف">
                        <Trash2 size={16} />
                      </button>
                    </div>
                  </Td>
                </Tr>
              ))}
            </tbody>
          </Table>
        </div>
      )}

      <Modal open={modalOpen} onClose={() => setModalOpen(false)} title={editing ? 'تعديل سعر الفرع' : 'إضافة سعر فرع'}>
        <div className="space-y-4">
          <Select
            label="القماش"
            value={form.fabric}
            onChange={(e) => setForm({ ...form, fabric: e.target.value })}
            options={availableFabrics.map((f) => ({
              value: f.id,
              label: `${f.name} (${f.code}) — جاري: ${f.sale_price_yard || 0}`,
            }))}
            disabled={!!editing}
            error={errors.fabric}
          />
          <div className="grid grid-cols-2 gap-4">
            <Input
              label="سعر بيع الياردة"
              type="number"
              min={0}
              value={form.sale_price_yard}
              onChange={(e) => setForm({ ...form, sale_price_yard: e.target.value })}
              error={errors.sale_price_yard}
              placeholder="0 = استخدم السعر العام"
            />
            <Input
              label="سعر بيع اللفة"
              type="number"
              min={0}
              value={form.sale_price_roll}
              onChange={(e) => setForm({ ...form, sale_price_roll: e.target.value })}
              error={errors.sale_price_roll}
              placeholder="اختياري"
            />
            <Input
              label="الحد الأدنى للياردة"
              type="number"
              min={0}
              value={form.min_sale_yard}
              onChange={(e) => setForm({ ...form, min_sale_yard: e.target.value })}
              error={errors.min_sale_yard}
              placeholder="اختياري"
            />
            <Input
              label="الحد الأدنى للفة"
              type="number"
              min={0}
              value={form.min_sale_roll}
              onChange={(e) => setForm({ ...form, min_sale_roll: e.target.value })}
              error={errors.min_sale_roll}
              placeholder="اختياري"
            />
          </div>
          <div className="flex justify-start gap-3 pt-2">
            <Button onClick={handleSave} loading={saving}>
              {editing ? 'تحديث' : 'إضافة'}
            </Button>
            <Button variant="secondary" onClick={() => setModalOpen(false)}>
              إلغاء
            </Button>
          </div>
        </div>
      </Modal>

      <ConfirmDialog
        open={!!deleting}
        onClose={() => setDeleting(null)}
        onConfirm={handleDelete}
        loading={deleteLoading}
        title="حذف سعر الفرع"
        message={`هل أنت متأكد من حذف سعر «${deleting?.fabric_name}» الخاص بهذا الفرع؟ سيعود البيع إلى السعر العام.`}
        confirmLabel="حذف"
      />
    </Card>
  );
}