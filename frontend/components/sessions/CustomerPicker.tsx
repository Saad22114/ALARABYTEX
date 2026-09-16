'use client';

import { useEffect, useRef, useState } from 'react';
import Input from '@/components/ui/Input';
import { Check, Loader2, Phone, Search, User } from 'lucide-react';
import { Customer } from '@/types';
import { lookupCustomer, listCustomers } from '@/services/customers';
import { searchContacts, CustomerContact, normalizePhone } from '@/lib/customerContacts';

type Props = {
  name: string;
  onChangeName: (v: string) => void;
  phone: string;
  onChangePhone: (v: string) => void;
  compact?: boolean;
  onFound?: (c: Customer | null) => void;
};

export default function CustomerPicker({ name, onChangeName, phone, onChangePhone, compact = false, onFound }: Props) {
  const [openList, setOpenList] = useState(false);
  const [found, setFound] = useState<Customer | null>(null);
  const [searching, setSearching] = useState(false);
  const [suggestions, setSuggestions] = useState<(Customer | CustomerContact)[]>([]);
  const blurTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const autoFillRef = useRef(false);
  const markedDirty = useRef(false);
  const callbackRef = useRef<Props['onFound']>(undefined);
  const changeNameRef = useRef(onChangeName);
  callbackRef.current = onFound;
  changeNameRef.current = onChangeName;

  useEffect(() => {
    markedDirty.current = false;
    let cancelled = false;
    const p = phone.trim();
    if (!p) {
      setFound(null);
      setSuggestions([]);
      setSearching(false);
      callbackRef.current?.(null);
      return;
    }
    setSearching(true);
    const t = setTimeout(async () => {
      try {
        const res = await lookupCustomer(p);
        if (cancelled) return;
        const customer = res.customer;
        setFound(customer);
        callbackRef.current?.(customer || null);
        if (customer) {
          if (!markedDirty.current) {
            autoFillRef.current = true;
            changeNameRef.current(customer.name);
            autoFillRef.current = false;
          }
          setSuggestions([]);
        } else {
          setSuggestions(searchContacts(p));
          try {
            const s = await listCustomers({ search: p, page_size: 8 });
            if (cancelled) return;
            if (s.results.length > 0) setSuggestions(s.results);
          } catch {
            /* تجاهل فشل البحث — تبقى الاقتراحات المحلية */
          }
        }
      } catch {
        if (!cancelled) setSuggestions(searchContacts(p));
      } finally {
        if (!cancelled) setSearching(false);
      }
    }, 350);
    return () => { cancelled = true; clearTimeout(t); };
  }, [phone]);

  const checkDigits = normalizePhone(phone || '').length;

  const pick = (c: { phone: string | null; name: string }) => {
    onChangePhone(c.phone || '');
    autoFillRef.current = true;
    onChangeName(c.name);
    autoFillRef.current = false;
    setOpenList(false);
  };

  const handleNameChange = (v: string) => {
    if (!autoFillRef.current) markedDirty.current = true;
    onChangeName(v);
  };

  const delayClose = () => {
    if (blurTimer.current) clearTimeout(blurTimer.current);
    blurTimer.current = setTimeout(() => setOpenList(false), 150);
  };

  return (
    <div className="rounded-xl border border-sand-200 bg-sand-50 p-3">
      <div className="mb-2 flex items-center justify-between gap-2">
        <span className="flex items-center gap-1.5 text-sm font-medium text-neutral-700">
          <Phone size={15} className="text-brand-600" />
          Customer (optional)
        </span>
        {searching ? (
          <span className="flex items-center gap-1 text-xs text-neutral-400">
            <Loader2 size={12} className="animate-spin" />
            Searching...
          </span>
        ) : found ? (
          <span className="flex items-center gap-1 text-xs text-emerald-600">
            <Check size={12} />
            Found: {found.name}
          </span>
        ) : checkDigits >= 7 ? (
          <span className="flex items-center gap-1 text-xs text-neutral-400">
            <Search size={12} />
            New customer — will be saved
          </span>
        ) : null}
      </div>
      <div className={compact ? 'grid gap-2 sm:grid-cols-2' : 'grid gap-3 sm:grid-cols-2'}>
        <div className="relative" onBlur={delayClose}>
          <div className="relative">
            <Phone size={15} className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-neutral-400" />
            <Input
              value={phone}
              onChange={(e) => {
                onChangePhone(e.target.value);
                setOpenList(true);
              }}
              onFocus={() => setOpenList(true)}
              placeholder="Phone number"
              inputMode="tel"
              className="pr-9"
            />
          </div>
          {openList && !found && suggestions.length > 0 && (
            <ul className="absolute z-20 mt-1 w-full overflow-hidden rounded-xl border border-sand-200 bg-surface shadow-lg">
              {suggestions.map((c) => (
                <li key={(c as Customer).id ?? `l-${c.phone}`}>
                  <button
                    onMouseDown={(e) => {
                      e.preventDefault();
                      pick(c);
                    }}
                    className="flex w-full items-center justify-between gap-2 px-3 py-2 text-sm text-neutral-700 hover:bg-sand-100"
                  >
                    <span className="flex items-center gap-2">
                      <User size={13} className="text-neutral-400" />
                      {c.name || '—'}
                    </span>
                    <span className="tabular-nums text-xs text-neutral-500" dir="ltr">{c.phone}</span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
        <div className="relative">
          <Input
            value={name}
            onChange={(e) => handleNameChange(e.target.value)}
            placeholder="Customer name"
          />
        </div>
      </div>
    </div>
  );
}