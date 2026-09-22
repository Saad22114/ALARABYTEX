'use client';

import React, {
  createContext,
  useContext,
  useState,
  useEffect,
  useMemo,
  useCallback,
} from 'react';
import { AuthSession, SessionEmployee } from '@/types';
import {
  hasToken,
  loadSession,
  login as doLogin,
  logout as doLogout,
  readStoredSession,
  setAuthCredentials,
} from '@/services/auth';

interface AuthContextValue {
  session: AuthSession | null;
  loading: boolean;
  login: (username: string, password: string) => Promise<AuthSession>;
  logout: () => Promise<void>;
  updateEmployee: (patch: Partial<SessionEmployee>) => void;
}

const AuthContext = createContext<AuthContextValue>({
  session: null,
  loading: true,
  login: async () => {
    throw new Error('AuthProvider غير مهيأ');
  },
  logout: async () => {},
  updateEmployee: () => {},
});

export function useAuth() {
  return useContext(AuthContext);
}

export default function AuthProvider({ children }: { children: React.ReactNode }) {
  const [session, setSession] = useState<AuthSession | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      if (!hasToken()) {
        if (!cancelled) setLoading(false);
        return;
      }
      const stored = readStoredSession();
      if (stored && !cancelled) setSession(stored);
      try {
        const fresh = await loadSession();
        if (!cancelled) setSession(fresh);
      } catch {
        if (!cancelled) setSession(null);
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const login = useCallback(async (username: string, password: string) => {
    const session = await doLogin(username, password);
    setSession(session);
    return session;
  }, []);

  const logout = useCallback(async () => {
    await doLogout();
    setSession(null);
  }, []);

  const updateEmployee = useCallback((patch: Partial<SessionEmployee>) => {
    setSession((prev) => {
      if (!prev) return prev;
      const next: AuthSession = {
        ...prev,
        employee: { ...prev.employee, ...patch } as SessionEmployee,
      };
      setAuthCredentials(next.token, next);
      return next;
    });
  }, []);

  const value = useMemo(
    () => ({ session, loading, login, logout, updateEmployee }),
    [session, loading, login, logout, updateEmployee],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}