import { apiRequest, buildQuery } from './api';
import { Partner, PartnerOperation, PartnerOperationWrite, PartnerMovementsResult, PartnerOperationsSummary, PartnerDistributionResult, Paginated } from '@/types';

export async function listPartners(params?: Record<string, string | number | undefined | null>): Promise<Paginated<Partner>> {
  const q = buildQuery(params || {});
  return apiRequest<Paginated<Partner>>(`/partners/${q}`);
}

export async function createPartner(data: Partial<Partner>): Promise<Partner> {
  return apiRequest<Partner>('/partners/', { method: 'POST', body: JSON.stringify(data) });
}

export async function updatePartner(id: number, data: Partial<Partner>): Promise<Partner> {
  return apiRequest<Partner>(`/partners/${id}/`, { method: 'PUT', body: JSON.stringify(data) });
}

export async function deletePartner(id: number): Promise<void> {
  return apiRequest<void>(`/partners/${id}/`, { method: 'DELETE' });
}

export async function listPartnerOperations(params?: Record<string, string | number | undefined | null>): Promise<Paginated<PartnerOperation>> {
  const q = buildQuery(params || {});
  return apiRequest<Paginated<PartnerOperation>>(`/partner-operations/${q}`);
}

export async function getPartnerOperationsSummary(params?: Record<string, string | number | undefined | null>): Promise<PartnerOperationsSummary> {
  const q = buildQuery(params || {});
  return apiRequest<PartnerOperationsSummary>(`/partner-operations/summary/${q}`);
}

export async function getPartnerDistribution(params?: Record<string, string | number | undefined | null>): Promise<PartnerDistributionResult> {
  const q = buildQuery(params || {});
  return apiRequest<PartnerDistributionResult>(`/partners/distribution/${q}`);
}

export async function createPartnerOperation(data: PartnerOperationWrite): Promise<PartnerOperation> {
  return apiRequest<PartnerOperation>('/partner-operations/', { method: 'POST', body: JSON.stringify(data) });
}

export async function updatePartnerOperation(id: number, data: PartnerOperationWrite): Promise<PartnerOperation> {
  return apiRequest<PartnerOperation>(`/partner-operations/${id}/`, { method: 'PATCH', body: JSON.stringify(data) });
}

export async function deletePartnerOperation(id: number): Promise<void> {
  return apiRequest<void>(`/partner-operations/${id}/`, { method: 'DELETE' });
}

export async function getPartnerMovements(id: number, params?: Record<string, string | number | undefined | null>): Promise<PartnerMovementsResult> {
  const q = buildQuery(params || {});
  return apiRequest<PartnerMovementsResult>(`/partners/${id}/movements/${q}`);
}