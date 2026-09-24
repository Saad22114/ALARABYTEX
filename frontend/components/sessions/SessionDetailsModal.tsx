'use client';

import { useState, useCallback, useEffect } from 'react';
import Modal from '@/components/ui/Modal';
import Badge from '@/components/ui/Badge';
import Button from '@/components/ui/Button';
import ConfirmDialog from '@/components/ui/ConfirmDialog';
import Table, { Th, Td, Tr } from '@/components/ui/Table';
import EmptyState from '@/components/ui/EmptyState';
import { formatCurrency, formatNumber, formatDate } from '@/lib/format';
import { reopenSaleSession } from '@/services/sessions';
import { useToast } from '@/components/ui/Toast';
import { useSettings } from '@/components/providers/SettingsProvider';
import { logoUrl } from '@/services/settings';
import { SaleSession } from '@/types';
import { Printer, FileDown, RotateCcw } from 'lucide-react';

interface Props {
  open: boolean;
  session: SaleSession | null;
  onClose: () => void;
  onReopened?: (session: SaleSession) => void;
}

function fmtTime(iso: string): string {
  return `${formatDate(iso)} ${new Date(iso).toLocaleTimeString('ar-EG-u-nu-latn', {
    hour: '2-digit',
    minute: '2-digit',
  })}`;
}

function elapsedText(minutes: number | null): string {
  if (minutes == null) return '';
  const m = Math.max(0, minutes);
  if (m < 60) return `${formatNumber(m)} دقيقة`;
  const h = Math.floor(m / 60);
  const r = m % 60;
  return r === 0 ? `${formatNumber(h)} ساعة` : `${formatNumber(h)} ساعة و ${formatNumber(r)} دقيقة`;
}

const num = (n: number): string =>
  n.toLocaleString('en-US', { minimumFractionDigits: 0, maximumFractionDigits: 2 });

export default function SessionDetailsModal({ open, session, onClose, onReopened }: Props) {
  const { toast } = useToast();
  const { settings } = useSettings();
  const [reopening, setReopening] = useState(false);
  const [confirmReopen, setConfirmReopen] = useState(false);

  useEffect(() => {
    if (open) {
      setConfirmReopen(false);
      setReopening(false);
    }
  }, [open]);

  const sym = settings?.currency_symbol ?? 'ر.س';

  const exportCsv = useCallback(() => {
    if (!session) return;
    const esc = (v: string) => `"${v.replace(/"/g, '""')}"`;
    const header = ['القماش', 'النوع', 'الكمية', 'الياردات الفعلية', 'سعر الوحدة', 'طريقة الدفع', 'الإجمالي', 'تاريخ البيع'];
    const rows = session.items.map((it) => [
      it.fabric_name,
      it.sale_type_label,
      `${it.quantity} ${it.sale_type === 'roll' ? 'طاقة' : 'يارد'}`,
      num(it.yards_effective),
      num(it.unit_price),
      it.payment_method_label,
      num(it.total),
      it.sale_date,
    ]);
    const footer = [
      ['الإجمالي', '', '', num(session.totals.yards), '', '', num(session.totals.total), ''],
      ['كاش', num(session.totals.cash)],
      ['تحويل', num(session.totals.transfer)],
      ['ماكينة', num(session.totals.card)],
    ];
    const lines = [
      `تقرير الوردية — ${session.employee_name} (${session.branch_name})`,
      '',
      [...header].map(esc).join(','),
      ...rows.map((r) => r.map(esc).join(',')),
      '',
      ...footer.map((r) => r.map(esc).join(',')),
    ];
    const blob = new Blob(['\ufeff' + lines.join('\r\n')], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `wardiya-${session.id}.csv`;
    a.click();
    URL.revokeObjectURL(url);
    toast('success', 'تم تصدير التقرير');
  }, [session, toast]);

  const printReport = useCallback(() => {
    if (!session) return;
    const paymentName: Record<string, string> = { cash: 'كاش', transfer: 'تحويل', card: 'ماكينة' };
    const rowsHtml = session.items
      .map(
        (it) => `
        <tr>
          <td>${it.fabric_name}</td>
          <td>${it.sale_type_label}</td>
          <td class="num">${it.quantity} ${it.sale_type === 'roll' ? 'طاقة' : 'يارد'}</td>
          <td class="num">${num(it.yards_effective)}</td>
          <td class="num">${num(it.unit_price)}</td>
          <td>${paymentName[it.payment_method] ?? it.payment_method_label}</td>
          <td class="num">${num(it.total)} ${sym}</td>
          <td class="num">${it.sale_date}</td>
        </tr>`
      )
      .join('');
    const html = `<!doctype html>
<html dir="rtl" lang="ar">
<head>
<meta charset="utf-8" />
<title>تقرير وردية</title>
<style>
  * { box-sizing: border-box; }
  body { font-family: "Segoe UI", Tahoma, Arial, sans-serif; color: #1f2937; margin: 0; padding: 24px; }
  .store { text-align: center; margin-bottom: 6px; }
  .store img { max-height: 64px; max-width: 96px; }
  h1 { font-size: 20px; margin: 0 0 2px; text-align: center; }
  .sub { text-align: center; color: #6b7280; font-size: 12px; margin-bottom: 16px; }
  .meta { display: flex; flex-wrap: wrap; gap: 8px 24px; font-size: 13px; margin-bottom: 12px; border: 1px solid #e5e7eb; border-radius: 8px; padding: 10px 14px; }
  .meta b { color: #111827; }
  table { width: 100%; border-collapse: collapse; font-size: 12px; }
  th, td { border: 1px solid #d1d5db; padding: 6px 8px; text-align: right; }
  th { background: #f3f4f6; font-weight: 600; }
  .num { text-align: left; font-variant-numeric: tabular-nums; white-space: nowrap; }
  .totals { margin-top: 14px; font-size: 13px; }
  .totals div { display: inline-flex; gap: 8px; margin-left: 20px; }
  .grand { font-size: 15px; font-weight: 700; margin-top: 8px; }
  .footer { margin-top: 24px; color: #6b7280; font-size: 12px; text-align: center; }
  @media print { body { -webkit-print-color-adjust: exact; print-color-adjust: exact; } }
</style>
</head>
<body>
  ${logoUrl(settings?.logo) ? `<div class="store"><img src="${logoUrl(settings?.logo)}" alt="الشعار" /></div>` : ''}
  <h1>${settings?.business_name || ''}</h1>
  ${settings?.commercial_registration ? `<div class="sub">السجل التجاري: ${settings.commercial_registration}</div>` : ''}
  <div class="sub">تقرير وردية بيع — رقم الإيصال: ${settings?.invoice_prefix || ''}${session.id}</div>
  <div class="meta">
    <span>الموظف: <b>${session.employee_name}</b></span>
    <span>الفرع: <b>${session.branch_name}</b></span>
    <span>الفُتحت: <b>${fmtTime(session.opened_at)}</b></span>
    <span>أُغلقت: <b>${session.closed_at ? fmtTime(session.closed_at) : '—'}</b></span>
    <span>المدة: <b>${elapsedText(session.elapsed_minutes) || '—'}</b></span>
    <span>الحالة: <b>${session.status_label}</b></span>
    ${settings?.receipt_show_phone && settings?.business_phone ? `<span>الهاتف: <b>${settings.business_phone}</b></span>` : ''}
    ${settings?.business_address ? `<span>العنوان: <b>${settings.business_address}</b></span>` : ''}
  </div>
  ${
    session.items.length === 0
      ? '<p style="text-align:center;color:#6b7280;padding:20px">لا توجد بنود</p>'
      : `<table>
        <thead><tr><th>القماش</th><th>النوع</th><th>الكمية</th><th>الياردات</th><th>سعر الوحدة</th><th>الدفع</th><th>الإجمالي</th><th>التاريخ</th></tr></thead>
        <tbody>${rowsHtml}</tbody>
      </table>`
  }
  <div class="totals">
    <div>كاش: <b>${num(session.totals.cash)} ${sym}</b></div>
    <div>تحويل: <b>${num(session.totals.transfer)} ${sym}</b></div>
    <div>ماكينة: <b>${num(session.totals.card)} ${sym}</b></div>
    <div>ياردات: <b>${num(session.totals.yards)}</b></div>
  </div>
  ${settings?.receipt_show_tax ? (() => {
    const taxRate = Number(settings.tax_rate || 0);
    const taxAmount = taxRate > 0 ? Math.round(session.totals.total * (taxRate / 100) * 100) / 100 : 0;
    return `<div class="totals"><div>ضريبة (${taxRate}%): <b>${num(taxAmount)} ${sym}</b></div></div>
    <div class="grand">الإجمالي (شامل الضريبة): ${num(Math.round((session.totals.total + taxAmount) * 100) / 100)} ${sym}</div>`;
  })() : `<div class="grand">الإجمالي: ${num(session.totals.total)} ${sym}</div>`}
  ${
    settings?.receipt_footer
      ? `<div class="footer">${settings.receipt_footer.split('\n').map((l) => `${l}<br />`).join('')}</div>`
      : ''
  }
  <script>setTimeout(() => window.print(), 200);</script>
</body>
</html>`;
    const win = window.open('', '_blank', 'width=900,height=700');
    if (!win) {
      toast('error', 'الرجاء السماح بالنوافذ المنبثقة للطباعة');
      return;
    }
    win.document.open();
    win.document.write(html);
    win.document.close();
  }, [session, settings, sym, toast]);

  const handleReopen = async () => {
    if (!session) return;
    setReopening(true);
    try {
      const updated = await reopenSaleSession(session.id);
      toast('success', 'تم إعادة فتح الوردية');
      setConfirmReopen(false);
      onClose();
      onReopened?.(updated);
    } catch (err: any) {
      toast('error', err.message);
    } finally {
      setReopening(false);
    }
  };

  return (
    <>
      <Modal open={open} onClose={onClose} title="مشاهدة الوردية" maxWidth="max-w-3xl">
        {session && (
          <div className="space-y-4">
            {/* Action bar */}
            <div className="flex flex-wrap items-center gap-2">
              <Button variant="secondary" size="sm" onClick={printReport}>
                <Printer size={15} className="ms-1" />
                طباعة / PDF
              </Button>
              <Button variant="secondary" size="sm" onClick={exportCsv}>
                <FileDown size={15} className="ms-1" />
                تصدير CSV
              </Button>
              {session.status === 'closed' && !session.is_manual && (
                <Button variant="primary" size="sm" className="mr-auto" onClick={() => setConfirmReopen(true)}>
                  <RotateCcw size={15} className="ms-1" />
                  إعادة فتح الوردية
                </Button>
              )}
              {session.is_manual && (
                <div className="mr-auto"><Badge variant="warning">وردية مُدخلة يدوياً</Badge></div>
              )}
            </div>

            {/* Session header */}
            <div className="rounded-xl border border-sand-200 bg-sand-50 p-4">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div>
                  <p className="text-lg font-bold text-neutral-800">{session.employee_name}</p>
                  <p className="text-sm text-neutral-500 mt-0.5">{session.branch_name}</p>
                </div>
                <Badge variant={session.status === 'open' ? 'success' : 'neutral'}>
                  {session.status_label}
                </Badge>
              </div>
              {session.is_manual && (
                <p className="mt-2 text-sm text-amber-700">
                  وردية مسجلة كمجموع يدوي بدون تفاصيل أصناف
                  {session.manual_date ? ` — بتاريخ ${formatDate(session.manual_date)}` : ''}
                </p>
              )}
              <div className="mt-3 grid grid-cols-1 sm:grid-cols-3 gap-3 text-sm">
                <div>
                  <p className="text-xs text-neutral-400">فُتحت</p>
                  <p className="mt-0.5 tabular-nums">{fmtTime(session.opened_at)}</p>
                </div>
                <div>
                  <p className="text-xs text-neutral-400">أُغلقت</p>
                  <p className="mt-0.5 tabular-nums">{session.closed_at ? fmtTime(session.closed_at) : '—'}</p>
                </div>
                <div>
                  <p className="text-xs text-neutral-400">المدة</p>
                  <p className="mt-0.5 tabular-nums">{elapsedText(session.elapsed_minutes) || '—'}</p>
                </div>
              </div>
              {session.notes && (
                <div className="mt-3 text-sm text-neutral-600">
                  <p className="text-xs text-neutral-400 mb-0.5">ملاحظات</p>
                  <p className="whitespace-pre-wrap">{session.notes}</p>
                </div>
              )}
            </div>

            {/* Totals */}
            <div className="flex flex-wrap items-center gap-2">
              <Badge variant="success">كاش {formatCurrency(session.totals.cash)}</Badge>
              <Badge variant="neutral">تحويل {formatCurrency(session.totals.transfer)}</Badge>
              <Badge variant="warning">ماكينة {formatCurrency(session.totals.card)}</Badge>
              <Badge variant="neutral">{formatNumber(session.totals.yards)} ياردة</Badge>
              <span className="mr-auto text-lg font-bold tabular-nums">{formatCurrency(session.totals.total)}</span>
            </div>

            {/* Items */}
            {session.items.length === 0 ? (
              <EmptyState title="لا توجد بنود" description="لا توجد بنود مسجلة في هذه الوردية" />
            ) : (
              <div className="overflow-x-auto rounded-xl border border-sand-200">
                <Table>
                  <thead>
                    <tr>
                      <Th>القماش</Th>
                      <Th>النوع</Th>
                      <Th>الكمية</Th>
                      <Th>الياردات الفعلية</Th>
                      <Th>سعر الوحدة</Th>
                      <Th>طريقة الدفع</Th>
                      <Th>الإجمالي</Th>
                      <Th>تاريخ البيع</Th>
                    </tr>
                  </thead>
                  <tbody>
                    {session.items.map((item) => (
                      <Tr key={item.id}>
                        <Td className="font-medium">
                          <span className="flex flex-wrap items-center gap-1.5">
                            {item.fabric_name}
                            {item.is_returned && <Badge variant="danger">مسترجع</Badge>}
                          </span>
                        </Td>
                        <Td><Badge variant="neutral">{item.sale_type_label}</Badge></Td>
                        <Td className="tabular-nums">{item.quantity} {item.sale_type === 'roll' ? 'طاقة' : 'يارد'}</Td>
                        <Td className="tabular-nums text-neutral-500">{formatNumber(item.yards_effective)} ياردة</Td>
                        <Td className="tabular-nums">{formatCurrency(item.unit_price)}</Td>
                        <Td>
                          <Badge variant={item.payment_method === 'card' ? 'warning' : item.payment_method === 'transfer' ? 'neutral' : 'success'}>
                            {item.payment_method === 'card' ? (item.card_type_label ? `ماكينة (${item.card_type_label})` : 'ماكينة') : item.payment_method_label}
                          </Badge>
                        </Td>
                        <Td
                          className="tabular-nums font-semibold"
                          title={
                            item.payment_method === 'card' && item.card_fee_amount > 0
                              ? `رسوم الماكينة: ${formatCurrency(item.card_fee_amount)} — الصافي: ${formatCurrency(item.net_total)}`
                              : undefined
                          }
                        >
                          {formatCurrency(item.payment_method === 'card' && item.net_total > 0 ? item.net_total : item.total)}
                          {item.payment_method === 'card' && item.card_fee_amount > 0 && (
                            <span className="block text-[10px] font-normal text-neutral-400">صافي بعد رسوم {formatCurrency(item.card_fee_amount)}</span>
                          )}
                        </Td>
                        <Td className="tabular-nums text-sm text-neutral-500">{formatDate(item.sale_date)}</Td>
                      </Tr>
                    ))}
                  </tbody>
                </Table>
              </div>
            )}
          </div>
        )}
      </Modal>

      <ConfirmDialog
        open={confirmReopen && !!session}
        onClose={() => setConfirmReopen(false)}
        onConfirm={handleReopen}
        loading={reopening}
        title="إعادة فتح الوردية"
        confirmLabel="إعادة فتح"
        message={
          session
            ? `سيتم إعادة فتح وردية ${session.employee_name} وإرجاع مبيعاتها (${formatNumber(session.totals.yards)} ياردة — ${formatCurrency(session.totals.total)}) إلى المخزون. يمكنك إضافة بنود ثم إغلاقها من جديد.`
            : ''
        }
      />
    </>
  );
}