import { apiRequest } from './api';
import { AccountAvatarResult, EmployeeProfile } from '@/types';

export async function updateAvatar(avatar: string): Promise<AccountAvatarResult> {
  return apiRequest<AccountAvatarResult>('/account/avatar/', {
    method: 'PATCH',
    body: JSON.stringify({ avatar }),
  });
}

export async function getEmployeeProfile(employeeId: number): Promise<EmployeeProfile> {
  return apiRequest<EmployeeProfile>(`/account/profile/?employee_id=${employeeId}`);
}