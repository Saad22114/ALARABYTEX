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

export async function updateSessionItem(id: number, itemId: number, data: SessionSaleItemWrite): Promise<SessionSaleItem> {
  return apiRequest<SessionSaleItem>(`/sale-sessions/${id}/items/${itemId}/`, { method: 'PUT', body: JSON.stringify(data) });
}

export async function removeSessionItem(id: number, itemId: number): Promise<void> {
  return apiRequest<void>(`/sale-sessions/${id}/items/${itemId}/`, { method: 'DELETE' });
}

export async function closeSaleSession(id: number): Promise<SaleSession> {
  return apiRequest<SaleSession>(`/sale-sessions/${id}/close/`, { method: 'POST', body: JSON.stringify({}) });
}