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
