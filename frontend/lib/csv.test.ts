import { describe, it, expect } from 'vitest';
import { buildCsv, csvCell, csvFilename, type CsvColumn } from './csv';

interface Row {
  name: string;
  qty: number;
  note: string | null;
}

const columns: CsvColumn<Row>[] = [
  { header: 'الاسم', value: (r) => r.name },
  { header: 'الكمية', value: (r) => r.qty },
  { header: 'ملاحظة', value: (r) => r.note },
];

describe('csvCell', () => {
  it('يحيّط كل خلية بعلامات اقتباس', () => {
    expect(csvCell('أحمد')).toBe('"أحمد"');
    expect(csvCell(5)).toBe('"5"');
  });

  it('يضاعف الاقتباس الداخلي حسب معيار RFC 4180', () => {
    expect(csvCell('قال "مرحباً"')).toBe('"قال ""مرحباً"""');
  });

  it('يحوّل null و undefined إلى خلية فارغة مقتبسة', () => {
    expect(csvCell(null)).toBe('""');
    expect(csvCell(undefined)).toBe('""');
  });

  it('لا يفسد الفواصل والأسطر داخل النص', () => {
    expect(csvCell('أ، ب')).toBe('"أ، ب"');
    expect(csvCell('سطر\nثانٍ')).toBe('"سطر\nثانٍ"');
  });
});

describe('buildCsv', () => {
  it('يكتب سطر عناوين ثم سطراً لكل صف', () => {
    const csv = buildCsv(columns, [
      { name: 'سالم', qty: 3, note: null },
      { name: 'نورة', qty: 10, note: 'VIP' },
    ]);
    expect(csv).toBe('"الاسم","الكمية","ملاحظة"\r\n"سالم","3",""\r\n"نورة","10","VIP"');
  });

  it('يكتب العناوين وحدها عندما لا توجد صفوف', () => {
    expect(buildCsv(columns, [])).toBe('"الاسم","الكمية","ملاحظة"');
  });

  it('يفصل بين الصفوف بـ CRLF لا بسطر واحد', () => {
    const csv = buildCsv(columns, [
      { name: 'أ', qty: 1, note: null },
      { name: 'ب', qty: 2, note: null },
    ]);
    expect(csv.split('\r\n')).toHaveLength(3);
  });
});

describe('csvFilename', () => {
  it('يلحق السنة والشهر واليوم', () => {
    expect(csvFilename('customers', '2026-09-28')).toBe('customers-2026-09-28.csv');
  });

  it('يبني الاسم من تاريخ اليوم إن لم يُمرَّر تاريخ', () => {
    expect(csvFilename('sales')).toMatch(/^sales-\d{4}-\d{2}-\d{2}\.csv$/);
  });

  it('يتجاهل تاريخاً غير صالح', () => {
    expect(csvFilename('sales', 'ليس تاريخاً')).toBe('sales.csv');
  });
});
