import { apiRequest, buildQuery } from './api';
import { Fabric, FabricStockResult, FabricSummary, Paginated } from '@/types';

export async function listFabrics(params?: Record<string, string | number | undefined | null>): Promise<Paginated<Fabric>> {
  const q = buildQuery(params || {});
  return apiRequest<Paginated<Fabric>>(`/fabrics/${q}`);
}

export async function getFabric(id: number): Promise<Fabric> {
  return apiRequest<Fabric>(`/fabrics/${id}/`);
}

export async function createFabric(data: Partial<Fabric>): Promise<Fabric> {
  return apiRequest<Fabric>('/fabrics/', {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

export async function updateFabric(id: number, data: Partial<Fabric>): Promise<Fabric> {
  return apiRequest<Fabric>(`/fabrics/${id}/`, {
    method: 'PUT',
    body: JSON.stringify(data),
  });
}

export async function deleteFabric(id: number): Promise<void> {
  return apiRequest<void>(`/fabrics/${id}/`, { method: 'DELETE' });
}

export async function getFabricSummary(): Promise<FabricSummary> {
  return apiRequest<FabricSummary>('/fabrics/summary/');
}

export async function getFabricStock(id: number): Promise<FabricStockResult> {
  return apiRequest<FabricStockResult>(`/fabrics/${id}/stock/`);
}

export interface BulkPriceUpdatePayload {
  field: 'sale_price_yard' | 'purchase_price' | 'min_sale_yard';
  mode: 'percent' | 'fixed';
  value: number;
  direction: 'increase' | 'decrease';
}

export async function bulkPriceUpdate(payload: BulkPriceUpdatePayload): Promise<{ detail: string; updated: number }> {
  return apiRequest<{ detail: string; updated: number }>(`/fabrics/bulk-price-update/`, {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}