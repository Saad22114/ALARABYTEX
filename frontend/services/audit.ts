import { apiRequest, buildQuery } from './api';

export interface AuditEntry {
  id: number;
  timestamp: string;
  employee_name: string | null;
  action_label: string;
  model_name: string;
  object_id: number | null;
  object_repr: string;
  changes: Record<string, unknown>;
}

export async function getSessionAudit(sessionId: number): Promise<{ results: AuditEntry[] }> {
  const query = buildQuery({ section: 'sessions', session_id: sessionId, limit: 100 });
  return apiRequest<{ results: AuditEntry[] }>(`/audit/${query}`);
}
