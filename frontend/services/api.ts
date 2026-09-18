import { clearAuthStorage, getStoredToken } from '@/lib/authStorage';

export const API_URL =
  process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000/api';

export function buildQuery(params: Record<string, string | number | boolean | undefined | null>): string {
  const sp = new URLSearchParams();
  Object.entries(params).forEach(([key, val]) => {
    if (val !== undefined && val !== null && val !== '') {
      sp.append(key, String(val));
    }
  });
  const s = sp.toString();
  return s ? `?${s}` : '';
}

export async function apiRequest<T>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  const url = `${API_URL}${path}`;
  const isForm = typeof FormData !== 'undefined' && options.body instanceof FormData;
  const token = getStoredToken();
  const authHeaders: Record<string, string> = token && !path.startsWith('/auth/login')
    ? { Authorization: `Token ${token}` }
    : {};
  const res = await fetch(url, {
    headers: isForm
      ? { ...authHeaders, ...(options.headers || {}) }
      : {
          'Content-Type': 'application/json',
          ...authHeaders,
          ...(options.headers || {}),
        },
    ...options,
  });

  if (res.status === 204) return undefined as T;

  const data = await res.json().catch(() => null);

  if (!res.ok) {
    if (res.status === 401 && typeof window !== 'undefined') {
      clearAuthStorage();
      if (window.location.pathname !== '/login') window.location.href = '/login';
    }
    if (data && typeof data === 'object') {
      if (data.detail) {
        throw new Error(data.detail);
      }
      const firstKey = Object.keys(data)[0];
      if (firstKey) {
        const val = data[firstKey];
        const msg = Array.isArray(val) ? val[0] : val;
        throw new Error(`${firstKey}: ${msg}`);
      }
    }
    throw new Error('حدث خطأ غير متوقع');
  }

  return data as T;
}
