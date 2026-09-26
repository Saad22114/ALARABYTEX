import { apiRequest, buildQuery, downloadBlob, API_URL } from './api';
import {
  Paginated,
  PayrollDates,
  PayrollEmployeesResult,
  PayrollPreview,
  PayrollRun,
  PayrollStatement,
  PayrollSummary,
  Payslip,
  SalaryAdvance,
  SalaryStructure,
} from '@/types';

type Params = Record<string, string | number | boolean | undefined | null>;

/* ------------------------------------------------------------------ */
/* هياكل الرواتب                                                       */
/* ------------------------------------------------------------------ */

export function listSalaryStructures(params?: Params): Promise<Paginated<SalaryStructure>> {
  return apiRequest<Paginated<SalaryStructure>>(`/payroll/salary-structures/${buildQuery(params || {})}`);
}

export function getSalaryStructure(id: number): Promise<SalaryStructure> {
  return apiRequest<SalaryStructure>(`/payroll/salary-structures/${id}/`);
}

export function createSalaryStructure(data: Partial<SalaryStructure>): Promise<SalaryStructure> {
  return apiRequest<SalaryStructure>('/payroll/salary-structures/', {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

export function updateSalaryStructure(id: number, data: Partial<SalaryStructure>): Promise<SalaryStructure> {
  return apiRequest<SalaryStructure>(`/payroll/salary-structures/${id}/`, {
    method: 'PUT',
    body: JSON.stringify(data),
  });
}

export function deleteSalaryStructure(id: number): Promise<void> {
  return apiRequest<void>(`/payroll/salary-structures/${id}/`, { method: 'DELETE' });
}

/* ------------------------------------------------------------------ */
/* السلف                                                               */
/* ------------------------------------------------------------------ */

export function listAdvances(params?: Params): Promise<Paginated<SalaryAdvance>> {
  return apiRequest<Paginated<SalaryAdvance>>(`/payroll/advances/${buildQuery(params || {})}`);
}

export function createAdvance(data: Record<string, unknown>): Promise<SalaryAdvance> {
  return apiRequest<SalaryAdvance>('/payroll/advances/', {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

export function updateAdvance(id: number, data: Record<string, unknown>): Promise<SalaryAdvance> {
  return apiRequest<SalaryAdvance>(`/payroll/advances/${id}/`, {
    method: 'PATCH',
    body: JSON.stringify(data),
  });
}

export function deleteAdvance(id: number): Promise<void> {
  return apiRequest<void>(`/payroll/advances/${id}/`, { method: 'DELETE' });
}

export function approveAdvance(id: number): Promise<SalaryAdvance> {
  return apiRequest<SalaryAdvance>(`/payroll/advances/${id}/approve/`, { method: 'POST' });
}

export function rejectAdvance(id: number): Promise<SalaryAdvance> {
  return apiRequest<SalaryAdvance>(`/payroll/advances/${id}/reject/`, { method: 'POST' });
}

export function repayAdvance(
  id: number,
  data: { amount: number; method?: string; date?: string; notes?: string },
): Promise<{ installment: unknown; advance: SalaryAdvance }> {
  return apiRequest<{ installment: unknown; advance: SalaryAdvance }>(
    `/payroll/advances/${id}/repay/`,
    { method: 'POST', body: JSON.stringify(data) },
  );
}

export function listAdvanceInstallments(params?: Params): Promise<Paginated<unknown>> {
  return apiRequest<Paginated<unknown>>(`/payroll/advance-installments/${buildQuery(params || {})}`);
}

export async function exportAdvances(params?: Params): Promise<void> {
  await downloadBlob(`${API_URL}/payroll/export/advances/${buildQuery(params || {})}`, 'سلف_الرواتب.xlsx');
}

/* ------------------------------------------------------------------ */
/* المسيّرات والقسائم                                                    */
/* ------------------------------------------------------------------ */

export function listRuns(params?: Params): Promise<Paginated<PayrollRun>> {
  return apiRequest<Paginated<PayrollRun>>(`/payroll/runs/${buildQuery(params || {})}`);
}

export function getRun(id: number): Promise<PayrollRun> {
  return apiRequest<PayrollRun>(`/payroll/runs/${id}/`);
}

export function createRun(data: { month: string; branch?: number | null; notes?: string }): Promise<PayrollRun> {
  return apiRequest<PayrollRun>('/payroll/runs/', {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

export function updateRun(id: number, data: Record<string, unknown>): Promise<PayrollRun> {
  return apiRequest<PayrollRun>(`/payroll/runs/${id}/`, {
    method: 'PATCH',
    body: JSON.stringify(data),
  });
}

export function deleteRun(id: number): Promise<void> {
  return apiRequest<void>(`/payroll/runs/${id}/`, { method: 'DELETE' });
}

export function approveRun(id: number): Promise<PayrollRun> {
  return apiRequest<PayrollRun>(`/payroll/runs/${id}/approve/`, { method: 'POST' });
}

export function payRun(id: number, paymentMethod?: string | null): Promise<PayrollRun> {
  return apiRequest<PayrollRun>(`/payroll/runs/${id}/pay/`, {
    method: 'POST',
    body: JSON.stringify({ payment_method: paymentMethod || null }),
  });
}

export function cancelRun(id: number): Promise<PayrollRun> {
  return apiRequest<PayrollRun>(`/payroll/runs/${id}/cancel/`, { method: 'POST' });
}

export async function exportRun(id: number, filename: string): Promise<void> {
  await downloadBlob(`${API_URL}/payroll/runs/${id}/export/`, filename);
}

export async function exportRuns(params?: Params): Promise<void> {
  await downloadBlob(`${API_URL}/payroll/export/runs/${buildQuery(params || {})}`, 'مسيّرات_الرواتب.xlsx');
}

export function listPayslips(params?: Params): Promise<Paginated<Payslip>> {
  return apiRequest<Paginated<Payslip>>(`/payroll/payslips/${buildQuery(params || {})}`);
}

export function createPayslip(data: Record<string, unknown>): Promise<Payslip> {
  return apiRequest<Payslip>('/payroll/payslips/', {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

export function updatePayslip(id: number, data: Record<string, unknown>): Promise<Payslip> {
  return apiRequest<Payslip>(`/payroll/payslips/${id}/`, {
    method: 'PATCH',
    body: JSON.stringify(data),
  });
}

/* ------------------------------------------------------------------ */
/* معاينات وتقارير                                                      */
/* ------------------------------------------------------------------ */

export function getPayrollPreview(params?: Params): Promise<PayrollPreview> {
  return apiRequest<PayrollPreview>(`/payroll/preview/${buildQuery(params || {})}`);
}

export function getPayrollSummary(params?: Params): Promise<PayrollSummary> {
  return apiRequest<PayrollSummary>(`/payroll/summary/${buildQuery(params || {})}`);
}

export function getPayrollEmployees(params?: Params): Promise<PayrollEmployeesResult> {
  return apiRequest<PayrollEmployeesResult>(`/payroll/employees/${buildQuery(params || {})}`);
}

export function getEmployeeStatement(employeeId: number, params?: Params): Promise<PayrollStatement> {
  return apiRequest<PayrollStatement>(`/payroll/employees/${employeeId}/statement/${buildQuery(params || {})}`);
}

export async function exportStatement(employeeId: number, filename: string): Promise<void> {
  await downloadBlob(`${API_URL}/payroll/export/statement/${employeeId}/`, filename);
}

export function getPayrollDates(): Promise<PayrollDates> {
  return apiRequest<PayrollDates>('/payroll/dates/');
}
