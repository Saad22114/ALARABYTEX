import { describe, it, expect, beforeEach } from 'vitest';
import {
  configureCurrency,
  configureDateFormat,
  formatNumber,
  formatCurrency,
  formatDate,
  formatArabicDate,
  formatLastSeen,
} from './format';

describe('formatCurrency', () => {
  beforeEach(() => {
    configureCurrency({ symbol: 'ر.ع', decimals: 2, position: 'after' });
  });

  it('appends the symbol after the value', () => {
    expect(formatCurrency(1234.5)).toBe('1,234.50 ر.ع');
  });

  it('places the symbol before the value when configured', () => {
    configureCurrency({ symbol: 'ر.ع', decimals: 0, position: 'before' });
    expect(formatCurrency(100)).toBe('ر.ع 100');
  });
});

describe('formatNumber', () => {
  it('formats with latin digits up to 2 decimals', () => {
    expect(formatNumber(1234.567)).toBe('1,234.57');
  });
});

describe('formatDate', () => {
  beforeEach(() => {
    configureDateFormat('DD-MM-YYYY');
  });

  it('formats ISO dates as DD-MM-YYYY', () => {
    expect(formatDate('2026-09-15T10:00:00')).toBe('15-09-2026');
  });

  it('supports DD/MM/YYYY', () => {
    configureDateFormat('DD/MM/YYYY');
    expect(formatDate('2026-09-15')).toBe('15/09/2026');
  });

  it('Returns empty string for empty input', () => {
    expect(formatDate('')).toBe('');
  });

  it('Returns the raw value for invalid dates', () => {
    expect(formatDate('not-a-date')).toBe('not-a-date');
  });
});

describe('formatArabicDate', () => {
  it('produces a deterministic Arabic date for the same Date object', () => {
    const d = new Date(2026, 8, 15); // 15 Sept 2026 -> Tuesday (الثلاثاء)
    const a = formatArabicDate(d);
    const b = formatArabicDate(new Date(2026, 8, 15));
    expect(a).toBe('الثلاثاء، 15 سبتمبر 2026');
    expect(a).toBe(b);
  });
});

describe('formatLastSeen', () => {
  // «الطلب: اكتب آخر ظهور الوقت، وإذا أكثر من يوم اكتب اليوم والتاريخ».
  const now = new Date(2026, 8, 30, 14, 5); // الأربعاء 30 سبتمبر 2026

  // ساعة النظام الـ12/24 وصيغة «ص/م» تختلفان بين بيئات Node حسب بيانات
  // ICU، فنقارن بالمُخرِج المرجعي نفسه بدل تثبيت نصّ الساعة حرفياً.
  // ما نتحقّق منه هنا هو **البُعد** الذي يهمّ: وقتٌ بلا تاريخ، أو «أمس»،
  // أو يومٌ وتاريخ — لا شكل الساعة.
  const clock = (d: Date) =>
    d.toLocaleTimeString('ar-EG-u-nu-latn', { hour: '2-digit', minute: '2-digit' });

  it('says the person never signed in when there is no timestamp', () => {
    expect(formatLastSeen(null, now)).toBe('لم يسجّل دخولاً بعد');
    expect(formatLastSeen(undefined, now)).toBe('لم يسجّل دخولاً بعد');
  });

  it('shows only the time for a sign-in earlier today', () => {
    const at = new Date(2026, 8, 30, 9, 12);
    const out = formatLastSeen(at.toISOString(), now);
    expect(out).toBe(`آخر ظهور الساعة ${clock(at)}`);
    // بلا تاريخ: لو أُهمل هنا لبان الغائب منذ ثلاثة أيام حاضراً اليوم.
    expect(out).not.toContain('سبتمبر');
    expect(out).not.toContain('أمس');
  });

  it('names yesterday as «أمس» so no date is needed', () => {
    const at = new Date(2026, 8, 29, 22, 40);
    const out = formatLastSeen(at.toISOString(), now);
    expect(out).toBe(`آخر ظهور أمس الساعة ${clock(at)}`);
    expect(out).not.toContain('سبتمبر');
  });

  it('writes the day and the date once it is older than a day', () => {
    const at = new Date(2026, 8, 27, 16, 5);
    const out = formatLastSeen(at.toISOString(), now);
    expect(out).toBe(`آخر ظهور ${formatArabicDate(at)} الساعة ${clock(at)}`);
  });

  it('crosses the month boundary without losing the day', () => {
    const at = new Date(2026, 7, 31, 8, 0);
    const out = formatLastSeen(at.toISOString(), now);
    expect(out).toContain('31 أغسطس 2026');
    expect(out).toContain(formatArabicDate(at));
  });

  it('stays silent on garbage instead of printing «Invalid Date»', () => {
    expect(formatLastSeen('not-a-date', now)).toBe('');
  });
});