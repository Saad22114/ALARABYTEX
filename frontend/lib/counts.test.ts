import { describe, it, expect } from 'vitest';
import {
  countedDifference, dirtyFabrics, progressPercent, rowStatus, ROW_STATUS_LABEL,
} from './counts';
import type { CountItem, CountSummary } from '@/types';

/**
 * منطق عرض الجرد، منفصلاً عن الشاشة ليبقى قابلاً للاختبار.
 *
 * كل ما هنا حالةٌ واحدة مُقلَّبة على نفسها: الصفر. «لم يُعدّ» ليست
 * صفراً، و«لا نعلم» ليست صفراً. ومن يخلط بينهما يعرض جرداً ناقصاً على
 * أنه جردٌ مطابق — وهو أسوأُ من عرض جردٍ خاطئ، لأن الخاطئ يُراجَع.
 */

function item(overrides: Partial<CountItem> = {}): CountItem {
  return {
    id: 1,
    fabric: 10,
    fabric_name: 'قطن',
    fabric_code: 'F-1',
    system_yards: 30,
    counted_yards: null,
    counted: false,
    note: '',
    ...overrides,
  };
}

function summary(overrides: Partial<CountSummary> = {}): CountSummary {
  return {
    items: 0, counted: 0, pending: 0, variances: 0,
    net_yards: 0, value: 0, complete: false,
    ...overrides,
  };
}

describe('countedDifference', () => {
  it('subtracts the book balance from the counted yardage', () => {
    expect(countedDifference(item(), '25')).toBe(-5);
    expect(countedDifference(item(), '35')).toBe(5);
    expect(countedDifference(item(), '30')).toBe(0);
  });

  it('reads an empty box as unknown, not as zero', () => {
    expect(countedDifference(item(), '')).toBeNull();
    expect(countedDifference(item(), '   ')).toBeNull();
    expect(countedDifference(item(), undefined)).toBeNull();
    expect(countedDifference(item(), null)).toBeNull();
  });

  it('refuses to guess while the book balance is hidden', () => {
    const blind = item({ system_yards: undefined });
    expect(countedDifference(blind, '25')).toBeNull();
  });

  it('rounds to the two decimals the field stores', () => {
    // 30.001 - 30 في التخزين يصير 0.01، فالرصيد المخزَّن نفسه مقرَّب.
    expect(countedDifference(item(), '30.004')).toBe(0);
    expect(countedDifference(item(), '30.01')).toBe(0.01);
  });

  it('treats a typed word as unknown rather than as a number', () => {
    expect(countedDifference(item(), 'abc')).toBeNull();
  });

  it('measures a found fabric against zero', () => {
    const found = item({ system_yards: 0 });
    expect(countedDifference(found, '15')).toBe(15);
  });
});

describe('rowStatus', () => {
  it('never calls an uncounted row a match', () => {
    expect(rowStatus(item(), '')).toBe('pending');
    expect(rowStatus(item({ counted: true }), '30')).toBe('match');
  });

  it('says "counted", not "match", while the balance is hidden', () => {
    // قولُ «مطابق» هنا كذبٌ يسلب الجردَ لغته: الرصيد مخفيّ فلا يُحكم.
    expect(rowStatus(item({ counted: true, system_yards: undefined }), '30')).toBe('counted');
  });

  it('marks a real difference as a variance', () => {
    expect(rowStatus(item({ counted: true }), '25')).toBe('variance');
    expect(rowStatus(item({ counted: true }), '35')).toBe('variance');
  });

  it('gives every status a distinct label', () => {
    // «مطابق» تعني قِسته فوجدته كذلك. فلا يجوز أن تنطبق على «لم يُعدّ»
    // ولا على «مرصود بلا مرجع»: في شاشة الجرد هذه كذبةٌ صغيرة صريحة.
    const labels = ['pending', 'counted', 'match', 'variance'] as const;
    const seen = new Set<string>();
    for (const status of labels) {
      expect(ROW_STATUS_LABEL[status]).toBeTruthy();
      seen.add(ROW_STATUS_LABEL[status]);
    }
    expect(seen.size).toBe(labels.length);
  });
});

describe('progressPercent', () => {
  it('measures counted over total', () => {
    expect(progressPercent(summary({ items: 4, counted: 1 }))).toBe(25);
    expect(progressPercent(summary({ items: 4, counted: 4 }))).toBe(100);
  });

  it('calls an empty session zero, not complete', () => {
    // جلسةٌ بلا أصناف لم تبدأ. «منتهية» بلا عملٍ تعني أنّ العمل بدأ.
    expect(progressPercent(summary({ items: 0, counted: 0 }))).toBe(0);
  });
});

describe('dirtyFabrics', () => {
  const rows = [
    item({ id: 1, fabric: 1, counted_yards: 30, counted: true, note: '' }),
    item({ id: 2, fabric: 2, counted_yards: null, counted: false, note: 'قصاصة' }),
  ];

  it('finds nothing when the screen matches the server', () => {
    const draft = { 1: { yards: '30', note: '' }, 2: { yards: '', note: 'قصاصة' } };
    expect(dirtyFabrics(rows, draft)).toEqual([]);
  });

  it('reports only the row the counter touched', () => {
    const draft = { 1: { yards: '28', note: '' }, 2: { yards: '', note: 'قصاصة' } };
    expect(dirtyFabrics(rows, draft)).toEqual([1]);
  });

  it('counts a reason on its own as a change', () => {
    const draft = { 1: { yards: '30', note: '' }, 2: { yards: '', note: 'تلف' } };
    expect(dirtyFabrics(rows, draft)).toEqual([2]);
  });

  it('treats clearing a count as a change', () => {
    const draft = { 1: { yards: '', note: '' }, 2: { yards: '', note: 'قصاصة' } };
    expect(dirtyFabrics(rows, draft)).toEqual([1]);
  });

  it('ignores a re-typed 30.00 for a stored 30', () => {
    // الخادم يعيد 30.00 نصّاً؛ لولا التطبيع لأُرسل طلبٌ بلا تغييرٍ حقيقي،
    // وأُعلن المستخدم أنه حفظ شيئاً لم يغيّره.
    const draft = { 1: { yards: '30.00', note: '' }, 2: { yards: '', note: 'قصاصة' } };
    expect(dirtyFabrics(rows, draft)).toEqual([]);
  });

  it('still counts a cleared box as a change', () => {
    const draft = { 1: { yards: '  ', note: '' }, 2: { yards: '', note: 'قصاصة' } };
    expect(dirtyFabrics(rows, draft)).toEqual([1]);
  });
});