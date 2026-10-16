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

/**
 * وقت آخر ظهور تحت الاسم.
 *
 * «الطلب: اكتب آخر ظهور الوقت، وإذا أكثر من يوم اكتب اليوم والتاريخ».
 * فنصاغه بحسب البُعد الذي يهمّ السائل: اليوم نفسه فيكتفي بالوقت، ويومٌ
 * سابق فيحتاج اليوم والتاريخ — لأن «٠٣:٤٠» بلا تاريخ توهم أن الموظف كان
 * حاضراً اليوم بينما هو غائب منذ ثلاثة أيام.
 */
export function formatLastSeen(iso: string | null | undefined, now = new Date()): string {
  if (!iso) return 'لم يسجّل دخولاً بعد';
  const at = new Date(iso);
  if (Number.isNaN(at.getTime())) return '';

  const sameDay = at.toDateString() === now.toDateString();
  if (sameDay) {
    return `آخر ظهور الساعة ${at.toLocaleTimeString('ar-EG-u-nu-latn', {
      hour: '2-digit',
      minute: '2-digit',
    })}`;
  }

  // «أمس» تُغني عن التاريخ، أما ما قبلها فيحتاج اليوم والتاريخ معاً.
  const yesterday = new Date(now);
  yesterday.setDate(now.getDate() - 1);
  if (at.toDateString() === yesterday.toDateString()) {
    return `آخر ظهور أمس الساعة ${at.toLocaleTimeString('ar-EG-u-nu-latn', {
      hour: '2-digit',
      minute: '2-digit',
    })}`;
  }

  return `آخر ظهور ${formatArabicDate(at)} الساعة ${at.toLocaleTimeString('ar-EG-u-nu-latn', {
    hour: '2-digit',
    minute: '2-digit',
  })}`;
}
