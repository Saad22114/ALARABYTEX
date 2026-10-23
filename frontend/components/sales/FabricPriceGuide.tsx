'use client';

import { useEffect, useMemo, useState } from 'react';
import Card from '@/components/ui/Card';
import SearchInput from '@/components/ui/SearchInput';
import Spinner from '@/components/ui/Spinner';
import Table, { Td, Th, Tr } from '@/components/ui/Table';
import { useSettings } from '@/components/providers/SettingsProvider';
import { useToast } from '@/components/ui/Toast';
import { Fabric, FabricBranchPrice, Branch } from '@/types';
import { listFabrics } from '@/services/fabrics';
import { listBranches, listBranchPrices } from '@/services/branches';
import { formatCurrency } from '@/lib/format';
import { rollSaleAllowed } from '@/lib/fabrics';
import EmptyState from '@/components/ui/EmptyState';
import { useAuth } from '@/components/providers/AuthProvider';

const PAGE_SIZE = 200;

async function getAllPages<T>(fetchPage: (page: number) => Promise<{ count: number; results: T[] }>): Promise<T[]> {
  const all: T[] = [];
  let page = 1;
  let count = 0;
  do {
    const result = await fetchPage(page);
    all.push(...result.results);
    count = result.count;
    page += 1;
  } while (all.length < count);
  return all;
}

function money(value: number | null | undefined): string {
  return value == null || !Number.isFinite(value) ? '—' : formatCurrency(value);
}

export default function FabricPriceGuide() {
  const { session } = useAuth();
  const employee = session?.employee;
  const isManager = employee?.role === 'admin' || employee?.role === 'supervisor';
  const employeeBranchId = employee?.branch ?? null;
  const { settings } = useSettings();
  const { toast } = useToast();
  const [fabrics, setFabrics] = useState<Fabric[]>([]);
  const [branches, setBranches] = useState<Branch[]>([]);
  const [prices, setPrices] = useState<FabricBranchPrice[]>([]);
  const [search, setSearch] = useState('');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    if (!employee) return () => { cancelled = true; };
    setLoading(true);
    Promise.all([
      getAllPages((page) => listFabrics({ page, page_size: PAGE_SIZE })),
      getAllPages((page) => listBranches({ page, page_size: PAGE_SIZE })),
      getAllPages((page) => listBranchPrices({
        page,
        page_size: PAGE_SIZE,
        ...(!isManager && employeeBranchId != null ? { branch: employeeBranchId } : {}),
      })),
    ])
      .then(([allFabrics, allBranches, allPrices]) => {
        if (cancelled) return;
        setFabrics(allFabrics);
        setBranches(allBranches.filter((branch) =>
          branch.is_active && (isManager || branch.id === employeeBranchId),
        ));
        setPrices(allPrices.filter((price) => isManager || price.branch === employeeBranchId));
      })
      .catch((error: any) => {
        if (!cancelled) toast('error', error?.message || 'تعذر تحميل دليل أسعار الأقمشة');
      })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [toast, employee, employeeBranchId, isManager]);

  const visibleFabrics = useMemo(() => {
    const needle = search.trim().toLocaleLowerCase();
    const sorted = [...fabrics].sort((a, b) => a.name.localeCompare(b.name, 'ar'));
    return needle
      ? sorted.filter((fabric) => `${fabric.name} ${fabric.code}`.toLocaleLowerCase().includes(needle))
      : sorted;
  }, [fabrics, search]);

  const priceMap = useMemo(() => {
    const map = new Map<string, FabricBranchPrice>();
    prices.forEach((price) => map.set(`${price.fabric}:${price.branch}`, price));
    return map;
  }, [prices]);

  const minSalePercent = Number(settings?.min_sale_percent ?? 15) / 100;
  const minPieceMultiplier = Number(settings?.min_piece_price_multiplier ?? 1);

  return (
    <Card className="!p-0">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-sand-200 p-4">
        <div>
          <h2 className="font-bold text-neutral-800">دليل أسعار الأقمشة حسب الفروع</h2>
          <p className="mt-1 text-xs text-neutral-500">اسم القماش وكوده وأسعار البيع الدنيا في كل فرع</p>
        </div>
        <SearchInput value={search} onChange={setSearch} placeholder="ابحث باسم القماش أو الكود..." />
      </div>
      {loading ? (
        <div className="flex justify-center py-12"><Spinner size={30} /></div>
      ) : visibleFabrics.length === 0 ? (
        <div className="p-4"><EmptyState title="لا توجد أقمشة مطابقة" /></div>
      ) : branches.length === 0 ? (
        <div className="p-4"><EmptyState title="لا توجد فروع متاحة لعرض الأسعار" /></div>
      ) : (
        <Table>
          <thead>
            <tr>
              <th rowSpan={2} className="sticky right-0 z-20 min-w-48 border-b border-sand-200 bg-sand-100 px-4 py-3 text-right text-xs font-semibold text-neutral-600">القماش / الكود</th>
              {branches.map((branch) => (
                <th key={branch.id} colSpan={5} className="border-b border-sand-200 bg-sand-100 px-4 py-3 text-center text-xs font-semibold text-neutral-600">{branch.name}</th>
              ))}
            </tr>
            <tr>
              {branches.map((branch) => (
                <FragmentBranchHead key={branch.id} branchId={branch.id} />
              ))}
            </tr>
          </thead>
          <tbody>
            {visibleFabrics.map((fabric) => (
              <Tr key={fabric.id}>
                <Td className="sticky right-0 z-10 min-w-48 bg-surface font-medium">
                  <span className="block text-neutral-800">{fabric.name}</span>
                  <span className="mt-0.5 block font-mono text-xs text-neutral-400" dir="ltr">{fabric.code}</span>
                </Td>
                {branches.map((branch) => {
                  const branchPrice = priceMap.get(`${fabric.id}:${branch.id}`);
                  const yardPrice = Number(branchPrice?.sale_price_yard)
                    || (Number(branchPrice?.piece_price) > 0 ? Number(branchPrice?.piece_price) / 3.5 : 0)
                    || Number(fabric.sale_price_yard)
                    || 0;
                  const piecePrice = branchPrice?.piece_price != null
                    ? Number(branchPrice.piece_price)
                    : fabric.piece_price != null
                      ? Number(fabric.piece_price)
                      : yardPrice * 3.5;
                  const minYard = Number(branchPrice?.min_sale_yard)
                    || Number(fabric.min_sale_yard)
                    || yardPrice * minSalePercent;
                  const minPiece = Math.max(
                    minYard * 3.5,
                    Number(fabric.purchase_price || 0) * 3.5 * minPieceMultiplier,
                  );
                  const rollAllowed = rollSaleAllowed(fabric, branch.id);
                  const rollPrice = branchPrice?.sale_price_roll != null
                    ? Number(branchPrice.sale_price_roll)
                    : fabric.sale_price_roll != null
                      ? Number(fabric.sale_price_roll)
                      : yardPrice * 25;
                  const minRoll = branchPrice?.min_sale_roll != null
                    ? Number(branchPrice.min_sale_roll)
                    : fabric.min_sale_roll != null
                      ? Number(fabric.min_sale_roll)
                      : yardPrice * 21;
                  return (
                    <FragmentPriceCells
                      key={`${fabric.id}:${branch.id}`}
                      piecePrice={piecePrice}
                      minPiece={minPiece}
                      rollAllowed={rollAllowed}
                      rollPrice={rollPrice}
                      minRoll={minRoll}
                      money={money}
                    />
                  );
                })}
              </Tr>
            ))}
          </tbody>
        </Table>
      )}
    </Card>
  );
}

function FragmentBranchHead({ branchId }: { branchId: number }) {
  return (
    <>
      <Th key={`${branchId}-piece`} className="whitespace-nowrap">سعر القطعة</Th>
      <Th key={`${branchId}-min-piece`} className="whitespace-nowrap">أدنى قطعة</Th>
      <Th key={`${branchId}-roll`} className="whitespace-nowrap">سعر الطاقة</Th>
      <Th key={`${branchId}-min-roll`} className="whitespace-nowrap">أدنى طاقة</Th>
      <Th key={`${branchId}-allowed`} className="whitespace-nowrap">بيع الطاقة</Th>
    </>
  );
}

function FragmentPriceCells({
  piecePrice,
  minPiece,
  rollAllowed,
  rollPrice,
  minRoll,
  money: formatMoney,
}: {
  piecePrice: number;
  minPiece: number;
  rollAllowed: boolean;
  rollPrice: number;
  minRoll: number;
  money: (value: number | null | undefined) => string;
}) {
  return (
    <>
      <Td className="whitespace-nowrap tabular-nums">{formatMoney(piecePrice)}</Td>
      <Td className="whitespace-nowrap tabular-nums text-amber-700">{formatMoney(minPiece)}</Td>
      <Td className="whitespace-nowrap tabular-nums">{rollAllowed ? formatMoney(rollPrice) : '—'}</Td>
      <Td className="whitespace-nowrap tabular-nums text-amber-700">{rollAllowed ? formatMoney(minRoll) : '—'}</Td>
      <Td className="whitespace-nowrap text-xs font-medium">
        <span className={rollAllowed ? 'text-emerald-700' : 'text-neutral-400'}>{rollAllowed ? 'مسموح' : 'غير مسموح'}</span>
      </Td>
    </>
  );
}
