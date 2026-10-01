import { apiRequest, buildQuery, downloadBlob, API_URL } from './api';
import {
  AttendanceDaySheet,
  AttendanceExcuse,
  AttendancePolicy,
  AttendanceRecord,
  AttendanceSummaryResult,
  Paginated,
} from '@/types';

/** الحضور والانصراف — طبقة الخدمة فوق `/attendance/`. */

/**
 * الحقول القابلة للكتابة في سطرٍ واحد.
 *
 * لا ``status`` هنا: الحالة مُشتقّة من الأوقات والسياسة، ولو سمحنا
 * بإرسالها لأرسلها كاتبٌ لا يعرف نافذة الدوام، فصار الحقل يُكتب مرّتين
 * وتضيع الحقيقة في المرّتين. وكذلك ``worked_minutes``: يُحسَب من
 * ``login_at`` و``logout_at`` وحدهما، فمن كتبه يدوياً يدّعي ما لا يعلم.
 */
export interface AttendanceRecordWrite {
  employee?: number | null;
  date?: string;
  login_at?: string | null;
  logout_at?: string | null;
  excuse?: AttendanceExcuse;
  note?: string;
}

// ---------------------------------------------------------------- السياسة

export async function getAttendancePolicy(): Promise<AttendancePolicy> {
  return apiRequest<AttendancePolicy>('/attendance/policy/');
}

/**
 * الحفظ جزئيٌّ دائماً: الشاشة ترسل الحقول التي غيّرها المستخدم وحدها،
 * والحقولُ الباقية تبقى على قيمتها. إرسال السياسة كاملةً يجعل الشاشة
 * تكتب عن حقولٍ لم ترها ولم تقصد تغييرها.
 */
export async function saveAttendancePolicy(
  data: Partial<AttendancePolicy>,
): Promise<AttendancePolicy> {
  return apiRequest<AttendancePolicy>('/attendance/policy/', {
    method: 'PATCH',
    body: JSON.stringify(data),
  });
}

// ----------------------------------------------------------------- السجلات

export async function listAttendance(
  params?: Record<string, string | number | undefined | null>,
): Promise<Paginated<AttendanceRecord>> {
  return apiRequest<Paginated<AttendanceRecord>>(
    `/attendance/records/${buildQuery(params || {})}`,
  );
}

/** سطرٌ يدويّ ليومٍ وموظف: من أُغاب سهواً أو نسي النظام تسجيله. */
export async function createAttendance(
  data: AttendanceRecordWrite & { employee: number; date: string },
): Promise<AttendanceRecord> {
  return apiRequest<AttendanceRecord>('/attendance/records/', {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

export async function updateAttendance(
  id: number,
  data: AttendanceRecordWrite,
): Promise<AttendanceRecord> {
  return apiRequest<AttendanceRecord>(`/attendance/records/${id}/`, {
    method: 'PATCH',
    body: JSON.stringify(data),
  });
}

// -------------------------------------------------------------- ورقة اليوم

/**
 * ورقة يومٍ واحد: صفٌّ لكل موظف نشط، حاضراً كان أو غائباً.
 * الغياب حالةٌ في الجدول لا سطرٌ ناقص، فمن يقتصر على «من له سجل» يُخفي
 * نصف الغائبين.
 */
export async function getDaySheet(date?: string): Promise<AttendanceDaySheet> {
  return apiRequest<AttendanceDaySheet>(
    `/attendance/records/sheet/${buildQuery({ date })}`,
  );
}

/** أرقام مدى زمني في سطر — تملأ بطاقات الملخّص. */
export async function getAttendanceSummary(params?: {
  start?: string;
  end?: string;
}): Promise<AttendanceSummaryResult> {
  return apiRequest<AttendanceSummaryResult>(
    `/attendance/records/summary/${buildQuery(params || {})}`,
  );
}

/** من دخل ولم يخرج بعد: دليلُ حضورٍ لا دليلُ غياب. */
export async function getOpenSessions(): Promise<AttendanceRecord[]> {
  return apiRequest<AttendanceRecord[]>('/attendance/records/open_sessions/');
}

/** تسجيل دخول المستخدم الحالي — يفتح سطر اليوم. */
export async function checkIn(): Promise<AttendanceRecord> {
  return apiRequest<AttendanceRecord>('/attendance/records/check_in/', {
    method: 'POST',
  });
}

/** تسجيل خروج المستخدم الحالي — يُغلق سطر اليوم. */
export async function checkOut(): Promise<AttendanceRecord> {
  return apiRequest<AttendanceRecord>('/attendance/records/check_out/', {
    method: 'POST',
  });
}

// ----------------------------------------------------------------- التصدير

/**
 * تصدير Excel عبر ``downloadBlob`` لا عبر رابط مباشر.
 *
 * السببُ الأول أنّه يمرّ بالمصادقة: رابطٌ مباشر على ``<a download>`` لا
 * يحمل الترويسة، فيردّ الخادم 401 وتُنزّل صفحة الدخول باسم «حضور». والسببُ
 * الثاني أنه يقرأ اسم الملف من ``Content-Disposition``، فلا يصطدم تنزيلان
 * في مجلدٍ واحد.
 *
 * تمرير ``date`` يصدّر ورقة اليوم كاملةً، بغياب من لا سجل لهم، وبلا
 * تمريره يصدّر المدى الزمني سطراً سطراً من جدول السجلات.
 */
export async function exportAttendance(params?: {
  date?: string;
  start?: string;
  end?: string;
  employee?: number;
}): Promise<void> {
  await downloadBlob(
    `${API_URL}/attendance/records/export/${buildQuery(params || {})}`,
    'الحضور-والانصراف.xlsx',
  );
}