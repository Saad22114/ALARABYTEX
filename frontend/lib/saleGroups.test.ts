import { describe, it, expect } from 'vitest';
import { saleGroupBadges, saleGroupKey, SALE_GROUP_COLORS } from './saleGroups';
import type { SessionSaleItem } from '@/types';

function item(over: Partial<SessionSaleItem> & { id: number }): SessionSaleItem {
  return {
    sale_group: '',
    group_no: null,
    ...over,
  } as SessionSaleItem;
}

describe('saleGroupKey', () => {
  it('يستخدم معرّف البيعة المشترك، ويجعل البند المفرد بيعة قائمة', () => {
    expect(saleGroupKey(item({ id: 7, sale_group: 'abc' }))).toBe('abc');
    expect(saleGroupKey(item({ id: 7, sale_group: '' }))).toBe('single-7');
  });
});

describe('saleGroupBadges', () => {
  it('يبدأ من 1 مع أقدم بيعة', () => {
    // البند المرتجع من الخادم أحدث أولاً (-id)؛ الترقيم يجب أن يتبع وقت
    // الخلق لا ترتيب الوصول، فالأقدم يأخذ 1.
    const items = [
      item({ id: 30, sale_group: 'g3', group_no: 3 }),
      item({ id: 20, sale_group: 'g2', group_no: 2 }),
      item({ id: 10, sale_group: 'g1', group_no: 1 }),
    ];
    const badges = saleGroupBadges(items);
    expect(badges.get('g1')?.num).toBe(1);
    expect(badges.get('g2')?.num).toBe(2);
    expect(badges.get('g3')?.num).toBe(3);
  });

  it('يجمع بنود البيعة الواحدة تحت رقم واحد', () => {
    const items = [
      item({ id: 21, sale_group: 'g1', group_no: 1 }),
      item({ id: 20, sale_group: 'g1', group_no: 1 }),
    ];
    const badges = saleGroupBadges(items);
    expect(badges.size).toBe(1);
    expect(badges.get('g1')?.num).toBe(1);
  });

  it('يترك فجوة ولا يعيد الترقيم بعد حذف بيعة', () => {
    // بيعة 2 حُذفت: بيعة 3 تبقى 3 ولا تصير 2
    const items = [
      item({ id: 30, sale_group: 'g3', group_no: 3 }),
      item({ id: 10, sale_group: 'g1', group_no: 1 }),
    ];
    const badges = saleGroupBadges(items);
    expect(badges.get('g1')?.num).toBe(1);
    expect(badges.get('g3')?.num).toBe(3);
    expect(badges.has('g2')).toBe(false);
  });

  it('حذف آخر بيعة لا يخفض رقم البقية', () => {
    // بيعة 3 حُذفت: الباقيتان 1 و2 كما هما
    const items = [
      item({ id: 20, sale_group: 'g2', group_no: 2 }),
      item({ id: 10, sale_group: 'g1', group_no: 1 }),
    ];
    const badges = saleGroupBadges(items);
    expect(badges.get('g1')?.num).toBe(1);
    expect(badges.get('g2')?.num).toBe(2);
  });

  it('الترتيب لا يتأثر بترتيب وصول البنود', () => {
    const oldest = [item({ id: 10, sale_group: 'g1', group_no: 1 })];
    const newest = [item({ id: 30, sale_group: 'g3', group_no: 3 })];
    const middle = [item({ id: 20, sale_group: 'g2', group_no: 2 })];

    const forward = saleGroupBadges([...oldest, ...middle, ...newest]);
    const reversed = saleGroupBadges([...newest, ...middle, ...oldest]);
    for (const badges of [forward, reversed]) {
      expect(badges.get('g1')?.num).toBe(1);
      expect(badges.get('g2')?.num).toBe(2);
      expect(badges.get('g3')?.num).toBe(3);
    }
  });

  it('يرتّب البنود بلا رقم محفوظ بأقدم id', () => {
    const items = [
      item({ id: 30, sale_group: 'g3' }),
      item({ id: 20, sale_group: 'g2' }),
      item({ id: 10, sale_group: 'g1' }),
    ];
    const badges = saleGroupBadges(items);
    expect(badges.get('g1')?.num).toBe(1);
    expect(badges.get('g2')?.num).toBe(2);
    expect(badges.get('g3')?.num).toBe(3);
  });

  it('البند بلا معرّف بيعة مستقل عن غيره', () => {
    const items = [item({ id: 2, group_no: 2 }), item({ id: 1, group_no: 1 })];
    const badges = saleGroupBadges(items);
    expect(badges.get('single-1')?.num).toBe(1);
    expect(badges.get('single-2')?.num).toBe(2);
  });

  it('يأخذ الرقم المحفوظ من أي بند في المجموعة', () => {
    // بنود قديمة جزئياً: واحد بلا رقم وآخر مرقّم
    const items = [
      item({ id: 20, sale_group: 'g1', group_no: 1 }),
      item({ id: 21, sale_group: 'g1', group_no: null }),
    ];
    const badges = saleGroupBadges(items);
    expect(badges.get('g1')?.num).toBe(1);
  });

  it('الترقيم غير المحفوظ يأتي بعد المحفوظ بأرقام لا تتعارض', () => {
    const items = [
      item({ id: 5, sale_group: 'legacy' }),
      item({ id: 20, sale_group: 'g1', group_no: 1 }),
    ];
    const badges = saleGroupBadges(items);
    expect(badges.get('g1')?.num).toBe(1);
    // يأخذ الرقم التالي بعد أكبر رقم محفوظ، لا رقماً محجوزاً
    expect(badges.get('legacy')?.num).toBe(2);
  });

  it('الترقيم غير المحفوظ لا يشغل رقماً محجوزاً بفجوة', () => {
    // المحفوظ: 1 و5 (2 و3 محذوفان، و4 محجوز لبيعة رابعة)؛ القديم بلا رقم
    const items = [
      item({ id: 5, sale_group: 'legacy' }),
      item({ id: 50, sale_group: 'g5', group_no: 5 }),
      item({ id: 10, sale_group: 'g1', group_no: 1 }),
    ];
    const badges = saleGroupBadges(items);
    expect(badges.get('g1')?.num).toBe(1);
    expect(badges.get('g5')?.num).toBe(5);
    expect(badges.get('legacy')?.num).toBe(6);
  });

  it('يدوّر الألوان مع الأرقام', () => {
    const items = Array.from({ length: 8 }, (_, i) =>
      item({ id: i + 1, sale_group: `g${i}`, group_no: i + 1 })
    );
    const badges = saleGroupBadges(items);
    expect(badges.get('g0')?.cls).toBe(SALE_GROUP_COLORS[0]);
    expect(badges.get('g5')?.cls).toBe(SALE_GROUP_COLORS[5]);
    // بعدد الألوان يعود الدوران من البداية
    expect(badges.get('g6')?.cls).toBe(SALE_GROUP_COLORS[0]);
    expect(badges.get('g7')?.cls).toBe(SALE_GROUP_COLORS[1]);
  });

  it('اللون يتبع رقم البيعة فتصمد الهوية بعد الحذف', () => {
    const before = saleGroupBadges([
      item({ id: 10, sale_group: 'g1', group_no: 1 }),
      item({ id: 20, sale_group: 'g2', group_no: 2 }),
      item({ id: 30, sale_group: 'g3', group_no: 3 }),
    ]);
    const after = saleGroupBadges([
      item({ id: 30, sale_group: 'g3', group_no: 3 }),
      item({ id: 10, sale_group: 'g1', group_no: 1 }),
    ]);
    // بيعة 1 و3 تحتفظان برقميهما ولونهما بعد حذف 2
    for (const key of ['g1', 'g3']) {
      expect(after.get(key)?.num).toBe(before.get(key)?.num);
      expect(after.get(key)?.cls).toBe(before.get(key)?.cls);
    }
  });

  it('قائمة فارغة لا تنتج أرقاماً', () => {
    expect(saleGroupBadges([]).size).toBe(0);
  });
});
