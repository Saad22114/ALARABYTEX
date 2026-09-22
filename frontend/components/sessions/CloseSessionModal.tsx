'use client';

import { useCallback } from 'react';
import Modal from '@/components/ui/Modal';
import Button from '@/components/ui/Button';
import { SaleSession } from '@/types';
import { formatCurrency, formatNumber, formatDate } from '@/lib/format';
import { printSessionReceipt } from '@/lib/receipt';
import { useToast } from '@/components/ui/Toast';
import { useSettings } from '@/components/providers/SettingsProvider';
import { Printer, Lock } from 'lucide-react';

interface Props {
  open: boolean;
  session: SaleSession | null;
  loading: boolean;
  onClose: () => void;
  onConfirm: () => void;
}

const PAYMENT_NAMES: Record<string, string> = { cash: 'كاش', transfer: 'تحويل', card: 'ماكينة' };

export default function CloseSessionModal({ open, session, loading, onClose, onConfirm }: Props) {
  const { toast } = useToast();
  const { settings } = useSettings();

  const printClose = useCallback(() => {
    if (!session) return;
    const ok = printSessionReceipt(session, settings || null, 'كشف إغلاق وردية بيع');
    if (!ok) toast('error', 'الرجاء السماح بالنوافذ المنبثقة للطباعة');
  }, [session, settings, toast]);

  return (
    <Modal open={open} onClose={onClose} title="كشف إغلاق الوردية" maxWidth="max-w-2xl">
      {session && (
        <div className="space-y-4">
          <div className="rounded-xl border border-sand-300 p-4">
            <div className="text-center">
              <div className="font-bold text-lg">{settings?.business_name || 'كشف الوردية'}</div>
              <div className="text-xs text-neutral-500">
                كشف إغلاق وردية بيع — رقم الإيصال: <b className="text-neutral-800">{`${settings?.invoice_prefix || ''}${session.id}`}</b>
              </div>
            </div>
            <div className="mt-3 flex flex-wrap gap-x-6 gap-y-1 text-sm text-neutral-600">
              <span>الموظف: <b className="text-neutral-900">{session.employee_name}</b></span>
              <span>الفرع: <b className="text-neutral-900">{session.branch_name}</b></span>
              <span>الفُتحت: <b className="text-neutral-900">{formatDate(session.opened_at)}</b></span>
              <span>البنود: <b className="text-neutral-900">{session.items.length}</b></span>
              {settings?.receipt_show_phone && settings?.business_phone && (
                <span>الهاتف: <b className="text-neutral-900" dir="ltr">{settings.business_phone}</b></span>
              )}
            </div>
            {session.items.length > 0 ? (
              <div className="mt-3 overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-sand-300 text-right text-xs text-neutral-500">
                      <th className="py-1.5 font-medium">القماش</th>
                      <th className="py-1.5 font-medium">النوع</th>
                      <th className="py-1.5 font-medium">الكمية</th>
                      <th className="py-1.5 font-medium">الياردات</th>
                      <th className="py-1.5 font-medium">السعر</th>
                      <th className="py-1.5 font-medium">الخصم</th>
                      <th className="py-1.5 font-medium">الدفع</th>
                      <th className="py-1.5 font-medium text-left">الإجمالي</th>
                    </tr>
                  </thead>
                  <tbody>
                    {session.items.map((it) => (
                      <tr key={it.id} className="border-b border-sand-100">
                        <td className="py-2">{it.fabric_name}</td>
                        <td className="py-2 text-neutral-500">{it.sale_type_label}</td>
                        <td className="py-2 tabular-nums">{it.quantity} {it.sale_type === 'roll' ? 'طاقة' : 'يارد'}</td>
                        <td className="py-2 tabular-nums text-neutral-500">{formatNumber(it.yards_effective)}</td>
                        <td className="py-2 tabular-nums">{formatCurrency(it.unit_price)}</td>
                        <td className="py-2 tabular-nums text-red-500">{it.discount_amount > 0 ? formatCurrency(it.discount_amount) : '—'}</td>
                        <td className="py-2">{PAYMENT_NAMES[it.payment_method] ?? it.payment_method_label}</td>
                        <td className="py-2 tabular-nums text-left font-semibold">{formatCurrency(it.total)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <div className="py-6 text-center text-sm text-neutral-400">لا توجد بنود في هذه الوردية</div>
            )}
            <div className="mt-3 flex flex-wrap items-center justify-between gap-3 border-t border-sand-200 pt-3 text-sm">
              <span className="flex flex-wrap gap-2">
                <span className="rounded-full bg-emerald-50 border border-emerald-200 px-2.5 py-0.5 text-xs font-medium text-emerald-700">كاش {formatCurrency(session.totals.cash)}</span>
                <span className="rounded-full bg-sand-100 border border-sand-200 px-2.5 py-0.5 text-xs font-medium text-neutral-600">تحويل {formatCurrency(session.totals.transfer)}</span>
                <span className="rounded-full bg-amber-50 border border-amber-200 px-2.5 py-0.5 text-xs font-medium text-amber-700">ماكينة {formatCurrency(session.totals.card)}</span>
                <span className="rounded-full bg-sand-100 border border-sand-200 px-2.5 py-0.5 text-xs font-medium text-neutral-600">{formatNumber(session.totals.yards)} ياردة</span>
              </span>
              <span className="text-lg font-bold tabular-nums">{formatCurrency(session.totals.total)}</span>
            </div>
            {(() => {
              const taxRate = Number(settings?.tax_rate ?? 0);
              const showTax = !!settings?.receipt_show_tax;
              const taxAmount = showTax && taxRate > 0 ? Math.round(session.totals.total * (taxRate / 100) * 100) / 100 : 0;
              return showTax ? (
                <div className="mt-2 flex items-center justify-between border-t border-dashed border-sand-300 pt-2 text-sm">
                  <span className="text-neutral-600">ضريبة ({taxRate}%)</span>
                  <span className="font-semibold tabular-nums">{formatCurrency(taxAmount)}</span>
                </div>
              ) : null;
            })()}
            {settings?.receipt_footer && (
              <div className="mt-3 border-t border-dashed border-sand-300 pt-2 text-center text-xs text-neutral-400">
                {settings.receipt_footer.split('\n').map((l, i) => <div key={i}>{l}</div>)}
              </div>
            )}
          </div>

          <p className="text-xs text-neutral-400">
            عند التأكيد تُسجَّل مبيعات هذه الوردية في قيود اليوم وتُخصم الكميات من مخزون الفرع ولا يمكن التراجع إلا بإعادة فتح الوردية.
          </p>

          <div className="flex items-center justify-end gap-3 pt-2">
            <Button variant="secondary" onClick={onClose}>
              تراجع
            </Button>
            <Button variant="secondary" onClick={printClose}>
              <Printer size={18} />
              طباعة
            </Button>
            <Button onClick={onConfirm} loading={loading}>
              <Lock size={18} />
              حفظ وإغلاق الوردية
            </Button>
          </div>
        </div>
      )}
    </Modal>
  );
}