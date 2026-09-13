'use client';

import {
  ComposedChart,
  Bar,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from 'recharts';
import { DashboardChartPoint } from '@/types';
import { formatCurrency } from '@/lib/format';
import EmptyState from '@/components/ui/EmptyState';
import { BarChart3 } from 'lucide-react';

interface SalesChartProps {
  data: DashboardChartPoint[];
}

function formatXAxis(dateStr: string): string {
  const d = new Date(dateStr);
  return `${d.getDate()}/${d.getMonth() + 1}`;
}

export default function SalesChart({ data }: SalesChartProps) {
  if (!data || data.length === 0) {
    return (
      <EmptyState
        icon={<BarChart3 size={48} />}
        title="لا توجد بيانات"
        description="لا توجد بيانات مبيعات ومصاريف لعرضها في الفترة الحالية"
      />
    );
  }

  const formatted = data.map((d) => ({
    ...d,
    label: formatXAxis(d.date),
  }));

  return (
    <div className="w-full h-[350px]" dir="ltr">
      <ResponsiveContainer width="100%" height="100%">
        <ComposedChart data={formatted} margin={{ top: 10, right: 10, left: 10, bottom: 0 }}>
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
            formatter={(value: number) => formatCurrency(value)}
          />
          <Legend
            wrapperStyle={{ fontSize: '13px' }}
            formatter={(value) =>
              value === 'sales' ? 'المبيعات' : value === 'expenses' ? 'المصاريف' : 'صافي'
            }
          />
          <Bar dataKey="sales" fill="#1e6b56" radius={[4, 4, 0, 0]} barSize={28} />
          <Bar dataKey="expenses" fill="#d97706" radius={[4, 4, 0, 0]} barSize={28} />
          <Line
            dataKey="net"
            stroke="#c9a63e"
            strokeWidth={2}
            dot={{ r: 3, fill: '#c9a63e' }}
          />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}
