import { apiRequest, buildQuery } from './api';
import { DashboardActivityItem, DashboardAlertsResult, DashboardSummary } from '@/types';

export async function getDashboardSummary(
  params?: Record<string, string | number | undefined | null>
): Promise<DashboardSummary> {
  const q = buildQuery(params || {});
  return apiRequest<DashboardSummary>(`/dashboard/summary/${q}`);
}

export async function getDashboardBranches(): Promise<Array<{ id: number; name: string }>> {
  return apiRequest<Array<{ id: number; name: string }>>('/dashboard/branches/');
}

export async function getDashboardAlerts(): Promise<DashboardAlertsResult> {
  return apiRequest<DashboardAlertsResult>('/dashboard/alerts/');
}

export async function getDashboardActivity(): Promise<{ activities: DashboardActivityItem[] }> {
  return apiRequest<{ activities: DashboardActivityItem[] }>('/dashboard/activity/');
}
