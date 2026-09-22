'use client';

import { useState } from 'react';
import Modal from '@/components/ui/Modal';
import Button from '@/components/ui/Button';
import Badge from '@/components/ui/Badge';
import { SaleSession, SessionSaleItem } from '@/types';
import { moveSessionItem } from '@/services/sessions';
import { formatNumber, formatCurrency } from '@/lib/format';
import { useToast } from '@/components/ui/Toast';
import { MoveRight, TriangleAlert } from 'lucide-react';

interface Props {
  open: boolean;
  session: SaleSession | null;
  item: SessionSaleItem | null;
  sessions: SaleSession[];
  onClose: () => void;
  onMoved: () => void;
}

export default function MoveItemModal({ open, session, item, sessions, onClose, onMoved }: Props) {
  const { toast } = useToast();
  const [targetId, setTargetId] = useState<number | null>(null);
  const [saving, setSaving] = useState(false);

  const targets = session
    ? sessions.filter((s) => s.id !== session.id)
    : [];

  const reset = () => {
    setTargetId(null);
    setSaving(false);
  };

  const handleConfirm = async () => {
    if (!session || !item) return;
    if (!targetId) {
      toast('error', 'اختر الوردية الهدف');
      return;
    }
    setSaving(true);
    try {
      await moveSessionItem(session.id, item.id, targetId);
      toast('success', 'تم نقل البند إلى الوردية الهدف');
      reset();
      onClose();
      onMoved();
    } catch (err: any) {
      toast('error', err.message);
    } finally {
      setSaving(false);
    }
  };

  return (
    <Modal open={open} onClose={onClose} title="نقل بند إلى وردية أخرى" maxWidth="max-w-lg">
      {item && (
        <div className="space-y-4">
          <div className="rounded-xl border border-sand-300 bg-sand-50 px-4 py-3 text-sm">
            <div className="font-semibold">{item.fabric_name}</div>
            <div className="mt-1 flex flex-wrap gap-2 text-neutral-500">
              <span>{item.quantity} {item.sale_type === 'roll' ? 'طاقة' : 'ياردة'}</span>
              <span>•</span>
              <span>{formatNumber(item.yards_effective)} ياردة</span>
              <span>•</span>
              <span>{formatCurrency(item.total)}</span>
              {item.discount_amount > 0 && (
                <>
                  <span>•</span>
                  <span className="text-red-500">خصم {formatCurrency(item.discount_amount)}</span>
                </>
              )}
            </div>
          </div>

          <div className="space-y-2">
            <label className="block text-sm font-medium text-neutral-700 mb-1.5">الوردية الهدف</label>
            {targets.length === 0 ? (
              <div className="rounded-xl border border-sand-300 px-4 py-3 text-sm text-neutral-500">
                لا توجد وردية مفتوحة أخرى لنقل البند إليها
              </div>
            ) : (
              targets.map((t) => (
                <button
                  key={t.id}
                  type="button"
                  onClick={() => setTargetId(t.id)}
                  className={`w-full text-right rounded-xl border px-4 py-3 transition-colors ${
                    targetId === t.id
                      ? 'border-brand-500 ring-2 ring-brand-100'
                      : 'border-sand-300 hover:border-brand-300'
                  }`}
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className="font-semibold">{t.employee_name} — {t.branch_name}</span>
                    <Badge variant={t.id === targetId ? 'success' : 'neutral'}>
                      {formatCurrency(t.totals.total)}
                    </Badge>
                  </div>
                  <div className="mt-1 text-xs text-neutral-400">
                    {t.items.length} بند
                  </div>
                </button>
              ))
            )}
          </div>

          <div className="flex items-start gap-2 rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-xs text-amber-700 dark:border-amber-500/25 dark:bg-amber-500/10 dark:text-amber-300">
            <TriangleAlert size={16} className="mt-0.5 shrink-0" />
            <span>
              يُعاد التحقق من الكمية المتوفرة في مخزون فرع الوردية الهدف قبل النقل — إذا لم تتوفر يُرفض النقل.
            </span>
          </div>

          <div className="flex items-center justify-end gap-3 pt-2">
            <Button variant="secondary" onClick={onClose}>
              إلغاء
            </Button>
            <Button onClick={handleConfirm} loading={saving} disabled={targets.length === 0}>
              <MoveRight size={18} />
              نقل البند
            </Button>
          </div>
        </div>
      )}
    </Modal>
  );
}