import { apiRequest, buildQuery } from './api';
import { MachineAccountResult, MachineCollection, Paginated } from '@/types';

export async function getMachineAccount(
  params?: Record<string, string | number | undefined | null>
): Promise<MachineAccountResult> {
  const q = buildQuery(params || {});
  return apiRequest<MachineAccountResult>(`/machine-account/${q}`);
}

export async function listCollections(
  params?: Record<string, string | number | undefined | null>
): Promise<Paginated<MachineCollection>> {
  const q = buildQuery(params || {});
  return apiRequest<Paginated<MachineCollection>>(`/machine-account/collections/${q}`);
}

export async function createCollection(data: Partial<MachineCollection>): Promise<MachineCollection> {
  return apiRequest<MachineCollection>('/machine-account/collections/', {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

export async function deleteCollection(id: number): Promise<void> {
  return apiRequest<void>(`/machine-account/collections/${id}/`, { method: 'DELETE' });
}