export interface Branch {
  id: number;
  name: string;
  code: string;
  phone: string;
  address: string;
  city: string;
  notes: string;
  is_active: boolean;
  sales_count: number;
  expenses_count: number;
  monthly_sales_target: number;
  monthly_sales: number;
  monthly_expenses: number;
  target_progress_pct: number | null;
  created_at: string;
  updated_at: string;
}

export interface FabricBranchPrice {
  id: number;
  branch: number;
  branch_name: string;
  fabric: number;
  fabric_name: string;
  fabric_code: string;
  fabric_unit: FabricUnit;
  yards_per_roll: number | null;
  global_sale_price_yard: number;
  global_sale_price_roll: number | null;
  sale_price_yard: number;
  sale_price_roll: number | null;
  min_sale_yard: number;
  min_sale_roll: number | null;
  created_at: string;
  updated_at: string;
}

export interface Supplier {
  id: number;
  name: string;
  company_name: string;
  phone: string;
  email: string;
  address: string;
  city: string;
  country: string;
  tax_number: string;
  notes: string;
  is_active: boolean;
  current_balance: number;
  created_at: string;
  updated_at: string;
}

export interface Customer {
  id: number;
  name: string;
  phone: string | null;
  email: string;
  address: string;
  notes: string;
  branch: number | null;
  branch_name: string;
  last_purchase_date?: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface CustomerLookupResult {
  found: boolean;
  customer: Customer | null;
}

export interface CustomersSummary {
  total_customers: number;
  active_count: number;
  new_count: number;
  with_phone_count: number;
}

export type FabricUnit = 'yard' | 'meter' | 'roll';

export interface Fabric {
  id: number;
  name: string;
  code: string;
  unit: FabricUnit;
  barcode: string;
  fabric_type: string;
  color: string;
  composition: string;
  width_cm: number | null;
  weight_gsm: number | null;
  origin: string;
  manufacturer: string;
  supplier: number | null;
  supplier_name: string;
  allow_roll_sale: boolean;
  roll_sale_overrides: Record<string, boolean>;
  purchase_price: number;
  sale_price_yard: number;
  sale_price_roll: number | null;
  min_sale_yard: number;
  min_sale_roll: number | null;
  sale_price_roll_display: number;
  min_sale_roll_display: number;
  profit_yard: number;
  profit_margin_pct: number;
  total_rolls: number;
  stock_yards: number;
  stock_cost_value: number;
  sold_count?: number;
  low_stock: boolean;
  min_stock: number;
  yards_per_roll: number | null;
  description: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface FabricSummary {
  fabric_count: number;
  active_count: number;
  low_stock_count: number;
  total_rolls: number;
  total_stock_yards: number;
  inventory_cost_value: number;
  inventory_retail_value: number;
}

export interface FabricStockItem {
  warehouse: number;
  warehouse_name: string;
  rolls: number;
  yards: number;
  cost_value: number;
}

export interface FabricStockResult {
  fabric: { id: number; name: string; code: string; unit: FabricUnit };
  items: FabricStockItem[];
  totals: { rolls: number; yards: number; cost_value: number };
}

export type PartnerOperationType = 'support' | 'withdraw';
export type PartnerPaymentMethod = 'cash' | 'transfer';

export interface Partner {
  id: number;
  name: string;
  share_percent: number;
  notes: string;
  is_active: boolean;
  total_support: number;
  total_withdraw: number;
  net_balance: number;
  created_at: string;
  updated_at: string;
}

export interface PartnerMovement {
  id: number;
  partner: number;
  partner_name: string;
  partner_share: number;
  movement_type: PartnerOperationType;
  movement_type_label: string;
  amount: number;
}

export interface PartnerOperation {
  id: number;
  number: string;
  date: string;
  partner: number | null;
  partner_name: string | null;
  operation_type: PartnerOperationType;
  operation_type_label: string;
  payment_method: PartnerPaymentMethod;
  payment_method_label: string;
  amount: number;
  reason: string;
  notes: string;
  movements: PartnerMovement[];
  created_at: string;
}

export interface PartnerOperationWrite {
  partner: number;
  date: string;
  operation_type: PartnerOperationType;
  payment_method: PartnerPaymentMethod;
  amount: number;
  reason?: string;
  notes?: string;
}

export interface PartnerMovementRecord {
  id: number;
  operation_id: number;
  date: string;
  number: string;
  movement_type: PartnerOperationType;
  movement_type_label: string;
  payment_method: PartnerPaymentMethod;
  payment_method_label: string;
  amount: number;
  reason: string;
  notes: string;
  running_balance: number;
}

export interface PartnerMovementsResult {
  partner: { id: number; name: string; share_percent: number; is_active: boolean };
  date_from: string | null;
  date_to: string | null;
  opening_balance: number;
  closing_balance: number;
  movements: PartnerMovementRecord[];
  totals: {
    total_support: number;
    total_withdraw: number;
    net: number;
  };
}

export interface PartnerOperationsSummary {
  count: number;
  total_amount: number;
  support_count: number;
  support_amount: number;
  withdraw_count: number;
  withdraw_amount: number;
  net: number;
}

export interface PartnerDistributionItem {
  id: number;
  name: string;
  share_percent: number;
  total_support: number;
  total_withdraw: number;
  actual_net: number;
  theoretical_share: number;
  difference: number;
  settlement: 'balanced' | 'add' | 'withdraw';
  settlement_amount: number;
}

export interface PartnerDistributionResult {
  date_from: string | null;
  date_to: string | null;
  total_support: number;
  total_withdraw: number;
  total_net: number;
  items: PartnerDistributionItem[];
}

export type SupplierEntryType = 'opening' | 'purchase' | 'payment' | 'return' | 'adjustment';
export type SupplierPayMethod = 'cash' | 'bank_transfer';

export interface LedgerItem {
  id: number;
  fabric: number;
  fabric_name: string;
  fabric_unit: string;
  quantity_yards: number;
  rolls: number;
  unit_price: number;
  total: number;
  warehouse?: number | null;
  warehouse_name?: string | null;
  branch?: number | null;
  branch_name?: string | null;
  destination_type?: 'warehouse' | 'branch' | '' | 'mixed';
  destination_name?: string | null;
}

export interface LedgerEntry {
  id: number;
  date: string;
  entry_type: SupplierEntryType;
  entry_type_label: string;
  amount: number;
  debit: number;
  credit: number;
  running_balance: number | null;
  description: string;
  receipt_no: string;
  payment_method: string | null;
  payment_method_label: string | null;
  bank_reference: string;
  receiver_name: string;
  notes: string;
  items: LedgerItem[];
  warehouse: number | null;
  warehouse_name: string | null;
  branch: number | null;
  branch_name: string | null;
  destination_type: 'warehouse' | 'branch' | 'mixed' | null;
  destination_name: string | null;
  goods_receipt_number: string | null;
  goods_receipt_status: string | null;
  created_at: string;
}

export interface LedgerSummary {
  opening_balance: number;
  total_purchases: number;
  total_payments: number;
  total_returns: number;
  balance: number;
  purchases_count: number;
  payments_count: number;
  returns_count: number;
}

export interface CreateLedgerEntry {
  entry_type: SupplierEntryType;
  date: string;
  amount?: number;
  payment_method?: SupplierPayMethod;
  payment_amount?: number;
  bank_reference?: string;
  receiver_name?: string;
  receipt_no?: string;
  description?: string;
  notes?: string;
  warehouse?: number | null;
  branch?: number | null;
  items?: Array<{
    fabric: number;
    quantity_yards?: number;
    rolls?: number;
    unit_price?: number;
    warehouse?: number | null;
    branch?: number | null;
  }>;
}

export type PaymentMethod = 'cash' | 'transfer' | 'card' | 'other';

export interface SalesByEmployeeRow {
  employee: number;
  employee_name: string;
  total_sales: number;
  cash_total: number;
  transfer_total: number;
  card_total: number;
  other_total: number;
  sales_count: number;
  items_count: number;
  yards_total: number;
}

export interface SalesByEmployeeResult {
  items: SalesByEmployeeRow[];
  unassigned_total: number;
  grand_total: number;
}

export interface SaleSummary {
  total_sales: number;
  cash: number;
  transfer: number;
  card: number;
  other: number;
  sales_count: number;
  days_count: number;
}

export interface DailySaleItem {
  id: number;
  fabric: number;
  fabric_name: string;
  fabric_unit: string;
  yards: number;
  unit_price: number | null;
}

export interface DailySaleItemWrite {
  fabric: number;
  yards: number;
  unit_price?: number;
}

export type SaleWritePayload = Omit<Partial<DailySale>, 'items'> & { items?: DailySaleItemWrite[] };

export interface DailySale {
  id: number;
  branch: number;
  branch_name: string;
  employee: number | null;
  employee_name: string | null;
  date: string;
  total_sales: number;
  cash_amount: number;
  transfer_amount: number;
  card_amount: number;
  other_amount: number;
  notes: string;
  payment_total: number;
  mismatch: boolean;
  items: DailySaleItem[];
  created_at: string;
  updated_at: string;
}

export interface Expense {
  id: number;
  branch: number;
  branch_name: string;
  category: number;
  category_name: string;
  date: string;
  amount: number;
  payment_method: PaymentMethod;
  description: string;
  notes: string;
  created_at: string;
  updated_at: string;
}

export interface ExpenseCategory {
  id: number;
  name: string;
  code: string;
  is_system: boolean;
  notes: string;
  is_active: boolean;
  expense_count: number;
  created_at: string;
  updated_at: string;
}

export interface ExpenseBudget {
  id: number;
  branch: number;
  branch_name: string;
  category: number;
  category_name: string;
  month: string;
  amount: number;
  created_at: string;
  updated_at: string;
}

export interface Paginated<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}

export interface SuppliersOverview {
  total_suppliers: number;
  active_count: number;
  total_purchases: number;
  purchases_count: number;
  total_payments: number;
  payments_count: number;
  total_returns: number;
  returns_count: number;
  outstanding_debit: number;
  owing_count: number;
  top_suppliers: { id: number; name: string; company_name: string; balance: number }[];
}

export interface DashboardChartPoint {
  date: string;
  sales: number;
  expenses: number;
  net: number;
  cogs: number;
  gross_profit: number;
}

export interface TopFabricProfit {
  fabric: number;
  fabric_name: string;
  fabric_code: string;
  yards_sold: number;
  unit_cost: number;
  revenue: number;
  cogs: number;
  profit: number;
}

export interface DashboardSummary {
  total_sales: number;
  total_expenses: number;
  net: number;
  gross_profit: number;
  margin_pct: number;
  branches_count: number;
  suppliers_count: number;
  chart_data: DashboardChartPoint[];
  chart_previous: DashboardChartPoint[];
  previous_sales: number;
  previous_expenses: number;
  previous_net: number;
  sales_delta_pct: number | null;
  expenses_delta_pct: number | null;
  net_delta_pct: number | null;
  top_fabrics: TopFabricProfit[];
  period: string;
  start_date: string;
  end_date: string;
}

export interface SalesReportData {
  date: string;
  branch_name: string;
  total_sales: number;
  cash_amount: number;
  transfer_amount: number;
  card_amount: number;
  other_amount: number;
}

export interface ExpensesReportData {
  date: string;
  branch_name: string;
  category_name: string;
  amount: number;
  payment_method: string;
  description: string;
}

export interface ExpenseBudgetReportRow {
  branch: number;
  branch_name: string;
  category: number;
  category_name: string;
  budget: number;
  spent: number;
  remaining: number;
  used_pct: number;
}

export interface CommissionReportRow {
  employee: number;
  employee_name: string;
  branch: number;
  branch_name: string;
  sessions_count: number;
  total_sales: number;
  total_commission: number;
}

export interface NetDailyReportData {
  date: string;
  sales: number;
  expenses: number;
  net: number;
}

export interface BranchesReportData {
  name: string;
  code: string;
  phone: string;
  city: string;
  sales_count: number;
  expenses_count: number;
  total_sales: number;
  total_expenses: number;
}

export interface SuppliersReportData {
  name: string;
  company_name: string;
  phone: string;
  email: string;
  city: string;
  country: string;
}

export interface AppSettings {
  pk: number;
  business_name: string;
  trade_name: string;
  commercial_registration: string;
  business_phone: string;
  business_address: string;
  tax_number: string;
  business_email: string;
  currency_symbol: string;
  currency_code: string;
  decimal_places: number;
  currency_position: 'after' | 'before';
  default_period: 'today' | 'week' | 'month';
  default_page_size: number;
  hidden_sections: string[];
  low_stock_threshold: number;
  low_stock_alert_enabled: boolean;
  date_format: string;
  default_theme: string;
  font_family: string;
  receipt_footer: string;
  invoice_notes: string;
  invoice_prefix: string;
  tax_rate: number;
  previous_day_cutoff_hour: number;
  session_warn_hours: number;
  session_danger_hours: number;
  default_payment_method: SessionPaymentMethod;
  discount_max_percent: number;
  receipt_show_tax: boolean;
  receipt_show_phone: boolean;
  logo: string;
  backup_password?: string;
  has_backup_password?: boolean;
  auto_backup_enabled?: boolean;
  auto_backup_time?: string | null;
  auto_backup_every_hours?: number;
  last_auto_backup_at?: string | null;
  last_auto_backup_path?: string;
  created_at: string;
  updated_at: string;
}

export interface SettingsContextValue {
  settings: AppSettings | null;
  loading: boolean;
  error: string | null;
  updateSettings: (partial: Partial<AppSettings>) => Promise<AppSettings>;
  refreshSettings: () => Promise<void>;
}

export interface ThemesControl {
  logo: string;
  default_theme: string;
  font_family: string;
  receipt_footer: string;
  invoice_notes: string;
  receipt_show_tax: boolean;
  receipt_show_phone: boolean;
  tax_rate: number;
}

export interface Warehouse {
  id: number;
  name: string;
  code: string;
  location: string;
  phone: string;
  manager_name: string;
  notes: string;
  branch: number | null;
  branch_name: string;
  is_branch_stock: boolean;
  is_active: boolean;
  total_rolls: number;
  total_yards: number;
  created_at: string;
  updated_at: string;
}

export type RollStatus = 'available' | 'consumed' | 'damaged';

export interface FabricRoll {
  id: number;
  code: string;
  warehouse: number;
  warehouse_name: string;
  fabric: number;
  fabric_name: string;
  fabric_unit: string;
  yards: number;
  remaining_yards: number;
  unit_cost: number;
  status: RollStatus;
  status_label: string;
  received_date: string | null;
  notes: string;
  created_at: string;
}

export interface WarehouseBalance {
  fabric: number;
  fabric_name: string;
  total_yards: number;
  rolls_available: number;
}

export type MovementType =
  | 'receipt'
  | 'transfer_out'
  | 'transfer_in'
  | 'adjustment_in'
  | 'adjustment_out'
  | 'count'
  | 'opening'
  | 'sale';

export interface StockMovement {
  id: number;
  date: string;
  warehouse: number;
  warehouse_name: string;
  fabric: number;
  fabric_name: string;
  roll: number | null;
  roll_code: string;
  movement_type: MovementType;
  movement_type_label: string;
  quantity: number;
  balance_before: number | null;
  balance_after: number | null;
  reference_type: string;
  reference_id: number | null;
  reference_no: string;
  notes: string;
  created_at: string;
}

export type ReceiptStatus = 'draft' | 'posted';

export interface ReceiptItem {
  id?: number;
  fabric: number;
  fabric_name?: string;
  rolls_count: number;
  yards: number;
  unit_price: number;
  total?: number;
}

export interface GoodsReceipt {
  id: number;
  number: string;
  warehouse: number | null;
  warehouse_name: string;
  branch: number | null;
  branch_name: string;
  dest_type: 'warehouse' | 'branch';
  dest_name: string;
  supplier: number | null;
  supplier_name: string;
  date: string;
  supplier_receipt_no: string;
  status: ReceiptStatus;
  status_label: string;
  notes: string;
  items: ReceiptItem[];
  total_yards: number;
  total_value: number;
  purchase_entry_number: string | null;
  created_at: string;
}

export interface GoodsReceiptWrite {
  warehouse?: number | null;
  branch?: number | null;
  supplier: number | null;
  date: string;
  supplier_receipt_no: string;
  notes: string;
  items: Array<{ fabric: number; yards: number; rolls: number; unit_price: number }>;
}

export type TransferStatus =
  | 'draft'
  | 'requested'
  | 'approved'
  | 'rejected'
  | 'completed'
  | 'cancelled';

export type TransferQuantityMode = 'yard' | 'roll';

export interface TransferItem {
  id?: number;
  fabric: number;
  fabric_name?: string;
  yards: number;
  rolls_count: number;
  quantity_mode?: TransferQuantityMode;
  quantity_mode_label?: string;
}

export interface StockTransfer {
  id: number;
  number: string;
  from_warehouse: number;
  from_warehouse_name: string;
  to_warehouse: number | null;
  to_warehouse_name: string;
  to_branch: number | null;
  to_branch_name: string;
  dest_type: 'warehouse' | 'branch';
  dest_name: string;
  date: string;
  status: TransferStatus;
  status_label: string;
  requested_by: string;
  approved_by: string;
  requested_at: string | null;
  approved_at: string | null;
  completed_at: string | null;
  notes: string;
  items: TransferItem[];
  total_yards: number;
  created_at: string;
}

export type AdjustmentDirection = 'in' | 'out';
export type AdjustmentReason = 'damage' | 'loss' | 'gain' | 'correction' | '';

export interface AdjustmentItem {
  id?: number;
  fabric: number;
  fabric_name?: string;
  yards: number;
  rolls_count: number;
}

export interface StockAdjustment {
  id: number;
  number: string;
  warehouse: number;
  warehouse_name: string;
  date: string;
  reason: AdjustmentReason;
  reason_label: string;
  direction: AdjustmentDirection;
  direction_label: string;
  notes: string;
  items: AdjustmentItem[];
  created_at: string;
}

export type CountStatus = 'open' | 'posted' | 'cancelled';

export interface CountItem {
  id: number;
  fabric: number;
  fabric_name: string;
  system_yards: number;
  counted_yards: number | null;
  difference: number;
}

export interface StockCount {
  id: number;
  number: string;
  warehouse: number;
  warehouse_name: string;
  date: string;
  status: CountStatus;
  status_label: string;
  notes: string;
  items: CountItem[];
  created_at: string;
}

export interface StockWarehouseBalance {
  warehouse: number;
  warehouse_name: string;
  is_branch_stock: boolean;
  total_yards: number;
  rolls_available: number;
  last_receipt_date: string | null;
}

export interface StockBalanceItem {
  fabric: number;
  fabric_name: string;
  fabric_code: string;
  min_stock: number;
  unit: string;
  total_yards: number;
  rolls_available: number;
  low_stock: boolean;
  warehouses: StockWarehouseBalance[];
}

export interface StockBalanceResult {
  items: StockBalanceItem[];
  totals: {
    total_yards: number;
    rolls_available: number;
    low_stock_count: number;
    warehouses: number;
  };
}

export interface StockOpeningItem {
  id: number;
  fabric: number;
  fabric_name: string;
  yards: number;
  rolls_count: number;
  unit_price: number;
}

export interface StockOpening {
  id: number;
  number: string;
  warehouse: number;
  warehouse_name: string;
  date: string;
  notes: string;
  items: StockOpeningItem[];
  total_yards: number;
  created_at: string;
}

export interface StockOpeningWriteItem {
  fabric: number;
  yards: number;
  rolls_count: number;
  unit_price: number;
}

export interface StockOpeningWrite {
  warehouse: number;
  date: string;
  notes?: string;
  items: StockOpeningWriteItem[];
}

export interface SaleStockResult {
  warehouse: number | null;
  warehouse_name: string;
  items: Array<{ fabric: number; fabric_name: string; yards: number }>;
}

export interface InventoryReportRow {
  fabric: number;
  fabric_code: string;
  fabric_name: string;
  min_stock: number;
  unit: string;
  total_yards: number;
  rolls_available: number;
  low_stock: boolean;
  rows: Array<{
    warehouse: number;
    warehouse_name: string;
    total_yards: number;
    rolls_available: number;
  }>;
}

export interface InventoryReportResult {
  items: InventoryReportRow[];
  totals: {
    total_yards: number;
    rolls_available: number;
    low_stock_count: number;
    fabrics: number;
  };
}

export interface InventoryMovementReportRow {
  date: string;
  warehouse_name: string;
  fabric_name: string;
  movement_type: string;
  movement_type_label: string;
  quantity: number;
  balance_before: number | null;
  balance_after: number | null;
  reference_no: string;
}

export interface InventoryMovementsReportResult {
  movements: InventoryMovementReportRow[];
  totals: { in: number; out: number; count: number };
}

export interface CogsReportRow {
  fabric: number;
  fabric_code: string;
  fabric_name: string;
  unit: string;
  yards_sold: number;
  avg_cost: number;
  revenue: number;
  cogs: number;
  profit: number;
}

export interface CogsReportResult {
  items: CogsReportRow[];
  totals: { yards_sold: number; revenue: number; cogs: number; profit: number };
  start_date: string;
  end_date: string;
}

export interface ProfitLossTotals {
  total_sales: number;
  cogs: number;
  gross_profit: number;
  expenses: number;
  net_profit: number;
}

export interface ProfitLossBranchRow {
  branch_name: string;
  sales: number;
  expenses: number;
  net: number;
}

export interface ProfitLossReportResult {
  totals: ProfitLossTotals;
  branches: ProfitLossBranchRow[];
}

export interface JournalReportRow {
  date: string;
  sales: number;
  purchases: number;
  expenses: number;
  support: number;
  withdraw: number;
  net: number;
  running_balance: number;
}

export interface JournalReportResult {
  journal: JournalReportRow[];
  totals: { sales: number; purchases: number; expenses: number; support: number; withdraw: number; net: number };
  start_date: string;
  end_date: string;
}

export interface LowStockAlert {
  fabric: number;
  fabric_name: string;
  fabric_code: string;
  unit: string;
  total_yards: number;
  min_stock: number;
}

export interface DashboardAlertsResult {
  date: string;
  low_stock: LowStockAlert[];
  low_stock_count: number;
  open_sessions: OpenSessionAlert[];
  open_sessions_count: number;
  pending_receipts: PendingReceiptAlert[];
  pending_receipts_count: number;
  today: {
    sales: number;
    expenses: number;
    support: number;
    withdraw: number;
    net: number;
  };
}

export interface OpenSessionAlert {
  id: number;
  employee_name: string;
  branch_name: string;
  opened_at: string;
}

export interface PendingReceiptAlert {
  id: number;
  supplier: number;
  supplier_name: string;
  receipt_no: string;
  date: string;
  amount: number;
  destination: string;
}

export interface DashboardActivityItem {
  type: 'sale' | 'purchase' | 'payment' | 'expense';
  id: number;
  title: string;
  amount: number;
  date: string;
  created_at: string;
  link: string;
}

export type EmployeeRole = 'admin' | 'supervisor' | 'sales' | 'accountant' | 'viewer' | 'custom';

export interface EmployeePermissions {
  [sectionKey: string]: {
    view: boolean;
    create: boolean;
    edit: boolean;
    delete: boolean;
    windows?: string[];
  };
}

export interface Employee {
  id: number;
  name: string;
  avatar: string;
  phone: string;
  branch: number | null;
  branch_name: string | null;
  allowed_branches: number[];
  allowed_branches_names: string[];
  notes: string;
  is_active: boolean;
  role: EmployeeRole;
  role_label: string;
  permissions: EmployeePermissions;
  hidden_sections: string[];
  commission_active: boolean;
  commission_percent: number;
  department: string;
  position: string;
  email: string;
  employee_code: string | null;
  multi_branch_access: boolean;
  must_change_password: boolean;
  birth_date: string | null;
  civil_id: string;
  address: string;
  hire_date: string | null;
  base_salary: number | string;
  username: string | null;
  password?: string;
  created_at: string;
  updated_at: string;
}

export interface AppSection {
  key: string;
  label: string;
  fixed: boolean;
  actions: string[];
  windows?: { key: string; label: string }[];
}

export interface RolePreset {
  label: string;
  description: string;
  permissions: EmployeePermissions;
  hidden_sections: string[];
}

export interface SectionsInfo {
  sections: AppSection[];
  roles: Record<string, RolePreset>;
}

export interface SessionEmployee {
  id: number;
  name: string;
  avatar: string;
  phone: string;
  branch: number | null;
  branch_name: string | null;
  allowed_branches: number[];
  allowed_branches_names: string[];
  role: EmployeeRole;
  role_label: string;
  permissions: EmployeePermissions;
  hidden_sections: string[];
  is_active: boolean;
  username: string | null;
  commission_active: boolean;
}

export interface AuthSession {
  token: string;
  employee: SessionEmployee;
  sections: AppSection[];
  roles: Record<string, RolePreset>;
}

export type SessionSaleType = 'yard' | 'roll';
export type SessionPaymentMethod = 'cash' | 'transfer' | 'card';

export interface SessionSaleItem {
  id: number;
  fabric: number;
  fabric_name: string;
  fabric_code: string;
  fabric_unit: string;
  sale_type: SessionSaleType;
  sale_type_label: string;
  quantity: number;
  unit_price: number;
  discount_amount: number;
  payment_method: SessionPaymentMethod;
  payment_method_label: string;
  total: number;
  sale_date: string;
  yards_effective: number;
  customer_name: string;
  customer_phone: string;
  sale_group: string;
  is_returned: boolean;
  returned_at: string | null;
  return_reason: string;
}

export interface SessionSaleItemWrite {
  fabric: number;
  sale_type: SessionSaleType;
  quantity: number;
  unit_price?: number;
  discount_amount?: number;
  payment_method: SessionPaymentMethod;
  customer_name?: string;
  customer_phone?: string;
}

export interface SessionTotals {
  cash: number;
  transfer: number;
  card: number;
  total: number;
  yards: number;
}

export type SessionStatus = 'open' | 'closed';

export interface SaleSession {
  id: number;
  employee: number;
  employee_name: string;
  branch: number;
  branch_name: string;
  status: SessionStatus;
  status_label: string;
  opened_at: string;
  closed_at: string | null;
  notes: string;
  commission_amount: number;
  elapsed_minutes: number | null;
  items: SessionSaleItem[];
  totals: SessionTotals;
  is_manual: boolean;
  manual_date: string | null;
  manual_cash: number;
  manual_transfer: number;
  manual_card: number;
}

export interface ManualSessionWrite {
  employee: number;
  branch?: number;
  date: string;
  cash: number;
  transfer: number;
  card: number;
  notes?: string;
}

export interface SaleSessionSummary {
  count: number;
  open_count: number;
  closed_count: number;
  items_count: number;
  returned_items_count: number;
  yards: number;
  total: number;
  cash: number;
  transfer: number;
  card: number;
}

export interface CustomerSalesResult {
  phone: string;
  items: Array<SessionSaleItem & {
    session_id: number;
    session_status: string;
    session_status_label: string;
    session_closed: boolean;
  }>;
  totals: {
    count: number;
    returned_count: number;
    total: number;
    yards: number;
  };
}

export type AccountType = 'asset' | 'liability' | 'equity' | 'income' | 'expense';

export interface Account {
  id: number;
  code: string;
  name: string;
  type: AccountType;
  type_label: string;
  parent: number | null;
  is_active: boolean;
  is_system: boolean;
  children_count: number;
}

export type JournalSource = 'manual' | 'session' | 'purchase' | 'expense' | 'partner' | 'closing';

export interface JournalLine {
  id: number;
  account: number;
  account_code: string;
  account_name: string;
  debit: number;
  credit: number;
  description: string;
}

export interface JournalEntry {
  id: number;
  number: string;
  date: string;
  description: string;
  source: JournalSource;
  source_label: string;
  source_id: number | null;
  created_by: number | null;
  created_by_name: string;
  created_at: string;
  reversed_at: string | null;
  lines: JournalLine[];
  total_debit: number;
  total_credit: number;
}

export interface TrialBalanceRow {
  id: number;
  code: string;
  name: string;
  type: AccountType;
  type_label: string;
  parent_id: number | null;
  debit: number;
  credit: number;
}

export interface TrialBalance {
  date_to: string | null;
  rows: TrialBalanceRow[];
  totals: { debit: number; credit: number };
  balanced: boolean;
}

export interface IncomeStatementRow {
  code: string;
  name: string;
  amount: number;
}

export interface IncomeStatement {
  date_from: string | null;
  date_to: string | null;
  income_rows: IncomeStatementRow[];
  expense_rows: IncomeStatementRow[];
  total_income: number;
  total_expenses: number;
  net_profit: number;
}

export interface BalanceSheetRow {
  code: string;
  name: string;
  amount: number;
}

export interface BalanceSheet {
  date_to: string | null;
  asset_rows: BalanceSheetRow[];
  liability_rows: BalanceSheetRow[];
  equity_rows: BalanceSheetRow[];
  total_assets: number;
  total_liabilities: number;
  total_equity: number;
  difference: number;
  balanced: boolean;
}

export interface CashFlowRow {
  source: JournalSource;
  label: string;
  in: number;
  out: number;
  net: number;
}

export interface CashFlow {
  date_from: string | null;
  date_to: string | null;
  rows: CashFlowRow[];
  totals: { in: number; out: number; net: number };
}

export interface CashBoxRow {
  source: JournalSource;
  label: string;
  in: number;
  out: number;
}

export interface CashBox {
  date: string;
  opening: number;
  rows: CashBoxRow[];
  totals: { in: number; out: number };
  closing: number;
}

export interface ClosedPeriod {
  id: number;
  period_end: string;
  description: string;
  net_profit: number;
  created_at: string;
}

export interface ChatMessage {
  id: number;
  sender: number;
  sender_name: string;
  receiver: number;
  receiver_name: string;
  body: string;
  read_at: string | null;
  edited_at: string | null;
  deleted_at: string | null;
  is_deleted: boolean;
  reply_to_id: number | null;
  reply_to_body: string;
  reply_from_name: string;
  created_at: string;
}

export interface ChatContactSummary {
  employee: {
    id: number;
    name: string;
    avatar: string;
    phone: string;
    role_label: string;
    branch_name: string;
    is_online: boolean;
  };
  last_message: string;
  last_message_from_me: boolean;
  last_at: string;
  unread: number;
}

export interface ConversationsResult {
  me: { id: number; name: string; avatar: string; role_label: string };
  conversations: ChatContactSummary[];
  unread_total: number;
}

export interface MessageThreadResult {
  with_employee: {
    id: number;
    name: string;
    avatar: string;
    branch_name: string;
    role_label: string;
    is_online: boolean;
  };
  messages: ChatMessage[];
}

export interface MessagingContact {
  id: number;
  name: string;
  avatar: string;
  phone: string;
  role_label: string;
  branch_name: string;
  is_online: boolean;
}

export interface MessageContactListResult {
  me: { id: number; name: string; avatar: string; role_label: string };
  employees: MessagingContact[];
}

export interface MessageSearchMatch {
  id: number;
  sender: number;
  sender_name: string;
  receiver: number;
  receiver_name: string;
  body: string;
  read_at: string | null;
  edited_at: string | null;
  deleted_at: string | null;
  is_deleted: boolean;
  reply_to_id: number | null;
  reply_to_body: string;
  reply_from_name: string;
  created_at: string;
}

export interface MessageSearchGroup {
  employee: MessagingContact;
  matches: MessageSearchMatch[];
  last_at: string;
}

export interface MessageSearchResult {
  q: string;
  groups: MessageSearchGroup[];
}

export interface EmployeeProfile {
  id: number;
  name: string;
  avatar: string;
  role: EmployeeRole;
  role_label: string;
  branch: number | null;
  branch_name: string;
  phone: string;
  email: string;
  department: string;
  position: string;
  employee_code: string;
  hire_date: string | null;
  is_active: boolean;
}

export interface AccountAvatarResult {
  employee: SessionEmployee;
}
