'use client';

import React, { createContext, useContext, useState, useCallback, useEffect, useMemo } from 'react';
import { STORAGE_KEYS } from '@/lib/themes';

interface ThemeContextValue {
  theme: string;
  setTheme: (id: string) => void;
  dark: boolean;
  toggleDark: () => void;
}

const ThemeContext = createContext<ThemeContextValue>({
  theme: 'green',
  setTheme: () => {},
  dark: false,
  toggleDark: () => {},
});

export function useTheme() {
  return useContext(ThemeContext);
}

export default function ThemeProvider({ children }: { children: React.ReactNode }) {
  const [theme, setThemeState] = useState('green');
  const [dark, setDark] = useState(false);

  useEffect(() => {
    try {
      const t = localStorage.getItem(STORAGE_KEYS.theme);
      if (t) {
        setThemeState(t);
        document.documentElement.dataset.theme = t;
      }
    } catch {}
  }, []);

  useEffect(() => {
    try {
      const stored = localStorage.getItem(STORAGE_KEYS.dark);
      const isDark = stored ? stored === '1' : window.matchMedia('(prefers-color-scheme: dark)').matches;
      setDark(isDark);
      document.documentElement.classList.toggle('dark', isDark);
    } catch {}
  }, []);

  const setTheme = useCallback((id: string) => {
    setThemeState(id);
    try {
      localStorage.setItem(STORAGE_KEYS.theme, id);
    } catch {}
    document.documentElement.dataset.theme = id;
  }, []);

  const toggleDark = useCallback(() => {
    setDark((prev) => {
      const next = !prev;
      try {
        localStorage.setItem(STORAGE_KEYS.dark, next ? '1' : '0');
      } catch {}
      document.documentElement.classList.toggle('dark', next);
      return next;
    });
  }, []);

  const value = useMemo(() => ({ theme, setTheme, dark, toggleDark }), [theme, setTheme, dark, toggleDark]);

  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}