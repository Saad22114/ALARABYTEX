import { apiRequest } from './api';

export interface AppNotification {
  id: number;
  kind: string;
  title: string;
  body: string;
  url: string;
  created_at: string;
  read_at: string | null;
}

export interface NotificationsResult {
  results: AppNotification[];
  unread_count: number;
}

export function getNotifications(): Promise<NotificationsResult> {
  return apiRequest<NotificationsResult>('/notifications/');
}

export function markNotificationRead(id: number): Promise<{ detail: string }> {
  return apiRequest<{ detail: string }>(`/notifications/${id}/read/`, { method: 'POST' });
}

export function markAllNotificationsRead(): Promise<{ detail: string }> {
  return apiRequest<{ detail: string }>('/notifications/read-all/', { method: 'POST' });
}
