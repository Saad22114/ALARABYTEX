import { apiRequest, buildQuery } from './api';
import { MachineAccountResult, MachineCollection, Paginated } from '@/types';

export async function getMachineAccount(
  params?: Record<string, string | number | undefined | null>
): Promise<MachineAccountResult> {
  const q = buildQuery(params || {});
  return apiRequest<MachineAccountResult>(`/machine-account/${q}`);
}

/** كل الدفعات، لا Paginated الأولى فقط — التصدير يحتاج سجلاً واحداً كاملاً. */
export async function listAllCollections(
  params?: Record<string, string | number | undefined | null>
): Promise<MachineCollection[]> {
  const q = buildQuery({ ...(params || {}), page_size: 100000 });
  const res = await apiRequest<Paginated<MachineCollection>>(
    `/machine-account/collections/${q}`
  );
  return res.results;
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

/** مالٌ يخرج من الماكينة إلى البنك. الخادمُ هو من يمنع تجاوز الرصيد — لا النموذج. */
export interface TransferResult {
  collection: MachineCollection;
  transferred: number;
  machine_remaining: number;
}

export interface TransferPayload {
  amount: number;
  date: string;
  branch?: number | null;
  reference?: string;
  notes?: string;
}

export async function transferToBank(data: TransferPayload): Promise<TransferResult> {
  return apiRequest<TransferResult>('/machine-account/collections/transfer/', {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

export async function deleteCollection(id: number): Promise<void> {
  return apiRequest<void>(`/machine-account/collections/${id}/`, { method: 'DELETE' });
}