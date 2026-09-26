'use client';

import { useCallback, useEffect, useState } from 'react';
import Button from '@/components/ui/Button';
import Table, { Th, Td, Tr } from '@/components/ui/Table';
import Select from '@/components/ui/Select';
import Spinner from '@/components/ui/Spinner';
import EmptyState from '@/components/ui/EmptyState';
import { useToast } from '@/components/ui/Toast';
import DateRangeToolbar, { currentMonthRange } from '@/components/ui/DateRangeToolbar';
import { PayrollStatement } from '@/types';
import { exportStatement, getEmployeeStatement } from '@/services/payroll';
import { formatCurrency, formatDate } from '@/lib/format';
import type { StructureEmployeeOption } from './SalaryStructureForm';

interface StatementModalProps {
  employees: StructureEmployeeOption[];
  initialEmployeeId?: number | null;
  open: boolean;
  onClose: () => void;
}

export default function StatementModal({
  employees,
  initialEmployeeId,
  open,
  onClose,
}: StatementModalProps) {
  const { toast } = useToast();
  const [employee, setEmployee] = useState<string>(
    initialEmployeeId ? String(initialEmployeeId) : '',
  );
  const [range, setRange] = useState(currentMonthRange());
  const [data, setData] = useState<PayrollStatement | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (initialEmployeeId) setEmployee(String(initialEmployeeId));
  }, [initialEmployeeId, open]);

  const load = useCallback(() => {
    if (!employee) {
      setData(null);
      return;
    }
    setLoading(true);
    getEmployeeStatement(Number(employee), { date_from: range.from, date_to: range.to })
      .then(setData)
      .catch((err) => toast('error', err.message))
      .finally(() => setLoading(false));
  }, [employee, range.from, range.to, toast]);

  useEffect(() => {
    if (open) load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  const handleExport = async () => {
    if (!data) return;
    try {
      await exportStatement(data.employee, `كشف_${data.employee_name}.xlsx`);
      toast('success', 'تم تنزيل الكشف');
    } catch (err: any) {
      toast('error', err.message);
    }
  };

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 items-end">
        <Select
          label="الموظف"
          value={employee}
          onChange={(e) => setEmployee(e.target.value)}
          options={employees.map((emp) => ({
            value: emp.id,
            label: emp.branch_name ? `${emp.name} — ${emp.branch_name}` : emp.name,
          }))}
          placeholder="اختر الموظف"
        />
        <DateRangeToolbar from={range.from} to={range.to} onChange={(f, t) => setRange({ from: f, to: t })} />
      </div>

      {loading ? (
        <div className="flex justify-center py-10">
          <Spinner size={28} />
        </div>
      ) : !data ? (
        <EmptyState title="اختر موظفاً" description="سيظهر كشف حسابه هنا" />
      ) : data.rows.length === 0 ? (
        <EmptyState title="لا توجد حركات" description="لا توجد رواتب أو سلف في هذه الفترة" />
      ) : (
        <>
          <Table>
            <thead>
              <tr>
                <Th>التاريخ</Th>
                <Th>النوع</Th>
                <Th>المرجع</Th>
                <Th>مدين</Th>
                <Th>دائن</Th>
                <Th>الرصيد</Th>
              </tr>
            </thead>
            <tbody>
              {data.rows.map((r, i) => (
                <Tr key={`${r.type}-${i}`}>
                  <Td>{formatDate(r.date)}</Td>
                  <Td className="font-medium">{r.type_label}</Td>
                  <Td className="text-neutral-500">{r.ref}</Td>
                  <Td className="tabular-nums">{formatCurrency(r.debit)}</Td>
                  <Td className="tabular-nums">{formatCurrency(r.credit)}</Td>
                  <Td
                    className={`tabular-nums font-medium ${
                      r.net < 0 ? 'text-red-600' : 'text-emerald-700'
                    }`}
                  >
                    {formatCurrency(r.net)}
                  </Td>
                </Tr>
              ))}
            </tbody>
          </Table>

          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-sm">
            <div className="rounded-xl bg-sand-100 px-3 py-2">
              <span className="block text-xs text-neutral-500">صافي المصروف</span>
              <span className="tabular-nums font-semibold">{formatCurrency(data.totals.net_paid)}</span>
            </div>
            <div className="rounded-xl bg-sand-100 px-3 py-2">
              <span className="block text-xs text-neutral-500">السلف الممنوحة</span>
              <span className="tabular-nums font-semibold">{formatCurrency(data.totals.advances)}</span>
            </div>
            <div className="rounded-xl bg-sand-100 px-3 py-2">
              <span className="block text-xs text-neutral-500">المسدد</span>
              <span className="tabular-nums font-semibold">{formatCurrency(data.totals.recovered)}</span>
            </div>
            <div className="rounded-xl bg-red-50 dark:bg-red-500/10 px-3 py-2">
              <span className="block text-xs text-red-600">المتبقي عليه</span>
              <span className="tabular-nums font-semibold text-red-700 dark:text-red-300">
                {formatCurrency(data.totals.outstanding)}
              </span>
            </div>
          </div>

          <div className="flex gap-3">
            <Button type="button" onClick={load} variant="secondary">
              تحديث
            </Button>
            <Button type="button" onClick={handleExport}>
              تنزيل Excel
            </Button>
            <Button type="button" onClick={onClose} variant="ghost">
              إغلاق
            </Button>
          </div>
        </>
      )}
    </div>
  );
}
