import { apiRequest } from './api';
import { AuthSession } from '@/types';

const TOKEN_KEY = 'qomash_token';
const SESSION_KEY = 'qomash_session';
export const LOGIN_PENDING_KEY = 'qomash_login_pending';
export const MUST_CHANGE_KEY = 'qomash_must_change';

export function getToken(): string | null {
  if (typeof window === 'undefined') return null;
  try {
    return localStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

export function hasToken(): boolean {
  return Boolean(getToken());
}

export function setAuthCredentials(token: string, session: AuthSession): void {
  try {
    localStorage.setItem(TOKEN_KEY, token);
    localStorage.setItem(SESSION_KEY, JSON.stringify(session));
  } catch {}
}

export function readStoredSession(): AuthSession | null {
  if (typeof window === 'undefined') return null;
  try {
    const raw = localStorage.getItem(SESSION_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as AuthSession;
    if (!parsed?.token || !parsed?.employee?.id) return null;
    return parsed;
  } catch {
    return null;
  }
}

export function clearAuthStorage(): void {
  try {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(SESSION_KEY);
    sessionStorage.removeItem(MUST_CHANGE_KEY);
    sessionStorage.removeItem(LOGIN_PENDING_KEY);
  } catch {}
}

export async function login(
  username: string,
  password: string,
): Promise<AuthSession> {
  const session = await apiRequest<AuthSession>('/auth/login/', {
    method: 'POST',
    body: JSON.stringify({ username, password }),
  });
  setAuthCredentials(session.token, session);
  try {
    if (!session.employee?.must_change_password) {
      sessionStorage.removeItem(MUST_CHANGE_KEY);
    }
  } catch {}
  return session;
}

export async function logout(): Promise<void> {
  try {
    await apiRequest<{ detail: string }>('/auth/logout/', { method: 'POST' });
  } catch {
    // تجاهل أخطاء الاتصال — نمسح الجلسة محلياً على أي حال
  } finally {
    clearAuthStorage();
  }
}

export async function refreshSession(): Promise<AuthSession> {
  const me = await apiRequest<Omit<AuthSession, 'token'>>('/auth/me/');
  const session: AuthSession = { token: getToken() || '', ...me };
  if (session.token) setAuthCredentials(session.token, session);
  try {
    if (session.employee && !session.employee.must_change_password) {
      sessionStorage.removeItem(MUST_CHANGE_KEY);
    }
  } catch {}
  return session;
}

export async function changePassword(
  currentPassword: string,
  newPassword: string,
): Promise<AuthSession> {
  const res = await apiRequest<
    Omit<AuthSession, 'token'> & { detail?: string }
  >('/auth/change-password/', {
    method: 'POST',
    body: JSON.stringify({
      current_password: currentPassword,
      new_password: newPassword,
      confirm_password: newPassword,
    }),
  });
  const session: AuthSession = { token: getToken() || '', ...res };
  if (session.token) setAuthCredentials(session.token, session);
  return session;
}

export async function loadSession(): Promise<AuthSession | null> {
  const token = getToken();
  if (!token) return null;
  try {
    return await refreshSession();
  } catch {
    clearAuthStorage();
    return null;
  }
}