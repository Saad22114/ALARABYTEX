import { apiRequest } from './api';
import { AccountAvatarResult, EmployeeProfile } from '@/types';

/** تحدّث الثيم المفضّل للموظف على الخادم. */
export async function updateEmployeeTheme(theme: string): Promise<{ theme: string }> {
  return apiRequest<{ theme: string }>('/account/profile/?employee_id=me', {
    method: 'PATCH',
    body: JSON.stringify({ theme }),
  });
}

export async function updateAvatar(avatar: string): Promise<AccountAvatarResult> {
  return apiRequest<AccountAvatarResult>('/account/avatar/', {
    method: 'PATCH',
    body: JSON.stringify({ avatar }),
  });
}

/** رفع صورة شخصية من جهاز المستخدم (data URL مُصغَّرة مسبقاً). */
export async function updateAvatarImage(avatarImage: string): Promise<AccountAvatarResult> {
  return apiRequest<AccountAvatarResult>('/account/avatar/', {
    method: 'PATCH',
    body: JSON.stringify({ avatar_image: avatarImage }),
  });
}

/** حذف الصورة الشخصية والعودة إلى الأفاتار الرمزي. */
export async function clearAvatarImage(): Promise<AccountAvatarResult> {
  return apiRequest<AccountAvatarResult>('/account/avatar/', {
    method: 'PATCH',
    body: JSON.stringify({ clear_avatar_image: true }),
  });
}

export async function getEmployeeProfile(employeeId: number): Promise<EmployeeProfile> {
  return apiRequest<EmployeeProfile>(`/account/profile/?employee_id=${employeeId}`);
}