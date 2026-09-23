import { describe, it, expect } from 'vitest';
import { buildSessionReceipt } from './receipt';
import { SaleSession, AppSettings } from '@/types';

function makeSession(): SaleSession {
  return {
    id: 42,
    employee: 1,
    employee_name: 'أحمد',
    branch: 1,
    branch_name: 'الفرع الرئيسي',
    status: 'closed',
    status_label: 'مغلقة',
    opened_at: '2026-09-15T10:30:00',
    closed_at: '2026-09-15T12:00:00',
    notes: '',
    commission_amount: 0,
    elapsed_minutes: 90,
    items: [
      {
        id: 1,
        fabric: 1,
        fabric_name: 'قطن',
        fabric_code: 'FAB-1',
        fabric_unit: 'yard',
        sale_type: 'yard',
        sale_type_label: 'يارد',
        quantity: 3.5,
        unit_price: 5,
        discount_amount: 0,
        payment_method: 'cash',
        payment_method_label: 'كاش',
        total: 17.5,
        sale_date: '2026-09-15',
        yards_effective: 3.5,
        customer_name: '',
        customer_phone: '',
        sale_group: 'group-1',
        is_returned: false,
        returned_at: null,
        return_reason: '',
      },
    ],
    totals: { cash: 17.5, transfer: 0, card: 0, total: 17.5, yards: 3.5 },
    is_manual: false,
    manual_date: null,
    manual_cash: 0,
    manual_transfer: 0,
    manual_card: 0,
  };
}

function makeSettings(): AppSettings {
  return {
    pk: 1,
    business_name: 'القماش العربي',
    trade_name: '',
    commercial_registration: '',
    business_phone: '91234567',
    business_address: 'مسقط',
    tax_number: '',
    business_email: '',
    currency_symbol: 'ر.ع',
    currency_code: 'OMR',
    decimal_places: 2,
    currency_position: 'after',
    default_period: 'today',
    default_page_size: 25,
    hidden_sections: [],
    low_stock_threshold: 0,
    low_stock_alert_enabled: false,
    date_format: 'YYYY-MM-DD',
    default_theme: 'light',
    font_family: 'cairo',
    receipt_footer: 'شكراً لزيارتكم',
    invoice_notes: '',
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
  };
}

describe('buildSessionReceipt', () => {
  it('includes business name, invoice number and item rows', () => {
    const html = buildSessionReceipt(makeSession(), makeSettings(), 'إيصال وردية');
    expect(html).toContain('<title>إيصال وردية</title>');
    expect(html).toContain('<h1>القماش العربي</h1>');
    expect(html).toContain('INV-42');
    expect(html).toContain('قطن');
    expect(html).toContain('كاش');
  });

  it('includes totals in the print area', () => {
    const html = buildSessionReceipt(makeSession(), makeSettings(), 'إيصال وردية');
    expect(html).toContain('17.5 ر.ع');
  });

  it('omits item table when the session has no items', () => {
    const session = makeSession();
    session.items = [];
    const html = buildSessionReceipt(session, makeSettings(), 'إيصال');
    expect(html).toContain('لا توجد بنود');
  });

  it('includes tax only when enabled', () => {
    const settings = makeSettings();
    settings.receipt_show_tax = true;
    const withTax = buildSessionReceipt(makeSession(), settings, 'إيصال');
    expect(withTax).toContain('ضريبة (5%)');
    expect(withTax).toContain('18.38'); // 17.5 * 1.05 = 18.375 -> 18.38

    settings.receipt_show_tax = false;
    const withoutTax = buildSessionReceipt(makeSession(), settings, 'إيصال');
    expect(withoutTax).not.toContain('ضريبة');
  });
});