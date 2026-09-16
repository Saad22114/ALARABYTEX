import { apiRequest, buildQuery } from './api';
import { Customer, CustomerLookupResult, Paginated } from '@/types';

export async function lookupCustomer(phone: string): Promise<CustomerLookupResult> {
  const q = buildQuery({ phone: phone || undefined });
  return apiRequest<CustomerLookupResult>(`/customers/lookup/${q}`);
}

export async function listCustomers(params?: Record<string, string | number | undefined | null>): Promise<Paginated<Customer>> {
  const q = buildQuery(params || {});
  return apiRequest<Paginated<Customer>>(`/customers/${q}`);
}

export async function getCustomer(id: number): Promise<Customer> {
  return apiRequest<Customer>(`/customers/${id}/`);
}

export async function createCustomer(data: Partial<Customer>): Promise<Customer> {
  return apiRequest<Customer>('/customers/', {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

export async function updateCustomer(id: number, data: Partial<Customer>): Promise<Customer> {
  return apiRequest<Customer>(`/customers/${id}/`, {
    method: 'PUT',
    body: JSON.stringify(data),
  });
}

export async function deleteCustomer(id: number): Promise<void> {
  return apiRequest<void>(`/customers/${id}/`, { method: 'DELETE' });
}