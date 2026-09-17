import { AppSettings, DailySale, SaleSession, SessionSaleItem } from '@/types';
import { formatNumber, formatDate } from '@/lib/format';
import { logoUrl } from '@/services/settings';

const sym = (settings: AppSettings | null) => settings?.currency_symbol || '';

const num = (v: number | string) => formatNumber(Number(v));

function esc(v: string | number | null | undefined): string {
  return String(v ?? '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

const PAY_NAMES: Record<string, string> = { cash: 'كاش', transfer: 'تحويل', card: 'بطاقة', other: 'أخرى' };

function saleNumber(invoicePrefix: string, sale: DailySale): string {
  return `${invoicePrefix}${sale.id}`;
}

const UNITS = ['', 'واحد', 'اثنان', 'ثلاثة', 'أربعة', 'خمسة', 'ستة', 'سبعة', 'ثمانية', 'تسعة'];
const TEENS = ['عشرة', 'أحد عشر', 'اثنا عشر', 'ثلاثة عشر', 'أربعة عشر', 'خمسة عشر', 'ستة عشر', 'سبعة عشر', 'ثمانية عشر', 'تسعة عشر'];
const TENS = ['', '', 'عشرون', 'ثلاثون', 'أربعون', 'خمسون', 'ستون', 'سبعون', 'ثمانون', 'تسعون'];
const HUNDREDS = ['', 'مائة', 'مائتان', 'ثلاثمائة', 'أربعمائة', 'خمسمائة', 'ستمائة', 'سبعمائة', 'ثمانمائة', 'تسعمائة'];

function below1000(n: number): string {
  const h = Math.floor(n / 100);
  const r = n % 100;
  const parts: string[] = [];
  if (h) parts.push(HUNDREDS[h]);
  if (r) {
    if (r < 10) parts.push(UNITS[r]);
    else if (r < 20) parts.push(TEENS[r - 10]);
    else {
      const u = r % 10;
      if (u) parts.push(UNITS[u]);
      parts.push(TENS[Math.floor(r / 10)]);
    }
  }
  return parts.join(' و');
}

export function arabicWords(amount: number): string {
  if (!Number.isFinite(amount)) return '';
  if (amount === 0) return 'صفر';
  const scales = [
    { factor: 1000000000, single: 'مليار', dual: 'ملياران', plural310: 'مليارات', plural11: 'مليار' },
    { factor: 1000000, single: 'مليون', dual: 'مليونان', plural310: 'ملايين', plural11: 'مليون' },
    { factor: 1000, single: 'ألف', dual: 'ألفان', plural310: 'آلاف', plural11: 'ألف' },
  ];
  let remaining = Math.abs(Math.floor(amount));
  const parts: string[] = [];
  for (const s of scales) {
    const count = Math.floor(remaining / s.factor);
    if (count) {
      if (count === 1) parts.push(s.single);
      else if (count === 2) parts.push(s.dual);
      else if (count <= 10) parts.push(`${below1000(count)} ${s.plural310}`);
      else parts.push(`${below1000(count)} ${s.plural11}`);
      remaining -= count * s.factor;
    }
  }
  if (remaining) parts.push(below1000(remaining));
  return parts.join(' و');
}

export function englishWords(amount: number): string {
  if (!Number.isFinite(amount)) return '';
  if (amount === 0) return 'Zero';
  const ones = ['zero', 'one', 'two', 'three', 'four', 'five', 'six', 'seven', 'eight', 'nine', 'ten', 'eleven', 'twelve', 'thirteen', 'fourteen', 'fifteen', 'sixteen', 'seventeen', 'eighteen', 'nineteen'];
  const tens = ['', '', 'twenty', 'thirty', 'forty', 'fifty', 'sixty', 'seventy', 'eighty', 'ninety'];
  const below100 = (n: number): string => {
    if (n < 20) return ones[n];
    const t = Math.floor(n / 10);
    const u = n % 10;
    return u ? `${tens[t]}-${ones[u]}` : tens[t];
  };
  const below1000 = (n: number): string => {
    const h = Math.floor(n / 100);
    const r = n % 100;
    if (!h) return below100(r);
    const tail = r ? ` ${below100(r)}` : '';
    return `${ones[h]} hundred${tail}`;
  };
  const scales = [
    { factor: 1000000000, word: 'billion' },
    { factor: 1000000, word: 'million' },
    { factor: 1000, word: 'thousand' },
  ];
  let remaining = Math.abs(Math.floor(amount));
  const parts: string[] = [];
  for (const s of scales) {
    const count = Math.floor(remaining / s.factor);
    if (count) {
      parts.push(`${below1000(count)} ${s.word}${count > 1 ? 's' : ''}`);
      remaining -= count * s.factor;
    }
  }
  if (remaining) parts.push(below1000(remaining));
  const text = parts.join(' ');
  return text.charAt(0).toUpperCase() + text.slice(1);
}

const round2 = (v: number) => Math.round(v * 100) / 100;

export function sessionToDailySales(session: SaleSession): DailySale[] {
  if (session.is_manual) {
    const cash = Number(session.manual_cash) || 0;
    const transfer = Number(session.manual_transfer) || 0;
    const card = Number(session.manual_card) || 0;
    const total = round2(cash + transfer + card);
    return [{
      id: 0,
      branch: session.branch,
      branch_name: session.branch_name,
      employee: session.employee,
      employee_name: session.employee_name,
      date: session.manual_date || '',
      total_sales: total,
      cash_amount: round2(cash),
      transfer_amount: round2(transfer),
      card_amount: round2(card),
      other_amount: 0,
      notes: session.notes || '',
      payment_total: total,
      mismatch: false,
      items: [],
      created_at: '',
      updated_at: '',
    }];
  }
  const byDate = new Map<string, DailySale>();
  for (const it of session.items) {
    const date = it.sale_date;
    let sale = byDate.get(date);
    if (!sale) {
      sale = {
        id: 0,
        branch: session.branch,
        branch_name: session.branch_name,
        employee: session.employee,
        employee_name: session.employee_name,
        date,
        total_sales: 0,
        cash_amount: 0,
        transfer_amount: 0,
        card_amount: 0,
        other_amount: 0,
        notes: session.notes || '',
        payment_total: 0,
        mismatch: false,
        items: [],
        created_at: '',
        updated_at: '',
      };
      byDate.set(date, sale);
    }
    const t = Number(it.total) || 0;
    sale.total_sales += t;
    sale.payment_total += t;
    if (it.payment_method === 'cash') sale.cash_amount += t;
    else if (it.payment_method === 'transfer') sale.transfer_amount += t;
    else if (it.payment_method === 'card') sale.card_amount += t;
    else sale.other_amount += t;
    sale.items.push({
      id: it.id,
      fabric: it.fabric,
      fabric_name: it.fabric_name,
      fabric_unit: it.fabric_unit,
      yards: Number(it.yards_effective ?? it.quantity) || 0,
      unit_price: it.unit_price != null ? Number(it.unit_price) : null,
    });
  }
  return Array.from(byDate.values()).map((s) => ({
    ...s,
    total_sales: round2(s.total_sales),
    payment_total: round2(s.payment_total),
    cash_amount: round2(s.cash_amount),
    transfer_amount: round2(s.transfer_amount),
    card_amount: round2(s.card_amount),
    other_amount: round2(s.other_amount),
  }));
}

export function buildSalesInvoice(
  sales: DailySale[],
  settings: AppSettings | null,
  opts: { title?: string; autoPrint?: boolean } = {}
): string {
  const title = opts.title || `فاتورة ${sales.length > 1 ? 'مجمعة' : 'بيع'}`;
  const prefix = settings?.invoice_prefix || '';
  const taxRate = Number(settings?.tax_rate ?? 0);
  const showTax = !!settings?.receipt_show_tax;
  const totalOfSales = sales.reduce((sum, s) => sum + Number(s.total_sales), 0);
  const taxAmount = showTax && taxRate > 0 ? Math.round((totalOfSales * (taxRate / 100)) * 100) / 100 : 0;
  const grandTotal = Math.round((totalOfSales + taxAmount) * 100) / 100;
  const cash = sales.reduce((s, x) => s + Number(x.cash_amount), 0);
  const transfer = sales.reduce((s, x) => s + Number(x.transfer_amount), 0);
  const card = sales.reduce((s, x) => s + Number(x.card_amount), 0);
  const other = sales.reduce((s, x) => s + Number(x.other_amount), 0);
  const decimalPlaces = settings?.decimal_places ?? 2;
  const wordsScale = Math.pow(10, decimalPlaces);
  const wordsFrac = Math.round((grandTotal - Math.floor(grandTotal)) * wordsScale);

  const flatRows = sales
    .flatMap((s) => {
      if (s.items.length === 0) {
        return [`<tr><td>${esc(saleNumber(prefix, s))}</td><td>${esc(s.date)}</td><td class="empty" colspan="4">لا توجد أصناف</td></tr>`];
      }
      return s.items.map((it) => {
        const unitPrice = it.unit_price;
        const lineTotal = unitPrice != null ? unitPrice * Number(it.yards) : null;
        return `<tr>
        <td>${esc(saleNumber(prefix, s))}</td>
        <td>${esc(s.date)}</td>
        <td>${esc(it.fabric_name)}</td>
        <td class="num">${num(it.yards)}</td>
        <td class="num">${unitPrice != null ? num(unitPrice) : '—'}</td>
        <td class="num">${lineTotal != null ? num(lineTotal) : '—'}</td>
      </tr>`;
      });
    })
    .join('');

  const singleSections = sales
    .map((s) => {
      const rows = s.items
        .map((it) => {
          const unitPrice = it.unit_price;
          const lineTotal = unitPrice != null ? unitPrice * Number(it.yards) : null;
          return `<tr>
        <td>${esc(it.fabric_name)}</td>
        <td class="num">${num(it.yards)}</td>
        <td class="num">${unitPrice != null ? num(unitPrice) : '—'}</td>
        <td class="num">${lineTotal != null ? num(lineTotal) : '—'}</td>
      </tr>`;
        })
        .join('');
      return `
    <div class="sale">
      <h3 class="sec">${sales.length > 1 ? `${esc(saleNumber(prefix, s))} — ${esc(s.date)}` : esc(saleNumber(prefix, s))}</h3>
      <p class="sale-meta">
        التاريخ: <b>${esc(s.date)}</b> · الفرع: <b>${esc(s.branch_name)}</b>${s.employee_name ? ` · الموظف: <b>${esc(s.employee_name)}</b>` : ''}
      </p>
      <table>
        <thead><tr><th>القماش</th><th>الياردات</th><th>سعر الوحدة</th><th>الإجمالي</th></tr></thead>
        <tbody>${rows || '<tr><td colspan="4" class="empty">لا توجد أصناف</td></tr>'}</tbody>
        <tfoot>
          <tr><td colspan="3">إجمالي البيعة</td><td class="num">${num(s.total_sales)} ${sym(settings)}</td></tr>
        </tfoot>
      </table>
      <div class="pmt">
        <span>كاش: <b>${num(s.cash_amount)} ${sym(settings)}</b></span>
        <span>تحويل: <b>${num(s.transfer_amount)} ${sym(settings)}</b></span>
        <span>بطاقة: <b>${num(s.card_amount)} ${sym(settings)}</b></span>
        <span>أخرى: <b>${num(s.other_amount)} ${sym(settings)}</b></span>
      </div>
    </div>`;
    })
    .join('');

  const body = sales.length > 1
    ? `<div class="sale">
      <h3 class="sec">جميع البنود</h3>
      <table>
        <thead><tr><th>رقم الفاتورة</th><th>التاريخ</th><th>القماش</th><th>الياردات</th><th>سعر الوحدة</th><th>الإجمالي</th></tr></thead>
        <tbody>${flatRows || '<tr><td colspan="6" class="empty">لا توجد بنود</td></tr>'}</tbody>
        <tfoot>
          <tr><td colspan="5">إجمالي بيوعات الفواتير المختارة</td><td class="num">${num(totalOfSales)} ${sym(settings)}</td></tr>
        </tfoot>
      </table>
    </div>`
    : singleSections;

  const logo = logoUrl(settings?.logo);

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
  .sale { margin-bottom: 18px; }
  .sec { font-size: 13px; margin: 0 0 4px; color: #111827; }
  .sale-meta { font-size: 12px; color: #6b7280; margin: 0 0 6px; }
  table { width: 100%; border-collapse: collapse; font-size: 12px; }
  th, td { border: 1px solid #d1d5db; padding: 6px 8px; text-align: right; }
  th { background: #f3f4f6; font-weight: 600; }
  tfoot td { font-weight: 700; background: #f9fafb; }
  .num { text-align: left; font-variant-numeric: tabular-nums; white-space: nowrap; }
  .empty { text-align: center; color: #9ca3af; }
  .pmt { display: flex; flex-wrap: wrap; gap: 6px 18px; font-size: 12px; margin-top: 8px; color: #374151; }
  .totals { border-top: 2px solid #111827; margin-top: 18px; padding-top: 10px; font-size: 13px; }
  .totals div { display: inline-flex; gap: 8px; margin-left: 22px; }
  .words { font-size: 13px; margin-top: 10px; color: #374151; }
  .grand { font-size: 16px; font-weight: 700; margin-top: 8px; }
  .notes { margin-top: 22px; padding: 10px 12px; background: #f9fafb; border: 1px dashed #d1d5db; border-radius: 6px; font-size: 12px; color: #374151; }
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
        <span>عدد الفواتير: <b>${sales.length}</b></span>
        ${sales.length === 1 ? `<span>رقم الفاتورة: <b>${esc(saleNumber(prefix, sales[0]))}</b></span>` : `<span>أرقام الفواتير: <b>${esc(sales.map((s) => saleNumber(prefix, s)).join('، '))}</b></span>`}
        <span>التاريخ: <b>${esc(formatDate(new Date().toISOString()))}</b></span>
      </div>
    </div>
  </div>

  ${body}

  <div class="totals">
    <div>كاش: <b>${num(cash)} ${sym(settings)}</b></div>
    <div>تحويل: <b>${num(transfer)} ${sym(settings)}</b></div>
    <div>بطاقة: <b>${num(card)} ${sym(settings)}</b></div>
    <div>أخرى: <b>${num(other)} ${sym(settings)}</b></div>
  </div>
  ${showTax ? `<div class="totals"><div>ضريبة (${taxRate}%): <b>${num(taxAmount)} ${sym(settings)}</b></div></div>` : ''}
  <div class="words">المبلغ كتابةً: <b>${esc(arabicWords(grandTotal))}${wordsFrac > 0 ? ` و${wordsFrac}/${wordsScale}` : ''} ${esc(settings?.currency_code || '')}</b></div>
  <div class="grand">الإجمالي${showTax ? ' (شامل الضريبة)' : ''}: ${num(grandTotal)} ${sym(settings)}</div>

  ${settings?.invoice_notes ? `<div class="notes">${esc(settings.invoice_notes)}</div>` : ''}

  <div class="sig">
    <div>توقيع البائع</div>
    <div>توقيع الزبون</div>
  </div>

  ${
    settings?.receipt_footer
      ? `<div class="footer">${esc(settings.receipt_footer)}</div>`
      : '<div class="footer">شكراً لتعاملكم معنا</div>'
  }
  ${opts.autoPrint ? '<script>setTimeout(function(){ window.print(); }, 300);</script>' : ''}
</body>
</html>`;
}

export function openSalesInvoice(
  sales: DailySale[],
  settings: AppSettings | null,
  opts: { title?: string; autoPrint?: boolean; showPayments?: boolean } = {}
): boolean {
  if (!sales || sales.length === 0) return false;
  const win = window.open('', '_blank', 'width=900,height=700');
  if (!win) return false;
  win.document.open();
  win.document.write(buildSalesInvoice(sales, settings, opts));
  win.document.close();
  return true;
}

export function openHtmlInvoice(html: string): boolean {
  const win = window.open('', '_blank', 'width=900,height=700');
  if (!win) return false;
  win.document.open();
  win.document.write(html);
  win.document.close();
  return true;
}

const SEL_INVOICE_STYLES = `<style>
  * { box-sizing: border-box; }
  body { font-family: "Segoe UI", Tahoma, Arial, sans-serif; color: #1f2937; margin: 0; padding: 24px; }
  .head { display: flex; align-items: flex-start; justify-content: space-between; gap: 16px; border-bottom: 2px solid #111827; padding-bottom: 14px; margin-bottom: 16px; }
  .head .store { display: flex; gap: 10px; align-items: center; }
  .head img { max-height: 64px; max-width: 96px; }
  h1 { font-size: 21px; margin: 0; }
  .sub { color: #6b7280; font-size: 12px; margin-top: 2px; }
  .doc { text-align: right; }
  .doc h2 { font-size: 18px; margin: 0 0 4px; }
  .doc .meta { color: #374151; font-size: 12px; }
  .doc .meta span { display: block; margin-top: 2px; }
  table { width: 100%; border-collapse: collapse; font-size: 12px; }
  th, td { border: 1px solid #d1d5db; padding: 6px 8px; text-align: left; }
  th { background: #f3f4f6; font-weight: 600; }
  tfoot td { font-weight: 700; background: #f9fafb; }
  .num { text-align: left; font-variant-numeric: tabular-nums; white-space: nowrap; }
  .empty { text-align: center; color: #9ca3af; }
  .pmt { display: flex; flex-wrap: wrap; gap: 6px 18px; font-size: 12px; margin-top: 8px; color: #374151; }
  .totals { border-top: 2px solid #111827; margin-top: 18px; padding-top: 10px; font-size: 13px; }
  .totals div { display: inline-flex; gap: 8px; margin-left: 22px; }
  .words { font-size: 13px; margin-top: 10px; color: #374151; }
  .grand { font-size: 16px; font-weight: 700; margin-top: 8px; }
  .notes { margin-top: 22px; padding: 10px 12px; background: #f9fafb; border: 1px dashed #d1d5db; border-radius: 6px; font-size: 12px; color: #374151; }
  .footer { margin-top: 26px; color: #6b7280; font-size: 12px; text-align: center; border-top: 1px dashed #d1d5db; padding-top: 12px; }
  .sig { display: flex; justify-content: space-between; margin-top: 44px; padding: 0 12px; }
  .sig div { text-align: center; width: 45%; border-top: 1px solid #9ca3af; padding-top: 6px; font-size: 11px; color: #6b7280; }
  @media print { body { -webkit-print-color-adjust: exact; print-color-adjust: exact; } }
</style>`;

function enDate(d: Date = new Date()): string {
  return d.toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' });
}

export function buildSessionItemsInvoice(
  items: SessionSaleItem[],
  session: SaleSession,
  settings: AppSettings | null,
  opts: { title?: string; invoiceNo?: string; customerName?: string; customerPhone?: string; autoPrint?: boolean } = {}
): string {
  const title = opts.title || 'INVOICE';
  const prefix = settings?.invoice_prefix || '';
  const invoiceNo = opts.invoiceNo || `${prefix}${session.id}`;
  const customerName = (opts.customerName || '').trim();
  const customerPhone = (opts.customerPhone || '').trim();
  const taxRate = Number(settings?.tax_rate ?? 0);
  const showTax = !!settings?.receipt_show_tax;

  const total = round2(items.reduce((s, i) => s + Number(i.total), 0));
  const yards = round2(items.reduce((s, i) => s + Number(i.yards_effective ?? i.quantity), 0));
  const taxAmount = showTax && taxRate > 0 ? round2(total * (taxRate / 100)) : 0;
  const grandTotal = round2(total + taxAmount);

  const decimalPlaces = settings?.decimal_places ?? 2;
  const wordsScale = Math.pow(10, decimalPlaces);
  const wordsFrac = Math.round((grandTotal - Math.floor(grandTotal)) * wordsScale);

  const rows = items
    .map(
      (it, idx) => `<tr>
        <td class="num">${idx + 1}</td>
        <td>${esc(it.fabric_name)}</td>
        <td>${it.sale_type === 'roll' ? 'Roll' : 'Yard'}</td>
        <td class="num">${num(it.quantity)} ${it.sale_type === 'roll' ? 'roll(s)' : 'yard(s)'}</td>
        <td class="num">${num(it.yards_effective ?? it.quantity)}</td>
        <td class="num">${num(it.unit_price)}</td>
        <td class="num">${it.discount_amount > 0 ? num(it.discount_amount) : '—'}</td>
        <td class="num">${num(it.total)} ${sym(settings)}</td>
      </tr>`
    )
    .join('');

  const logo = logoUrl(settings?.logo);

  return `<!doctype html>
<html dir="ltr" lang="en">
<head>
<meta charset="utf-8" />
<title>${esc(title)}</title>
${SEL_INVOICE_STYLES}
</head>
<body>
  <div class="head">
    <div class="store">
      ${logo ? `<img src="${esc(logo)}" alt="logo" />` : ''}
      <div>
        <h1>${esc(settings?.business_name || '')}</h1>
        ${settings?.trade_name ? `<div class="sub">${esc(settings.trade_name)}</div>` : ''}
        ${settings?.commercial_registration ? `<div class="sub">CR. Nu.: ${esc(settings.commercial_registration)}</div>` : ''}
        ${settings?.business_address ? `<div class="sub">${esc(settings.business_address)}</div>` : ''}
        ${settings?.business_phone ? `<div class="sub" dir="ltr">${esc(settings.business_phone)}</div>` : ''}
        ${settings?.business_email ? `<div class="sub" dir="ltr">${esc(settings.business_email)}</div>` : ''}
        ${settings?.tax_number ? `<div class="sub">Tax No.: ${esc(settings.tax_number)}</div>` : ''}
      </div>
    </div>
    <div class="doc">
      <h2>${esc(title)}</h2>
      <div class="meta">
        <span>Invoice No.: <b>${esc(invoiceNo)}</b></span>
        <span>Customer: <b>${esc(customerName || 'Cash customer')}</b></span>
        ${customerPhone ? `<span>Phone: <b dir="ltr">${esc(customerPhone)}</b></span>` : ''}
        <span>Employee: <b>${esc(session.employee_name)}</b> · Branch: <b>${esc(session.branch_name)}</b></span>
        <span>Date: <b>${esc(enDate())}</b></span>
        <span>Items: <b>${items.length}</b></span>
      </div>
    </div>
  </div>

  ${
    items.length === 0
      ? '<p style="text-align:center;color:#6b7280;padding:20px">No items selected</p>'
      : `<table>
        <thead><tr><th>#</th><th>Fabric</th><th>Type</th><th>Quantity</th><th>Yards</th><th>Unit Price</th><th>Discount</th><th>Amount</th></tr></thead>
        <tbody>${rows}</tbody>
      </table>`
  }

  ${items.length > 0 ? `<div class="totals"><div>Total Yards: <b>${num(yards)}</b></div></div>` : ''}
  <div class="totals"><div>Subtotal: <b>${num(total)} ${sym(settings)}</b></div></div>
  ${showTax ? `<div class="totals"><div>VAT (${taxRate}%): <b>${num(taxAmount)} ${sym(settings)}</b></div></div>` : ''}
  <div class="words">Amount in words: <b>${esc(englishWords(grandTotal))}${wordsFrac > 0 ? ` and ${wordsFrac}/${wordsScale}` : ''} ${esc(settings?.currency_code || '')}</b></div>
  <div class="grand">Grand Total${showTax ? ' (incl. VAT)' : ''}: ${num(grandTotal)} ${sym(settings)}</div>

  ${settings?.invoice_notes ? `<div class="notes">${esc(settings.invoice_notes)}</div>` : ''}

  <div class="sig">
    <div>Seller's signature</div>
    <div>Customer's signature</div>
  </div>

  ${
    settings?.receipt_footer
      ? `<div class="footer">${esc(settings.receipt_footer)}</div>`
      : '<div class="footer">Thank you for your business</div>'
  }
  ${opts.autoPrint ? '<script>setTimeout(function(){ window.print(); }, 300);</script>' : ''}
</body>
</html>`;
}