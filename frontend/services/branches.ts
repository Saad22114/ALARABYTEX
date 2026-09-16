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

export async function deleteBranch(id: number): Promise<void> {
  return apiRequest<void>(`/branches/${id}/`, { method: 'DELETE' });
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
