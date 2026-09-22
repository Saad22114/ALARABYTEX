'use client';

import React, { createContext, useContext, useState, useCallback, useEffect, useMemo } from 'react';
import { FONT_PRESETS, STORAGE_KEYS } from '@/lib/themes';

interface FontContextValue {
  font: string;
  setFont: (id: string) => void;
  fontScale: number;
  setFontScale: (scale: number) => void;
}

const FontContext = createContext<FontContextValue>({
  font: 'cairo',
  setFont: () => {},
  fontScale: 100,
  setFontScale: () => {},
});

export function useFonts() {
  return useContext(FontContext);
}

const FONT_VARS: Record<string, string> = {
  cairo: 'var(--font-cairo)',
  ibm: 'var(--font-ibm)',
  amiri: 'var(--font-amiri)',
  noto: 'var(--font-noto)',
  almarai: 'var(--font-almarai)',
  tajawal: 'var(--font-tajawal)',
  rubik: 'var(--font-rubik)',
  changa: 'var(--font-changa)',
  mada: 'var(--font-mada)',
};

function applyFont(id: string) {
  try {
    document.documentElement.style.setProperty('--app-font', FONT_VARS[id] || FONT_VARS.cairo);
    document.body.style.fontFamily = FONT_VARS[id] || FONT_VARS.cairo;
  } catch {}
}

function applyScale(scale: number) {
  try {
    document.documentElement.style.fontSize = `${scale}%`;
  } catch {}
}

export default function FontProvider({ children }: { children: React.ReactNode }) {
  const [font, setFontState] = useState('cairo');
  const [fontScale, setFontScaleState] = useState(100);

  useEffect(() => {
    try {
      const stored = localStorage.getItem(STORAGE_KEYS.font);
      if (stored && FONT_PRESETS.some((p) => p.id === stored)) {
        setFontState(stored);
        applyFont(stored);
        return;
      }
      applyFont('cairo');
    } catch {
      applyFont('cairo');
    }

    try {
      const s = localStorage.getItem(STORAGE_KEYS.fontScale);
      const scale = s ? Number(s) : 100;
      if (!Number.isFinite(scale) || scale < 70 || scale > 200) {
        setFontScaleState(100);
        applyScale(100);
        return;
      }
      setFontScaleState(scale);
      applyScale(scale);
    } catch {
      applyScale(100);
    }
  }, []);

  const setFont = useCallback((id: string) => {
    setFontState(id);
    applyFont(id);
    try {
      localStorage.setItem(STORAGE_KEYS.font, id);
    } catch {}
  }, []);

  const setFontScale = useCallback((scale: number) => {
    setFontScaleState(scale);
    applyScale(scale);
    try {
      localStorage.setItem(STORAGE_KEYS.fontScale, String(scale));
    } catch {}
  }, []);

  const value = useMemo(() => ({ font, setFont, fontScale, setFontScale }), [font, setFont, fontScale, setFontScale]);

  return <FontContext.Provider value={value}>{children}</FontContext.Provider>;
}