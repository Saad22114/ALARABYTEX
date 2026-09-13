import { apiRequest, buildQuery } from './api';
import { DailySale, Paginated, SaleStockResult, SaleSummary, SaleWritePayload, SalesByEmployeeResult } from '@/types';

export async function listSales(params?: Record<string, string | number | undefined | null>): Promise<Paginated<DailySale>> {
  const q = buildQuery(params || {});
  return apiRequest<Paginated<DailySale>>(`/sales/${q}`);
}

export async function getSalesSummary(
  params?: Record<string, string | number | undefined | null>
): Promise<SaleSummary> {
  const q = buildQuery(params || {});
  return apiRequest<SaleSummary>(`/sales/summary/${q}`);
}

export function salesExportUrl(params?: Record<string, string | number | undefined | null>): string {
  const q = buildQuery({ ...params, export: 'xlsx' });
  return `/sales/${q}`;
}

export async function getSale(id: number): Promise<DailySale> {
  return apiRequest<DailySale>(`/sales/${id}/`);
}

export async function createSale(data: SaleWritePayload): Promise<DailySale> {
  return apiRequest<DailySale>('/sales/', {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

export async function updateSale(id: number, data: SaleWritePayload): Promise<DailySale> {
  return apiRequest<DailySale>(`/sales/${id}/`, {
    method: 'PUT',
    body: JSON.stringify(data),
  });
}

export async function deleteSale(id: number): Promise<void> {
  return apiRequest<void>(`/sales/${id}/`, { method: 'DELETE' });
}

export async function getSaleStock(branch: number): Promise<SaleStockResult> {
  const q = buildQuery({ branch: String(branch) });
  return apiRequest<SaleStockResult>(`/sales/stock/${q}`);
}

export async function getSalesByEmployee(
  params?: Record<string, string | number | undefined | null>
): Promise<SalesByEmployeeResult> {
  const q = buildQuery(params || {});
  return apiRequest<SalesByEmployeeResult>(`/sales/by-employee/${q}`);
}
