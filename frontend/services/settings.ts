import { apiRequest, API_URL } from './api';
import { AppSettings } from '@/types';

export function getSettings(): Promise<AppSettings> {
  return apiRequest<AppSettings>('/settings/');
}

export async function updateSettings(patch: Partial<AppSettings>): Promise<AppSettings> {
  return apiRequest<AppSettings>('/settings/', { method: 'PATCH', body: JSON.stringify(patch) });
}

function mediaBase(): string {
  return API_URL.replace(/\/?api\/?$/, '');
}

export function logoUrl(path?: string | null): string {
  if (!path) return '';
  if (/^https?:\/\//.test(path)) return path;
  return `${mediaBase()}/${path.replace(/^\/+/, '')}`;
}

export async function uploadLogo(file: File): Promise<AppSettings> {
  const form = new FormData();
  form.append('file', file);
  return apiRequest<AppSettings>('/settings/logo/', { method: 'POST', body: form });
}

export async function removeLogo(): Promise<AppSettings> {
  return apiRequest<AppSettings>('/settings/logo/', { method: 'DELETE' });
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