import { apiRequest, buildQuery } from './api';
import { Expense, ExpenseCategory, Paginated } from '@/types';

export async function listExpenses(params?: Record<string, string | number | undefined | null>): Promise<Paginated<Expense>> {
  const q = buildQuery(params || {});
  return apiRequest<Paginated<Expense>>(`/expenses/${q}`);
}

export async function getExpense(id: number): Promise<Expense> {
  return apiRequest<Expense>(`/expenses/${id}/`);
}

export async function createExpense(data: Partial<Expense>): Promise<Expense> {
  return apiRequest<Expense>('/expenses/', {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

export async function updateExpense(id: number, data: Partial<Expense>): Promise<Expense> {
  return apiRequest<Expense>(`/expenses/${id}/`, {
    method: 'PUT',
    body: JSON.stringify(data),
  });
}

export async function deleteExpense(id: number): Promise<void> {
  return apiRequest<void>(`/expenses/${id}/`, { method: 'DELETE' });
}

export async function listExpenseCategories(params?: Record<string, string | number | undefined | null>): Promise<Paginated<ExpenseCategory>> {
  const q = buildQuery(params || {});
  return apiRequest<Paginated<ExpenseCategory>>(`/expense-categories/${q}`);
}

export async function createExpenseCategory(data: Partial<ExpenseCategory>): Promise<ExpenseCategory> {
  return apiRequest<ExpenseCategory>('/expense-categories/', {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

export async function deleteExpenseCategory(id: number): Promise<void> {
  return apiRequest<void>(`/expense-categories/${id}/`, { method: 'DELETE' });
}
