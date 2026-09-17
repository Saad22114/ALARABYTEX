'use client';

import { useState, useEffect, useCallback } from 'react';
import AppShell from '@/components/layout/AppShell';
import Card from '@/components/ui/Card';
import Table, { Th, Td, Tr } from '@/components/ui/Table';
import SearchInput from '@/components/ui/SearchInput';
import Select from '@/components/ui/Select';
import Pagination from '@/components/ui/Pagination';
import DateRangeToolbar, { currentMonthRange } from '@/components/ui/DateRangeToolbar';
import Badge from '@/components/ui/Badge';
import EmptyState from '@/components/ui/EmptyState';
import Spinner from '@/components/ui/Spinner';
import { StockMovement, Paginated, Warehouse } from '@/types';
import { listMovements } from '@/services/warehouses';
import { listWarehouses } from '@/services/warehouses';
import { useToast } from '@/components/ui/Toast';
import { useSettings } from '@/components/providers/SettingsProvider';
import { useUrlState } from '@/lib/useUrlState';

const TYPE_META: Record<string, { label: string; variant: 'success' | 'warning' | 'danger' | 'neutral' }> = {
  receipt: { label: 'استلام من مورد', variant: 'success' },
  transfer_out: { label: 'تحويل صادر', variant: 'warning' },
  transfer_in: { label: 'تحويل ياردةد', variant: 'success' },
  adjustment_in: { label: 'تسوية إضافة', variant: 'success' },
  adjustment_out: { label: 'تسوية خصم', variant: 'danger' },
  count: { label: 'فارق جرد', variant: 'warning' },
  opening: { label: 'رصيد افتتاحي', variant: 'neutral' },
  sale: { label: 'مبيعات', variant: 'danger' },
};

export default function MovementsPage() {
  const { toast } = useToast();
  const { settings } = useSettings();
  const pageSize = settings?.default_page_size ?? 10;
  const [data, setData] = useState<Paginated<StockMovement> | null>(null);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useUrlState('page', 1);
  const [search, setSearch] = useUrlState('q', '');
  const [warehouse, setWarehouse] = useUrlState('warehouse', '');
  const [movementType, setMovementType] = useUrlState('type', '');
  const [dateFrom, setDateFrom] = useUrlState('from', currentMonthRange().from);
  const [dateTo, setDateTo] = useUrlState('to', currentMonthRange().to);
  const [warehouses, setWarehouses] = useState<Warehouse[]>([]);

  const fetchData = useCallback(() => {
    let cancelled = false;
    setLoading(true);
    const params: Record<string, string | number | undefined | null> = {
      page,
      page_size: pageSize,
      search: search || undefined,
      warehouse: warehouse || undefined,
      movement_type: movementType || undefined,
      date_from: dateFrom || undefined,
      date_to: dateTo || undefined,
    };
    listMovements(params)
      .then((res) => { if (!cancelled) setData(res); })
      .catch((err: any) => { if (!cancelled) toast('error', err.message); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [page, pageSize, search, warehouse, movementType, dateFrom, dateTo]);

  useEffect(() => fetchData(), [fetchData]);

  useEffect(() => {
    listWarehouses({ page_size: 100 }).then((r) => setWarehouses(r.results)).catch(() => {});
  }, []);

  const totalPages = data ? Math.ceil(data.count / pageSize) : 1;

  return (
    <AppShell>
      <div className="space-y-6">
        <div>
          <h1 className="text-xl font-bold text-neutral-800">حركات المخزون</h1>
          <p className="text-sm text-neutral-500">السجل الزمني الكامل لجميع الحركات الموثقة في المخازن</p>
        </div>

        <DateRangeToolbar
          from={dateFrom}
          to={dateTo}
          onChange={(f, t) => { setDateFrom(f); setDateTo(t); setPage(1); }}
        />

        <Card>
          <div className="grid grid-cols-2 md:grid-cols-3 gap-3 p-4 border-b border-sand-100">
            <SearchInput value={search} onChange={(v) => { setSearch(v); setPage(1); }} />
            <Select
              value={warehouse}
              onChange={(e) => { setWarehouse(e.target.value); setPage(1); }}
              options={warehouses.map((w) => ({ value: w.id, label: w.name }))}
              placeholder="كل المخازن"
            />
            <Select
              value={movementType}
              onChange={(e) => { setMovementType(e.target.value); setPage(1); }}
              options={Object.entries(TYPE_META).map(([v, m]) => ({ value: v, label: m.label }))}
              placeholder="كل أنواع الحركات"
            />
          </div>

          {loading ? (
            <div className="flex justify-center py-12"><Spinner size={32} /></div>
          ) : !data || data.results.length === 0 ? (
            <EmptyState title="لا توجد حركات" description="سجّل استلاماً أو تحويلاً لعرض الحركات هنا" />
          ) : (
            <>
              <Table>
                <thead>
                  <tr>
                    <Th>التاريخ</Th>
                    <Th>المخزن</Th>
                    <Th>الحالة</Th>
                    <Th>القماش</Th>
                    <Th>اللفة</Th>
                    <Th>الكمية</Th>
                    <Th>الرصيد قبل</Th>
                    <Th>الرصيد بعد</Th>
                    <Th>مرجع الوثيقة</Th>
                  </tr>
                </thead>
                <tbody>
                  {data.results.map((m: StockMovement) => {
                    const meta = TYPE_META[m.movement_type] || TYPE_META.opening;
                    return (
                      <Tr key={m.id}>
                        <Td className="tabular-nums">{m.date}</Td>
                        <Td>{m.warehouse_name}</Td>
                        <Td><Badge variant={meta.variant}>{meta.label}</Badge></Td>
                        <Td>{m.fabric_name}</Td>
                        <Td><span className="font-mono text-xs text-neutral-500" dir="ltr">{m.roll_code || '—'}</span></Td>
                        <Td className={`tabular-nums font-medium ${Number(m.quantity) < 0 ? 'text-red-600' : 'text-emerald-700'}`}>
                          {Number(m.quantity) > 0 ? '+' : ''}{formatNumberYards(Number(m.quantity))}
                        </Td>
                        <Td className="tabular-nums text-neutral-500">{m.balance_before != null ? formatNumberYards(Number(m.balance_before)) : '—'}</Td>
                        <Td className="tabular-nums font-medium">{m.balance_after != null ? formatNumberYards(Number(m.balance_after)) : '—'}</Td>
                        <Td className="text-xs text-neutral-500" dir="ltr">{m.reference_no || '—'}</Td>
                      </Tr>
                    );
                  })}
                </tbody>
              </Table>
              {totalPages > 1 && (
                <div className="p-4">
                  <Pagination page={page} totalPages={totalPages} onChange={setPage} />
                </div>
              )}
            </>
          )}
        </Card>
      </div>
    </AppShell>
  );
}

function formatNumberYards(n: number): string {
  return new Intl.NumberFormat('ar-EG-u-nu-latn', { maximumFractionDigits: 2 }).format(n);
}