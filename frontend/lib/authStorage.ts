import type { Employee } from '@/types';

const TOKEN_KEY = 'qomash_token';
const EMPLOYEE_KEY = 'qomash_auth_employee';
const CURRENT_KEY = 'qomash_current_employee';

export function getStoredToken(): string | null {
  if (typeof window === 'undefined') return null;
  try {
    return localStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

export function getStoredEmployee(): Employee | null {
  if (typeof window === 'undefined') return null;
  try {
    const raw = localStorage.getItem(EMPLOYEE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as Employee;
    if (!parsed?.id) return null;
    return parsed;
  } catch {
    return null;
  }
}

export function saveAuth(token: string, employee: Employee | null): void {
  if (typeof window === 'undefined') return;
  try {
    localStorage.setItem(TOKEN_KEY, token);
    if (employee) localStorage.setItem(EMPLOYEE_KEY, JSON.stringify(employee));
    else localStorage.removeItem(EMPLOYEE_KEY);
    if (employee) {
      localStorage.setItem(
        CURRENT_KEY,
        JSON.stringify({
          id: employee.id,
          name: employee.name,
          role_label: employee.role_label,
          branch_name: employee.branch_name,
        }),
      );
    }
  } catch {}
}

export function clearAuthStorage(): void {
  if (typeof window === 'undefined') return;
  try {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(EMPLOYEE_KEY);
  } catch {}
}