import { apiRequest, buildQuery } from './api';
import { Branch, FabricBranchPrice, Paginated } from '@/types';

export async function listBranches(params?: Record<string, string | number | undefined | null>): Promise<Paginated<Branch>> {
  const q = buildQuery(params || {});
  return apiRequest<Paginated<Branch>>(`/branches/${q}`);
}

export async function getBranch(id: number): Promise<Branch> {
  return apiRequest<Branch>(`/branches/${id}/`);
}

export async function createBranch(data: Partial<Branch>): Promise<Branch> {
  return apiRequest<Branch>('/branches/', {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

export async function updateBranch(id: number, data: Partial<Branch>): Promise<Branch> {
  return apiRequest<Branch>(`/branches/${id}/`, {
    method: 'PATCH',
    body: JSON.stringify(data),
  });
}

export async function deleteBranch(id: number, adminPassword?: string): Promise<void> {
  return apiRequest<void>(`/branches/${id}/`, {
    method: 'DELETE',
    body: JSON.stringify({ admin_password: adminPassword ?? '' }),
  });
}

export async function listBranchPrices(
  params?: Record<string, string | number | undefined | null>
): Promise<Paginated<FabricBranchPrice>> {
  const q = buildQuery(params || {});
  return apiRequest<Paginated<FabricBranchPrice>>(`/branch-prices/${q}`);
}

export async function createBranchPrice(data: Partial<FabricBranchPrice>): Promise<FabricBranchPrice> {
  return apiRequest<FabricBranchPrice>('/branch-prices/', {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

export async function updateBranchPrice(id: number, data: Partial<FabricBranchPrice>): Promise<FabricBranchPrice> {
  return apiRequest<FabricBranchPrice>(`/branch-prices/${id}/`, {
    method: 'PATCH',
    body: JSON.stringify(data),
  });
}

export async function deleteBranchPrice(id: number): Promise<void> {
  return apiRequest<void>(`/branch-prices/${id}/`, { method: 'DELETE' });
}

export interface BranchPriceUpsertItem {
  branch: number;
  sale_price_yard: number;
  sale_price_roll?: number | null;
  min_sale_yard: number;
  min_sale_roll?: number | null;
  piece_price?: number | null;
}

export async function upsertBranchPrices(
  fabricId: number,
  prices: BranchPriceUpsertItem[]
): Promise<{ created: number; updated: number; errors: unknown[] }> {
  return apiRequest<{ created: number; updated: number; errors: unknown[] }>(`/branch-prices/bulk/`, {
    method: 'POST',
    body: JSON.stringify({ fabric: fabricId, prices }),
  });
}
