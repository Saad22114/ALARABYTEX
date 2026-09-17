'use client';

import { useCallback, useEffect, useRef, useState } from 'react';

export function useUrlState(key: string, defaultValue: string): [string, (value: string) => void];
export function useUrlState(key: string, defaultValue: number): [number, (value: number) => void];
export function useUrlState<T extends string | number>(
  key: string,
  defaultValue: T,
): [T, (value: T) => void];
export function useUrlState<T extends string | number>(
  key: string,
  defaultValue: T,
): [T, (value: T) => void] {
  const [value, setValue] = useState<T>(defaultValue);
  const defaultRef = useRef(defaultValue);

  useEffect(() => {
    if (typeof window === 'undefined') return;
    const raw = new URLSearchParams(window.location.search).get(key);
    if (raw === null) return;
    if (typeof defaultValue === 'number') {
      const n = Number(raw);
      if (!Number.isNaN(n)) setValue(n as T);
    } else {
      setValue(raw as T);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);

  const update = useCallback(
    (next: T) => {
      setValue(next);
      if (typeof window === 'undefined') return;
      const url = new URL(window.location.href);
      if (String(next) === '' || next === defaultRef.current) url.searchParams.delete(key);
      else url.searchParams.set(key, String(next));
      window.history.replaceState(null, '', url.toString());
    },
    [key],
  );

  return [value, update];
}
