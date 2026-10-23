'use client';

import { ReactNode, useEffect, useMemo, useState } from 'react';
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
import { Building2, Info, Package, Search, X } from 'lucide-react';

const PAGE_SIZE = 200;
const BRANCH_STYLES = [
  { header: 'bg-sky-100 text-sky-900', cell: 'bg-sky-50/60', divider: 'border-l-2 border-l-sky-300' },
  { header: 'bg-emerald-100 text-emerald-900', cell: 'bg-emerald-50/60', divider: 'border-l-2 border-l-emerald-300' },
  { header: 'bg-violet-100 text-violet-900', cell: 'bg-violet-50/60', divider: 'border-l-2 border-l-violet-300' },
  { header: 'bg-amber-100 text-amber-900', cell: 'bg-amber-50/60', divider: 'border-l-2 border-l-amber-300' },
  { header: 'bg-rose-100 text-rose-900', cell: 'bg-rose-50/60', divider: 'border-l-2 border-l-rose-300' },
  { header: 'bg-teal-100 text-teal-900', cell: 'bg-teal-50/60', divider: 'border-l-2 border-l-teal-300' },
];

function branchStyle(index: number) {
  return BRANCH_STYLES[index % BRANCH_STYLES.length];
}

function SummaryBadge({ icon, label, value }: { icon: ReactNode; label: string; value: number }) {
  return (
    <span className="inline-flex items-center gap-1.5 rounded-lg border border-sand-200 bg-surface/90 px-2.5 py-1.5 text-neutral-600">
      <span className="text-brand-600">{icon}</span>
      <span>{label}</span>
      <span className="font-bold tabular-nums text-neutral-800">{value}</span>
    </span>
  );
}

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
    <Card className="!p-0 overflow-hidden">
      <div className="border-b border-sand-200 bg-gradient-to-l from-brand-50/80 via-surface to-surface p-4 sm:p-5">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="flex items-start gap-3">
            <div className="rounded-xl bg-brand-100 p-2.5 text-brand-700"><Package size={22} /></div>
            <div>
              <h2 className="text-lg font-bold text-neutral-900">دليل أسعار الأقمشة</h2>
              <p className="mt-1 text-sm text-neutral-500">قارن أسعار البيع والحدود الدنيا حسب الفرع بسرعة.</p>
            </div>
          </div>
          <div className="flex flex-wrap gap-2 text-xs">
            <SummaryBadge icon={<Package size={14} />} label="الأقمشة" value={fabrics.length} />
            <SummaryBadge icon={<Building2 size={14} />} label="الفروع" value={branches.length} />
            <SummaryBadge icon={<Search size={14} />} label="نتائج البحث" value={visibleFabrics.length} />
          </div>
        </div>
        <div className="mt-4 flex flex-wrap items-center gap-3">
          <div className="min-w-[260px] flex-1">
            <SearchInput value={search} onChange={setSearch} placeholder="اكتب اسم القماش أو الكود للبحث..." />
          </div>
          {search && (
            <button type="button" onClick={() => setSearch('')} className="inline-flex items-center gap-1.5 rounded-lg border border-sand-300 bg-surface px-3 py-2 text-sm text-neutral-600 transition hover:bg-sand-50">
              <X size={15} /> مسح البحث
            </button>
          )}
          <span className="inline-flex items-center gap-1.5 text-xs text-neutral-500">
            <Info size={14} /> الحد الأدنى هو أقل سعر مسموح للبيع
          </span>
        </div>
      </div>
      {loading ? (
        <div className="flex justify-center py-12"><Spinner size={30} /></div>
      ) : visibleFabrics.length === 0 ? (
        <div className="p-4"><EmptyState title="لا توجد أقمشة مطابقة" /></div>
      ) : branches.length === 0 ? (
        <div className="p-4"><EmptyState title="لا توجد فروع متاحة لعرض الأسعار" /></div>
      ) : (
        <Table className="[&_table]:min-w-max">
          <thead>
            <tr>
              <th rowSpan={2} className="sticky right-0 z-20 min-w-52 border-b border-sand-200 bg-sand-100 px-4 py-3 text-right text-xs font-bold text-neutral-700">القماش / الكود</th>
              {branches.map((branch, index) => {
                const style = branchStyle(index);
                return (
                <th key={branch.id} colSpan={5} className={`border-b border-sand-200 px-4 py-3 text-center text-sm font-bold ${style.header} ${style.divider}`}>
                  <span className="inline-flex items-center justify-center gap-1.5"><Building2 size={14} />{branch.name}</span>
                </th>
                );
              })}
            </tr>
            <tr>
              {branches.map((branch, index) => (
                <FragmentBranchHead key={branch.id} branchId={branch.id} style={branchStyle(index)} />
              ))}
            </tr>
          </thead>
          <tbody>
            {visibleFabrics.map((fabric) => (
              <Tr key={fabric.id}>
                <Td className="sticky right-0 z-10 min-w-48 bg-surface font-medium">
                  <span className="block font-semibold text-neutral-800">{fabric.name}</span>
                  <span className="mt-1 inline-block rounded bg-sand-100 px-1.5 py-0.5 font-mono text-[11px] text-neutral-500" dir="ltr">{fabric.code}</span>
                </Td>
                {branches.map((branch, branchIndex) => {
                  const style = branchStyle(branchIndex);
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
                      style={style}
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

function FragmentBranchHead({ branchId, style }: { branchId: number; style: (typeof BRANCH_STYLES)[number] }) {
  return (
    <>
      <Th key={`${branchId}-piece`} className={`whitespace-nowrap ${style.header}`}>سعر القطعة</Th>
      <Th key={`${branchId}-min-piece`} className={`whitespace-nowrap ${style.header}`}>أدنى قطعة</Th>
      <Th key={`${branchId}-roll`} className={`whitespace-nowrap ${style.header}`}>سعر الطاقة</Th>
      <Th key={`${branchId}-min-roll`} className={`whitespace-nowrap ${style.header}`}>أدنى طاقة</Th>
      <Th key={`${branchId}-allowed`} className={`whitespace-nowrap ${style.header} ${style.divider}`}>بيع الطاقة</Th>
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
  style,
}: {
  piecePrice: number;
  minPiece: number;
  rollAllowed: boolean;
  rollPrice: number;
  minRoll: number;
  money: (value: number | null | undefined) => string;
  style: (typeof BRANCH_STYLES)[number];
}) {
  return (
    <>
      <Td className={`whitespace-nowrap tabular-nums font-semibold text-neutral-800 ${style.cell}`}>{formatMoney(piecePrice)}</Td>
      <Td className={`whitespace-nowrap tabular-nums font-medium text-amber-800 ${style.cell}`}>{formatMoney(minPiece)}</Td>
      <Td className={`whitespace-nowrap tabular-nums font-semibold text-neutral-800 ${style.cell}`}>{rollAllowed ? formatMoney(rollPrice) : '—'}</Td>
      <Td className={`whitespace-nowrap tabular-nums font-medium text-amber-800 ${style.cell}`}>{rollAllowed ? formatMoney(minRoll) : '—'}</Td>
      <Td className={`whitespace-nowrap text-xs font-medium ${style.cell} ${style.divider}`}>
        <span className={`inline-flex rounded-full px-2 py-1 ${rollAllowed ? 'bg-emerald-100 text-emerald-800' : 'bg-neutral-100 text-neutral-500'}`}>{rollAllowed ? 'مسموح' : 'غير مسموح'}</span>
      </Td>
    </>
  );
}
