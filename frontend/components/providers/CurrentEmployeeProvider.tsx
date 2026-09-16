'use client';

import React, { createContext, useContext, useState, useEffect, useMemo, useCallback } from 'react';

export interface CurrentEmployee {
  id: number;
  name: string;
  role_label?: string;
  branch_name?: string;
}

interface CurrentEmployeeContextValue {
  currentEmployee: CurrentEmployee | null;
  setCurrentEmployee: (emp: CurrentEmployee | null) => void;
  clearCurrentEmployee: () => void;
}

const CurrentEmployeeContext = createContext<CurrentEmployeeContextValue>({
  currentEmployee: null,
  setCurrentEmployee: () => {},
  clearCurrentEmployee: () => {},
});

export function useCurrentEmployee() {
  return useContext(CurrentEmployeeContext);
}

const KEY = 'qomash_current_employee';

export function readStoredEmployee(): CurrentEmployee | null {
  try {
    const raw = localStorage.getItem(KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as CurrentEmployee;
    if (!parsed?.id) return null;
    return parsed;
  } catch {
    return null;
  }
}

export default function CurrentEmployeeProvider({ children }: { children: React.ReactNode }) {
  const [currentEmployee, setCurrentEmployeeState] = useState<CurrentEmployee | null>(null);

  useEffect(() => {
    setCurrentEmployeeState(readStoredEmployee());
  }, []);

  const setCurrentEmployee = useCallback((emp: CurrentEmployee | null) => {
    setCurrentEmployeeState(emp);
    try {
      if (emp) localStorage.setItem(KEY, JSON.stringify(emp));
      else localStorage.removeItem(KEY);
    } catch {}
  }, []);

  const clearCurrentEmployee = useCallback(() => setCurrentEmployee(null), [setCurrentEmployee]);

  const value = useMemo(
    () => ({ currentEmployee, setCurrentEmployee, clearCurrentEmployee }),
    [currentEmployee, setCurrentEmployee, clearCurrentEmployee],
  );

  return (
    <CurrentEmployeeContext.Provider value={value}>{children}</CurrentEmployeeContext.Provider>
  );
}

