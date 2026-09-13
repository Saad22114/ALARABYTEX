let currencyConfig = { symbol: 'ر.ع', decimals: 2 };

export function configureCurrency(config: { symbol: string; decimals: number }) {
  currencyConfig = config;
}

export function formatNumber(n: number): string {
  return new Intl.NumberFormat('ar-EG-u-nu-latn', {
    maximumFractionDigits: 2,
  }).format(n);
}

export function formatCurrency(n: number): string {
  const formatted = new Intl.NumberFormat('ar-EG-u-nu-latn', {
    minimumFractionDigits: currencyConfig.decimals,
    maximumFractionDigits: currencyConfig.decimals,
  }).format(n);
  return `${formatted} ${currencyConfig.symbol}`;
}

export function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString('ar-EG-u-nu-latn', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  });
}

export function formatShortDate(iso: string): string {
  return new Date(iso).toLocaleDateString('ar-EG-u-nu-latn', {
    month: 'short',
    day: 'numeric',
  });
}

export function formatArabicDate(date: Date): string {
  return date.toLocaleDateString('ar-EG-u-nu-latn', {
    weekday: 'long',
    year: 'numeric',
    month: 'long',
    day: 'numeric',
  });
}
