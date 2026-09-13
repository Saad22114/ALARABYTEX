'use client';

import React, { createContext, useContext, useState, useEffect, useCallback, useMemo } from 'react';
import { AppSettings, SettingsContextValue } from '@/types';
import { getSettings, updateSettings as apiUpdateSettings } from '@/services/settings';
import { configureCurrency } from '@/lib/format';
import { STORAGE_KEYS } from '@/lib/themes';

const SettingsContext = createContext<SettingsContextValue>({
  settings: null,
  loading: true,
  error: null,
  updateSettings: async () => undefined as unknown as AppSettings,
  refreshSettings: async () => {},
});

export function useSettings() {
  return useContext(SettingsContext);
}

export default function SettingsProvider({ children }: { children: React.ReactNode }) {
  const [settings, setSettings] = useState<AppSettings | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const applyTheme = useCallback(() => {
    try {
      const t = localStorage.getItem(STORAGE_KEYS.theme);
      if (t) document.documentElement.dataset.theme = t;
    } catch {}
  }, []);

  const applyCurrency = useCallback((s: AppSettings) => {
    configureCurrency({ symbol: s.currency_symbol, decimals: s.decimal_places });
  }, []);

  const refreshSettings = useCallback(async () => {
    setLoading(true);
    try {
      const res = await getSettings();
      setSettings(res);
      setError(null);
      try {
        localStorage.setItem(STORAGE_KEYS.settings, JSON.stringify(res));
      } catch {}
      applyCurrency(res);
    } catch (err: any) {
      let fallback: AppSettings | null = null;
      try {
        const cached = localStorage.getItem(STORAGE_KEYS.settings);
        if (cached) fallback = JSON.parse(cached) as AppSettings;
      } catch {}
      if (fallback) {
        setSettings(fallback);
        applyCurrency(fallback);
      }
      setError(err?.message || 'خطأ في تحميل الإعدادات');
    } finally {
      setLoading(false);
    }
  }, [applyCurrency]);

  useEffect(() => {
    applyTheme();
    refreshSettings();
  }, [applyTheme, refreshSettings]);

  const updateSettings = useCallback(
    async (partial: Partial<AppSettings>): Promise<AppSettings> => {
      const res = await apiUpdateSettings(partial);
      setSettings(res);
      try {
        localStorage.setItem(STORAGE_KEYS.settings, JSON.stringify(res));
      } catch {}
      applyCurrency(res);
      return res;
    },
    [applyCurrency]
  );

  const value = useMemo(
    () => ({ settings, loading, error, updateSettings, refreshSettings }),
    [settings, loading, error, updateSettings, refreshSettings]
  );

  return <SettingsContext.Provider value={value}>{children}</SettingsContext.Provider>;
}