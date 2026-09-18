import { apiRequest } from './api';
import type { Employee } from '@/types';

export interface LoginResult {
  token: string;
  employee: Employee;
}

export async function login(username: string, password: string): Promise<LoginResult> {
  return apiRequest<LoginResult>('/auth/login/', {
    method: 'POST',
    body: JSON.stringify({ username, password }),
  });
}

export async function logout(): Promise<void> {
  try {
    await apiRequest<{ detail: string }>('/auth/logout/', { method: 'POST' });
  } catch {
    // تجاهل أخطاء تسجيل الخروج — الحساب يُمسح محلياً على أي حال
  }
}

export async function fetchMe(): Promise<Employee> {
  return apiRequest<Employee>('/auth/me/');
}