'use client';

import { useEffect, useState } from 'react';
import Card from '@/components/ui/Card';
import Spinner from '@/components/ui/Spinner';
import Table, { Td, Th, Tr } from '@/components/ui/Table';
import DateRangeToolbar, { getRangeForKey } from '@/components/ui/DateRangeToolbar';
import { formatCurrency } from '@/lib/format';
import { useToast } from '@/components/ui/Toast';
import { getSalesBySupplierFabric, SupplierFabricSalesResult } from '@/services/sales';

export default function SupplierFabricSalesReport({ branch }: { branch?: string }) {
  const { toast } = useToast();
  const [from, setFrom] = useState(getRangeForKey('today').from);
  const [to, setTo] = useState(getRangeForKey('today').to);
  const [report, setReport] = useState<SupplierFabricSalesResult | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    getSalesBySupplierFabric({ date_from: from, date_to: to, branch: branch || undefined })
      .then((result) => { if (!cancelled) setReport(result); })
      .catch((error: any) => { if (!cancelled) toast('error', error?.message || 'تعذر تحميل مبيعات الأقمشة حسب المورد'); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [from, to, branch, toast]);

  return (
    <div className="space-y-4">
      <Card className="space-y-4">
        <div>
          <h2 className="text-lg font-bold text-neutral-900">مبيعات الأقمشة حسب المورد</h2>
          <p className="mt-1 text-sm text-neutral-500">قيمة بنود الأقمشة المباعة، مجمعة حسب المورد الأساسي المسجل لكل قماش.</p>
        </div>
        <DateRangeToolbar from={from} to={to} onChange={(start, end) => { setFrom(start); setTo(end); }} />
      </Card>

      <Card className="!p-0 overflow-hidden">
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-sand-200 bg-gradient-to-l from-brand-50/70 to-surface px-4 py-4">
          <span className="font-semibold text-neutral-700">إجمالي قيمة المبيعات في الفترة</span>
          <strong className="text-xl tabular-nums text-brand-700">{report ? formatCurrency(report.grand_total) : '—'}</strong>
        </div>
        {loading ? <div className="flex justify-center py-12"><Spinner size={28} /></div> : !report?.results.length ? (
          <p className="py-10 text-center text-sm text-neutral-500">لا توجد مبيعات أقمشة في الفترة المحددة.</p>
        ) : (
          <Table>
            <thead><tr><Th>المورد</Th><Th>عدد بنود البيع</Th><Th>قيمة المبيعات</Th></tr></thead>
            <tbody>{report.results.map((row) => (
              <Tr key={row.supplier ?? 'unassigned'}>
                <Td className="font-semibold">{row.supplier_name}</Td>
                <Td className="tabular-nums">{row.items_count}</Td>
                <Td className="font-bold tabular-nums text-brand-700">{formatCurrency(row.sales_total)}</Td>
              </Tr>
            ))}</tbody>
          </Table>
        )}
      </Card>
      <p className="px-1 text-xs text-neutral-500">المبلغ هو قيمة بيع الأقمشة التابعة للمورد حسب سعر البيعة بعد الخصم، وليس رصيدًا مستحقًا دفعه للمورد.</p>
    </div>
  );
}
