import type { SessionSaleItem } from '@/types';

export const SALE_GROUP_COLORS = [
  'bg-brand-50 text-brand-700 border-brand-200',
  'bg-emerald-50 text-emerald-700 border-emerald-200',
  'bg-amber-50 text-amber-700 border-amber-200',
  'bg-sky-50 text-sky-700 border-sky-200',
  'bg-violet-50 text-violet-700 border-violet-200',
  'bg-rose-50 text-rose-700 border-rose-200',
];

/** مفتاح يجمع بنود البيعة الواحدة؛ البنود المفردة كل بند منها بيعة قائمة. */
export function saleGroupKey(item: Pick<SessionSaleItem, 'id' | 'sale_group'>): string {
  return item.sale_group || `single-${item.id}`;
}

export interface SaleGroupBadge {
  /** الرقم المعروض للمستخدم: الأقدم = 1. */
  num: number;
  cls: string;
}

/**
 * ترقيم البيّعات داخل الوردية وربط كل بيعة بلونها.
 *
 * الرقم يُعرض كما حُفظ في `group_no`، فيرتّب حسب وقت الخلق لا حسب موقع
 * الصف: أقدم بيعة = 1، والأحدث في الأعلى برقمها الأكبر. ولأن الرقم محفوظ
 * ولا يُشتق من موقعه في القائمة، فإن حذف بيعة يترك فجوة في الأرقام ولا
 * يعيد ترقيم ما بعدها — بيعة 3 تبقى 3 ولا تصير 2.
 *
 * البنود بلا `group_no` (صفوف أنشئت قبل إضافة الترقيم) تأخذ أرقاماً بعد
 * أكبر رقم محفوظ، مرتّبة بأقدم `id`، فلا تختلط بالأرقام المحفوظة.
 */
export function saleGroupBadges(items: SessionSaleItem[]): Map<string, SaleGroupBadge> {
  // الرقم المحفوظ لكل مجموعة، وأقدم id كمرجع احتياطي للترتيب
  const groups = new Map<string, { saved: number | null; oldestId: number }>();
  for (const item of items) {
    const key = saleGroupKey(item);
    const entry = groups.get(key);
    if (!entry) {
      groups.set(key, { saved: item.group_no ?? null, oldestId: item.id });
    } else {
      // بنود الدفعة الواحدة تشارك الرقم، لكن قد يكون بعضها بلا رقم
      if (item.group_no != null) entry.saved = item.group_no;
      if (item.id < entry.oldestId) entry.oldestId = item.id;
    }
  }

  // المرقّم المحفوظ أولاً (تصاعدياً)، ثم غير المرقّم (بأقدم id)
  const ordered = Array.from(groups.entries()).sort((a, b) => {
    if (a[1].saved != null && b[1].saved != null) return a[1].saved - b[1].saved;
    if (a[1].saved != null) return -1;
    if (b[1].saved != null) return 1;
    return a[1].oldestId - b[1].oldestId;
  });

  // البنود بلا رقم محفوظ تُرقَّم بعد أكبر رقم قائم، فلا تشغل رقماً محجوزاً
  let highest = 0;
  groups.forEach((entry) => {
    if (entry.saved != null && entry.saved > highest) highest = entry.saved;
  });

  const badges = new Map<string, SaleGroupBadge>();
  for (const [key, entry] of ordered) {
    const num = entry.saved ?? ++highest;
    badges.set(key, { num, cls: SALE_GROUP_COLORS[(num - 1) % SALE_GROUP_COLORS.length] });
  }
  return badges;
}
