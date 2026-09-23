import { apiRequest, API_URL, downloadBlob } from './api';
import { AppSettings, ThemesControl } from '@/types';

export function getSettings(): Promise<AppSettings> {
  return apiRequest<AppSettings>('/settings/');
}

export async function updateSettings(patch: Partial<AppSettings>): Promise<AppSettings> {
  return apiRequest<AppSettings>('/settings/', { method: 'PATCH', body: JSON.stringify(patch) });
}

export function getThemesControl(): Promise<ThemesControl> {
  return apiRequest<ThemesControl>('/settings/themes-control/');
}

export async function updateThemesControl(patch: Partial<ThemesControl>): Promise<ThemesControl> {
  return apiRequest<ThemesControl>('/settings/themes-control/', { method: 'PATCH', body: JSON.stringify(patch) });
}

function mediaBase(): string {
  return API_URL.replace(/\/?api\/?$/, '');
}

export function logoUrl(path?: string | null): string {
  // يُقدَّم الشعار من الباكند مباشرةً (logo-file/) حتى يعمل أون لاين
  // دون الحاجة لخدمة ملفات media منفصلة، ويعمل أيضاً في صفحة تسجيل الدخول.
  if (!path) return '';
  return `${API_URL.replace(/\/+$/, '')}/settings/logo-file/`;
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

export async function resetData(payload: { confirm: boolean; scope: 'transactions' | 'all'; admin_password: string }): Promise<unknown> {
  return apiRequest('/settings/reset/', { method: 'POST', body: JSON.stringify(payload) });
}

export interface AutoBackupFile {
  name: string;
  size: number;
  modified: string;
}

export interface AutoBackupInfo {
  files: AutoBackupFile[];
  last_auto_backup_at: string | null;
  last_auto_backup_path: string;
}

export function getAutoBackups(): Promise<AutoBackupInfo> {
  return apiRequest<AutoBackupInfo>('/settings/auto-backup/');
}

export function runAutoBackup(): Promise<{ detail: string; path: string }> {
  return apiRequest<{ detail: string; path: string }>('/settings/auto-backup/', { method: 'POST' });
}

export function autoBackupDownloadUrl(name: string): string {
  return `${API_URL}/settings/auto-backup/${encodeURIComponent(name)}/`;
}

export async function downloadBackup(): Promise<void> {
  await downloadBlob(`${API_URL}/settings/backup/`, 'backup.json');
}

export async function downloadAutoBackup(name: string): Promise<void> {
  await downloadBlob(`${API_URL}/settings/auto-backup/${encodeURIComponent(name)}/`, name);
}