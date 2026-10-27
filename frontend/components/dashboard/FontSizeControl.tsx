'use client';

import { useEffect, useState } from 'react';
import { Ellipsis, Minus, Plus, Type } from 'lucide-react';
import {
  applyFontScale,
  DEFAULT_FONT_SCALE,
  FONT_SCALE_STORAGE_KEY,
  FONT_SCALE_STEP,
  loadFontScale,
  MAX_FONT_SCALE,
  MIN_FONT_SCALE,
} from '@/lib/fontScale';

export default function FontSizeControl() {
  const [scale, setScale] = useState(DEFAULT_FONT_SCALE);

  useEffect(() => {
    setScale(applyFontScale(loadFontScale()));
  }, []);

  const updateScale = (next: number) => {
    const applied = applyFontScale(next);
    setScale(applied);
    try { localStorage.setItem(FONT_SCALE_STORAGE_KEY, String(applied)); } catch {}
  };

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (!event.altKey || !event.shiftKey || event.ctrlKey || event.metaKey) return;
      const target = event.target;
      if (target instanceof HTMLElement && (target.isContentEditable || /^(INPUT|TEXTAREA|SELECT)$/.test(target.tagName))) return;

      if (event.key === 'ArrowUp') {
        event.preventDefault();
        updateScale(scale + FONT_SCALE_STEP);
      } else if (event.key === 'ArrowDown') {
        event.preventDefault();
        updateScale(scale - FONT_SCALE_STEP);
      } else if (event.key === '0' || event.code === 'Digit0') {
        event.preventDefault();
        updateScale(DEFAULT_FONT_SCALE);
      }
    };

    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [scale]);

  return (
    <div role="group" aria-label="التحكم في حجم الكتابة" className="inline-flex items-center gap-0.5 rounded-xl border border-sand-200 bg-surface p-1 text-neutral-600 shadow-sm">
      <Type size={15} className="mx-1 text-brand-600" aria-hidden="true" />
      <span className="hidden px-1 text-[11px] font-medium text-neutral-500 xl:inline">حجم الخط</span>
      <button
        type="button"
        aria-label="تصغير الخط"
        title="تصغير الخط"
        disabled={scale <= MIN_FONT_SCALE}
        onClick={() => updateScale(scale - FONT_SCALE_STEP)}
        className="rounded-lg border border-sand-200 bg-sand-50 p-1.5 transition hover:bg-sand-100 disabled:cursor-not-allowed disabled:opacity-40"
      >
        <Minus size={15} />
      </button>
      <span className="min-w-10 text-center text-xs font-extrabold tabular-nums text-neutral-800 dark:text-neutral-100" aria-live="polite">{scale}%</span>
      <button
        type="button"
        aria-label="تكبير الخط"
        title="تكبير الخط"
        disabled={scale >= MAX_FONT_SCALE}
        onClick={() => updateScale(scale + FONT_SCALE_STEP)}
        className="rounded-lg border border-sand-200 bg-sand-50 p-1.5 transition hover:bg-sand-100 disabled:cursor-not-allowed disabled:opacity-40"
      >
        <Plus size={15} />
      </button>
      <details className="relative">
        <summary
          aria-label="خيارات حجم الخط واختصارات لوحة المفاتيح"
          title="خيارات حجم الخط"
          className="flex cursor-pointer list-none items-center justify-center rounded-lg p-1.5 text-neutral-500 transition hover:bg-sand-100 hover:text-neutral-800 dark:hover:text-neutral-100"
        >
          <Ellipsis size={17} />
        </summary>
        <div className="absolute left-0 top-full z-50 mt-2 w-56 rounded-xl border border-sand-200 bg-surface p-3 text-right shadow-xl">
          <button
            type="button"
            disabled={scale === DEFAULT_FONT_SCALE}
            onClick={() => updateScale(DEFAULT_FONT_SCALE)}
            className="w-full rounded-lg px-3 py-2 text-sm font-semibold text-neutral-700 transition hover:bg-sand-50 disabled:cursor-not-allowed disabled:opacity-45 dark:text-neutral-200 dark:hover:bg-sand-100"
          >
            إعادة الحجم الافتراضي (100%)
          </button>
          <p className="mt-2 border-t border-sand-100 px-2 pt-2 text-[11px] leading-5 text-neutral-500">
            اختصارات: Alt + Shift + ↑ / ↓ للتكبير والتصغير، وAlt + Shift + 0 للإعادة.
          </p>
        </div>
      </details>
    </div>
  );
}
