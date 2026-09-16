import { AppSettings, LedgerEntry, LedgerSummary, Supplier, SuppliersOverview } from '@/types';
import { formatNumber, formatDate } from '@/lib/format';
import { logoUrl } from '@/services/settings';

const sym = (settings: AppSettings | null) => settings?.currency_symbol || '';

const num = (v: number | string) => formatNumber(Number(v));

function esc(v: string | number | null | undefined): string {
  return String(v ?? '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

const TYPE_CLASS: Record<string, string> = {
  opening: 'type-open',
  purchase: 'type-purchase',
  payment: 'type-payment',
  return: 'type-return',
  adjustment: 'type-adjustment',
};

function stats(label: string, value: string, sub?: string): string {
  return `
    <div class="stat">
      <div class="stat-val">${value}</div>
      <div class="stat-label">${esc(label)}${sub ? `<span class="stat-sub">${esc(sub)}</span>` : ''}</div>
    </div>`;
}

function entryDetails(e: LedgerEntry, settings: AppSettings | null): string {
  const parts: string[] = [];
  if (e.receipt_no) parts.push(`<span class="det">فاتورة: <b>${esc(e.receipt_no)}</b></span>`);
  if (e.destination_name) parts.push(`<span class="det">التوريد: <b>${esc(e.destination_name)}</b></span>`);
  if (e.payment_method_label) {
    parts.push(`<span class="det">الدفع: <b>${esc(e.payment_method_label)}</b>${e.bank_reference ? ` (مرجع: ${esc(e.bank_reference)})` : ''}</span>`);
  }
  if (e.receiver_name) parts.push(`<span class="det">المستلم: <b>${esc(e.receiver_name)}</b></span>`);
  if (e.goods_receipt_number) parts.push(`<span class="det">تم الاستلام (${esc(e.goods_receipt_number)})</span>`);
  return parts.length ? `<div class="dets">${parts.join('')}</div>` : '';
}

function entryItems(e: LedgerEntry, settings: AppSettings | null): string {
  if (!e.items || e.items.length === 0) return '';
  const rows = e.items
    .map(
      (it) => `<tr>
        <td>${esc(it.fabric_name)}</td>
        <td class="num">${num(it.quantity_yards)}</td>
        <td class="num">${it.rolls ? num(it.rolls) : '—'}</td>
        <td class="num">${num(it.unit_price)} ${sym(settings)}</td>
        <td class="num">${num(it.total)} ${sym(settings)}</td>
        <td>${it.destination_name ? `${it.destination_type === 'branch' ? 'فرع' : 'مخزن'}: ${esc(it.destination_name)}` : '—'}</td>
      </tr>`
    )
    .join('');
  return `
    <tr>
      <td colspan="5" class="items-cell">
        <div class="items-head">تفاصيل الفاتورة</div>
        <table class="items">
          <thead><tr><th>القماش</th><th>الكمية (ياردة)</th><th>عدد اللفات</th><th>سعر الياردة</th><th>الإجمالي</th><th>الوجهة</th></tr></thead>
          <tbody>${rows}</tbody>
        </table>
      </td>
    </tr>`;
}

function docShell(title: string, settings: AppSettings | null, content: string, autoPrint: boolean): string {
  const logo = logoUrl(settings?.logo);
  const dateStr = esc(formatDate(new Date().toISOString()));
  return `<!doctype html>
<html dir="rtl" lang="ar">
<head>
<meta charset="utf-8" />
<title>${esc(title)}</title>
<style>
  * { box-sizing: border-box; }
  body { font-family: "Segoe UI", Tahoma, Arial, sans-serif; color: #1f2937; margin: 0; padding: 24px; }
  .head { display: flex; align-items: flex-start; justify-content: space-between; gap: 16px; border-bottom: 2px solid #111827; padding-bottom: 14px; margin-bottom: 16px; }
  .head .store { display: flex; gap: 10px; align-items: center; }
  .head img { max-height: 64px; max-width: 96px; }
  h1 { font-size: 21px; margin: 0; }
  .sub { color: #6b7280; font-size: 12px; margin-top: 2px; }
  .doc { text-align: left; }
  .doc h2 { font-size: 18px; margin: 0 0 4px; }
  .doc .meta { color: #374151; font-size: 12px; }
  .doc .meta span { display: block; margin-top: 2px; }
  .party { border: 1px solid #d1d5db; border-radius: 8px; padding: 10px 12px; margin-bottom: 12px; display: flex; justify-content: space-between; gap: 12px; flex-wrap: wrap; }
  .party .half { font-size: 12px; }
  .party .half .k { color: #6b7280; }
  .stats { display: grid; grid-template-columns: repeat(5, 1fr); gap: 8px; margin-bottom: 14px; }
  .stat { border: 1px solid #e5e7eb; border-radius: 8px; padding: 8px 10px; background: #f9fafb; }
  .stat-val { font-size: 13px; font-weight: 700; font-variant-numeric: tabular-nums; white-space: nowrap; }
  .stat-label { font-size: 11px; color: #6b7280; margin-top: 2px; }
  .stat-sub { display: block; color: #9ca3af; }
  table { width: 100%; border-collapse: collapse; font-size: 12px; }
  th, td { border: 1px solid #d1d5db; padding: 6px 8px; text-align: right; }
  th { background: #f3f4f6; font-weight: 600; }
  tfoot td { font-weight: 700; background: #f9fafb; }
  .num { text-align: left; font-variant-numeric: tabular-nums; white-space: nowrap; }
  .empty { text-align: center; color: #9ca3af; padding: 18px; }
  .badge { display: inline-block; padding: 2px 8px; border-radius: 999px; font-size: 11px; font-weight: 600; }
  .type-open, .type-adjustment { background: #f3f4f6; color: #374151; }
  .type-purchase { background: #fef3c7; color: #92400e; }
  .type-payment { background: #d1fae5; color: #065f46; }
  .type-return { background: #fee2e2; color: #991b1b; }
  .desc { margin-top: 4px; color: #374151; }
  .dets { margin-top: 4px; display: flex; flex-wrap: wrap; gap: 2px 14px; }
  .det { color: #6b7280; font-size: 11px; }
  .items-cell { background: #faf9f6; padding: 8px !important; }
  .items-head { font-size: 11px; color: #6b7280; margin-bottom: 6px; }
  table.items th, table.items td { border-color: #e5e7eb; background: #fff; padding: 5px 7px; }
  .summary-line { margin-top: 14px; font-size: 13px; }
  .footer { margin-top: 26px; color: #6b7280; font-size: 12px; text-align: center; border-top: 1px dashed #d1d5db; padding-top: 12px; }
  .sig { display: flex; justify-content: space-between; margin-top: 44px; padding: 0 12px; }
  .sig div { text-align: center; width: 45%; border-top: 1px solid #9ca3af; padding-top: 6px; font-size: 11px; color: #6b7280; }
  @media print { body { -webkit-print-color-adjust: exact; print-color-adjust: exact; } }
</style>
</head>
<body>
  <div class="head">
    <div class="store">
      ${logo ? `<img src="${esc(logo)}" alt="الشعار" />` : ''}
      <div>
        <h1>${esc(settings?.business_name || '')}</h1>
        ${settings?.trade_name ? `<div class="sub">${esc(settings.trade_name)}</div>` : ''}
        ${settings?.commercial_registration ? `<div class="sub">السجل التجاري: ${esc(settings.commercial_registration)}</div>` : ''}
        ${settings?.business_address ? `<div class="sub">${esc(settings.business_address)}</div>` : ''}
        ${settings?.business_phone ? `<div class="sub" dir="ltr">${esc(settings.business_phone)}</div>` : ''}
        ${settings?.business_email ? `<div class="sub" dir="ltr">${esc(settings.business_email)}</div>` : ''}
        ${settings?.tax_number ? `<div class="sub">الرقم الضريبي: ${esc(settings.tax_number)}</div>` : ''}
      </div>
    </div>
    <div class="doc">
      <h2>${esc(title)}</h2>
      <div class="meta">
        <span>تاريخ التقرير: <b>${dateStr}</b></span>
      </div>
    </div>
  </div>

  ${content}

  <div class="sig">
    <div>توقيع المورد</div>
    <div>الختم</div>
  </div>

  ${
    settings?.receipt_footer
      ? `<div class="footer">${esc(settings.receipt_footer)}</div>`
      : '<div class="footer">شكراً لتعاملكم معنا</div>'
  }
  ${autoPrint ? '<script>setTimeout(function(){ window.print(); }, 300);</script>' : ''}
</body>
</html>`;
}

export function buildSupplierReport(
  supplier: Supplier,
  entries: LedgerEntry[],
  summary: LedgerSummary,
  settings: AppSettings | null,
  opts: { title?: string; autoPrint?: boolean } = {}
): string {
  const title = opts.title || 'كشف حساب مورد';
  const debit = entries.reduce((s, e) => s + (Number(e.debit) || 0), 0);
  const credit = entries.reduce((s, e) => s + (Number(e.credit) || 0), 0);
  const rows =
    entries.length === 0
      ? '<tr><td colspan="5" class="empty">لا توجد قيود مسجلة لهذا المورد</td></tr>'
      : entries
          .map(
            (e) => `
          <tr>
            <td class="num">${esc(formatDate(e.date))}</td>
            <td>
              <span class="badge ${TYPE_CLASS[e.entry_type] || 'type-open'}">${esc(e.entry_type_label)}</span>
              ${e.description ? `<div class="desc">${esc(e.description)}</div>` : ''}
              ${entryDetails(e, settings)}
            </td>
            <td class="num">${e.debit ? num(e.debit) : '—'}</td>
            <td class="num">${e.credit ? num(e.credit) : '—'}</td>
            <td class="num">${e.running_balance != null ? num(e.running_balance) : '—'}</td>
          </tr>
          ${entryItems(e, settings)}`
          )
          .join('');

  const content = `
  <div class="party">
    <div class="half">
      <div><span class="k">المورد: </span><b>${esc(supplier.name)}</b></div>
      ${supplier.company_name ? `<div><span class="k">الشركة: </span>${esc(supplier.company_name)}</div>` : ''}
      ${supplier.city ? `<div><span class="k">المدينة: </span>${esc(supplier.city)}</div>` : ''}
    </div>
    <div class="half">
      ${supplier.phone ? `<div><span class="k">الهاتف: </span><span dir="ltr">${esc(supplier.phone)}</span></div>` : ''}
      ${supplier.email ? `<div><span class="k">البريد: </span><span dir="ltr">${esc(supplier.email)}</span></div>` : ''}
      ${supplier.tax_number ? `<div><span class="k">الرقم الضريبي: </span>${esc(supplier.tax_number)}</div>` : ''}
    </div>
  </div>

  <div class="stats">
    ${stats('رصيد افتتاحي', `${num(summary.opening_balance)} ${sym(settings)}`)}
    ${stats('إجمالي المشتريات', `${num(summary.total_purchases)} ${sym(settings)}`, `${summary.purchases_count} فاتورة`)}
    ${stats('إجمالي الدفعات', `${num(summary.total_payments)} ${sym(settings)}`, `${summary.payments_count} دفعة`)}
    ${stats('المرتجعات', `${num(summary.total_returns)} ${sym(settings)}`, `${summary.returns_count} مرتجع`)}
    ${stats('الرصيد الحالي', `${num(summary.balance)} ${sym(settings)}`, summary.balance > 0 ? 'مستحق للمورد' : summary.balance < 0 ? 'مستحق لنا' : '')}
  </div>

  <table>
    <thead>
      <tr><th>التاريخ</th><th>البيان</th><th>مدين</th><th>دائن</th><th>الرصيد</th></tr>
    </thead>
    <tbody>${rows}</tbody>
    <tfoot>
      <tr><td colspan="2">إجمالي الحركة</td><td class="num">${num(debit)} ${sym(settings)}</td><td class="num">${num(credit)} ${sym(settings)}</td><td class="num">${num(summary.balance)} ${sym(settings)}</td></tr>
    </tfoot>
  </table>`;

  return docShell(title, settings, content, !!opts.autoPrint);
}

export function buildSuppliersOverviewReport(
  overview: SuppliersOverview,
  suppliers: Supplier[],
  settings: AppSettings | null,
  opts: { title?: string; autoPrint?: boolean } = {}
): string {
  const title = opts.title || 'تقرير الموردين';
  const rows =
    suppliers.length === 0
      ? '<tr><td colspan="5" class="empty">لا يوجد موردون</td></tr>'
      : suppliers
          .map(
            (s) => `<tr>
            <td><b>${esc(s.name)}</b>${s.company_name ? `<div class="desc">${esc(s.company_name)}</div>` : ''}</td>
            <td dir="ltr" style="text-align:right">${esc(s.phone || '—')}</td>
            <td>${esc(s.city || '—')}</td>
            <td>${esc(s.country || '—')}</td>
            <td class="num">${num(s.current_balance)} ${sym(settings)}</td>
          </tr>`
          )
          .join('');

  const content = `
  <div class="stats" style="grid-template-columns: repeat(5, 1fr);">
    ${stats('إجمالي الموردين', `${overview.total_suppliers}`, `${overview.active_count} نشط`)}
    ${stats('إجمالي المشتريات', `${num(overview.total_purchases)} ${sym(settings)}`, `${overview.purchases_count} فاتورة`)}
    ${stats('إجمالي الدفعات', `${num(overview.total_payments)} ${sym(settings)}`, `${overview.payments_count} دفعة`)}
    ${stats('المرتجعات', `${num(overview.total_returns)} ${sym(settings)}`, `${overview.returns_count} مرتجع`)}
    ${stats('المستحق للموردين', `${num(overview.outstanding_debit)} ${sym(settings)}`, `${overview.owing_count} مورد`)}
  </div>

  <table>
    <thead>
      <tr><th>المورد</th><th>الهاتف</th><th>المدينة</th><th>الدولة</th><th>الرصيد</th></tr>
    </thead>
    <tbody>${rows}</tbody>
  </table>

  ${
    overview.top_suppliers.length > 0
      ? `<div class="summary-line"><b>أعلى الموردين رصيداً:</b> ${overview.top_suppliers
          .map((t) => `${esc(t.name)} (${num(t.balance)} ${sym(settings)})`)
          .join('، ')}</div>`
      : ''
  }`;

  return docShell(title, settings, content, !!opts.autoPrint);
}

export function openSupplierReport(
  supplier: Supplier,
  entries: LedgerEntry[],
  summary: LedgerSummary,
  settings: AppSettings | null,
  opts: { title?: string; autoPrint?: boolean } = {}
): boolean {
  if (!supplier || entries.length === 0) return false;
  const win = window.open('', '_blank', 'width=900,height=700');
  if (!win) return false;
  win.document.open();
  win.document.write(buildSupplierReport(supplier, entries, summary, settings, opts));
  win.document.close();
  return true;
}

export function openSuppliersOverviewReport(
  overview: SuppliersOverview,
  suppliers: Supplier[],
  settings: AppSettings | null,
  opts: { title?: string; autoPrint?: boolean } = {}
): boolean {
  if (!overview || suppliers.length === 0) return false;
  const win = window.open('', '_blank', 'width=900,height=700');
  if (!win) return false;
  win.document.open();
  win.document.write(buildSuppliersOverviewReport(overview, suppliers, settings, opts));
  win.document.close();
  return true;
}