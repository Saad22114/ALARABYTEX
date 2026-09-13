import { apiRequest, buildQuery } from './api';
import {
  SalesReportData,
  ExpensesReportData,
  NetDailyReportData,
  BranchesReportData,
  SuppliersReportData,
  InventoryReportResult,
  InventoryMovementsReportResult,
  CogsReportResult,
  ProfitLossReportResult,
  JournalReportResult,
} from '@/types';

export interface SalesReportResult {
  sales: SalesReportData[];
  totals: {
    total_sales: number;
    cash: number;
    transfer: number;
    card: number;
    other: number;
  };
  count: number;
}

export interface ExpensesReportResult {
  expenses: ExpensesReportData[];
  totals: { total_amount: number };
  count: number;
}

export interface NetDailyReportResult {
  chart_data: NetDailyReportData[];
  start_date: string;
  end_date: string;
}

export interface SuppliersReportResult {
  suppliers: SuppliersReportData[];
  count: number;
}

export interface BranchesReportResult {
  branches: BranchesReportData[];
  count: number;
}

export async function getSalesReport(
  params?: Record<string, string | number | undefined | null>
): Promise<SalesReportResult> {
  const q = buildQuery(params || {});
  return apiRequest<SalesReportResult>(`/reports/sales/${q}`);
}

export async function getExpensesReport(
  params?: Record<string, string | number | undefined | null>
): Promise<ExpensesReportResult> {
  const q = buildQuery(params || {});
  return apiRequest<ExpensesReportResult>(`/reports/expenses/${q}`);
}

export async function getNetDailyReport(
  params?: Record<string, string | number | undefined | null>
): Promise<NetDailyReportResult> {
  const q = buildQuery(params || {});
  return apiRequest<NetDailyReportResult>(`/reports/net-daily/${q}`);
}

export async function getSuppliersReport(): Promise<SuppliersReportResult> {
  return apiRequest<SuppliersReportResult>('/reports/suppliers/');
}

export async function getBranchesReport(): Promise<BranchesReportResult> {
  return apiRequest<BranchesReportResult>('/reports/branches/');
}

export async function getInventoryReport(
  params?: Record<string, string | number | undefined | null>
): Promise<InventoryReportResult> {
  const q = buildQuery(params || {});
  return apiRequest<InventoryReportResult>(`/reports/inventory/${q}`);
}

export async function getInventoryMovementsReport(
  params?: Record<string, string | number | undefined | null>
): Promise<InventoryMovementsReportResult> {
  const q = buildQuery(params || {});
  return apiRequest<InventoryMovementsReportResult>(`/reports/inventory-movements/${q}`);
}

export async function getCogsReport(
  params?: Record<string, string | number | undefined | null>
): Promise<CogsReportResult> {
  const q = buildQuery(params || {});
  return apiRequest<CogsReportResult>(`/reports/cogs/${q}`);
}

export async function getProfitLossReport(
  params?: Record<string, string | number | undefined | null>
): Promise<ProfitLossReportResult> {
  const q = buildQuery(params || {});
  return apiRequest<ProfitLossReportResult>(`/reports/profit-loss/${q}`);
}

export async function getJournalReport(
  params?: Record<string, string | number | undefined | null>
): Promise<JournalReportResult> {
  const q = buildQuery(params || {});
  return apiRequest<JournalReportResult>(`/reports/journal/${q}`);
}
