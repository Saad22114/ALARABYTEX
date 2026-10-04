'use client';

import { useEffect, useRef, useState } from 'react';
import { Check, Copy, TriangleAlert } from 'lucide-react';
import { copyText } from '@/lib/clipboard';

type Props = {
  value: string | null | undefined;
  /** ما يُقرأ عند تمرير المؤشّر، ويُقال لقارئ الشاشة أيضاً. */
  title?: string;
  className?: string;
};

type State = 'idle' | 'ok' | 'fail';

/**
 * زرُّ نسخٍ صغيرٌ بجانب الرقم.
 *
 * أخضرُ يعني أنّ النصّ صار في الحافظة، وكهرمانيُّ يعني أنّه لم يصِر.
 * ورسالةُ الفشلِ ليست زينة، بل هي التي تمنع اللصقَ الخاطئ: من يُقال له
 * «تمّ» على جهازٍ لا يسمحُ بالكتابةِ يظنّ أنّ الرقمَ في يده، فيلصقُ
 * نصّاً قديماً في فاتورة زبونٍ آخر.
 *
 * ولا نستعملُ هنا نشرةً عامة. من ينسخُ عشرين رقماً في دقيقةٍ تتكدّس
 * عليه النشراتُ وتُخفي ما أُصلح، والأيقونةُ وحدها تكفي.
 */
export default function CopyButton({ value, title = 'نسخ الرقم', className = '' }: Props) {
  const [state, setState] = useState<State>('idle');
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => () => {
    if (timer.current) clearTimeout(timer.current);
  }, []);

  const text = (value || '').trim();
  // لا زرّ ميّتاً عند خانةٍ خالية: الجدولُ يعرض خطاً بدل رقم، وزرٌ
  // معطّل عندها يوهم بأنّ هناك ما يُنسخ.
  if (!text) return null;

  const handle = async () => {
    const ok = await copyText(text);
    setState(ok ? 'ok' : 'fail');
    if (timer.current) clearTimeout(timer.current);
    // الفشلُ وقتُه أطول، فالموظفُ قد لا ينتبهُ لأشارةٍ خاطئة.
    timer.current = setTimeout(() => setState('idle'), ok ? 1600 : 2600);
  };

  const tone = {
    idle: 'text-neutral-400',
    ok: 'text-emerald-600',
    fail: 'text-amber-600',
  }[state];
  const label = state === 'ok'
    ? 'تمّ نسخ الرقم'
    : state === 'fail' ? 'تعذّر نسخ الرقم' : title;

  return (
    <button
      type="button"
      onClick={handle}
      title={label}
      aria-label={label}
      className={`p-1 rounded-lg transition-colors hover:bg-sand-100 ${tone} ${className}`}
    >
      {state === 'ok' ? (
        <Check size={15} />
      ) : state === 'fail' ? (
        <TriangleAlert size={15} />
      ) : (
        <Copy size={15} />
      )}
      <span role="status" aria-live="polite" className="sr-only">{label}</span>
    </button>
  );
}
