import { apiRequest, buildQuery } from './api';
import {
  Paginated,
  Warehouse,
  FabricRoll,
  WarehouseBalance,
  StockMovement,
  GoodsReceipt,
  StockTransfer,
  StockAdjustment,
  StockCount,
  CountItem,
  StockBalanceResult,
  StockOpening,
  StockOpeningWrite,
} from '@/types';

export interface ReceiptWrite {
  warehouse?: number | null;
  branch?: number | null;
  supplier?: number | null;
  date: string;
  supplier_receipt_no?: string;
  notes?: string;
  items: Array<{ fabric: number; rolls_count: number; yards: number; unit_price: number }>;
}

export interface TransferWrite {
  from_warehouse: number;
  to_warehouse?: number | null;
  to_branch?: number | null;
  date: string;
  requested_by?: string;
  notes?: string;
  items: Array<{
    fabric: number;
    yards?: number;
    rolls_count?: number;
    quantity_mode?: 'yard' | 'roll';
  }>;
}

export interface AdjustmentWrite {
  warehouse: number;
  date: string;
  direction: 'in' | 'out';
  reason?: string;
  notes?: string;
  items: Array<{ fabric: number; yards: number; rolls_count?: number }>;
}

// المخازن
export async function listWarehouses(params?: Record<string, string | number | undefined | null>): Promise<Paginated<Warehouse>> {
  return apiRequest<Paginated<Warehouse>>(`/warehouses/${buildQuery(params || {})}`);
}

export async function createWarehouse(data: Partial<Warehouse>): Promise<Warehouse> {
  return apiRequest<Warehouse>('/warehouses/', { method: 'POST', body: JSON.stringify(data) });
}

export async function updateWarehouse(id: number, data: Partial<Warehouse>): Promise<Warehouse> {
  return apiRequest<Warehouse>(`/warehouses/${id}/`, { method: 'PUT', body: JSON.stringify(data) });
}

export async function deleteWarehouse(id: number): Promise<void> {
  return apiRequest<void>(`/warehouses/${id}/`, { method: 'DELETE' });
}

export async function getWarehouseSummary(id: number): Promise<WarehouseBalance[]> {
  return apiRequest<WarehouseBalance[]>(`/warehouses/${id}/summary/`);
}

// اللفات
export async function listRolls(params?: Record<string, string | number | undefined | null>): Promise<Paginated<FabricRoll>> {
  return apiRequest<Paginated<FabricRoll>>(`/warehouses/rolls/${buildQuery(params || {})}`);
}

// الاستلامات
export async function listReceipts(params?: Record<string, string | number | undefined | null>): Promise<Paginated<GoodsReceipt>> {
  return apiRequest<Paginated<GoodsReceipt>>(`/warehouses/receipts/${buildQuery(params || {})}`);
}

export async function createReceipt(data: ReceiptWrite): Promise<GoodsReceipt> {
  return apiRequest<GoodsReceipt>('/warehouses/receipts/', { method: 'POST', body: JSON.stringify(data) });
}

export async function postReceipt(id: number): Promise<GoodsReceipt> {
  return apiRequest<GoodsReceipt>(`/warehouses/receipts/${id}/post/`, { method: 'POST' });
}

export async function deleteReceipt(id: number): Promise<void> {
  return apiRequest<void>(`/warehouses/receipts/${id}/`, { method: 'DELETE' });
}

// التحويلات
export async function listTransfers(params?: Record<string, string | number | undefined | null>): Promise<Paginated<StockTransfer>> {
  return apiRequest<Paginated<StockTransfer>>(`/warehouses/transfers/${buildQuery(params || {})}`);
}

export async function getTransfer(id: number): Promise<StockTransfer> {
  return apiRequest<StockTransfer>(`/warehouses/transfers/${id}/`);
}

export async function createTransfer(data: TransferWrite): Promise<StockTransfer> {
  return apiRequest<StockTransfer>('/warehouses/transfers/', { method: 'POST', body: JSON.stringify(data) });
}

export async function deleteTransfer(id: number): Promise<void> {
  return apiRequest<void>(`/warehouses/transfers/${id}/`, { method: 'DELETE' });
}

export async function changeTransferStatus(id: number, action: 'request' | 'approve' | 'reject' | 'complete' | 'cancel', payload?: Record<string, string>): Promise<StockTransfer> {
  return apiRequest<StockTransfer>(`/warehouses/transfers/${id}/${action}/`, {
    method: 'POST',
    body: payload ? JSON.stringify(payload) : undefined,
  });
}

// التسويات
export async function listAdjustments(params?: Record<string, string | number | undefined | null>): Promise<Paginated<StockAdjustment>> {
  return apiRequest<Paginated<StockAdjustment>>(`/warehouses/adjustments/${buildQuery(params || {})}`);
}

export async function createAdjustment(data: AdjustmentWrite): Promise<StockAdjustment> {
  return apiRequest<StockAdjustment>('/warehouses/adjustments/', { method: 'POST', body: JSON.stringify(data) });
}

// الجرد
export async function listCounts(params?: Record<string, string | number | undefined | null>): Promise<Paginated<StockCount>> {
  return apiRequest<Paginated<StockCount>>(`/warehouses/counts/${buildQuery(params || {})}`);
}

export async function createCount(data: { warehouse: number; date: string; notes?: string }): Promise<StockCount> {
  return apiRequest<StockCount>('/warehouses/counts/', { method: 'POST', body: JSON.stringify(data) });
}

export async function getCount(id: number): Promise<StockCount> {
  return apiRequest<StockCount>(`/warehouses/counts/${id}/`);
}

export async function updateCountItems(id: number, items: Array<{ fabric: number; counted_yards: number | null }>): Promise<CountItem[]> {
  return apiRequest<CountItem[]>(`/warehouses/counts/${id}/items/`, {
    method: 'PATCH',
    body: JSON.stringify({ items }),
  });
}

export async function postCount(id: number): Promise<StockCount> {
  return apiRequest<StockCount>(`/warehouses/counts/${id}/post/`, { method: 'POST' });
}

export async function cancelCount(id: number): Promise<StockCount> {
  return apiRequest<StockCount>(`/warehouses/counts/${id}/cancel/`, { method: 'POST' });
}

// حركات المخزون
export async function listMovements(params?: Record<string, string | number | undefined | null>): Promise<Paginated<StockMovement>> {
  return apiRequest<Paginated<StockMovement>>(`/warehouses/movements/${buildQuery(params || {})}`);
}

// الرصيد الكلي (المخزون الموحد)
export async function getStockBalances(params?: Record<string, string | number | undefined | null>): Promise<StockBalanceResult> {
  return apiRequest<StockBalanceResult>(`/warehouses/stock/${buildQuery(params || {})}`);
}

export async function setStockBalance(data: { fabric: number; items: Array<{ warehouse: number; yards: number }> }): Promise<{ detail: string }> {
  return apiRequest<{ detail: string }>('/warehouses/stock/set/', { method: 'POST', body: JSON.stringify(data) });
}

// الأرصدة الافتتاحية
export async function listOpenings(params?: Record<string, string | number | undefined | null>): Promise<Paginated<StockOpening>> {
  return apiRequest<Paginated<StockOpening>>(`/warehouses/openings/${buildQuery(params || {})}`);
}

export async function createOpening(data: StockOpeningWrite): Promise<StockOpening> {
  return apiRequest<StockOpening>('/warehouses/openings/', { method: 'POST', body: JSON.stringify(data) });
}