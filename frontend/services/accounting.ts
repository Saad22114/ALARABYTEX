import { apiRequest, buildQuery } from './api';
import {
  Account,
  BalanceSheet,
  CashBox,
  CashFlow,
  ClosedPeriod,
  IncomeStatement,
  JournalEntry,
  Paginated,
  TrialBalance,
} from '@/types';

export async function listAccounts(params?: Record<string, string | number | undefined | null>): Promise<Paginated<Account>> {
  const q = buildQuery(params || {});
  return apiRequest<Paginated<Account>>(`/accounts/${q}`);
}

export async function createAccount(data: Partial<Account>): Promise<Account> {
  return apiRequest<Account>('/accounts/', {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

export async function updateAccount(id: number, data: Partial<Account>): Promise<Account> {
  return apiRequest<Account>(`/accounts/${id}/`, {
    method: 'PUT',
    body: JSON.stringify(data),
  });
}

export async function deleteAccount(id: number): Promise<void> {
  return apiRequest<void>(`/accounts/${id}/`, { method: 'DELETE' });
}

export async function listJournalEntries(params?: Record<string, string | number | undefined | null>): Promise<Paginated<JournalEntry>> {
  const q = buildQuery(params || {});
  return apiRequest<Paginated<JournalEntry>>(`/journal/${q}`);
}

export async function createJournalEntry(data: Record<string, unknown>): Promise<JournalEntry> {
  return apiRequest<JournalEntry>('/journal/', {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

export async function deleteJournalEntry(id: number): Promise<void> {
  return apiRequest<void>(`/journal/${id}/`, { method: 'DELETE' });
}

export async function reverseJournalEntry(id: number): Promise<void> {
  return apiRequest<void>(`/journal/${id}/reverse/`, { method: 'POST' });
}

export async function getTrialBalance(params?: Record<string, string | number | undefined | null>): Promise<TrialBalance> {
  const q = buildQuery(params || {});
  return apiRequest<TrialBalance>(`/reports/trial-balance/${q}`);
}

export async function getIncomeStatement(params?: Record<string, string | number | undefined | null>): Promise<IncomeStatement> {
  const q = buildQuery(params || {});
  return apiRequest<IncomeStatement>(`/reports/income-statement/${q}`);
}

export async function getBalanceSheet(params?: Record<string, string | number | undefined | null>): Promise<BalanceSheet> {
  const q = buildQuery(params || {});
  return apiRequest<BalanceSheet>(`/reports/balance-sheet/${q}`);
}

export async function getCashFlow(params?: Record<string, string | number | undefined | null>): Promise<CashFlow> {
  const q = buildQuery(params || {});
  return apiRequest<CashFlow>(`/reports/cash-flow/${q}`);
}

export async function getCashBox(params?: Record<string, string | number | undefined | null>): Promise<CashBox> {
  const q = buildQuery(params || {});
  return apiRequest<CashBox>(`/reports/cashbox/${q}`);
}

export async function listClosedPeriods(): Promise<ClosedPeriod[]> {
  return apiRequest<ClosedPeriod[]>('/close-period/');
}

export async function closePeriod(periodEnd: string, description?: string): Promise<{ net_profit: number; entries: number }> {
  return apiRequest<{ net_profit: number; entries: number }>('/close-period/', {
    method: 'POST',
    body: JSON.stringify({ period_end: periodEnd, description: description || '' }),
  });
}