export const API_URL =
  process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000/api';

const TOKEN_KEY = 'qomash_token';

function authHeaders(): Record<string, string> {
  if (typeof window === 'undefined') return {};
  try {
    const token = localStorage.getItem(TOKEN_KEY);
    return token ? { Authorization: `Token ${token}` } : {};
  } catch {
    return {};
  }
}

function redirectToLogin(): void {
  try {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem('qomash_session');
  } catch {}
  if (typeof window !== 'undefined' && window.location.pathname !== '/login') {
    window.location.href = '/login';
  }
}

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
  const res = await fetch(url, {
    headers: {
      ...authHeaders(),
      ...(isForm ? {} : { 'Content-Type': 'application/json' }),
      ...(options.headers || {}),
    },
    ...options,
  });

  if (res.status === 401 && !path.startsWith('/auth/login/')) {
    redirectToLogin();
  }

  if (res.status === 204) return undefined as T;

  const data = await res.json().catch(() => null);

  if (!res.ok) {
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
