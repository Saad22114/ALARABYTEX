/**
 * تصدير الجداول إلى CSV.
 *
 * نكتب CSV بأنفسنا بدل الاعتماد على مكتبة: المتطلب هنا صفّ واحد بسيط،
 * والدالة تُجرَّب بـ vitest في `csv.test.ts` فلا حاجة لحزمة إضافية.
 *
 * تفاصيل مهمة:
 * - BOM (`\uFEFF`) في بداية الملف حتى يفتح Excel العربية بترميز صحيح.
 * - كل خلية تُحاط بعلامات اقتباس و`"` داخلها تُضاعف حسب معيار RFC 4180،
 *   وإلا كسر الفاصلة أو السطر داخل النص.
 * - `,` تُفصل الحقول حتى لو كان Excel العربي يفصل بـ `;`.
 */

/** يهرّب خلية واحدة: يضيف الاقتباس ويضاعف الاقتباسات الداخلية. */
export function csvCell(value: unknown): string {
  if (value === null || value === undefined) return '""';
  const s = typeof value === 'string' ? value : String(value);
  return `"${s.replace(/"/g, '""')}"`;
}

export type CsvColumn<T> = {
  /** عنوان العمود كما يظهر في الملف. */
  header: string;
  /** يحوّل كائن الصف إلى قيمة الخلية. */
  value: (row: T) => unknown;
};

/** يبني نص CSV من عناوين الأعمدة وصفوفها. */
export function buildCsv<T>(columns: CsvColumn<T>[], rows: T[]): string {
  const lines = [columns.map((c) => csvCell(c.header)).join(',')];
  for (const row of rows) {
    lines.push(columns.map((c) => csvCell(c.value(row))).join(','));
  }
  return lines.join('\r\n');
}

/**
 * ينزّل ملف CSV في المتصفح.
 *
 * نستخدم anchor مع Blob وعناوين blob مع وقت الإضافة: بعض المتصفحات
 * (خاصة Safari) تتجاهل `download` إن كان العنوان مكرراً من قبل.
 */
export function downloadCsv<T>(filename: string, columns: CsvColumn<T>[], rows: T[]): void {
  if (typeof window === 'undefined') return;
  const content = '\uFEFF' + buildCsv(columns, rows);
  const blob = new Blob([content], { type: 'text/csv;charset=utf-8;' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename.endsWith('.csv') ? filename : `${filename}.csv`;
  a.style.display = 'none';
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  // الإفراغ بعد النقر لا فوراً: بعض المتصفحات تلغي التنزيل إن أُلغي العنوان مبكراً
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

/** اسم ملف بتاريخ اليوم، مثل `customers-2026-09-28.csv`. */
export function csvFilename(base: string, isoDate?: string): string {
  const d = isoDate ? new Date(isoDate) : new Date();
  const stamp = isNaN(d.getTime())
    ? ''
    : `-${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
  return `${base}${stamp}.csv`;
}
