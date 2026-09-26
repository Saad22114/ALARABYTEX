import { AnalyticsReportDef } from '@/types';

export const PAYMENT_METHODS = [
  { value: 'cash', label: 'نقدي' },
  { value: 'transfer', label: 'تحويل' },
  { value: 'card', label: 'بطاقة' },
  { value: 'other', label: 'أخرى' },
] as const;

export const DATE_PERIODS = [
  { value: 'today', label: 'اليوم' },
  { value: 'week', label: 'هذا الأسبوع' },
  { value: 'month', label: 'هذا الشهر' },
  { value: 'custom', label: 'فترة مخصصة' },
] as const;

export const PAYMENT_METHODS_MAP: Record<string, string> = {
  cash: 'نقدي',
  transfer: 'تحويل',
  card: 'بطاقة',
  other: 'أخرى',
};

export const PAYROLL_RUN_STATUSES: Record<string, string> = {
  DRAFT: 'مسودة',
  APPROVED: 'معتمد',
  PAID: 'مصروف',
  CANCELLED: 'ملغى',
};

export const SALARY_ADVANCE_STATUSES: Record<string, string> = {
  PENDING: 'مسودة',
  APPROVED: 'معتمد',
  REJECTED: 'مرفوض',
  SETTLED: 'مسدد',
};

export const PAYROLL_METHODS: Record<string, string> = {
  CASH: 'نقدي',
  BANK: 'تحويل بنكي',
};

export const PAYROLL_METHODS_LIST = [
  { value: 'CASH', label: 'نقدي' },
  { value: 'BANK', label: 'تحويل بنكي' },
] as const;

export const ADVANCE_METHODS: Record<string, string> = {
  CASH: 'نقدي',
  DEDUCTION: 'خصم من الراتب',
  BANK: 'تحويل بنكي',
};

export const ADVANCE_METHODS_LIST = [
  { value: 'CASH', label: 'نقدي' },
  { value: 'DEDUCTION', label: 'خصم من الراتب' },
  { value: 'BANK', label: 'تحويل بنكي' },
] as const;

export const REPORT_GROUPS: { key: string; label: string }[] = [  { key: 'overview', label: 'نظرة عامة' },
  { key: 'sales', label: 'المبيعات' },
  { key: 'inventory', label: 'المخزون' },
  { key: 'people', label: 'الموظفون والرواتب' },
  { key: 'finance', label: 'المالية' },
  { key: 'partners', label: 'الموردون والشركاء' },
];

export const ANALYTICS_REPORTS: AnalyticsReportDef[] = [
  {
    key: 'summary',
    label: 'ملخص الأداء',
    group: 'overview',
    window: 'summary',
    supportsGroupBy: false,
    supportsIdleDays: false,
    description: 'مؤشرات المبيعات والمصروفات والأرباح مع مقارنة بالفترة السابقة',
  },
  {
    key: 'sales-trend',
    label: 'تطور المبيعات',
    group: 'sales',
    window: 'sales-trend',
    supportsGroupBy: true,
    supportsIdleDays: false,
    description: 'منحنى المبيعات والهوامش عبر الفترة مع خط مقارنة',
  },
  {
    key: 'branch-performance',
    label: 'أداء الفروع',
    group: 'sales',
    window: 'branch-performance',
    supportsGroupBy: false,
    supportsIdleDays: false,
    description: 'مبيعات ومصروفات وصافي كل فرع مع حصته من الإجمالي',
  },
  {
    key: 'employee-performance',
    label: 'أداء الموظفين',
    group: 'people',
    window: 'employee-performance',
    supportsGroupBy: false,
    supportsIdleDays: false,
    description: 'مبيعات كل موظف وعمولته ونسبته من إجمالي الفريق',
  },
  {
    key: 'payroll',
    label: 'تقرير الرواتب',
    group: 'people',
    window: 'payroll',
    supportsGroupBy: false,
    supportsIdleDays: false,
    description: 'إجمالي الرواتب والخصومات والبدلات لكل مسيّر في الفترة',
  },
  {
    key: 'fabric-profitability',
    label: 'ربحية الأقمشة',
    group: 'inventory',
    window: 'fabric-profitability',
    supportsGroupBy: false,
    supportsIdleDays: false,
    description: 'تكلفة-yard مقابل الإيراد والربح وهامش كل قماش',
  },
  {
    key: 'inventory-slow',
    label: 'المخزون الراكد',
    group: 'inventory',
    window: 'inventory-slow',
    supportsGroupBy: false,
    supportsIdleDays: true,
    description: 'الأقمشة بطيئة الحركة مع قيمة المخزون الراكد',
  },
  {
    key: 'cashflow',
    label: 'حركة الخزينة',
    group: 'finance',
    window: 'cashflow',
    supportsGroupBy: true,
    supportsIdleDays: false,
    description: 'المقبوضات والمصروفات وصافي التدفق النقدي',
  },
  {
    key: 'supplier-aging',
    label: 'أعمار ديون الموردين',
    group: 'partners',
    window: 'supplier-aging',
    supportsGroupBy: false,
    supportsIdleDays: false,
    description: 'توزيع مستحقات الموردين على شرائح_age مع أقدم تاريخ',
  },
  {
    key: 'partner-aging',
    label: 'أعمار حسابات الشركاء',
    group: 'partners',
    window: 'partner-aging',
    supportsGroupBy: false,
    supportsIdleDays: false,
    description: 'رصيد كل شريك بعد التسديدات موزعاً على شرائح_age',
  },
];
