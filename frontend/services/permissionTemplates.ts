import { apiRequest } from './api';
import { EmployeePermissions, EmployeeRole } from '@/types';

export interface PermissionTemplate {
  id: number;
  name: string;
  role: EmployeeRole;
  permissions: EmployeePermissions;
  hidden_sections: string[];
  allowed_branches: number[];
}

export async function listPermissionTemplates(): Promise<PermissionTemplate[]> {
  const result = await apiRequest<PermissionTemplate[] | { results: PermissionTemplate[] }>('/permission-templates/');
  return Array.isArray(result) ? result : result.results;
}

export async function createPermissionTemplate(
  data: Omit<PermissionTemplate, 'id'>,
): Promise<PermissionTemplate> {
  return apiRequest<PermissionTemplate>('/permission-templates/', {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

export async function deletePermissionTemplate(id: number): Promise<void> {
  await apiRequest<void>(`/permission-templates/${id}/`, { method: 'DELETE' });
}
