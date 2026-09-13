import { apiRequest } from './api';
import { AppSettings } from '@/types';

export async function getSettings(): Promise<AppSettings> {
  return apiRequest<AppSettings>('/settings/');
}

export async function updateSettings(patch: Partial<AppSettings>): Promise<AppSettings> {
  return apiRequest<AppSettings>('/settings/', { method: 'PATCH', body: JSON.stringify(patch) });
}

export function backupUrl(): string {
  return `${process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000/api'}/settings/backup/`;
}

export async function restoreSettings(body: unknown): Promise<unknown> {
  return apiRequest('/settings/restore/', { method: 'POST', body: JSON.stringify(body) });
}

export async function resetData(payload: { confirm: boolean; scope: 'transactions' | 'all' }): Promise<unknown> {
  return apiRequest('/settings/reset/', { method: 'POST', body: JSON.stringify(payload) });
}