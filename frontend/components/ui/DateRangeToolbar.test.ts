import { describe, expect, it, vi, afterEach } from 'vitest';
import { getRangeForKey, getActivePreset } from './DateRangeToolbar';

function setToday(iso: string) {
  const d = new Date(`${iso}T12:00:00`);
  vi.useFakeTimers();
  vi.setSystemTime(d);
}
afterEach(() => vi.useRealTimers());

describe('getRangeForKey', () => {
  it('week returns the last 7 days ending today', () => {
    setToday('2026-09-21');
    expect(getRangeForKey('week')).toEqual({ from: '2026-09-15', to: '2026-09-21' });
  });

  it('week is stable across a month boundary', () => {
    setToday('2026-09-02');
    expect(getRangeForKey('week')).toEqual({ from: '2026-08-27', to: '2026-09-02' });
  });

  it('today returns a single day', () => {
    setToday('2026-09-21');
    expect(getRangeForKey('today')).toEqual({ from: '2026-09-21', to: '2026-09-21' });
  });

  it('month starts on the first and ends today', () => {
    setToday('2026-09-21');
    expect(getRangeForKey('month')).toEqual({ from: '2026-09-01', to: '2026-09-21' });
  });
});

describe('getActivePreset', () => {
  it('identifies the week preset for a 7-day trailing range', () => {
    setToday('2026-09-21');
    expect(getActivePreset('2026-09-15', '2026-09-21')).toBe('week');
  });

  it('identifies month, last_month and today', () => {
    setToday('2026-09-21');
    expect(getActivePreset('2026-09-01', '2026-09-21')).toBe('month');
    expect(getActivePreset('2026-08-01', '2026-08-31')).toBe('last_month');
    expect(getActivePreset('2026-09-21', '2026-09-21')).toBe('today');
  });

  it('returns null for a custom range', () => {
    setToday('2026-09-21');
    expect(getActivePreset('2026-09-10', '2026-09-12')).toBeNull();
  });
});