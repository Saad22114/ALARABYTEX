'use client';

import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';
import { DashboardChartPoint } from '@/types';
import { formatCurrency } from '@/lib/format';
import EmptyState from '@/components/ui/EmptyState';
import { TrendingUp } from 'lucide-react';

interface ComparisonChartProps {
  current: DashboardChartPoint[];
  previous: DashboardChartPoint[];
}

function formatXAxis(dateStr: string): string {
  const d = new Date(dateStr);
  return `${d.getDate()}/${d.getMonth() + 1}`;
}

export default function ComparisonChart({ current, previous }: ComparisonChartProps) {
  if (!current || current.length === 0) {
    return (
      <EmptyState
        icon={<TrendingUp size={48} />}
        title="لا توجد بيانات"
        description="لا توجد بيانات مقارنة لعرضها في الفترة الحالية"
      />
    );
  }

  const data = current.map((d, i) => {
    const prev = previous && previous[i];
    return {
      label: formatXAxis(d.date),
      current: d.sales,
      previous: prev ? prev.sales : 0,
    };
  });

  return (
    <div className="w-full h-[350px]" dir="ltr">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data} margin={{ top: 10, right: 10, left: 10, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#e8e4db" />
          <XAxis dataKey="label" tick={{ fontSize: 12, fill: '#737373' }} />
          <YAxis tick={{ fontSize: 12, fill: '#737373' }} />
          <Tooltip
            contentStyle={{
              borderRadius: '12px',
              border: '1px solid #e8e4db',
              boxShadow: '0 4px 12px rgba(0,0,0,0.08)',
              direction: 'rtl',
            }}
            formatter={(value: number, name: string) => [formatCurrency(value), name === 'current' ? 'الفترة الحالية' : 'الفترة السابقة']}
          />
          <Legend
            wrapperStyle={{ fontSize: '13px' }}
            formatter={(value) =>
              value === 'current' ? 'الفترة الحالية' : 'الفترة السابقة'
            }
          />
          <Line type="monotone" dataKey="current" stroke="#1e6b56" strokeWidth={2.5} dot={{ r: 4, fill: '#1e6b56' }} />
          <Line type="monotone" dataKey="previous" stroke="#a8a29e" strokeWidth={2} strokeDasharray="5 5" dot={{ r: 3, fill: '#a8a29e' }} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}