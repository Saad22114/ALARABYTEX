'use client';

import Link from 'next/link';
import { ArrowLeft, Banknote, HandCoins, ReceiptText, ShoppingCart } from 'lucide-react';
import Card from '@/components/ui/Card';
import { DashboardActivityItem } from '@/types';
import { formatCurrency, formatDate } from '@/lib/format';
import EmptyState from '@/components/ui/EmptyState';

interface RecentActivityProps {
  activities: DashboardActivityItem[];
}

const typeMeta: Record<DashboardActivityItem['type'], { icon: React.ReactNode; color: string }> = {
  sale: { icon: <Banknote size={17} />, color: 'bg-emerald-50 text-emerald-600 dark:bg-emerald-500/15 dark:text-emerald-400' },
  purchase: { icon: <ShoppingCart size={17} />, color: 'bg-blue-50 text-blue-600 dark:bg-blue-500/15 dark:text-blue-400' },
  payment: { icon: <HandCoins size={17} />, color: 'bg-gold-400/20 text-gold-700 dark:text-gold-400' },
  expense: { icon: <ReceiptText size={17} />, color: 'bg-red-50 text-red-600 dark:bg-red-500/15 dark:text-red-400' },
};

export default function RecentActivity({ activities }: RecentActivityProps) {
  return (
    <Card title="آخر العمليات" subtitle="أحدث الحركات على النظام">
      {activities.length === 0 ? (
        <EmptyState
          icon={<Banknote size={40} />}
          title="لا توجد عمليات"
          description="لم تُسجَّل أي عمليات بعد"
        />
      ) : (
        <ul className="divide-y divide-sand-100">
          {activities.map((a) => {
            const meta = typeMeta[a.type];
            return (
              <li key={`${a.type}-${a.id}`}>
                <Link href={a.link} className="flex items-center gap-3 py-2.5 group">
                  <span className={`w-9 h-9 rounded-xl flex items-center justify-center shrink-0 ${meta.color}`}>
                    {meta.icon}
                  </span>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-neutral-800 truncate">{a.title}</p>
                    <p className="text-xs text-neutral-400">{formatDate(a.date)}</p>
                  </div>
                  <span className="text-sm font-semibold text-neutral-800 tabular-nums shrink-0">
                    {formatCurrency(a.amount)}
                  </span>
                  <ArrowLeft
                    size={16}
                    className="text-neutral-300 group-hover:text-brand-500 transition-colors shrink-0"
                  />
                </Link>
              </li>
            );
          })}
        </ul>
      )}
    </Card>
  );
}