let currencyConfig = { symbol: 'ر.ع', decimals: 2, position: 'after' as 'after' | 'before' };
let dateFormat = 'YYYY-MM-DD';

export function configureCurrency(config: { symbol: string; decimals: number; position?: 'after' | 'before' }) {
  currencyConfig = { symbol: config.symbol, decimals: config.decimals, position: config.position || 'after' };
}

export function configureDateFormat(format: string) {
  dateFormat = format;
}

export function formatNumber(n: number): string {
  return new Intl.NumberFormat('ar-EG-u-nu-latn', {
    maximumFractionDigits: 2,
  }).format(n);
}

export function formatCurrency(n: number): string {
  const formatted = new Intl.NumberFormat('ar-EG-u-nu-latn', {
    minimumFractionDigits: currencyConfig.decimals,
    maximumFractionDigits: currencyConfig.decimals,
  }).format(n);
  return currencyConfig.position === 'before'
    ? `${currencyConfig.symbol} ${formatted}`
    : `${formatted} ${currencyConfig.symbol}`;
}

function pad2(v: number | string): string {
  return String(v).padStart(2, '0');
}

export function formatDate(iso: string): string {
  if (!iso) return '';
  const d = new Date(iso);
  if (isNaN(d.getTime())) return iso;
  const y = String(d.getFullYear());
  const m = pad2(d.getMonth() + 1);
  const day = pad2(d.getDate());
  switch (dateFormat) {
    case 'DD-MM-YYYY': return `${day}-${m}-${y}`;
    case 'DD/MM/YYYY': return `${day}/${m}/${y}`;
    case 'MM-DD-YYYY': return `${m}-${day}-${y}`;
    default: return `${y}-${m}-${day}`;
  }
}

export function formatShortDate(iso: string): string {
  return new Date(iso).toLocaleDateString('ar-EG-u-nu-latn', {
    month: 'short',
    day: 'numeric',
  });
}

const AR_DAYS = ['الأحد', 'الاثنين', 'الثلاثاء', 'الأربعاء', 'الخميس', 'الجمعة', 'السبت'];
const AR_MONTHS = ['يناير', 'فبراير', 'مارس', 'أبريل', 'مايو', 'يونيو', 'يوليو', 'أغسطس', 'سبتمبر', 'أكتوبر', 'نوفمبر', 'ديسمبر'];

export function formatArabicDate(date: Date): string {
  return `${AR_DAYS[date.getDay()]}، ${date.getDate()} ${AR_MONTHS[date.getMonth()]} ${date.getFullYear()}`;
}
