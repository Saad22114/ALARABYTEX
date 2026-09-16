'use client';

import Link from 'next/link';
import { AlertTriangle, Clock, PackageOpen } from 'lucide-react';
import Card from '@/components/ui/Card';
import { DashboardAlertsResult } from '@/types';
import { formatCurrency } from '@/lib/format';

interface AlertsPanelProps {
  alerts: DashboardAlertsResult;
}

export default function AlertsPanel({ alerts }: AlertsPanelProps) {
  const total = alerts.low_stock_count + alerts.open_sessions_count + alerts.pending_receipts_count;

  if (total === 0) {
    return (
      <div className="rounded-2xl bg-surface border border-emerald-200 dark:border-emerald-500/25 p-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <span className="w-9 h-9 rounded-xl bg-emerald-50 text-emerald-600 dark:bg-emerald-500/15 dark:text-emerald-400 flex items-center justify-center">
            <AlertTriangle size={18} />
          </span>
          <div>
            <p className="text-sm font-medium text-neutral-800">لا توجد تنبيهات</p>
            <p className="text-xs text-neutral-400">لا نقص في المخزون، ولا ورديات متأخرة، ولا مشتريات غير مستلمة</p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <Card title="التنبيهات" subtitle={`${total} تنبيه يحتاج انتباهك`}>
      <div className="space-y-4">
        {alerts.low_stock_count > 0 && (
          <div className="flex items-start justify-between gap-4">
            <div className="flex items-start gap-3 min-w-0">
              <span className="w-9 h-9 rounded-xl bg-red-50 text-red-600 dark:bg-red-500/15 dark:text-red-400 flex items-center justify-center shrink-0">
                <AlertTriangle size={18} />
              </span>
              <div className="min-w-0">
                <p className="text-sm font-medium text-neutral-800">
                  نقص المخزون: {alerts.low_stock_count} صنف أقل من حد التنبيه
                </p>
                <p className="text-xs text-neutral-500 mt-0.5 truncate">
                  {alerts.low_stock.slice(0, 3).map((f) => f.fabric_name).join('، ')}
                  {alerts.low_stock_count > 3 ? ` (+${alerts.low_stock_count - 3})` : ''}
                </p>
              </div>
            </div>
            <Link
              href="/warehouses"
              className="text-xs font-medium text-brand-600 hover:text-brand-700 shrink-0 mt-1"
            >
              المخازن ←
            </Link>
          </div>
        )}

        {alerts.open_sessions_count > 0 && (
          <div className="flex items-start justify-between gap-4">
            <div className="flex items-start gap-3 min-w-0">
              <span className="w-9 h-9 rounded-xl bg-amber-50 text-amber-600 dark:bg-amber-500/15 dark:text-amber-400 flex items-center justify-center shrink-0">
                <Clock size={18} />
              </span>
              <div className="min-w-0">
                <p className="text-sm font-medium text-neutral-800">
                  ورديات مفتوحة من أيام سابقة: {alerts.open_sessions_count}
                </p>
                <ul className="text-xs text-neutral-500 mt-1 space-y-0.5">
                  {alerts.open_sessions.slice(0, 3).map((s) => (
                    <li key={s.id}>
                      {s.employee_name} — {s.branch_name}
                    </li>
                  ))}
                  {alerts.open_sessions_count > 3 && (
                    <li>+{alerts.open_sessions_count - 3} أخرى</li>
                  )}
                </ul>
              </div>
            </div>
            <Link
              href="/sessions"
              className="text-xs font-medium text-brand-600 hover:text-brand-700 shrink-0 mt-1"
            >
              الورديات ←
            </Link>
          </div>
        )}

        {alerts.pending_receipts_count > 0 && (
          <div className="flex items-start justify-between gap-4">
            <div className="flex items-start gap-3 min-w-0">
              <span className="w-9 h-9 rounded-xl bg-blue-50 text-blue-600 dark:bg-blue-500/15 dark:text-blue-400 flex items-center justify-center shrink-0">
                <PackageOpen size={18} />
              </span>
              <div className="min-w-0">
                <p className="text-sm font-medium text-neutral-800">
                  مشتريات موردين غير مستلمة: {alerts.pending_receipts_count}
                </p>
                <ul className="text-xs text-neutral-500 mt-1 space-y-0.5">
                  {alerts.pending_receipts.slice(0, 3).map((p) => (
                    <li key={p.id}>
                      {p.supplier_name} — {formatCurrency(p.amount)}
                    </li>
                  ))}
                  {alerts.pending_receipts_count > 3 && (
                    <li>+{alerts.pending_receipts_count - 3} أخرى</li>
                  )}
                </ul>
              </div>
            </div>
            <Link
              href="/suppliers"
              className="text-xs font-medium text-brand-600 hover:text-brand-700 shrink-0 mt-1"
            >
              الموردون ←
            </Link>
          </div>
        )}
      </div>
    </Card>
  );
}