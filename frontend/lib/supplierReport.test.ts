import { describe, it, expect } from 'vitest';
import { buildSupplierReport, buildSuppliersOverviewReport } from './supplierReport';
import { Supplier, LedgerEntry, LedgerSummary, AppSettings, SuppliersOverview } from '@/types';

function makeSettings(): AppSettings {
  return {
    pk: 1,
    business_name: 'القماش العربي',
    trade_name: 'مؤسسة الأقمشة العربية',
    commercial_registration: '100987654',
    business_phone: '91234567',
    business_address: 'مسقط',
    tax_number: 'OM-12345',
    business_email: '',
    currency_symbol: 'ر.ع',
    currency_code: 'OMR',
    decimal_places: 2,
    currency_position: 'after',
    default_period: 'today',
    default_page_size: 25,
    allow_negative_stock: false,
    hidden_sections: [],
    low_stock_threshold: 0,
    low_stock_alert_enabled: false,
    date_format: 'YYYY-MM-DD',
    default_theme: 'light',
    receipt_footer: 'شكراً لتعاملكم معنا',
    invoice_notes: 'تُسلم البضاعة حسب المواصفات المتفق عليها',
    invoice_prefix: 'INV-',
    tax_rate: 5,
    previous_day_cutoff_hour: 3,
    session_warn_hours: 6,
    session_danger_hours: 12,
    default_payment_method: 'transfer',
    discount_max_percent: 20,
    receipt_show_tax: false,
    receipt_show_phone: true,
    logo: '',
    created_at: '',
    updated_at: '',
  } as AppSettings;
}

function makeSupplier(): Supplier {
  return {
    id: 1,
    name: 'مؤسسة النور',
    company_name: 'شركة النور للتجارة',
    phone: '99999999',
    email: '',
    address: '',
    city: 'نزوى',
    country: 'عمان',
    tax_number: 'OM-9999',
    notes: '',
    is_active: true,
    current_balance: 150,
    created_at: '',
    updated_at: '',
  } as Supplier;
}

function makeEntries(): LedgerEntry[] {
  return [
    {
      id: 1,
      date: '2026-08-01',
      entry_type: 'opening',
      entry_type_label: 'رصيد افتتاحي',
      amount: 100,
      debit: 100,
      credit: 0,
      running_balance: 100,
      description: 'رصيد افتتاحي',
      warehouse_name: '',
      branch_name: '',
      created_at: '',
      receipt_no: '',
      payment_method: null,
      payment_method_label: null,
      bank_reference: '',
      receiver_name: '',
      notes: '',
      items: [],
      warehouse: null,
      branch: null,
      destination_type: null,
      destination_name: null,
      goods_receipt_number: null,
      goods_receipt_status: null,
    },
    {
      id: 2,
      date: '2026-08-05',
      entry_type: 'purchase',
      entry_type_label: 'شراء',
      amount: 60,
      debit: 60,
      credit: 0,
      running_balance: 160,
      description: 'شراء أقمشة',
      warehouse_name: '',
      branch_name: '',
      created_at: '',
      receipt_no: 'GRN-101',
      payment_method: null,
      payment_method_label: null,
      bank_reference: '',
      receiver_name: '',
      notes: '',
      items: [
        { id: 1, fabric: 1, fabric_name: 'حرير', fabric_unit: 'ياردة', quantity_yards: 12, rolls: 2, unit_price: 5, total: 60 },
      ],
      warehouse: 1,
      branch: null,
      destination_type: 'warehouse',
      destination_name: 'المخزن الرئيسي',
      goods_receipt_number: null,
      goods_receipt_status: 'pending',
    },
    {
      id: 3,
      date: '2026-08-10',
      entry_type: 'payment',
      entry_type_label: 'دفعة',
      amount: 50,
      debit: 0,
      credit: 50,
      running_balance: 110,
      description: 'دفعة نقدية',
      warehouse_name: '',
      branch_name: '',
      created_at: '',
      receipt_no: '',
      payment_method: 'cash',
      payment_method_label: 'كاش',
      bank_reference: 'BR-7',
      receiver_name: 'سالم',
      notes: '',
      items: [],
      warehouse: null,
      branch: null,
      destination_type: null,
      destination_name: null,
      goods_receipt_number: null,
      goods_receipt_status: null,
    },
  ];
}

function makeSummary(): LedgerSummary {
  return {
    opening_balance: 100,
    total_purchases: 60,
    total_payments: 50,
    total_returns: 0,
    balance: 110,
    purchases_count: 1,
    payments_count: 1,
    returns_count: 0,
  };
}

describe('buildSupplierReport', () => {
  it('renders a full HTML ledger report with payments and item details', () => {
    const html = buildSupplierReport(makeSupplier(), makeEntries(), makeSummary(), makeSettings());
    expect(html).toContain('كشف حساب مورد');
    expect(html).toContain('مؤسسة النور');
    expect(html).toContain('شركة النور للتجارة');
    expect(html).toContain('رصيد افتتاحي');
    expect(html).toContain('إجمالي المشتريات');
    expect(html).toContain('إجمالي الدفعات');
    expect(html).toContain('دفعة نقدية');
    expect(html).toContain('كاش');
    expect(html).toContain('BR-7');
    expect(html).toContain('سالم');
    expect(html).toContain('حرير');
    expect(html).toContain('12');
    expect(html).toContain('2');
    expect(html).toContain('GRN-101');
    expect(html).toContain('المخزن الرئيسي');
    expect(html).toContain('التاريخ');
    expect(html).toContain('مدين');
    expect(html).toContain('دائن');
    expect(html).toContain('الرصيد');
  });

  it('totals debits and credits across entries', () => {
    const html = buildSupplierReport(makeSupplier(), makeEntries(), makeSummary(), makeSettings());
    expect(html).toContain('إجمالي الحركة');
    expect(html).toContain('160');
    expect(html).toContain('50');
    expect(html).toContain('110');
  });

  it('shows empty state when no entries', () => {
    const html = buildSupplierReport(makeSupplier(), [], makeSummary(), makeSettings());
    expect(html).toContain('لا توجد قيود مسجلة لهذا المورد');
  });
});

describe('buildSuppliersOverviewReport', () => {
  it('renders overview stats and supplier balances', () => {
    const overview: SuppliersOverview = {
      total_suppliers: 2,
      active_count: 2,
      total_purchases: 1000,
      purchases_count: 5,
      total_payments: 400,
      payments_count: 3,
      total_returns: 50,
      returns_count: 1,
      outstanding_debit: 600,
      owing_count: 1,
      top_suppliers: [{ id: 1, name: 'مؤسسة النور', company_name: 'شركة النور', balance: 600 }],
    };
    const suppliers = [
      { ...makeSupplier(), current_balance: 600 },
      { ...makeSupplier(), id: 2, name: 'مصنع الصباح', current_balance: -100 },
    ];
    const html = buildSuppliersOverviewReport(overview, suppliers, makeSettings());
    expect(html).toContain('تقرير الموردين');
    expect(html).toContain('إجمالي المشتريات');
    expect(html).toContain('إجمالي الدفعات');
    expect(html).toContain('مؤسسة النور');
    expect(html).toContain('مصنع الصباح');
    expect(html).toContain('600');
    expect(html).toContain('أعلى الموردين رصيداً');
  });
});