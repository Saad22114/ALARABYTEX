'use client';

import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';
import { DashboardChartPoint } from '@/types';
import { formatCurrency } from '@/lib/format';
import EmptyState from '@/components/ui/EmptyState';
import { BarChart3 } from 'lucide-react';

interface MonthCompareChartProps {
  monthA: string; // YYYY-MM (first month / base)
  monthB: string; // YYYY-MM (second month / compare)
  seriesA: DashboardChartPoint[];
  seriesB: DashboardChartPoint[];
}

function byDay(series: DashboardChartPoint[]): Record<number, number> {
  const map: Record<number, number> = {};
  series.forEach((p) => {
    const d = new Date(p.date);
    map[d.getDate()] = p.sales;
  });
  return map;
}

function monthLabel(ym: string): string {
  const [y, m] = ym.split('-').map(Number);
  const months = ['يناير', 'فبراير', 'مارس', 'أبريل', 'مايو', 'يونيو', 'يوليو', 'أغسطس', 'سبتمبر', 'أكتوبر', 'نوفمبر', 'ديسمبر'];
  return `${months[(m || 1) - 1]} ${y}`;
}

export default function MonthCompareChart({ monthA, monthB, seriesA, seriesB }: MonthCompareChartProps) {
  const hasData = (seriesA && seriesA.length > 0) || (seriesB && seriesB.length > 0);
  if (!hasData) {
    return (
      <EmptyState
        icon={<BarChart3 size={48} />}
        title="لا توجد بيانات مقارنة"
        description="اختر شهرين من القائمة لعرض المقارنة بينهما"
      />
    );
  }

  const mapA = byDay(seriesA);
  const mapB = byDay(seriesB);
  const data = Array.from({ length: 31 }, (_, i) => ({
    day: i + 1,
    a: mapA[i + 1] || 0,
    b: mapB[i + 1] || 0,
  }));

  return (
    <div className="w-full h-[350px]" dir="ltr">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data} margin={{ top: 10, right: 10, left: 10, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#e8e4db" />
          <XAxis dataKey="day" tick={{ fontSize: 12, fill: '#737373' }} />
          <YAxis tick={{ fontSize: 12, fill: '#737373' }} />
          <Tooltip
            contentStyle={{
              borderRadius: '12px',
              border: '1px solid #e8e4db',
              boxShadow: '0 4px 12px rgba(0,0,0,0.08)',
              direction: 'rtl',
            }}
            labelFormatter={(label) => `اليوم ${label}`}
            formatter={(value: number, name: string) => [
              formatCurrency(value),
              name === 'a' ? monthLabel(monthA) : monthLabel(monthB),
            ]}
          />
          <Legend
            wrapperStyle={{ fontSize: '13px' }}
            formatter={(value) => (value === 'a' ? monthLabel(monthA) : monthLabel(monthB))}
          />
          <Line type="monotone" dataKey="a" stroke="#1e6b56" strokeWidth={2.5} dot={{ r: 3.5, fill: '#1e6b56' }} />
          <Line type="monotone" dataKey="b" stroke="#d97706" strokeWidth={2.5} dot={{ r: 3.5, fill: '#d97706' }} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}