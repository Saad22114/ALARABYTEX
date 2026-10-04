import { formatNumber } from './format';

/**
 * The shift counter. Both the panel card and the details dialog read it, so it
 * lives here rather than twice.
 */

/**
 * Minutes a shift has been open, measured between the two clocks.
 *
 * It used to be measured against "the current wall clock moved onto the shift's
 * own day", so that a shift deliberately backdated by days would read in
 * minutes rather than days. That reference lands before the opening time for
 * most of the day, so a shift genuinely left open overnight read 13 minutes
 * instead of 24 hours, and one that spanned midnight read a flat zero -- which
 * is the case a person opens this page to find.
 */
export function elapsedMinutes(openedAt: string, nowMs: number): number {
  const opened = new Date(openedAt).getTime();
  if (!Number.isFinite(opened)) return 0;
  return Math.max(0, Math.floor((nowMs - opened) / 60000));
}

/** «منذ ساعتين و 5 دقائق» — hours and minutes, never a day count. */
export function elapsedLabel(minutes: number | null, prefix = 'منذ '): string {
  if (minutes == null) return '';
  const m = Math.max(0, minutes);
  if (m < 60) return `${prefix}${formatNumber(m)} دقيقة`;
  const h = Math.floor(m / 60);
  const r = m % 60;
  if (r === 0) return `${prefix}${formatNumber(h)} ساعة`;
  return `${prefix}${formatNumber(h)} ساعة و ${formatNumber(r)} دقيقة`;
}