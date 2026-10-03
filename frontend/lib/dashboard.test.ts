import { describe, it, expect } from 'vitest';
import {
  axisMoney,
  comparableMonthSpans,
  compareLabel,
  currentMonthKey,
  deltaText,
  monthLabel,
  monthSpan,
  shiftMonthKey,
} from './dashboard';

describe('axisMoney', () => {
  it('says the unit, because a bare number is read as the wrong amount', () => {
    // The complaint that started this: 200000 on an axis reads as millions.
    expect(axisMoney(200000)).toBe('200 ألف');
    expect(axisMoney(1000000)).toBe('1 مليون');
    expect(axisMoney(2500000000)).toBe('2.5 مليار');
  });

  it('keeps small numbers whole and grouped', () => {
    expect(axisMoney(0)).toBe('0');
    expect(axisMoney(150)).toBe('150');
    expect(axisMoney(4000)).toBe('4 ألف');
    expect(axisMoney(1500)).toBe('1.5 ألف');
  });

  it('rounds large magnitudes so the label stays readable', () => {
    expect(axisMoney(3400000)).toBe('3.4 مليون');
    expect(axisMoney(123456789)).toBe('123 مليون');
  });

  it('keeps the sign on the negative side of a loss chart', () => {
    expect(axisMoney(-4000)).toBe('−4 ألف');
    expect(axisMoney(-200000)).toBe('−200 ألف');
  });

  it('does not invent a unit for zero or rubbish', () => {
    expect(axisMoney(0)).toBe('0');
    expect(axisMoney(Number.NaN)).toBe('0');
  });
});

describe('monthLabel', () => {
  it('names the month the way the owner says it', () => {
    expect(monthLabel('2026-10')).toBe('أكتوبر 2026');
    expect(monthLabel('2026-01')).toBe('يناير 2026');
    expect(monthLabel('2026-12')).toBe('ديسمبر 2026');
  });
});

describe('currentMonthKey / shiftMonthKey', () => {
  it('crosses the year boundary in both directions', () => {
    expect(shiftMonthKey('2026-01', -1)).toBe('2025-12');
    expect(shiftMonthKey('2026-12', 1)).toBe('2027-01');
    expect(shiftMonthKey('2026-10', 0)).toBe('2026-10');
  });

  it('pads single-digit months', () => {
    expect(currentMonthKey(new Date(2026, 0, 5))).toBe('2026-01');
    expect(currentMonthKey(new Date(2026, 8, 5))).toBe('2026-09');
  });
});

describe('monthSpan', () => {
  const third = new Date(2026, 9, 3);

  it('stops at today when the month is still running', () => {
    // "October" on the 3rd is three days of data, not thirty-one.
    expect(monthSpan('2026-10', third)).toEqual({
      month: '2026-10',
      from: '2026-10-01',
      to: '2026-10-03',
      lastDay: 3,
      partial: true,
    });
  });

  it('reads a finished month whole, however recently it ended', () => {
    expect(monthSpan('2026-09', third)).toEqual({
      month: '2026-09',
      from: '2026-09-01',
      to: '2026-09-30',
      lastDay: 30,
      partial: false,
    });
  });

  it('knows the length of every month, leap years included', () => {
    expect(monthSpan('2024-02', new Date(2024, 2, 15)).to).toBe('2024-02-29');
    expect(monthSpan('2026-02', new Date(2026, 2, 15)).to).toBe('2026-02-28');
    expect(monthSpan('2026-04', new Date(2026, 4, 15)).to).toBe('2026-04-30');
  });
});

describe('comparableMonthSpans', () => {
  const third = new Date(2026, 9, 3);

  it('cuts both months at the same day before comparing them', () => {
    // Comparing 1-3 October against 1-30 September measured three days
    // against thirty, and then reported the difference as a percentage.
    const spans = comparableMonthSpans('2026-10', '2026-09', third);
    expect(spans.days).toBe(3);
    expect(spans.a.to).toBe('2026-10-03');
    expect(spans.b.to).toBe('2026-09-03');
    expect(spans.partial).toBe(true);
  });

  it('marks the truncated finished month as not comparable either', () => {
    const spans = comparableMonthSpans('2026-10', '2026-09', third);
    expect(spans.b.partial).toBe(true);
    expect(spans.a.partial).toBe(true);
  });

  it('leaves two finished months alone', () => {
    const spans = comparableMonthSpans('2026-09', '2026-08', third);
    expect(spans.days).toBe(30);
    expect(spans.a.to).toBe('2026-09-30');
    expect(spans.b.to).toBe('2026-08-31');
    expect(spans.partial).toBe(false);
  });

  it('uses the shorter month only when one of them is still running', () => {
    // Two finished months are read whole: March really is longer than
    // February, and shortening it would hide that rather than fix a bias.
    const spans = comparableMonthSpans('2026-03', '2026-02', new Date(2026, 5, 1));
    expect(spans.days).toBe(28);
    expect(spans.a.to).toBe('2026-03-31');
    expect(spans.b.to).toBe('2026-02-28');
    expect(spans.partial).toBe(false);
  });
});

describe('compareLabel', () => {
  it('names what it could not measure instead of dividing by zero', () => {
    // The guard used to say "no sales" under the expenses card.
    expect(compareLabel('مبيعات', 0, 100)).toBe('لا مبيعات في الشهر الأول');
    expect(compareLabel('مصاريف', 0, 50)).toBe('لا مصاريف في الشهر الأول');
  });

  it('rounds to one decimal and keeps the direction', () => {
    expect(compareLabel('مبيعات', 100, 150)).toBe('+50.0% مقارنةً بالشهر الأول');
    expect(compareLabel('مبيعات', 100, 50)).toBe('−50.0% مقارنةً بالشهر الأول');
    expect(compareLabel('مبيعات', 207155.18, 3703.21)).toBe(
      '−98.2% مقارنةً بالشهر الأول'
    );
  });

  it('measures growth off the magnitude, so a shrinking loss is not a fall', () => {
    // A net that went from -100 to -50 improved. Dividing by the signed value
    // printed a minus sign for good news.
    expect(compareLabel('صافي', -100, -50)).toBe('+50.0% مقارنةً بالشهر الأول');
    expect(compareLabel('صافي', -100, -150)).toBe('−50.0% مقارنةً بالشهر الأول');
  });
});

describe('deltaText', () => {
  it('says nothing when there is no previous period to compare against', () => {
    expect(deltaText(null)).toBe('');
    expect(deltaText(undefined)).toBe('');
  });

  it('rounds, so the card never shows a runaway float', () => {
    expect(deltaText(12.34)).toBe('+12.3% عن الفترة السابقة');
    expect(deltaText(-12.36)).toBe('−12.4% عن الفترة السابقة');
    expect(deltaText(0)).toBe('+0.0% عن الفترة السابقة');
  });
});