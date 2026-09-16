import { apiRequest, buildQuery } from './api';
import {
  Employee,
  Paginated,
  SaleSession,
  SaleSessionSummary,
  SessionSaleItem,
  SessionSaleItemWrite,
} from '@/types';

export async function listEmployees(params?: Record<string, string | number | undefined | null>): Promise<Paginated<Employee>> {
  const q = buildQuery(params || {});
  return apiRequest<Paginated<Employee>>(`/employees/${q}`);
}

export async function createEmployee(data: Partial<Employee>): Promise<Employee> {
  return apiRequest<Employee>('/employees/', { method: 'POST', body: JSON.stringify(data) });
}

export async function updateEmployee(id: number, data: Partial<Employee>): Promise<Employee> {
  return apiRequest<Employee>(`/employees/${id}/`, { method: 'PUT', body: JSON.stringify(data) });
}

export async function deleteEmployee(id: number): Promise<void> {
  return apiRequest<void>(`/employees/${id}/`, { method: 'DELETE' });
}

export async function listSaleSessions(params?: Record<string, string | number | undefined | null>): Promise<Paginated<SaleSession>> {
  const q = buildQuery(params || {});
  return apiRequest<Paginated<SaleSession>>(`/sale-sessions/${q}`);
}

export async function getSaleSessionSummary(
  params?: Record<string, string | number | undefined | null>
): Promise<SaleSessionSummary> {
  const q = buildQuery(params || {});
  return apiRequest<SaleSessionSummary>(`/sale-sessions/summary/${q}`);
}

export async function openSaleSession(employee: number): Promise<SaleSession> {
  return apiRequest<SaleSession>('/sale-sessions/', { method: 'POST', body: JSON.stringify({ employee }) });
}

export async function addSessionItem(id: number, data: SessionSaleItemWrite): Promise<SessionSaleItem> {
  return apiRequest<SessionSaleItem>(`/sale-sessions/${id}/items/`, { method: 'POST', body: JSON.stringify(data) });
}

export async function addSessionItems(id: number, items: SessionSaleItemWrite[]): Promise<SessionSaleItem[]> {
  return apiRequest<SessionSaleItem[]>(`/sale-sessions/${id}/items/bulk/`, {
    method: 'POST',
    body: JSON.stringify({ items }),
  });
}

export async function updateSessionItem(id: number, itemId: number, data: SessionSaleItemWrite): Promise<SessionSaleItem> {
  return apiRequest<SessionSaleItem>(`/sale-sessions/${id}/items/${itemId}/`, { method: 'PUT', body: JSON.stringify(data) });
}

export async function removeSessionItem(id: number, itemId: number): Promise<void> {
  return apiRequest<void>(`/sale-sessions/${id}/items/${itemId}/`, { method: 'DELETE' });
}

export async function closeSaleSession(id: number): Promise<SaleSession> {
  return apiRequest<SaleSession>(`/sale-sessions/${id}/close/`, { method: 'POST', body: JSON.stringify({}) });
}

export async function reopenSaleSession(id: number): Promise<SaleSession> {
  return apiRequest<SaleSession>(`/sale-sessions/${id}/reopen/`, { method: 'POST', body: JSON.stringify({}) });
}

export async function updateSaleSession(id: number, data: Partial<SaleSession>): Promise<SaleSession> {
  return apiRequest<SaleSession>(`/sale-sessions/${id}/`, { method: 'PATCH', body: JSON.stringify(data) });
}

export async function deleteSaleSession(id: number): Promise<void> {
  return apiRequest<void>(`/sale-sessions/${id}/`, { method: 'DELETE' });
}

export async function clearSaleSession(id: number): Promise<SaleSession> {
  return apiRequest<SaleSession>(`/sale-sessions/${id}/clear/`, { method: 'POST', body: JSON.stringify({}) });
}

export async function moveSessionItem(id: number, itemId: number, targetSession: number): Promise<SessionSaleItem> {
  return apiRequest<SessionSaleItem>(`/sale-sessions/${id}/move-item/${itemId}/`, {
    method: 'POST',
    body: JSON.stringify({ target_session: targetSession }),
  });
}