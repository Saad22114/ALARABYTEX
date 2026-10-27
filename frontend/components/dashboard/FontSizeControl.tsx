'use client';

import { useEffect, useState } from 'react';
import { Minus, Plus, RotateCcw, Type } from 'lucide-react';
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
      <button
        type="button"
        aria-label="إعادة حجم الخط إلى الافتراضي"
        title="إعادة الحجم الافتراضي (100%)"
        disabled={scale === DEFAULT_FONT_SCALE}
        onClick={() => updateScale(DEFAULT_FONT_SCALE)}
        className="rounded-lg p-1.5 text-neutral-500 transition hover:bg-sand-100 hover:text-neutral-800 disabled:cursor-not-allowed disabled:opacity-40 dark:hover:text-neutral-100"
      >
        <RotateCcw size={14} />
      </button>
    </div>
  );
}
