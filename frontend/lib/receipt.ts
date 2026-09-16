import { SaleSession, AppSettings } from '@/types';
import { formatNumber } from '@/lib/format';
import { logoUrl } from '@/services/settings';

const PAYMENT_NAMES: Record<string, string> = { cash: 'كاش', transfer: 'تحويل', card: 'ماكينة' };

const num = (v: number) => formatNumber(Number(v));

function esc(v: string | number | null | undefined): string {
  return String(v ?? '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

function timeOnly(iso: string): string {
  const d = new Date(iso);
  if (isNaN(d.getTime())) return '';
  return `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`;
}

function dateOnly(iso: string): string {
  const d = new Date(iso);
  if (isNaN(d.getTime())) return '';
  return `${String(d.getFullYear())}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
}

export function buildSessionReceipt(session: SaleSession, settings: AppSettings | null, title: string) {
  const sym = settings?.currency_symbol || '';
  const taxRate = Number(settings?.tax_rate ?? 0);
  const showTax = !!settings?.receipt_show_tax;
  const invoiceNo = `${settings?.invoice_prefix || ''}${session.id}`;
  const taxAmount = showTax && taxRate > 0 ? Math.round(session.totals.total * (taxRate / 100) * 100) / 100 : 0;
  const grandTotal = Math.round((session.totals.total + taxAmount) * 100) / 100;

  const rowsHtml = session.items
    .map(
      (it) => `
      <tr>
        <td>${it.fabric_name}</td>
        <td>${it.sale_type_label}</td>
        <td class="num">${it.quantity} ${it.sale_type === 'roll' ? 'لفة' : 'يارد'}</td>
        <td class="num">${num(it.yards_effective)} ياردة</td>
        <td class="num">${num(it.unit_price)}</td>
        <td class="num">${it.discount_amount > 0 ? num(it.discount_amount) : '—'}</td>
        <td>${PAYMENT_NAMES[it.payment_method] ?? it.payment_method_label}</td>
        <td class="num">${num(it.total)} ${sym}</td>
      </tr>`
    )
    .join('');

  return `<!doctype html>
<html dir="rtl" lang="ar">
<head>
<meta charset="utf-8" />
<title>${title}</title>
<style>
  * { box-sizing: border-box; }
  body { font-family: "Segoe UI", Tahoma, Arial, sans-serif; color: #1f2937; margin: 0; padding: 24px; }
  .store { text-align: center; margin-bottom: 6px; }
  .store img { max-height: 64px; max-width: 96px; }
  h1 { font-size: 20px; margin: 0 0 2px; text-align: center; }
  .sub { text-align: center; color: #6b7280; font-size: 12px; margin-bottom: 16px; }
  .meta { display: flex; flex-wrap: wrap; gap: 8px 24px; font-size: 13px; margin-bottom: 12px; border: 1px solid #e5e7eb; border-radius: 8px; padding: 10px 14px; }
  .meta b { color: #111827; }
  table { width: 100%; border-collapse: collapse; font-size: 12px; margin-top: 8px; }
  th, td { border: 1px solid #d1d5db; padding: 6px 8px; text-align: right; }
  th { background: #f3f4f6; font-weight: 600; }
  .num { text-align: left; font-variant-numeric: tabular-nums; white-space: nowrap; }
  .totals { margin-top: 14px; font-size: 13px; }
  .totals div { display: inline-flex; gap: 8px; margin-left: 20px; }
  .grand { font-size: 15px; font-weight: 700; margin-top: 8px; border-top: 2px solid #111827; padding-top: 8px; }
  .footer { margin-top: 24px; color: #6b7280; font-size: 12px; text-align: center; }
  @media print { body { -webkit-print-color-adjust: exact; print-color-adjust: exact; } }
</style>
</head>
<body>
  ${logoUrl(settings?.logo) ? `<div class="store"><img src="${esc(logoUrl(settings?.logo))}" alt="الشعار" /></div>` : ''}
  <h1>${settings?.business_name || ''}</h1>
  ${settings?.commercial_registration ? `<div class="sub">السجل التجاري: ${esc(settings.commercial_registration)}</div>` : ''}
  <div class="sub">${title}</div>
  <div class="meta">
    <span>رقم الإيصال: <b>${invoiceNo}</b></span>
    <span>الموظف: <b>${session.employee_name}</b></span>
    <span>الفرع: <b>${session.branch_name}</b></span>
    <span>التاريخ: <b>${dateOnly(session.opened_at)} ${timeOnly(session.opened_at)}</b></span>
    <span>عدد البنود: <b>${session.items.length}</b></span>
    ${settings?.receipt_show_phone && settings?.business_phone ? `<span>الهاتف: <b>${settings.business_phone}</b></span>` : ''}
    ${settings?.business_address ? `<span>العنوان: <b>${settings.business_address}</b></span>` : ''}
  </div>
  ${
    session.items.length === 0
      ? '<p style="text-align:center;color:#6b7280;padding:20px">لا توجد بنود</p>'
      : `<table>
        <thead><tr><th>القماش</th><th>النوع</th><th>الكمية</th><th>الياردات</th><th>سعر الوحدة</th><th>الخصم</th><th>الدفع</th><th>الإجمالي</th></tr></thead>
        <tbody>${rowsHtml}</tbody>
      </table>`
  }
  <div class="totals">
    <div>كاش: <b>${num(session.totals.cash)} ${sym}</b></div>
    <div>تحويل: <b>${num(session.totals.transfer)} ${sym}</b></div>
    <div>ماكينة: <b>${num(session.totals.card)} ${sym}</b></div>
    <div>ياردات: <b>${num(session.totals.yards)}</b></div>
  </div>
  ${showTax ? `<div class="totals"><div>ضريبة (${taxRate}%): <b>${num(taxAmount)} ${sym}</b></div></div>` : ''}
  <div class="grand">الإجمالي${showTax ? ' (شامل الضريبة)' : ''}: ${num(grandTotal)} ${sym}</div>
  ${
    settings?.receipt_footer
      ? `<div class="footer">${settings.receipt_footer.split('\n').map((l) => `${l}<br />`).join('')}</div>`
      : ''
  }
  <script>setTimeout(() => window.print(), 200);</script>
</body>
</html>`;
}

export function printSessionReceipt(session: SaleSession, settings: AppSettings | null, title: string): boolean {
  const win = window.open('', '_blank', 'width=900,height=700');
  if (!win) return false;
  win.document.open();
  win.document.write(buildSessionReceipt(session, settings, title));
  win.document.close();
  return true;
}