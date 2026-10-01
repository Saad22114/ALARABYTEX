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

function redirectToChangePassword(): void {
  try {
    sessionStorage.setItem('qomash_must_change', '1');
  } catch {}
  if (
    typeof window !== 'undefined' &&
    window.location.pathname !== '/change-password' &&
    window.location.pathname !== '/login'
  ) {
    window.location.href = '/change-password';
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
      if (data.code === 'must_change_password') {
        redirectToChangePassword();
        throw new Error(data.detail || 'يجب تغيير كلمة المرور قبل استخدام النظام');
      }
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
    // ردّ بلا JSON: Django يرفض أجسام الطلبات الضخمة قبل أن تصل إلى العرض،
    // فيردّ 400 فارغاً. بلا هذا التمييز يظهر للمستخدم «خطأ غير متوقع» فيتومه
    // أن كلمة مروره هي السبب.
    if (!data && res.status === 400) {
      throw new Error('الملف أو البيانات أكبر من الحدّ الذي يقبله الخادم');
    }
    throw new Error(`تعذّرت العملية (رمز ${res.status})`);
  }

  return data as T;
}

/** اسم الملف من ترويسة الخادم، فإن غاب فاسم احتياطي. */
function filenameFromDisposition(header: string | null, fallback: string): string {
  if (!header) return fallback;
  // filename*=UTF-8''... (RFC 5987) يتقدّم على filenamePlain لأنه يحمل العربية.
  const star = /filename\*\s*=\s*UTF-8''([^;]+)/i.exec(header);
  if (star) {
    try {
      return decodeURIComponent(star[1].trim()) || fallback;
    } catch {
      /* ترويسة مشوّهة: نكمل بالاسم الاحتياطي */
    }
  }
  const plain = /filename\s*=\s*"?([^";]+)"?/i.exec(header);
  return plain ? plain[1].trim() || fallback : fallback;
}

export async function downloadBlob(url: string, fallbackFilename: string): Promise<void> {
  const res = await fetch(url, { headers: authHeaders() });
  if (!res.ok) {
    let detail = '';
    let code = '';
    try {
      const data = await res.json();
      detail = data?.detail || '';
      code = data?.code || '';
    } catch {}
    // الرمز منتهٍ أو محذوف: النتيجة «لم يتم تزويد بيانات الدخول»، وهي رسالة
    // عن العَرَض لا عن السبب. فنعيده إلى صفحة الدخول كما يفعل
    // ``apiRequest``، وإلا بقي المستخدم أمام رسالة تظنّأن الخادم معطّل.
    if (res.status === 401 && code !== 'must_change_password') {
      redirectToLogin();
    }
    if (code === 'must_change_password') {
      redirectToChangePassword();
    }
    throw new Error(detail || 'تعذر تنزيل الملف');
  }
  const blob = await res.blob();
  const link = document.createElement('a');
  const objectUrl = URL.createObjectURL(blob);
  link.href = objectUrl;
  // اسم الخادم يحمل التاريخ والوقت، فيُعرف أي نسخة هذا الملف. وتجاهله كان
  // يجعل كل تنزيلات النسخة باسم واحد فيصطدم بعضها ببعض في مجلد التنزيلات.
  link.download = filenameFromDisposition(res.headers.get('Content-Disposition'), fallbackFilename);
  document.body.appendChild(link);
  link.click();
  link.remove();
  // لا يُبطَل الرابط قبل أن يبدأ المتصفح قراءته: الإبطال الفوري يقطع
  // التنزيل في أوله فيخرج ملف نسخة احتياطية ناقصاً لا يُفتح ولا يُستعاد —
  // والسبب لا يظهر إلا عند الاستعادة بعد شهور.
  setTimeout(() => URL.revokeObjectURL(objectUrl), 30_000);
}
