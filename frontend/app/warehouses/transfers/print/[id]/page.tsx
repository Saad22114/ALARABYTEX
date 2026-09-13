'use client';

import { useEffect, useState } from 'react';
import { useParams } from 'next/navigation';
import Button from '@/components/ui/Button';
import Spinner from '@/components/ui/Spinner';
import { Printer, ArrowRight } from 'lucide-react';
import { StockTransfer } from '@/types';
import { getTransfer } from '@/services/warehouses';
import { useToast } from '@/components/ui/Toast';
import { useSettings } from '@/components/providers/SettingsProvider';
import { formatNumber, formatArabicDate } from '@/lib/format';

export default function TransferPrintPage() {
  const params = useParams<{ id: string }>();
  const { toast } = useToast();
  const { settings } = useSettings();
  const [transfer, setTransfer] = useState<StockTransfer | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getTransfer(Number(params.id))
      .then(setTransfer)
      .catch((err: any) => { setError(err.message); toast('error', err.message); });
  }, [params.id]);

  if (error) {
    return (
      <div className="min-h-screen bg-sand-50 flex items-center justify-center p-6">
        <div className="text-center">
          <p className="text-red-600 font-semibold mb-4">{error}</p>
          <button onClick={() => window.history.back()} className="text-brand-600 underline text-sm">
            العودة
          </button>
        </div>
      </div>
    );
  }

  if (!transfer) {
    return (
      <div className="min-h-screen bg-sand-50 flex items-center justify-center">
        <Spinner size={40} />
      </div>
    );
  }

  const totalCost = transfer.items.reduce((s, it) => s + Number(it.yards), 0);

  return (
    <div className="min-h-screen bg-sand-100 print:bg-white p-6 print:p-0">
      <div className="max-w-2xl mx-auto no-print flex items-center justify-between mb-6 print:hidden">
        <button
          onClick={() => window.history.back()}
          className="inline-flex items-center gap-2 text-sm text-neutral-600 hover:text-brand-700"
        >
          <ArrowRight size={16} />
          العودة للتحويلات
        </button>
        <Button onClick={() => window.print()}>
          <Printer size={16} />
          طباعة السند
        </Button>
      </div>

      <div className="max-w-2xl mx-auto bg-white border border-sand-200 shadow-sm rounded-2xl print:rounded-none print:border-0 print:shadow-none p-8">
        <div className="flex items-start justify-between pb-6 mb-6 border-b-2 border-neutral-800">
          <div>
            <h1 className="text-lg font-bold text-neutral-900">{settings?.business_name || 'القماش العربي'}</h1>
            {settings?.business_address && <p className="text-xs text-neutral-500 mt-1">{settings.business_address}</p>}
            {settings?.business_phone && <p className="text-xs text-neutral-500" dir="ltr">{settings.business_phone}</p>}
          </div>
          <div className="text-left">
            <h2 className="text-xl font-bold text-neutral-900 mb-1">سند تحويل بضاعة</h2>
            <p className="text-sm font-medium text-neutral-700" dir="ltr">{transfer.number}</p>
            <p className="text-xs text-neutral-500 mt-1 tabular-nums">
              {transfer.date}
            </p>
          </div>
        </div>

        <div className="grid grid-cols-2 gap-6 mb-6">
          <div className="border border-sand-200 rounded-xl p-4">
            <p className="text-xs font-semibold text-neutral-500 mb-2">من المخزن (المُرسِل)</p>
            <p className="font-bold text-neutral-900">{transfer.from_warehouse_name}</p>
            {transfer.requested_by && <p className="text-xs text-neutral-500 mt-2">مقدّم الطلب: {transfer.requested_by}</p>}
          </div>
          <div className="border border-sand-200 rounded-xl p-4">
            <p className="text-xs font-semibold text-neutral-500 mb-2">
              {transfer.dest_type === 'branch' ? 'إلى الفرع (المُستقبِل)' : 'إلى المخزن (المُستقبِل)'}
            </p>
            <p className="font-bold text-neutral-900">{transfer.dest_name}</p>
            {transfer.approved_by && <p className="text-xs text-neutral-500 mt-2">الموافِق: {transfer.approved_by}</p>}
          </div>
        </div>

        <table className="w-full text-sm mb-6">
          <thead>
            <tr className="bg-neutral-100">
              <th className="text-right px-3 py-2 font-semibold text-neutral-700 border border-neutral-200">م</th>
              <th className="text-right px-3 py-2 font-semibold text-neutral-700 border border-neutral-200">القماش</th>
              <th className="text-left px-3 py-2 font-semibold text-neutral-700 border border-neutral-200">العدد</th>
              <th className="text-left px-3 py-2 font-semibold text-neutral-700 border border-neutral-200">الياردات</th>
            </tr>
          </thead>
          <tbody>
            {transfer.items.map((it, i) => (
              <tr key={it.id ?? it.fabric}>
                <td className="px-3 py-2 border border-neutral-200 text-neutral-500">{i + 1}</td>
                <td className="px-3 py-2 border border-neutral-200 font-medium">{it.fabric_name}</td>
                <td className="px-3 py-2 border border-neutral-200 text-left tabular-nums">
                  {it.quantity_mode === 'roll' ? it.rolls_count : (it.rolls_count || '—')}
                </td>
                <td className="px-3 py-2 border border-neutral-200 text-left tabular-nums">
                  {formatNumber(Number(it.yards))}
                  {it.quantity_mode === 'roll' && it.yards > 0 && <span className="text-neutral-400 text-xs ms-1">ياردة</span>}
                </td>
              </tr>
            ))}
            <tr className="bg-neutral-50 font-bold">
              <td colSpan={3} className="px-3 py-2 border border-neutral-200 text-neutral-800">الإجمالي</td>
              <td className="px-3 py-2 border border-neutral-200 text-left tabular-nums">{formatNumber(totalCost)}</td>
            </tr>
          </tbody>
        </table>

        <div className="grid grid-cols-3 gap-6 pt-6 mt-6 border-t border-neutral-200">
          <div className="text-center">
            <p className="text-xs text-neutral-500 mb-8">توقيع أمين المخزن المُرسِل</p>
            <div className="border-t border-neutral-400 pt-2 text-xs text-neutral-500">من: {transfer.from_warehouse_name}</div>
          </div>
          <div className="text-center">
            <p className="text-xs text-neutral-500 mb-8">توقيع أمين المخزن المُستقبِل</p>
            <div className="border-t border-neutral-400 pt-2 text-xs text-neutral-500">إلى: {transfer.dest_name}</div>
          </div>
          <div className="text-center">
            <p className="text-xs text-neutral-500 mb-8">توقيع المدير</p>
            <div className="border-t border-neutral-400 pt-2 text-xs text-neutral-500">الموافقة</div>
          </div>
        </div>

        {transfer.notes && (
          <p className="mt-6 text-xs text-neutral-500 border-t border-neutral-100 pt-4">
            ملاحظات: {transfer.notes}
          </p>
        )}

        <div className="mt-6 text-center text-[10px] text-neutral-400">
          طُبع بواسطة {settings?.business_name || 'القماش العربي'} - {formatArabicDate(new Date())}
        </div>
      </div>
    </div>
  );
}