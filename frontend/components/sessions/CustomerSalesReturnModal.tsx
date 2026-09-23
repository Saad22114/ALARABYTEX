'use client';

import { useEffect, useState } from 'react';
import Modal from '@/components/ui/Modal';
import Button from '@/components/ui/Button';
import Input from '@/components/ui/Input';
import Badge from '@/components/ui/Badge';
import Spinner from '@/components/ui/Spinner';
import { Search, Check, Undo2, Phone } from 'lucide-react';
import { CustomerSalesResult } from '@/types';
import { getCustomerSales, returnSessionItems } from '@/services/sessions';
import { useToast } from '@/components/ui/Toast';
import { formatCurrency, formatDate, formatNumber } from '@/lib/format';

interface Props {
  open: boolean;
  onClose: () => void;
  onChanged?: () => void;
}

export default function CustomerSalesReturnModal({ open, onClose, onChanged }: Props) {
  const { toast } = useToast();
  const [phone, setPhone] = useState('');
  const [result, setResult] = useState<CustomerSalesResult | null>(null);
  const [searching, setSearching] = useState(false);
  const [searched, setSearched] = useState(false);
  const [selected, setSelected] = useState<number[]>([]);
  const [reason, setReason] = useState('');
  const [returning, setReturning] = useState(false);

  useEffect(() => {
    if (open) {
      setResult(null);
      setSelected([]);
      setReason('');
      setSearched(false);
    }
  }, [open]);

  const handleSearch = async () => {
    const p = phone.trim();
    if (!p) {
      toast('error', 'أدخل رقم الهاتف أولاً');
      return;
    }
    setSearching(true);
    setResult(null);
    setSelected([]);
    setSearched(true);
    try {
      const res = await getCustomerSales(p);
      setResult(res);
      if (res.items.length === 0) toast('info', 'لا توجد بيعات لهذا الرقم');
    } catch (err: any) {
      toast('error', err.message);
    } finally {
      setSearching(false);
    }
  };

  const toggle = (id: number, returned: boolean) => {
    if (returned) return;
    setSelected((cur) =>
      cur.includes(id) ? cur.filter((x) => x !== id) : [...cur, id]
    );
  };

  const handleReturn = async () => {
    if (selected.length === 0) {
      toast('error', 'اختر بنداً واحداً على الأقل للاسترجاع');
      return;
    }
    setReturning(true);
    try {
      await returnSessionItems(selected, reason.trim());
      toast('success', `تم استرجاع ${selected.length} بند وترجيع الكمية للمخزون`);
      setResult((cur) => {
        if (!cur) return cur;
        return {
          ...cur,
          items: cur.items.map((it) =>
            selected.includes(it.id)
              ? { ...it, is_returned: true, return_reason: reason.trim() }
              : it
          ),
        };
      });
      setSelected([]);
      onChanged?.();
    } catch (err: any) {
      toast('error', err.message);
    } finally {
      setReturning(false);
    }
  };

  const returnable = (result?.items ?? []).filter((it) => !it.is_returned);

  return (
    <Modal open={open} onClose={onClose} title="بحث زبون واسترجاع بيع" maxWidth="max-w-3xl">
      <div className="space-y-4">
        <div className="flex gap-2">
          <div className="flex-1 min-w-0">
            <div className="relative">
              <Phone size={15} className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-neutral-400" />
              <Input
                value={phone}
                onChange={(e) => setPhone(e.target.value)}
                onKeyDown={(e) => { if (e.key === 'Enter') handleSearch(); }}
                placeholder="رقم هاتف الزبون"
                inputMode="tel"
                className="pr-9"
              />
            </div>
          </div>
          <Button onClick={handleSearch} loading={searching}>
            <Search size={16} />
            بحث
          </Button>
        </div>

        {searching && (
          <div className="flex justify-center py-8">
            <Spinner />
          </div>
        )}

        {!searching && searched && result && result.items.length === 0 && (
          <div className="rounded-xl bg-sand-50 border border-sand-200 px-4 py-8 text-center text-sm text-neutral-500">
            لا توجد بيعات مسجلة برقم «{result.phone}» في فروعك.
          </div>
        )}

        {!searching && result && result.items.length > 0 && (
          <>
            <div className="flex flex-wrap items-center justify-between gap-2">
              <p className="text-sm text-neutral-600">
                عدد البيعات: <b className="text-neutral-800">{formatNumber(result.totals.count)}</b>
                {' '}· مسترجعة: <b className="text-amber-600">{formatNumber(result.totals.returned_count)}</b>
                {' '}· الإجمالي الصافي: <b className="text-brand-700">{formatCurrency(result.totals.total)}</b>
              </p>
              <Badge variant="neutral">النطاق يضم الورديات المفتوحة والمغلقة</Badge>
            </div>

            <div className="max-h-80 overflow-auto rounded-xl border border-sand-200 divide-y divide-sand-200">
              {result.items.map((it) => (
                <label
                  key={it.id}
                  className={`flex items-start gap-3 px-3 py-2.5 cursor-pointer transition-colors hover:bg-sand-50 ${it.is_returned ? 'opacity-60' : ''}`}
                >
                  <input
                    type="checkbox"
                    disabled={it.is_returned}
                    checked={selected.includes(it.id)}
                    onChange={() => toggle(it.id, it.is_returned)}
                    className="mt-1 w-4 h-4 accent-brand-600"
                  />
                  <div className="flex-1 min-w-0">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="text-sm font-medium text-neutral-800">{it.fabric_name}</span>
                      {it.is_returned ? (
                        <Badge variant="danger">مسترجع</Badge>
                      ) : (
                        <Badge variant={it.session_closed ? 'success' : 'warning'}>
                          {it.session_closed ? 'وردية مغلقة' : 'وردية مفتوحة'}
                        </Badge>
                      )}
                      <Badge variant="neutral">{it.sale_type === 'roll' ? 'طاقة' : 'ياردة'}</Badge>
                    </div>
                    <p className="mt-0.5 text-xs text-neutral-500">
                      {formatNumber(it.quantity)} {it.sale_type === 'roll' ? 'طاقة' : 'يارد'} · {formatNumber(it.yards_effective)} ياردة · {formatDate(it.sale_date)} · {it.payment_method_label}
                    </p>
                    {(it.is_returned && it.return_reason) || (it.is_returned && it.returned_at) ? (
                      <p className="mt-0.5 text-xs text-amber-600">
                        مسترجعة {it.returned_at ? formatDate(it.returned_at) : ''}{it.return_reason ? ` — ${it.return_reason}` : ''}
                      </p>
                    ) : null}
                  </div>
                  <span className="text-sm font-bold tabular-nums text-brand-700">{formatCurrency(Number(it.total))}</span>
                </label>
              ))}
            </div>

            {returnable.length > 0 && (
              <>
                <Input
                  label="سبب الاسترجاع (اختياري)"
                  value={reason}
                  onChange={(e) => setReason(e.target.value)}
                  placeholder="مثال: مقاس خاطئ / استبدال"
                />
                <div className="flex items-center justify-between gap-3">
                  <p className="text-xs text-neutral-500">
                    تم اختيار <b className="text-neutral-700">{selected.length}</b> بند — استرجاع وردية مغلقة يعيد الكمية للمخزون والسجل اليومي، وسيبقى البند مسجلاً بوسم «مسترجع».
                  </p>
                  <Button onClick={handleReturn} loading={returning} disabled={selected.length === 0}>
                    <Undo2 size={16} />
                    استرجاع المحدد ({selected.length})
                  </Button>
                </div>
              </>
            )}
          </>
        )}
      </div>
    </Modal>
  );
}