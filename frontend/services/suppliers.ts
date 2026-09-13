import { apiRequest, buildQuery } from './api';
import { Supplier, Paginated, LedgerEntry, LedgerSummary, CreateLedgerEntry } from '@/types';

export async function listSuppliers(params?: Record<string, string | number | undefined | null>): Promise<Paginated<Supplier>> {
  const q = buildQuery(params || {});
  return apiRequest<Paginated<Supplier>>(`/suppliers/${q}`);
}

export async function getSupplier(id: number): Promise<Supplier> {
  return apiRequest<Supplier>(`/suppliers/${id}/`);
}

export async function createSupplier(data: Partial<Supplier>): Promise<Supplier> {
  return apiRequest<Supplier>('/suppliers/', {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

export async function updateSupplier(id: number, data: Partial<Supplier>): Promise<Supplier> {
  return apiRequest<Supplier>(`/suppliers/${id}/`, {
    method: 'PUT',
    body: JSON.stringify(data),
  });
}

export async function deleteSupplier(id: number): Promise<void> {
  return apiRequest<void>(`/suppliers/${id}/`, { method: 'DELETE' });
}

export async function getSupplierSummary(id: number): Promise<LedgerSummary> {
  return apiRequest<LedgerSummary>(`/suppliers/${id}/summary/`);
}

export async function getSupplierLedger(id: number, page = 1, pageSize = 20): Promise<Paginated<LedgerEntry>> {
  const q = buildQuery({ page, page_size: pageSize });
  return apiRequest<Paginated<LedgerEntry>>(`/suppliers/${id}/ledger/${q}`);
}

export async function createLedgerEntry(id: number, data: CreateLedgerEntry): Promise<LedgerEntry> {
  return apiRequest<LedgerEntry>(`/suppliers/${id}/ledger/`, {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

export async function deleteLedgerEntry(id: number, entryId: number): Promise<void> {
  return apiRequest<void>(`/suppliers/${id}/ledger/${entryId}/`, { method: 'DELETE' });
}

export async function receiveLedgerEntry(id: number, entryId: number): Promise<LedgerEntry> {
  return apiRequest<LedgerEntry>(`/suppliers/${id}/ledger/${entryId}/receive/`, {
    method: 'POST',
  });
}
