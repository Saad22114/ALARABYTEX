import type { CountItem, CountSummary } from '@/types';

/**
 * حالة سطر الجرد كما تُعرض.
 *
 * أربعُ حالاتٍ لا ثلاث، والفصلُ بينها هو ما يمنع أكبر خطأ في الجرد: أن
 * يُعرض الصنفُ الذي لم يُعدّ على أنه «مطابق». الصفرُ نتيجتان مختلفتان —
 * «قِسته فوجدته كذلك» و«لم تقسه».
 *
 * - `pending`  لم يُرصد بعد.
 * - `counted`  رُصد، والرصيدُ الدفتري مخفيّ فلا يُحكم على مطابقة.
 * - `match`    رُصد، والفرق صفر.
 * - `variance` رُصد، والفرق فوق الحدّ.
 */
export type RowStatus = 'pending' | 'counted' | 'match' | 'variance';

/**
 * الفرق بين الرصيدين، أو `null` إن لم يكن هناك فرقٌ ليُحسب.
 *
 * `null` تعني «لا نعرف» لا «صفر»، ولهذا لا تُعرض ولا تُجمع. أما الصفرُ
 * فحقيقةٌ محسوبة، وكلاهما يظهر في الجدول بمظهرٍ واحد: فراغٌ ودائرة.
 */
export function countedDifference(item: CountItem, yards: string | undefined | null): number | null {
  const text = (yards ?? '').trim();
  if (text === '') return null;
  if (item.system_yards === undefined) return null;
  const counted = Number(text);
  if (!Number.isFinite(counted)) return null;
  return round2(counted - Number(item.system_yards));
}

/** الفرق مقرّباً بمنزلتين — نفس دقّة الحقل المخزَّن، فلا يظهر فرقُ كسرٍ واحد. */
function round2(value: number): number {
  return Math.round(value * 100) / 100;
}

/** يقرّر ما يُكتب في عمود الحالة، بلا أن يختلق مطابقةً لا يعلمها. */
export function rowStatus(item: CountItem, yards: string | undefined | null): RowStatus {
  const diff = countedDifference(item, yards);
  if (diff === null) return item.counted ? 'counted' : 'pending';
  return diff === 0 ? 'match' : 'variance';
}

/** نصّ عمود الحالة، مفصولاً عن الحساب ليُختبر دون واجهة. */
export const ROW_STATUS_LABEL: Record<RowStatus, string> = {
  pending: 'لم يُعدّ',
  counted: 'مرصود',
  match: 'مطابق',
  variance: 'فرق',
};

/**
 * نسبة التقدّم في الجلسة، 0 إلى 100.
 *
 * جلسةٌ بلا أصناف تُعتبر 0٪ لا 100٪: لا أحد عدّ شيئاً، و«منتهٍ» بلا
 * عملٍ لا تعني أنّ العملَ انتهى.
 */
export function progressPercent(summary: CountSummary): number {
  if (summary.items <= 0) return 0;
  return Math.round((summary.counted / summary.items) * 100);
}

/** الأصنافُ التي تغيّرها الشاشة وحدها: ما أمسّه العدّاد، لا كامل الجلسة. */
export function dirtyFabrics(items: CountItem[], draft: DraftMap): number[] {
  return items
    .filter((item) => {
      const cell = draft[item.fabric];
      if (!cell) return false;
      const wasYards =
        item.counted_yards === null || item.counted_yards === undefined ? '' : String(item.counted_yards);
      if (cell.note !== (item.note || '')) return true;
      return !sameYards(cell.yards, wasYards);
    })
    .map((item) => item.fabric);
}

/**
 * هل النصّان يقولان الرقمَ نفسه؟
 *
 * الخادم يعيد `30.00` والقارئ كتب `30`، فالمقارنةُ النصّية تعلن تغييراً
 * لم يحدث: فيرسل طلباً بلا داعٍ ويُعلن المستخدم أنه حفظ شيئاً لم يغيّره.
 * أمّا الفراغُ فليس رقماً — «لم يُعدّ» لا تساوي صفراً.
 */
function sameYards(left: string, right: string): boolean {
  const a = left.trim();
  const b = right.trim();
  if (a === b) return true;
  if (a === '' || b === '') return false;
  const x = Number(a);
  const y = Number(b);
  if (!Number.isFinite(x) || !Number.isFinite(y)) return false;
  return round2(x) === round2(y);
}

export interface DraftMap {
  [fabric: number]: { yards: string; note: string };
}