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

  // يدعم استجابة الخادم الأقدم أثناء إعادة تشغيله بعد التحديث، ويضمن أن
  // غياب قائمة الأقساط أو السلف لا يعطل نافذة كشف الحساب.
  const normalizeStatement = (raw: Partial<PayrollStatement>): PayrollStatement => {
    const rows = Array.isArray(raw.rows) ? raw.rows : [];
    const totals = (raw.totals || {}) as Partial<PayrollStatement['totals']> & { outstanding?: number };
    const salaryRows = rows.filter((row) => row.type === 'payslip');
    const advances = Array.isArray(raw.advances) ? raw.advances : [];
    const installments = Array.isArray(raw.installments) ? raw.installments : [];
    const gross = salaryRows.reduce((sum, row) => sum + (row.gross_salary ?? row.debit ?? 0), 0);
    const net = salaryRows.reduce((sum, row) => sum + (row.salary_net ?? row.credit ?? 0), 0);
    const deductionTotal = salaryRows.reduce(
      (sum, row) => sum + (row.total_deductions ?? Math.max(0, (row.debit ?? 0) - (row.credit ?? 0))), 0,
    );
    return {
      employee: raw.employee ?? 0,
      employee_name: raw.employee_name ?? '',
      date_from: raw.date_from ?? range.from,
      date_to: raw.date_to ?? range.to,
      rows: rows.map((row) => ({
        ...row,
        gross_salary: row.gross_salary ?? row.debit ?? 0,
        total_deductions: row.total_deductions ?? 0,
        salary_net: row.salary_net ?? row.credit ?? 0,
        paid_amount: row.paid_amount ?? row.credit ?? 0,
        salary_remaining: row.salary_remaining ?? (row.type === 'payslip' ? 0 : row.net ?? 0),
        advance_deduction: row.advance_deduction ?? 0,
        installment_deduction: row.installment_deduction ?? 0,
        other_deductions: row.other_deductions ?? 0,
      })),
      advances,
      installments,
      totals: {
        gross_salary: totals.gross_salary ?? gross,
        total_deductions: totals.total_deductions ?? deductionTotal,
        salary_net: totals.salary_net ?? net,
        net_paid: totals.net_paid ?? net,
        salary_remaining: totals.salary_remaining ?? 0,
        advance_deduction: totals.advance_deduction ?? 0,
        installment_deduction: totals.installment_deduction ?? 0,
        other_deductions: totals.other_deductions ?? 0,
        advances: totals.advances ?? 0,
        recovered: totals.recovered ?? 0,
        outstanding_advances: totals.outstanding_advances ?? totals.outstanding ?? 0,
        outstanding_installments: totals.outstanding_installments ?? 0,
      },
    };
  };

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
      .then((response) => setData(normalizeStatement(response)))
      .catch((err) => toast('error', err.message))
      .finally(() => setLoading(false));
  }, [employee, range.from, range.to, toast]);

  useEffect(() => {
    if (open) load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, load]);

  const handleExport = async () => {
    if (!data) return;
    try {
      await exportStatement(data.employee, `كشف_${data.employee_name}.xlsx`, { date_from: range.from, date_to: range.to });
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
      ) : (
        <>
          <div className="grid grid-cols-2 sm:grid-cols-3 xl:grid-cols-4 gap-3 text-sm">
            <div className="rounded-xl bg-sand-100 px-3 py-2"><span className="block text-xs text-neutral-500">إجمالي الراتب للفترة</span><span className="tabular-nums font-semibold">{formatCurrency(data.totals.gross_salary)}</span></div>
            <div className="rounded-xl bg-red-50 px-3 py-2"><span className="block text-xs text-red-600">إجمالي الخصومات</span><span className="tabular-nums font-semibold text-red-700">{formatCurrency(data.totals.total_deductions)}</span></div>
            <div className="rounded-xl bg-sand-100 px-3 py-2"><span className="block text-xs text-neutral-500">صافي الراتب بعد الخصم</span><span className="tabular-nums font-semibold">{formatCurrency(data.totals.salary_net)}</span></div>
            <div className="rounded-xl bg-emerald-50 px-3 py-2"><span className="block text-xs text-emerald-700">صافي الرواتب المصروفة</span><span className="tabular-nums font-semibold text-emerald-800">{formatCurrency(data.totals.net_paid)}</span></div>
            <div className="rounded-xl bg-amber-50 px-3 py-2"><span className="block text-xs text-amber-700">متبقي رواتب غير مصروفة</span><span className="tabular-nums font-semibold text-amber-800">{formatCurrency(data.totals.salary_remaining)}</span></div>
            <div className="rounded-xl bg-orange-50 px-3 py-2"><span className="block text-xs text-orange-700">خصم السلف من الرواتب</span><span className="tabular-nums font-semibold text-orange-800">{formatCurrency(data.totals.advance_deduction)}</span></div>
            <div className="rounded-xl bg-violet-50 px-3 py-2"><span className="block text-xs text-violet-700">خصم الأقساط من الرواتب</span><span className="tabular-nums font-semibold text-violet-800">{formatCurrency(data.totals.installment_deduction)}</span></div>
            <div className="rounded-xl bg-red-50 px-3 py-2"><span className="block text-xs text-red-600">رصيد السلف المتبقي</span><span className="tabular-nums font-semibold text-red-700">{formatCurrency(data.totals.outstanding_advances)}</span></div>
            <div className="rounded-xl bg-violet-50 px-3 py-2"><span className="block text-xs text-violet-700">رصيد الأقساط المتبقي</span><span className="tabular-nums font-semibold text-violet-800">{formatCurrency(data.totals.outstanding_installments)}</span></div>
          </div>

          <section className="space-y-2">
            <h3 className="font-semibold text-neutral-800">حركات الرواتب والسلف ضمن الفترة</h3>
            {data.rows.length === 0 ? <EmptyState title="لا توجد حركات في الفترة" description="الأرصدة الحالية للسلف والأقساط تظهر في الجداول أدناه." /> : (
              <Table>
                <thead><tr><Th>التاريخ</Th><Th>الحركة</Th><Th>المرجع والتفاصيل</Th><Th>الإجمالي</Th><Th>الخصم / المسدد</Th><Th>الصافي / المتبقي</Th></tr></thead>
                <tbody>{data.rows.map((r, i) => (
                  <Tr key={`${r.type}-${i}`}>
                    <Td>{formatDate(r.date)}</Td>
                    <Td className="font-medium">{r.type_label}</Td>
                    <Td><span className="block text-neutral-700">{r.ref}</span><span className="block max-w-sm text-xs text-neutral-500">{r.notes}</span></Td>
                    <Td className="tabular-nums">{formatCurrency(r.gross_salary)}</Td>
                    <Td className="tabular-nums">{formatCurrency(r.type === 'payslip' ? r.total_deductions : r.paid_amount)}</Td>
                    <Td className={`tabular-nums font-semibold ${r.type === 'payslip' && r.salary_remaining > 0 ? 'text-amber-700' : 'text-emerald-700'}`}>
                      {formatCurrency(r.type === 'payslip' ? r.salary_net : r.salary_remaining)}
                      {r.type === 'payslip' && <span className="block text-xs font-normal">{r.salary_remaining > 0 ? `غير مصروف: ${formatCurrency(r.salary_remaining)}` : 'تم صرفه'}</span>}
                    </Td>
                  </Tr>
                ))}</tbody>
              </Table>
            )}
          </section>

          <section className="space-y-2">
            <h3 className="font-semibold text-neutral-800">السلف ورصيد كل سلفة</h3>
            {data.advances.length === 0 ? <p className="text-sm text-neutral-500">لا توجد سلف مسجلة.</p> : <Table>
              <thead><tr><Th>التاريخ</Th><Th>السبب</Th><Th>الحالة</Th><Th>المبلغ</Th><Th>المسدد</Th><Th>المتبقي</Th></tr></thead>
              <tbody>{data.advances.map((a) => <Tr key={a.id}><Td>{formatDate(a.date)}</Td><Td>{a.reason || '—'}</Td><Td>{a.status}</Td><Td>{formatCurrency(a.amount)}</Td><Td>{formatCurrency(a.recovered_amount)}</Td><Td className="font-semibold text-red-700">{formatCurrency(a.remaining_amount)}</Td></Tr>)}</tbody>
            </Table>}
          </section>

          <section className="space-y-2">
            <h3 className="font-semibold text-neutral-800">الأقساط ورصيد كل قسط</h3>
            {data.installments.length === 0 ? <p className="text-sm text-neutral-500">لا توجد أقساط مسجلة.</p> : <Table>
              <thead><tr><Th>البيان</Th><Th>بدء الخصم</Th><Th>الإجمالي</Th><Th>القسط الشهري</Th><Th>المسدد</Th><Th>المتبقي</Th><Th>الحالة</Th></tr></thead>
              <tbody>{data.installments.map((p) => <Tr key={p.id}><Td>{p.description}</Td><Td>{formatDate(p.start_month)}</Td><Td>{formatCurrency(p.total_amount)}</Td><Td>{formatCurrency(p.monthly_amount)}</Td><Td>{formatCurrency(p.paid_amount)}</Td><Td className="font-semibold text-violet-800">{formatCurrency(p.remaining_amount)}</Td><Td>{p.remaining_amount <= 0 ? 'مكتمل' : p.is_active ? 'مستمر' : 'متوقف'}</Td></Tr>)}</tbody>
            </Table>}
          </section>

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
