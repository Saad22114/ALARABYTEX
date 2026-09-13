import { apiRequest, buildQuery } from './api';
import { DashboardAlertsResult, DashboardSummary } from '@/types';

export async function getDashboardSummary(
  params?: Record<string, string | number | undefined | null>
): Promise<DashboardSummary> {
  const q = buildQuery(params || {});
  return apiRequest<DashboardSummary>(`/dashboard/summary/${q}`);
}

export async function getDashboardAlerts(): Promise<DashboardAlertsResult> {
  return apiRequest<DashboardAlertsResult>('/dashboard/alerts/');
}
