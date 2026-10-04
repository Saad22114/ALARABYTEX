import { describe, it, expect } from 'vitest';
import {
  averagePerSellingDay,
  nonCashTotal,
  recordsInDaysNote,
  sellingDaysNote,
  type SalesSummaryTotals,
} from './salesSummary';

function totals(over: Partial<SalesSummaryTotals> = {}): SalesSummaryTotals {
  return {
    total_sales: 0, cash: 0, transfer: 0, card: 0, other: 0,
    sales_count: 0, days_count: 0,
    ...over,
  };
}

describe('nonCashTotal', () => {
  it('يجمع ما ليس نقداً كلَّه، فلا تسقط خانةٌ من التقسيم', () => {
    expect(nonCashTotal(totals({ transfer: 200, card: 150, other: 50 }))).toBe(400);
  });

  it('يجعل البطاقاتِ في الصفّ تجمع إلى الإجمالي', () => {
    // هذا هو السبب: لو سقطت «أخرى» لما جمع الصفُّ إلى الإجمالي، ولما
    // دلّ مجموعُ البطاقتين على أنّ المبلغَ كلَّه محسوبٌ وهو ناقصٌ منه شيء.
    const t = totals({ total_sales: 1000, cash: 600, transfer: 200, card: 150, other: 50 });
    expect(t.cash + nonCashTotal(t)).toBe(t.total_sales);
  });

  it('لا يختلقُ قيمةً من غائب، فيبقى صفراً صفراً', () => {
    expect(nonCashTotal(totals())).toBe(0);
    expect(nonCashTotal({ total_sales: 0 } as unknown as SalesSummaryTotals)).toBe(0);
  });
});

describe('averagePerSellingDay', () => {
  it('يقسم على أيامِ البيعِ التي فيها مبيعات، لا على أيامِ الفترة', () => {
    // خمسةُ أيامٍ مبيعٌ فيها من سبعة: المتوسّطُ على الخمسة.
    expect(averagePerSellingDay(1000, 5)).toBe(200);
  });

  it('لا يقسم على صفر، فلا يخرج «NaN» مكانَ رقم', () => {
    expect(averagePerSellingDay(1000, 0)).toBe(0);
    expect(averagePerSellingDay(0, 0)).toBe(0);
    expect(averagePerSellingDay(500, -3)).toBe(0);
  });

  it('يرفع متوسطاً أكبرَ على فتراتِ خلوٍ، لا أصغرَ منها', () => {
    // يومان خامدان لا يُنقصان المتوسّط: لم يدخلا في المجموع أصلاً،
    // فحسابُهما يُنقص شيئاً لم يُحسب زيادةً.
    expect(averagePerSellingDay(500, 2)).toBe(250);
    expect(averagePerSellingDay(500, 5)).toBe(100);
  });
});

describe('recordsInDaysNote', () => {
  it('يصوغ العددين معاً، فالعددُ بلا زمانٍ لا يعني شيئاً', () => {
    expect(recordsInDaysNote(12, 5)).toBe('12 سجل في 5 أيام');
    expect(recordsInDaysNote(1, 1)).toBe('1 سجل في 1 يوم');
    expect(recordsInDaysNote(3, 2)).toBe('3 سجلات في 2 يومان');
  });
});

describe('sellingDaysNote', () => {
  it('يقولُ كم يوماً قُسِم المجموعُ عليه', () => {
    expect(sellingDaysNote(5)).toBe('على 5 أيام بيعٍ');
    expect(sellingDaysNote(1)).toBe('على 1 يوم بيعٍ');
  });

  it('يفردُ يوماً واحداً، فلا يقول «على 1 أيام بيعٍ»', () => {
    expect(sellingDaysNote(2)).toBe('على 2 يومَي بيعٍ');
    expect(sellingDaysNote(0)).toBe('على 0 يوم بيعٍ');
  });
});