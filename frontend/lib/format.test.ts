import { describe, it, expect, beforeEach } from 'vitest';
import {
  configureCurrency,
  configureDateFormat,
  formatNumber,
  formatCurrency,
  formatDate,
  formatArabicDate,
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