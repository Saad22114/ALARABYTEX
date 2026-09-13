import { apiRequest, buildQuery } from './api';
import { Employee, Paginated } from '@/types';

export async function listEmployees(params?: Record<string, string | number | undefined | null>): Promise<Paginated<Employee>> {
  const q = buildQuery(params || {});
  return apiRequest<Paginated<Employee>>(`/employees/${q}`);
}