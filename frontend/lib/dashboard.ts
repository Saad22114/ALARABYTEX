/**
 * قراءاتُ أرقامِ الشاشة الرئيسية.
 *
 * ما يجمع هذا الملف أمرٌ واحد: أن تُقرأ أرقامُ الشاشة كما أُريد. وفيه
 * مواضعَ كانت تكذب في الصمت:
 *
 * محورٌ يرسم أرقاماً عاريةً بلا فواصل ولا عملة، فيقرأها الموظف مقداراً
 * مربوعاً فيحسبه أضعافَ ما هو؛ ونسبةٌ تقارن شهراً كاملاً بثلاثةِ أيام ثم
 * تنسبها إلى شهرٍ كاملٍ فتعطي رقماً ضخماً لا معنى له؛ و«لا مبيعات» مكتوبة
 * تحتَ بطاقةِ المصاريف لأنّ الحارسَ لم يكن يعرف أيَّ رقمٍ يحرس.
 */

/** أيّ شهرٍ يُقارَن، ولِماذا قُصِّر إلى يومٍ دون غيره. */
export interface MonthSpan {
  /** YYYY-MM */
  month: string;
  from: string;
  to: string;
  /** يومُ آخر الشهرِ في هذا امتداد — أي عددِ الأيام المقروءة فعلاً. */
  lastDay: number;
  /** أرقامُ الشهر كاملةٌ أم شهرٌ ما زال جارياً فنقرأ منه ما مضى منه فقط. */
  partial: boolean;
}

const MONTHS = [
  'يناير', 'فبراير', 'مارس', 'أبريل', 'مايو', 'يونيو',
  'يوليو', 'أغسطس', 'سبتمبر', 'أكتوبر', 'نوفمبر', 'ديسمبر',
];

function pad(n: number): string {
  return String(n).padStart(2, '0');
}

function daysInMonth(year: number, month1: number): number {
  return new Date(year, month1, 0).getDate();
}

export function monthLabel(ym: string): string {
  const [y, m] = ym.split('-').map(Number);
  return `${MONTHS[(m || 1) - 1] || ''} ${y}`;
}

export function currentMonthKey(now: Date = new Date()): string {
  return `${now.getFullYear()}-${pad(now.getMonth() + 1)}`;
}

export function shiftMonthKey(ym: string, delta: number): string {
  const [y, m] = ym.split('-').map(Number);
  const d = new Date(y, m - 1 + delta, 1);
  return currentMonthKey(d);
}

/**
 * امتدادُ شهرٍ واحد، مقصوصاً إن كان جارياً.
 *
 * «أكتوبر 2026» في الثالث من الشهر شهرٌ فيه ثلاثةُ أيامٍ بعد، لا واحدٌ
 * وثلاثون. وقصُّه إلى اليوم يفعل شيئين يجتمعان: يمنع مقارنةَ شهرٍ ناقصٍ
 * بشهرٍ كامل، ويمنع جملةَ «لا توجد بيانات» في الأيام التي لم يحنْ بعدًا.
 */
export function monthSpan(ym: string, now: Date = new Date()): MonthSpan {
  const [y, m] = ym.split('-').map(Number);
  const full = daysInMonth(y, m);
  const isThisMonth =
    y === now.getFullYear() && m === now.getMonth() + 1;
  const lastDay = isThisMonth ? now.getDate() : full;
  return {
    month: ym,
    from: `${ym}-01`,
    to: `${ym}-${pad(lastDay)}`,
    lastDay,
    partial: isThisMonth && lastDay < full,
  };
}

/**
 * شهران يُقارنان بعدلٍ واحد.
 *
 * المقارنةُ العادلة تقطع الطرفين على العدد نفسِه من الأيام. فإذا قورن شهرٌ
 * جارٍ (١ إلى ٣) بشهرٍ كامل (١ إلى ٣٠) ثم قيل إنّ الثاني «أكبر بنسبة
 * ٩٨٪»، فالذنبُ ليس في الشهر الأول بل في المقارنةِ نفسِها: قاست ثلاثةَ أيامٍ
 * في ثلاثين.
 *
 * والقصُّ لا يقع إلا حين يكون أحدُ الشهرين جارياً. أمّا شهران تمّا فهما يُقرأان
 * كما هما،والاختلاف الاختلافُ في عدد الأيام بينهما (٣١ في مارس و٢٨ في فبراير)
 * واقعٌ لا عيبٌ في الموظف، ولا يُقاس عليه.
 */
export function comparableMonthSpans(
  a: string,
  b: string,
  now: Date = new Date(),
): { a: MonthSpan; b: MonthSpan; days: number; partial: boolean } {
  const spanA = monthSpan(a, now);
  const spanB = monthSpan(b, now);
  const running = spanA.partial || spanB.partial;
  const days = Math.min(spanA.lastDay, spanB.lastDay);
  const clamp = (s: MonthSpan): MonthSpan => {
    if (!running || s.lastDay <= days) return s;
    return {
      ...s,
      to: `${s.month}-${pad(days)}`,
      lastDay: days,
      // قصرُ شهرٍ كاملٍ إلى نصفه ليس «شهراً جارياً»، بل لمقارنةٍ عادلة.
      partial: true,
    };
  };
  const aSpan = clamp(spanA);
  const bSpan = clamp(spanB);
  return {
    a: aSpan,
    b: bSpan,
    days,
    partial: aSpan.partial || bSpan.partial,
  };
}

/**
 * المحورُ يُقاس بالمال لا بأعمدةٍ مجرّدة.
 *
 * فرقمٌ عارٍ على المحور يقرأه الموظف مقداراً لا مقيساً: «٠٤٠٠٠٠٠» فيظنّه
 * أربعين مليوناً وهو أربعةُ آلاف. والمفتاحُ هنا ليس الفصلُ بين الأرقام —
 * فمن لم يُفصِل يظنّ الخمسةَ عشرةَ خمسمئة — بل العملُ، فيعرف أنّه يقرأ
 * ريالات، ولهذا تَقصَر الخاناتُ بالعتبات لا بالريال.
 */
export function axisMoney(n: number): string {
  const v = Math.abs(Number(n) || 0);
  const sign = (Number(n) || 0) < 0 ? '−' : '';
  const units: Array<[number, string]> = [
    [1e9, 'مليار'],
    [1e6, 'مليون'],
    [1e3, 'ألف'],
  ];
  for (const [size, word] of units) {
    if (v >= size) {
      const scaled = v / size;
      // منزلةٌ واحدة تكفي: «٣٫٤ مليون» تُقرأ، و«٣٫٤٥٦٧ مليون» رقمٌ يُشغل.
      const text = scaled >= 100 ? Math.round(scaled).toString() : scaled.toFixed(1).replace(/\.0$/, '');
      return `${sign}${text} ${word}`;
    }
  }
  return `${sign}${Math.round(v).toLocaleString('en-US')}`;
}

/**
 * فرقٌ بين شهرين، بصيغةٍ تقول أيَّ شيءٍ قاست.
 *
 * كان الحارسُ يقول «لا مبيعات في الشهر الأول» تحتَ بطاقة المصاريف، لأنّه
 * لم يكن يعرف أنّ أحداً ما — فصار اللفظُ جزءاً من السؤال. ومنهنا:
 * نسبةٌ بلا سابقةٍ ليست نسبةً، بل قسمةٌ على صفرٍ تُلبَس ثوبَ النسبة.
 */
export function compareLabel(noun: string, a: number, b: number): string {
  const first = Number(a) || 0;
  const second = Number(b) || 0;
  if (first === 0) return `لا ${noun} في الشهر الأول`;
  const pct = ((second - first) / Math.abs(first)) * 100;
  const sign = pct >= 0 ? '+' : '−';
  return `${sign}${Math.abs(pct).toFixed(1)}% مقارنةً بالشهر الأول`;
}

/** الفرقُ عن الفترة السابقة، ولا شيء إن لم تكن هناك فترةٌ سابقة. */
export function deltaText(pct: number | null | undefined): string {
  if (pct === null || pct === undefined) return '';
  const sign = pct >= 0 ? '+' : '−';
  return `${sign}${Math.abs(pct).toFixed(1)}% عن الفترة السابقة`;
}