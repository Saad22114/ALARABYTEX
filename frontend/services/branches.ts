import { apiRequest, buildQuery } from './api';
import { Branch, Paginated } from '@/types';

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
