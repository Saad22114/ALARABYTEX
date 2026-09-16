'use client';

import { useEffect, useMemo, useState } from 'react';
import { Printer } from 'lucide-react';
import { AppSettings, SaleSession } from '@/types';
import Modal from '@/components/ui/Modal';
import Button from '@/components/ui/Button';
import Table, { Th, Tr, Td } from '@/components/ui/Table';
import CustomerPicker from '@/components/sessions/CustomerPicker';
import { formatCurrency, formatNumber } from '@/lib/format';
import { buildSessionItemsInvoice, openHtmlInvoice, englishWords } from '@/lib/invoice';
import { saveContact } from '@/lib/customerContacts';
import { ensureCustomer } from '@/lib/registerCustomer';

type Props = {
  open: boolean;
  onClose: () => void;
  session: SaleSession | null;
  itemIds: number[];
  settings: AppSettings | null;
};

const r2 = (v: number) => Math.round(v * 100) / 100;

export default function SessionCustomerInvoiceModal({ open, onClose, session, itemIds, settings }: Props) {
  const [customerName, setCustomerName] = useState('');
  const [customerPhone, setCustomerPhone] = useState('');
  const [counter, setCounter] = useState(0);

  useEffect(() => {
    if (open) {
      setCounter((c) => c + 1);
      setCustomerName('');
      setCustomerPhone('');
    }
  }, [open]);

  const invoiceNo = `${settings?.invoice_prefix || ''}${session?.id ?? 0}-${counter}`;

  const items = useMemo(() => (session ? session.items.filter((i) => itemIds.includes(i.id)) : []), [session, itemIds]);

  const total = r2(items.reduce((s, i) => s + Number(i.total), 0));
  const yards = r2(items.reduce((s, i) => s + Number(i.yards_effective ?? i.quantity), 0));

  const taxRate = Number(settings?.tax_rate ?? 0);
  const showTax = !!settings?.receipt_show_tax;
  const taxAmount = showTax && taxRate > 0 ? r2(total * (taxRate / 100)) : 0;
  const grandTotal = r2(total + taxAmount);

  const handlePrint = () => {
    if (!session || items.length === 0) return;
    const phone = customerPhone.trim();
    saveContact(phone, customerName);
    void ensureCustomer(customerName, phone);
    const html = buildSessionItemsInvoice(items, session, settings, {
      title: 'INVOICE',
      invoiceNo,
      customerName,
      customerPhone: phone,
      autoPrint: true,
    });
    openHtmlInvoice(html);
  };

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Customer Invoice"
      maxWidth="max-w-4xl"
      footer={
        <>
          <Button onClick={handlePrint} disabled={items.length === 0}>
            <Printer size={18} />
            Print Invoice
          </Button>
          <Button variant="ghost" onClick={onClose}>
            Close
          </Button>
        </>
      }
    >
      <div className="space-y-4">
        <div className="rounded-xl border border-sand-200 bg-sand-50 p-4">
          <CustomerPicker
            name={customerName}
            onChangeName={setCustomerName}
            phone={customerPhone}
            onChangePhone={setCustomerPhone}
          />
          <div className="mt-3 flex flex-wrap items-center justify-between gap-3 text-sm text-neutral-600">
            <p>
              Invoice No.: <b className="text-neutral-900">{invoiceNo}</b>
            </p>
            <p>
              Date: <b className="text-neutral-900">{new Date().toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' })}</b>
            </p>
            {session && (
              <p>
                Employee: <b className="text-neutral-900">{session.employee_name}</b> · Branch:{' '}
                <b className="text-neutral-900">{session.branch_name}</b>
              </p>
            )}
          </div>
        </div>

        {items.length === 0 ? (
          <p className="py-8 text-center text-sm text-neutral-400">No items selected</p>
        ) : (
          <>
            <div className="overflow-x-auto rounded-xl border border-sand-200">
              <Table>
                <thead>
                  <tr>
                    <Th>#</Th>
                    <Th>Fabric</Th>
                    <Th>Type</Th>
                    <Th>Quantity</Th>
                    <Th>Unit Price</Th>
                    <Th>Discount</Th>
                    <Th>Amount</Th>
                  </tr>
                </thead>
                <tbody>
                  {items.map((it, idx) => (
                    <Tr key={it.id}>
                      <Td className="tabular-nums text-neutral-500">{idx + 1}</Td>
                      <Td className="font-medium">{it.fabric_name}</Td>
                      <Td>{it.sale_type === 'roll' ? 'Roll' : 'Yard'}</Td>
                      <Td className="tabular-nums">
                        {it.quantity} {it.sale_type === 'roll' ? 'roll(s)' : 'yard(s)'}
                        <span className="mr-2 text-xs text-neutral-400">({formatNumber(it.yards_effective ?? it.quantity)} yd)</span>
                      </Td>
                      <Td className="tabular-nums">{formatCurrency(it.unit_price)}</Td>
                      <Td className={`tabular-nums ${it.discount_amount > 0 ? 'text-red-500' : 'text-neutral-400'}`}>
                        {it.discount_amount > 0 ? formatCurrency(it.discount_amount) : '—'}
                      </Td>
                      <Td className="tabular-nums font-semibold">{formatCurrency(it.total)}</Td>
                    </Tr>
                  ))}
                </tbody>
              </Table>
            </div>

            <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-sand-200 bg-sand-50 px-4 py-3">
              <span className="text-sm text-neutral-600">
                Total Yards: <b className="tabular-nums text-neutral-900">{formatNumber(yards)}</b>
              </span>
              <div className="text-left">
                <p className="text-xs text-neutral-500">
                  Subtotal: {formatCurrency(total)}
                </p>
                {showTax && (
                  <p className="text-xs text-neutral-500">
                    VAT ({taxRate}%): {formatCurrency(taxAmount)}
                  </p>
                )}
                <p className="text-lg font-bold tabular-nums">
                  Grand Total{showTax ? ' (incl. VAT)' : ''}: {formatCurrency(grandTotal)}
                </p>
                <p className="text-xs text-neutral-500">
                  {englishWords(grandTotal)} {settings?.currency_code || ''}
                </p>
              </div>
            </div>
          </>
        )}
      </div>
    </Modal>
  );
}