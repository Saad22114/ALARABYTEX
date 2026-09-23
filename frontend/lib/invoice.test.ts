import { describe, it, expect } from 'vitest';
import { buildSalesInvoice, arabicWords, sessionToDailySales } from './invoice';
import { DailySale, AppSettings, SaleSession } from '@/types';

function makeSale(patch: Partial<DailySale> = {}): DailySale {
  return {
    id: 7,
    branch: 1,
    branch_name: 'فرع الخوض',
    employee: 1,
    employee_name: 'أحمد',
    date: '2026-09-15',
    total_sales: 17.5,
    cash_amount: 17.5,
    transfer_amount: 0,
    card_amount: 0,
    other_amount: 0,
    notes: '',
    payment_total: 17.5,
    mismatch: false,
    items: [
      {
        id: 1,
        fabric: 1,
        fabric_name: 'حرير',
        fabric_unit: 'yard',
        yards: 3.5,
        unit_price: 5,
      },
    ],
    created_at: '',
    updated_at: '',
    ...patch,
  };
}

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
    hidden_sections: [],
    low_stock_threshold: 0,
    low_stock_alert_enabled: false,
    date_format: 'YYYY-MM-DD',
    default_theme: 'light',
    font_family: 'cairo',
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
  };
}

describe('buildSalesInvoice', () => {
  it('includes business name, invoice number and item rows for a single sale', () => {
    const html = buildSalesInvoice([makeSale()], makeSettings(), { title: 'فاتورة بيع' });
    expect(html).toContain('<h2>فاتورة بيع</h2>');
    expect(html).toContain('<h1>القماش العربي</h1>');
    expect(html).toContain('INV-7');
    expect(html).toContain('حرير');
    expect(html).toContain('فرع الخوض');
    expect(html).toContain('أحمد');
  });

  it('combines multiple sales into one document with each invoice number', () => {
    const settings = makeSettings();
    const sales = [makeSale({ id: 7, total_sales: 17.5, cash_amount: 17.5 }), makeSale({ id: 8, total_sales: 30, cash_amount: 30 })];
    const html = buildSalesInvoice(sales, settings);
    expect(html).toContain('فاتورة مجمعة');
    expect(html).toContain('عدد الفواتير: <b>2</b>');
    expect(html).toContain('INV-7');
    expect(html).toContain('INV-8');
    expect(html).toContain('47.5 ر.ع');
  });

  it('flattens all items into a single table for a combined invoice', () => {
    const settings = makeSettings();
    const sale1 = makeSale({ id: 7, total_sales: 17.5, cash_amount: 17.5, items: [{ id: 1, fabric: 1, fabric_name: 'حرير', fabric_unit: 'yard', yards: 3.5, unit_price: 5 }] });
    const sale2 = makeSale({
      id: 8, total_sales: 30, cash_amount: 30,
      items: [
        { id: 2, fabric: 2, fabric_name: 'قطن', fabric_unit: 'yard', yards: 10, unit_price: 3 },
        { id: 3, fabric: 3, fabric_name: 'اكسفورد', fabric_unit: 'yard', yards: 5, unit_price: 2.5 },
      ],
    });
    const html = buildSalesInvoice([sale1, sale2], settings);
    expect(html).toContain('جميع البنود');
    // كل البنود في جدول واحد
    expect(html).toContain('<th>رقم الفاتورة</th>');
    expect(html).toContain('<th>القماش</th>');
    expect(html).toContain('<th>الياردات</th>');
    expect(html).toContain('<th>سعر الوحدة</th>');
    expect(html).toContain('<th>الإجمالي</th>');
    expect(html).toContain('حرير');
    expect(html).toContain('قطن');
    expect(html).toContain('اكسفورد');
    // لا أقسام منفصلة لكل بيعة
    expect(html).not.toContain('إجمالي البيعة');
    expect(html).toContain('إجمالي بيوعات الفواتير المختارة');
  });

  it('shows trade name, commercial registration and invoice notes', () => {
    const settings = makeSettings();
    const html = buildSalesInvoice([makeSale()], settings);
    expect(html).toContain('مؤسسة الأقمشة العربية');
    expect(html).toContain('السجل التجاري: 100987654');
    expect(html).toContain('تُسلم البضاعة حسب المواصفات المتفق عليها');
  });

  it('writes the grand total in Arabic words', () => {
    const settings = makeSettings();
    const html = buildSalesInvoice([makeSale({ id: 7, total_sales: 45.5, cash_amount: 45.5 })], settings);
    expect(html).toContain('المبلغ كتابةً');
    expect(html).toContain('خمسة وأربعون');
    expect(html).toContain('OMR');
  });

  it('converts amounts to Arabic words', () => {
    expect(arabicWords(0)).toBe('صفر');
    expect(arabicWords(45)).toBe('خمسة وأربعون');
    expect(arabicWords(1234)).toContain('ألف ومائتان وأربعة وثلاثون');
    expect(arabicWords(2500000)).toContain('مليونان');
  });

  it('builds DailySale invoices from a closed session grouped by date', () => {
    const session: SaleSession = {
      id: 42,
      employee: 1,
      employee_name: 'أحمد',
      branch: 1,
      branch_name: 'فرع الخوض',
      status: 'closed',
      status_label: 'مغلقة',
      opened_at: '2026-09-15T08:00:00',
      closed_at: '2026-09-15T14:00:00',
      notes: '',
      commission_amount: 0,
      elapsed_minutes: 360,
      items: [
        {
          id: 1, fabric: 1, fabric_name: 'حرير', fabric_code: 'H1', fabric_unit: 'يارد',
          sale_type: 'yard', sale_type_label: 'ياردات', quantity: 3.5, unit_price: 5,
          discount_amount: 0, payment_method: 'cash', payment_method_label: 'كاش',
          total: 17.5, sale_date: '2026-09-15', yards_effective: 3.5,
          customer_name: '', customer_phone: '', sale_group: 'group-1',
          is_returned: false, returned_at: null, return_reason: '',
        },
        {
          id: 2, fabric: 2, fabric_name: 'قطن', fabric_code: 'Q1', fabric_unit: 'يارد',
          sale_type: 'yard', sale_type_label: 'ياردات', quantity: 10, unit_price: 3,
          discount_amount: 0, payment_method: 'transfer', payment_method_label: 'تحويل',
          total: 30, sale_date: '2026-09-15', yards_effective: 10,
          customer_name: '', customer_phone: '', sale_group: 'group-2',
          is_returned: false, returned_at: null, return_reason: '',
        },
      ],
      totals: { cash: 17.5, transfer: 30, card: 0, total: 47.5, yards: 13.5 },
      is_manual: false,
      manual_date: null,
      manual_cash: 0,
      manual_transfer: 0,
      manual_card: 0,
    };
    const sales = sessionToDailySales(session);
    expect(sales).toHaveLength(1);
    expect(sales[0].date).toBe('2026-09-15');
    expect(sales[0].total_sales).toBe(47.5);
    expect(sales[0].cash_amount).toBe(17.5);
    expect(sales[0].transfer_amount).toBe(30);
    expect(sales[0].items).toHaveLength(2);
    expect(sales[0].items[0].yards).toBe(3.5);
    expect(sales[0].items[0].unit_price).toBe(5);
  });

  it('applies tax only when enabled', () => {
    const settings = makeSettings();
    const sale = makeSale({ total_sales: 17.5, cash_amount: 17.5 });

    settings.receipt_show_tax = true;
    const withTax = buildSalesInvoice([sale], settings);
    expect(withTax).toContain('ضريبة (5%)');
    expect(withTax).toContain('18.38'); // 17.5 * 1.05 = 18.375 -> 18.38

    settings.receipt_show_tax = false;
    const withoutTax = buildSalesInvoice([sale], settings);
    expect(withoutTax).not.toContain('ضريبة');
  });

  it('shows a placeholder when a line has no unit price', () => {
    const sale = makeSale();
    sale.items[0].unit_price = null;
    const html = buildSalesInvoice([sale], makeSettings());
    expect(html).toContain('سعر الوحدة');
    expect(html).toContain('—');
  });

  it('emits autoPrint script only when requested', () => {
    const html = buildSalesInvoice([makeSale()], makeSettings(), { autoPrint: true });
    expect(html).toContain('window.print()');
    const plain = buildSalesInvoice([makeSale()], makeSettings());
    expect(plain).not.toContain('window.print()');
  });
});