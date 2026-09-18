'use client';

import React, { createContext, useContext, useMemo, useState, useCallback, useEffect } from 'react';
import type { Employee } from '@/types';
import { login as apiLogin, logout as apiLogout, fetchMe } from '@/services/auth';
import { clearAuthStorage, getStoredEmployee, getStoredToken, saveAuth } from '@/lib/authStorage';

export type AuthStatus = 'authed' | 'guest';

interface AuthContextValue {
  status: AuthStatus;
  token: string | null;
  employee: Employee | null;
  isManager: boolean;
  login: (username: string, password: string) => Promise<Employee>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue>({
  status: 'guest',
  token: null,
  employee: null,
  isManager: false,
  login: async () => {
    throw new Error('AuthProvider غير مهيأ');
  },
  logout: async () => {},
});

export function useAuth() {
  return useContext(AuthContext);
}

export default function AuthProvider({ children }: { children: React.ReactNode }) {
  const [token, setToken] = useState<string | null>(() => getStoredToken());
  const [employee, setEmployee] = useState<Employee | null>(() => getStoredEmployee());
  const [status, setStatus] = useState<AuthStatus>(() =>
    getStoredToken() && getStoredEmployee() ? 'authed' : 'guest'
  );

  useEffect(() => {
    let cancelled = false;
    if (!getStoredToken()) return;
    fetchMe()
      .then((fresh) => {
        if (!cancelled) {
          setEmployee(fresh);
          saveAuth(getStoredToken() || '', fresh);
        }
      })
      .catch(() => {
        if (!cancelled) {
          clearAuthStorage();
          setToken(null);
          setEmployee(null);
          setStatus('guest');
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const login = useCallback(async (username: string, password: string) => {
    const res = await apiLogin(username, password);
    saveAuth(res.token, res.employee);
    setToken(res.token);
    setEmployee(res.employee);
    setStatus('authed');
    return res.employee;
  }, []);

  const logout = useCallback(async () => {
    await apiLogout().catch(() => {});
    clearAuthStorage();
    setToken(null);
    setEmployee(null);
    setStatus('guest');
  }, []);

  const value = useMemo(
    () => ({
      status,
      token,
      employee,
      isManager: employee?.role === 'admin',
      login,
      logout,
    }),
    [status, token, employee, login, logout],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}