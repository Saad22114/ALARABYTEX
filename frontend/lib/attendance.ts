/**
 * منطق عرض الحضور والانصراف، منفصلاً عن الشاشة ليبقى قابلاً للاختبار.
 *
 * كل ما هنا حالةٌ واحدة مُقلَّبة على نفسها: الصفر. `worked_minutes === null`
 * تعني «لم يخرج بعد» لا «عمل صفر دقيقة»، ومن يخلط بينهما يعرض موظفاً
 * داخل الدوام منذ ساعاتٍ على أنه لم يعمل دقيقةً واحدة — أي يُحتسب غائباً
 * وهو حاضر. فالدالة `workedText` ترفض أن تُخترع ساعةً لسطرٍ مفتوح.
 */

import type { BadgeVariant } from '@/components/ui/Badge';
import type { AttendanceRecord, AttendanceStatus } from '@/types';

/**
 * الحالة تُترجم مرة واحدة في هذا الملف. الخريطة تقيم بثلاثة لا بأربعة:
 * «متأخر» و«انصراف مبكر» يحذّران، و«غائب» و«عطلة» لا يوبّخان — الغائب
 * خصمٌ من الراتب، والعطلة ليست يوماً ناقصاً أصلاً.
 */
export const STATUS_LABEL: Record<AttendanceStatus, string> = {
  present: 'حاضر',
  late: 'متأخر',
  early_leave: 'انصراف مبكر',
  absent: 'غائب',
  excused: 'مبرر',
  inside: 'داخل الدوام',
  off: 'عطلة',
};

export const STATUS_VARIANT: Record<AttendanceStatus, BadgeVariant> = {
  present: 'success',
  late: 'warning',
  early_leave: 'warning',
  absent: 'danger',
  excused: 'neutral',
  inside: 'success',
  off: 'neutral',
};

export const EXCUSE_LABEL: Record<string, string> = {
  none: 'لا شيء',
  sick: 'مريض',
  leave: 'إجازة',
  official: 'مهمة رسمية',
  other: 'أخرى',
};

export const EXCUSE_OPTIONS = [
  { value: 'none', label: EXCUSE_LABEL.none },
  { value: 'sick', label: EXCUSE_LABEL.sick },
  { value: 'leave', label: EXCUSE_LABEL.leave },
  { value: 'official', label: EXCUSE_LABEL.official },
  { value: 'other', label: EXCUSE_LABEL.other },
];

/**
 * أسماء الأيام بترتيب ``date.weekday()`` — لا بترتيب ``getDay()``.
 *
 * الخلطُ بينهما يزيح عطلة الجمعة يوماً كاملاً، فيصير موظفٌ يوم أربعائه
 * عطلةً ويوم جمعته يومَ عمل. وقد ثبتُ الترتيب في الخلفية على
 * ``date.weekday()``، فبينهما هنا.
 */
export const WEEKDAY_NAME: Record<number, string> = {
  0: 'الاثنين',
  1: 'الثلاثاء',
  2: 'الأربعاء',
  3: 'الخميس',
  4: 'الجمعة',
  5: 'السبت',
  6: 'الأحد',
};

/** كل أيام الأسبوع بترتيب الخلفية، لعرضها بترتيبٍ لا يخلطه الناظر. */
export const ALL_WEEKDAYS = [0, 1, 2, 3, 4, 5, 6];

/** هل الحالة تستحق تمييزاً في الجدول أم تُقرأ من سطرها وحده؟ */
export function statusLabel(status: string): string {
  return STATUS_LABEL[status as AttendanceStatus] || status;
}

export function statusVariant(status: string): BadgeVariant {
  return STATUS_VARIANT[status as AttendanceStatus] || 'neutral';
}

/**
 * دقائق ← «7:30». ساعةٌ واحدة تُكتب 60 لا 1:00، و«0» لا «00».
 *
 * الدقائق السالبة مستحيلة في قاعدة البيانات، لكنها ممكنة في ردّ مُحَرَّر
 * يدوياً أو في حسابٍ نتج عن خطأ: تُقصّ عند الصفر بدل أن تُعرض «-0:30»،
 * لأن رقماً سالباً في جدول حضور يُقرأ كحقيقةٍ غريبة لا كخطأ.
 */
export function minutesToClock(minutes: number | null | undefined): string {
  if (minutes === null || minutes === undefined) return '';
  const total = Math.max(0, Math.floor(minutes));
  const hours = Math.floor(total / 60);
  const rest = total % 60;
  return `${hours}:${rest < 10 ? '0' : ''}${rest}`;
}

/**
 * «8 ساعات و30 دقيقة» — للملخّص لا للجدول. الحقل الفردي يكفي بالدقائق
 * في العمود الضيّق، والعبارة المكتوبةة تكفي في البطاقة الواسعة.
 */
export function workedText(minutes: number | null | undefined): string {
  if (minutes === null || minutes === undefined) return 'لم يخرج بعد';
  if (minutes <= 0) return 'لا عمل';
  const hours = Math.floor(minutes / 60);
  const rest = minutes % 60;
  if (hours === 0) return `${rest} دقيقة`;
  if (rest === 0) return `${hours} ساعة`;
  return `${hours} ساعة و${rest} دقيقة`;
}

/**
 * صيغة العدد: واحدٌ ومثنًى وجمع.
 *
 * ثلاثةٌ وعشرةٌ يقعان في «دقائق»، والخمسةُ والعشرون في «دقيقة». من كتب
 * «دقيقتان» بجوار الرقم 2 كتب جملةً عربيةً جُرّدت من العدد، فيقرأها
 * العربي «دقيقتين» فيبحث عن رقمٍ ليس في السطر.
 */
export function pluralize(
  count: number,
  singular: string,
  dual: string,
  plural: string,
): string {
  if (count === 1) return singular;
  if (count === 2) return dual;
  if (count >= 3 && count <= 10) return plural;
  return singular;
}

/**
 * الدقائق في جملة: «55 دقيقة»، «120 دقيقتان»… بلغة العرض لا بلغة التخزين.
 *
 * «لا شيء» لكل صفرٍ أو فارغ. والصفرُ هنا معنىً لا غيابُ معلومة: الحقلُ
 * المشتقّ في ردٍّ قد لا يحمل أصلاً.
 */
export function minutesLabel(minutes: number | null | undefined): string {
  if (!minutes) return 'لا شيء';
  return `${minutes} ${pluralize(minutes, 'دقيقة', 'دقيقتان', 'دقائق')}`;
}

/**
 * استحقاق النقص: كم دقيقةً ينقص الموظف عن يومه الكامل.
 *
 * يومٌ ناقص لا يُقرّض. من لم يُسجَّل له دخول أصلاً ينقصه اليوم كله، ولو
 * ظهر ذلك الرقم على راتبه كأنّه أراد أن يعمل ولم يستطع — والصحيح أن
 * يعمل غداً. فنُبقي الرقم صفراً، والقرارُ لمن يقرأ التقرير.
 */
/**
 * كم دقيقةً ينقص عملَ هذا اليوم عن يوم العمل.
 *
 * ``workdayMinutes`` قد يكون ``null`` أي «لا نعرف يوم العمل» — وهي
 * الحالة التي يفترض فيها غيري رقماً فيظهر «ناقص ساعتان» تحت كل سطرٍ
 * من جدولٍ لم يُفتح بعد سياسته. فالنقصُ يُخفى عند عدم اليقين: الرقمُ
 * المختلَق يُقرأ حُكماً على الموظف.
 */
export function shortfall(
  minutes: number | null,
  workdayMinutes: number | null,
): number {
  if (!minutes || !workdayMinutes) return 0;
  return Math.max(0, workdayMinutes - minutes);
}

/**
 * الصفّ مغلق أم مفتوح؟ السطر المفتوح يُقرأ «داخل الدوام» لا «حاضر»:
 * من انتهى ومن ما زال يعمل فرقٌ يُفقد بالأرقام: مطابقةُ الأول على
 * الثاني تجعل من نسي أن يخرج يبدو أنه أنهى يومه في وقته.
 */
export function isOpen(record: Pick<AttendanceRecord, 'login_at' | 'logout_at'>): boolean {
  return Boolean(record.login_at) && !record.logout_at;
}

/**
 * هل تغيّر ما كتبه المستخدم في حقلي التبرير والملاحظة؟
 *
 * الحقولُ الأربعة مقصودةُ الكتابة؛ وهذا للحقلين النصّيين وحدهما، لأن
 * المقارنةَ بينهما نصٌّ بنصّ. أمّا الوقتان فهما تاريخان يُقارنان
 * بـ ``dirtyTimes``.
 */
export function dirtyRecord(
  draft: Pick<Partial<AttendanceRecord>, 'excuse' | 'note'>,
  saved: AttendanceRecord,
): boolean {
  if (draft.excuse !== undefined && draft.excuse !== saved.excuse) return true;
  if (draft.note !== undefined && draft.note !== saved.note) return true;
  return false;
}

/**
 * هل تغيّر الوقتان عن ما في السجل؟
 *
 * الحقلان نصّان محليان، والوقت في السجل تاريخٌ بصيغة ISO. فالمقارنةُ
 * حقلاً بحقل تكسر كلَّ مرّة، و«لا تغيّر» لا تعني «السلسلة الفارغة
 * سلسلةٌ فارغة»: الحقلَ الفارغَ مقارنةٌ مع وقتٍ محفوظ تغييرٌ حقيقي —
 * تفريغُ وقت الخروج هو ما يجعل موظفاً نسي أن يخرج يبدو أنه أنهى يومه.
 */
export function dirtyTimes(
  draftLogin: string,
  draftLogout: string,
  saved: AttendanceRecord,
): boolean {
  return (
    draftLogin !== toDateTimeLocal(saved.login_at) ||
    draftLogout !== toDateTimeLocal(saved.logout_at)
  );
}

/** نسبة ما عمل إلى ما كان عليه أن يعمله، مقصوصةً إلى 100 وبحدٍّ أدنى صفر. */
export function attainmentPercent(
  workedMinutes: number,
  expectedMinutes: number,
): number {
  if (!expectedMinutes) return 0;
  return Math.min(100, Math.max(0, Math.round((workedMinutes / expectedMinutes) * 100)));
}

/** الشهر بالعربية («سبتمبر 2026») — يُبنى من ISO بلا المنطقة الزمنية. */
export function monthLabel(iso: string): string {
  if (!iso || iso.length < 7) return '';
  const months = [
    'يناير', 'فبراير', 'مارس', 'أبريل', 'مايو', 'يونيو',
    'يوليو', 'أغسطس', 'سبتمبر', 'أكتوبر', 'نوفمبر', 'ديسمبر',
  ];
  const index = Number(iso.slice(5, 7)) - 1;
  if (index < 0 || index > 11) return '';
  return `${months[index]} ${iso.slice(0, 4)}`;
}

/** «اليوم»، «أمس»، «قبل يومين»، أو تاريخٌ كامل. */
export function relativeDayLabel(iso: string, today: string): string {
  if (!iso || !today) return iso || '';
  if (iso === today) return 'اليوم';
  const diff = daysBetween(iso, today);
  if (diff === 1) return 'أمس';
  if (diff === 2) return 'قبل يومين';
  return iso;
}

/**
 * ISO ← قيمة حقل ``datetime-local``.
 *
 * الخادم يخزّن UTC ويعرضه بتوقيت المتصفح، وحقل الإدخال يريد وقتاً
 * محلياً بلا منطقة.ollars ومجرد إفلات الـ Z: الحقل يعرض «00:00»
 * لمحو دخل عند التاسعة، ومن حفظها سجّل دخولاً فجراً. فنحوّل الطرفين
 * صراحةً عبر ``Date``.
 */
export function toDateTimeLocal(iso: string | null | undefined): string {
  if (!iso) return '';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return '';
  return `${d.getFullYear()}-${pad2(d.getMonth() + 1)}-${pad2(d.getDate())}T${pad2(d.getHours())}:${pad2(d.getMinutes())}`;
}

/** قيمة ``datetime-local`` ← ISO. سلسلةٌ فارغة تعني «لا وقت»، لا «منتصف الليل». */
export function fromDateTimeLocal(value: string): string | null {
  if (!value) return null;
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return null;
  return d.toISOString();
}

/** الساعة وحدها «07:00» — لحقول نافذة الدوام. */
export function clockLabel(iso: string | null | undefined): string {
  if (!iso) return '';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return '';
  return `${pad2(d.getHours())}:${pad2(d.getMinutes())}`;
}

function pad2(value: number): string {
  return String(value).padStart(2, '0');
}

function daysBetween(from: string, to: string): number {
  const a = Date.parse(`${from}T00:00:00`);
  const b = Date.parse(`${to}T00:00:00`);
  if (Number.isNaN(a) || Number.isNaN(b)) return 0;
  return Math.round((b - a) / 86_400_000);
}