'use client';

import { useEffect, useRef, useState } from 'react';
import Link from 'next/link';
import { AlertTriangle, Bell, RefreshCw, Wallet } from 'lucide-react';
import { getDashboardAlerts } from '@/services/dashboard';
import { DashboardAlertsResult } from '@/types';
import { formatCurrency, formatNumber } from '@/lib/format';

export default function NotificationsBell() {
  const [open, setOpen] = useState(false);
  const [alerts, setAlerts] = useState<DashboardAlertsResult | null>(null);
  const boxRef = useRef<HTMLDivElement>(null);

  const load = () => {
    getDashboardAlerts().then(setAlerts).catch(() => {});
  };

  useEffect(() => {
    load();
    const iv = setInterval(load, 60000);
    return () => clearInterval(iv);
  }, []);

  useEffect(() => {
    const onClick = (e: MouseEvent) => {
      if (boxRef.current && !boxRef.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener('mousedown', onClick);
    return () => document.removeEventListener('mousedown', onClick);
  }, []);

  const count = alerts?.low_stock_count || 0;

  return (
    <div ref={boxRef} className="relative">
      <button
        onClick={() => setOpen((o) => !o)}
        aria-label="الإشعارات"
        className="relative p-2 rounded-xl hover:bg-sand-100 text-neutral-600 dark:text-neutral-300 transition-colors"
      >
        <Bell size={20} />
        {count > 0 && (
          <span className="absolute -top-1 -right-1 min-w-[18px] h-[18px] px-1 rounded-full bg-red-500 text-white text-[11px] font-bold flex items-center justify-center">
            {count}
          </span>
        )}
      </button>

      {open && (
        <div className="absolute left-0 mt-2 w-80 max-h-[70vh] overflow-hidden rounded-2xl bg-surface border border-sand-200 shadow-xl z-50 flex flex-col">
          <div className="flex items-center justify-between px-4 py-3 border-b border-sand-200">
            <span className="font-semibold text-sm text-neutral-800">الإشعارات</span>
            <button
              onClick={load}
              aria-label="تحديث"
              className="p-1.5 rounded-lg hover:bg-sand-100 text-neutral-500"
            >
              <RefreshCw size={14} />
            </button>
          </div>

          <div className="overflow-y-auto">
            <div className="px-4 py-3 border-b border-sand-100">
              <div className="flex items-center gap-2 text-xs text-neutral-500 mb-2">
                <Wallet size={14} />
                ملخص اليوم
              </div>
              <div className="grid grid-cols-2 gap-2 text-sm">
                <div className="flex justify-between">
                  <span className="text-neutral-500">المبيعات</span>
                  <span className="tabular-nums font-medium">{formatCurrency(alerts?.today.sales ?? 0)}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-neutral-500">المصاريف</span>
                  <span className="tabular-nums font-medium">{formatCurrency(alerts?.today.expenses ?? 0)}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-neutral-500">دعم الشركاء</span>
                  <span className="tabular-nums font-medium">{formatCurrency(alerts?.today.support ?? 0)}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-neutral-500">سحب الشركاء</span>
                  <span className="tabular-nums font-medium">{formatCurrency(alerts?.today.withdraw ?? 0)}</span>
                </div>
                <div className="col-span-2 flex justify-between border-t border-sand-100 pt-2">
                  <span className="text-neutral-500">الصافي</span>
                  <span className={`tabular-nums font-bold ${(alerts?.today.net ?? 0) < 0 ? 'text-red-600' : 'text-brand-700'}`}>
                    {formatCurrency(alerts?.today.net ?? 0)}
                  </span>
                </div>
              </div>
            </div>

            <div className="px-4 py-3">
              <div className="flex items-center gap-2 text-xs text-neutral-500 mb-2">
                <AlertTriangle size={14} />
                نقص المخزون
              </div>
              {count === 0 ? (
                <p className="text-sm text-neutral-400 py-2">لا توجد أصناف تحت الحد الأدنى</p>
              ) : (
                <ul className="space-y-1">
                  {alerts!.low_stock.map((a) => (
                    <li key={a.fabric}>
                      <Link
                        href="/warehouses"
                        onClick={() => setOpen(false)}
                        className="flex items-center justify-between gap-2 rounded-lg px-2 py-1.5 hover:bg-sand-50 transition-colors"
                      >
                        <span className="flex items-center gap-2 min-w-0">
                          <span className="font-medium text-sm text-neutral-700 truncate">{a.fabric_name}</span>
                          <span className="font-mono text-[10px] bg-sand-100 px-1.5 py-0.5 rounded text-neutral-500">{a.fabric_code}</span>
                        </span>
                        <span className="text-xs tabular-nums text-red-600 shrink-0">
                          {formatNumber(a.total_yards)} / {formatNumber(a.min_stock)}
                        </span>
                      </Link>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}