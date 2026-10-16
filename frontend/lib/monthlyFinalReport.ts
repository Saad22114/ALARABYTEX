import { AppSettings } from '@/types';
import { formatCurrency, formatDate } from '@/lib/format';
import { MonthlyFinalReport } from '@/services/accounting';
import { logoUrl } from '@/services/settings';

type MetricKey = 'sales' | 'expenses' | 'supplier_payments' | 'payroll' | 'net';

const METRICS: { key: MetricKey; label: string; positiveWhenUp: boolean }[] = [
  { key: 'sales', label: 'إجمالي المبيعات', positiveWhenUp: true },
  { key: 'expenses', label: 'إجمالي المصاريف', positiveWhenUp: false },
  { key: 'supplier_payments', label: 'مدفوعات الموردين', positiveWhenUp: false },
  { key: 'payroll', label: 'إجمالي الرواتب', positiveWhenUp: false },
  { key: 'net', label: 'صافي الشهر', positiveWhenUp: true },
];

function esc(value: unknown): string {
  return String(value ?? '').replace(/[&<>"']/g, (char) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
  })[char] || char);
}

function amount(value: number): string {
  return esc(formatCurrency(value));
}

function percentage(value: number, base: number): string {
  if (!base) return value ? 'جديد' : '—';
  const pct = ((value - base) / Math.abs(base)) * 100;
  const sign = pct > 0 ? '+' : '';
  return `${sign}${pct.toFixed(1)}%`;
}

export function buildMonthlyFinalReport(
  report: MonthlyFinalReport,
  settings: AppSettings | null,
  autoPrint = false,
): string {
  const previous = report.previous_month;
  const logo = logoUrl(settings?.logo);
  const incomeOutflow = report.expenses + report.supplier_payments + report.payroll;
  const netMargin = report.sales ? (report.net / report.sales) * 100 : 0;
  const outflowRatio = report.sales ? (incomeOutflow / report.sales) * 100 : 0;
  const rows = METRICS.map((metric) => {
    const current = report[metric.key];
    const before = previous[metric.key];
    const delta = current - before;
    const isGood = delta === 0 ? 'flat' : ((delta > 0) === metric.positiveWhenUp ? 'good' : 'bad');
    return `<tr>
      <td>${esc(metric.label)}</td>
      <td class="num">${amount(current)}</td>
      <td class="num">${amount(before)}</td>
      <td class="num ${isGood}">${delta > 0 ? '+' : ''}${amount(delta)}</td>
      <td class="trend ${isGood}">${percentage(current, before)}</td>
    </tr>`;
  }).join('');

  return `<!doctype html>
<html lang="ar" dir="rtl">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>التقرير الشهري النهائي ${esc(report.month)}</title>
  <style>
    :root { color-scheme: light; --ink:#172554; --muted:#64748b; --line:#dbe4f0; --blue:#1d4ed8; --pale:#eff6ff; }
    * { box-sizing: border-box; }
    body { margin:0; background:#eef2f7; color:#172033; font-family:Tahoma,Arial,sans-serif; }
    .toolbar { position:sticky; top:0; z-index:2; display:flex; justify-content:center; padding:12px; background:#172554; }
    .toolbar button { border:0; border-radius:9px; background:#fff; color:#172554; padding:10px 22px; font:700 14px Tahoma,Arial,sans-serif; cursor:pointer; }
    .page { width:210mm; min-height:297mm; margin:18px auto; padding:15mm 16mm 13mm; background:white; box-shadow:0 10px 35px #0f172a1c; }
    .header { display:flex; align-items:center; justify-content:space-between; gap:24px; padding-bottom:18px; border-bottom:3px solid var(--blue); }
    .company { display:flex; align-items:center; gap:15px; min-width:0; }
    .logo { width:82px; height:72px; object-fit:contain; }
    .brand h1 { color:var(--ink); margin:0; font-size:21px; }
    .brand .trade { margin-top:4px; color:var(--blue); font-size:13px; font-weight:700; }
    .details { display:flex; flex-wrap:wrap; gap:4px 14px; margin-top:8px; color:var(--muted); font-size:10px; }
    .details span { white-space:nowrap; }
    .report-title { text-align:left; min-width:150px; }
    .report-title .eyebrow { color:var(--blue); font-size:10px; font-weight:700; letter-spacing:.04em; }
    .report-title h2 { color:var(--ink); font-size:19px; margin:5px 0; }
    .report-title p { color:var(--muted); font-size:11px; margin:0; }
    .intro { margin:18px 0; padding:14px 16px; border-radius:12px; background:linear-gradient(110deg,#eff6ff,#f8fafc); border:1px solid #dbeafe; }
    .intro strong { display:block; font-size:14px; color:var(--ink); }
    .intro span { display:block; margin-top:5px; color:var(--muted); font-size:11px; line-height:1.8; }
    .kpis { display:grid; grid-template-columns:repeat(4,1fr); gap:9px; margin:14px 0 18px; }
    .kpi { border:1px solid var(--line); border-radius:11px; padding:12px; background:#fff; }
    .kpi .label { color:var(--muted); font-size:10px; }
    .kpi .value { margin-top:7px; color:var(--ink); font-size:16px; font-weight:800; font-variant-numeric:tabular-nums; white-space:nowrap; }
    .kpi .change { margin-top:5px; font-size:10px; font-weight:700; }
    .good { color:#15803d !important; } .bad { color:#b91c1c !important; } .flat { color:#64748b !important; }
    .section-title { display:flex; align-items:center; gap:8px; color:var(--ink); font-size:13px; margin:20px 0 9px; }
    .section-title:before { content:''; width:4px; height:15px; border-radius:3px; background:var(--blue); }
    table { width:100%; border-collapse:collapse; font-size:10px; }
    th,td { border-bottom:1px solid var(--line); padding:10px 8px; text-align:right; }
    th { background:#f1f5f9; color:#334155; font-size:10px; }
    tbody tr:last-child td { border-bottom:0; }
    .num { text-align:left; direction:ltr; font-variant-numeric:tabular-nums; white-space:nowrap; }
    .trend { text-align:center; font-weight:700; white-space:nowrap; }
    .net-box { display:flex; justify-content:space-between; align-items:center; margin-top:16px; padding:16px 18px; border-radius:12px; color:white; background:linear-gradient(110deg,#1d4ed8,#1e3a8a); }
    .net-box.negative { background:linear-gradient(110deg,#b91c1c,#7f1d1d); }
    .net-box .caption { font-size:12px; font-weight:700; }
    .net-box .formula { margin-top:5px; color:#dbeafe; font-size:9px; }
    .net-box .value { font-size:21px; font-weight:800; font-variant-numeric:tabular-nums; direction:ltr; }
    .insights { display:grid; grid-template-columns:1fr 1fr; gap:9px; margin-top:14px; }
    .insight { border:1px solid var(--line); border-radius:10px; padding:11px 13px; background:#f8fafc; }
    .insight .label { color:var(--muted); font-size:10px; }
    .insight .value { margin-top:5px; color:var(--ink); font-size:15px; font-weight:800; }
    .note { margin-top:14px; padding:10px 12px; border-right:3px solid #93c5fd; color:#475569; background:#f8fafc; font-size:9px; line-height:1.8; }
    .signatures { display:grid; grid-template-columns:1fr 1fr 1fr; gap:24px; margin-top:38px; }
    .signatures div { border-top:1px solid #94a3b8; padding-top:7px; text-align:center; color:#64748b; font-size:9px; }
    .footer { display:flex; justify-content:space-between; gap:12px; margin-top:24px; padding-top:9px; border-top:1px solid var(--line); color:#94a3b8; font-size:8px; }
    @page { size:A4; margin:0; }
    @media print { body { background:#fff; print-color-adjust:exact; -webkit-print-color-adjust:exact; } .toolbar { display:none; } .page { width:auto; min-height:297mm; margin:0; padding:14mm 15mm 12mm; box-shadow:none; } }
    @media screen and (max-width:760px) { .page { width:100%; min-height:0; margin:0; padding:22px 16px; } .header { align-items:flex-start; } .logo { width:56px; height:56px; } .brand h1 { font-size:16px; } .report-title { min-width:105px; } .report-title h2 { font-size:15px; } .kpis { grid-template-columns:repeat(2,1fr); } }
  </style>
</head>
<body>
  <div class="toolbar"><button onclick="window.print()">طباعة التقرير أو حفظه PDF</button></div>
  <main class="page">
    <header class="header">
      <div class="company">
        ${logo ? `<img class="logo" src="${esc(logo)}" alt="شعار الشركة" />` : ''}
        <div class="brand">
          <h1>${esc(settings?.business_name || settings?.trade_name || 'اسم المنشأة')}</h1>
          ${settings?.trade_name && settings.trade_name !== settings.business_name ? `<div class="trade">${esc(settings.trade_name)}</div>` : ''}
          <div class="details">
            ${settings?.commercial_registration ? `<span>السجل التجاري: ${esc(settings.commercial_registration)}</span>` : ''}
            ${settings?.tax_number ? `<span>الرقم الضريبي: ${esc(settings.tax_number)}</span>` : ''}
            ${settings?.business_address ? `<span>${esc(settings.business_address)}</span>` : ''}
            ${settings?.business_phone ? `<span dir="ltr">${esc(settings.business_phone)}</span>` : ''}
            ${settings?.business_email ? `<span dir="ltr">${esc(settings.business_email)}</span>` : ''}
          </div>
        </div>
      </div>
      <div class="report-title">
        <div class="eyebrow">تقرير مالي رسمي</div>
        <h2>النتيجة الشهرية</h2>
        <p>${esc(report.month)} · ${esc(formatDate(new Date().toISOString()))}</p>
      </div>
    </header>
    <div class="intro">
      <strong>ملخص الأداء المالي لشهر ${esc(report.month)}</strong>
      <span>يعرض التقرير إجمالي المبيعات والمصاريف ومدفوعات الموردين والرواتب، ويقارن النتائج بالشهر السابق. الرواتب محسوبة من مسيّرات الشهر المعتمدة أو المصروفة.</span>
    </div>
    <section class="kpis">
      ${METRICS.slice(0, 4).map((m) => {
        const current = report[m.key]; const before = previous[m.key];
        const delta = current - before;
        const isGood = delta === 0 ? 'flat' : ((delta > 0) === m.positiveWhenUp ? 'good' : 'bad');
        return `<div class="kpi"><div class="label">${esc(m.label)}</div><div class="value">${amount(current)}</div><div class="change ${isGood}">${esc(percentage(current, before))} عن الشهر السابق</div></div>`;
      }).join('')}
    </section>
    <h3 class="section-title">تفاصيل المقارنة الشهرية</h3>
    <table>
      <thead><tr><th>البند</th><th class="num">الشهر الحالي</th><th class="num">الشهر السابق</th><th class="num">الفرق</th><th class="trend">التغير</th></tr></thead>
      <tbody>${rows}</tbody>
    </table>
    <div class="net-box ${report.net < 0 ? 'negative' : ''}">
      <div><div class="caption">صافي الشهر</div><div class="formula">المبيعات − المصاريف − مدفوعات الموردين − الرواتب</div></div>
      <div class="value">${amount(report.net)}</div>
    </div>
    <section class="insights">
      <div class="insight"><div class="label">هامش صافي الشهر من المبيعات</div><div class="value">${report.sales ? `${netMargin.toFixed(1)}%` : '—'}</div></div>
      <div class="insight"><div class="label">المصاريف والمدفوعات والرواتب من المبيعات</div><div class="value">${report.sales ? `${outflowRatio.toFixed(1)}%` : '—'}</div></div>
    </section>
    <div class="note"><b>ملاحظة محاسبية:</b> صافي هذا التقرير مبني على التدفقات المحددة أعلاه، ولا يخصم تكلفة الأقمشة المباعة. يقيس التقرير مدفوعات الموردين حسب تاريخ الدفع، والرواتب حسب شهر مسيّر الرواتب المعتمد أو المصروف.</div>
    <section class="signatures"><div>إعداد التقرير</div><div>المراجعة المالية</div><div>اعتماد الإدارة</div></section>
    <footer class="footer"><span>${esc(settings?.receipt_footer || 'مستند داخلي للاستخدام المالي والإداري')}</span><span>تاريخ الإصدار: ${esc(formatDate(new Date().toISOString()))}</span></footer>
  </main>
  ${autoPrint ? `<script>
    const images = Array.from(document.images);
    Promise.all(images.map((image) => image.complete ? Promise.resolve() : new Promise((resolve) => { image.onload = resolve; image.onerror = resolve; })))
      .then(() => setTimeout(() => window.print(), 250));
  </script>` : ''}
</body>
</html>`;
}

export function openMonthlyFinalReport(
  report: MonthlyFinalReport,
  settings: AppSettings | null,
  autoPrint = false,
): boolean {
  const popup = window.open('', '_blank', 'width=1000,height=800');
  if (!popup) return false;
  popup.document.open();
  popup.document.write(buildMonthlyFinalReport(report, settings, autoPrint));
  popup.document.close();
  return true;
}
