'use client';

import { useCallback, useEffect, useState } from 'react';
import Button from '@/components/ui/Button';
import Card from '@/components/ui/Card';
import Badge from '@/components/ui/Badge';
import Table, { Th, Td, Tr } from '@/components/ui/Table';
import SearchInput from '@/components/ui/SearchInput';
import Select from '@/components/ui/Select';
import Input from '@/components/ui/Input';
import Modal from '@/components/ui/Modal';
import ConfirmDialog from '@/components/ui/ConfirmDialog';
import EmptyState from '@/components/ui/EmptyState';
import Spinner from '@/components/ui/Spinner';
import Pagination from '@/components/ui/Pagination';
import { useToast } from '@/components/ui/Toast';
import { Branch, SalaryAdvance } from '@/types';
import { ADVANCE_METHODS, SALARY_ADVANCE_STATUSES } from '@/lib/constants';
import {
  approveAdvance,
  createAdvance,
  deleteAdvance,
  exportAdvances,
  listAdvances,
  rejectAdvance,
  repayAdvance,
  updateAdvance,
} from '@/services/payroll';
import { formatCurrency, formatDate } from '@/lib/format';
import AdvanceForm from './AdvanceForm';
import type { StructureEmployeeOption } from './SalaryStructureForm';

const badgeVariant = (status: string) =>
  status === 'SETTLED'
    ? 'success'
    : status === 'APPROVED'
      ? 'warning'
      : status === 'REJECTED'
        ? 'danger'
        : 'neutral';

interface AdvancesTabProps {
  branches: Branch[];
  employees: StructureEmployeeOption[];
  defaultDate: string;
}

export default function AdvancesTab({ branches, employees, defaultDate }: AdvancesTabProps) {
  const { toast } = useToast();
  const [data, setData] = useState<{ results: SalaryAdvance[]; count: number } | null>(null);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [branchFilter, setBranchFilter] = useState('');

  const [formOpen, setFormOpen] = useState(false);
  const [editing, setEditing] = useState<SalaryAdvance | null>(null);
  const [repayOpen, setRepayOpen] = useState<SalaryAdvance | null>(null);
  const [repayForm, setRepayForm] = useState({ amount: '', method: 'CASH', date: defaultDate, notes: '' });
  const [detail, setDetail] = useState<SalaryAdvance | null>(null);
  const [confirm, setConfirm] = useState<{ advance: SalaryAdvance; action: 'reject' | 'delete' } | null>(
    null,
  );
  const [actionLoading, setActionLoading] = useState(false);

  const pageSize = 15;

  const load = useCallback(() => {
    setLoading(true);
    listAdvances({
      page,
      page_size: pageSize,
      search: search || undefined,
      status: statusFilter || undefined,
      branch: branchFilter || undefined,
    })
      .then(setData)
      .catch((err) => toast('error', err.message))
      .finally(() => setLoading(false));
  }, [page, search, statusFilter, branchFilter, toast]);

  useEffect(() => {
    load();
  }, [load]);

  const totalPages = data ? Math.max(1, Math.ceil(data.count / pageSize)) : 1;

  const handleSubmit = async (payload: Record<string, unknown>) => {
    try {
      if (editing) {
        await updateAdvance(editing.id, payload);
        toast('success', 'تم تحديث السلفة');
      } else {
        await createAdvance(payload);
        toast('success', 'تم تسجيل السلفة');
      }
      setFormOpen(false);
      setEditing(null);
      load();
    } catch (err: any) {
      toast('error', err.message);
      throw err;
    }
  };

  const doApprove = async (advance: SalaryAdvance) => {
    try {
      await approveAdvance(advance.id);
      toast('success', 'تم اعتماد السلفة');
      load();
    } catch (err: any) {
      toast('error', err.message);
    }
  };

  const doConfirmAction = async () => {
    if (!confirm) return;
    setActionLoading(true);
    try {
      if (confirm.action === 'reject') {
        await rejectAdvance(confirm.advance.id);
        toast('success', 'تم رفض السلفة');
      } else {
        await deleteAdvance(confirm.advance.id);
        toast('success', 'تم حذف السلفة');
      }
      setConfirm(null);
      load();
    } catch (err: any) {
      toast('error', err.message);
    } finally {
      setActionLoading(false);
    }
  };

  const doRepay = async () => {
    if (!repayOpen) return;
    if (!repayForm.amount || Number(repayForm.amount) <= 0) {
      toast('error', 'أدخل مبلغ السداد');
      return;
    }
    setActionLoading(true);
    try {
      await repayAdvance(repayOpen.id, {
        amount: Number(repayForm.amount),
        method: repayForm.method,
        date: repayForm.date,
        notes: repayForm.notes,
      });
      toast('success', 'تم تسجيل السداد');
      setRepayOpen(null);
      load();
    } catch (err: any) {
      toast('error', err.message);
    } finally {
      setActionLoading(false);
    }
  };

  const handleExport = async () => {
    try {
      await exportAdvances({
        status: statusFilter || undefined,
        branch: branchFilter || undefined,
      });
      toast('success', 'تم تنزيل كشف السلف');
    } catch (err: any) {
      toast('error', err.message);
    }
  };

  return (
    <div className="space-y-4">
      <Card className="!p-4">
        <div className="flex flex-wrap items-end gap-4">
          <div className="flex-1 min-w-[200px]">
            <SearchInput
              value={search}
              onChange={(v) => {
                setSearch(v);
                setPage(1);
              }}
              placeholder="بحث في السلف..."
            />
          </div>
          <Select
            value={statusFilter}
            onChange={(e) => {
              setStatusFilter(e.target.value);
              setPage(1);
            }}
            options={[
              { value: '', label: 'كل الحالات' },
              ...Object.entries(SALARY_ADVANCE_STATUSES).map(([value, label]) => ({ value, label })),
            ]}
            className="sm:w-40"
          />
          <Select
            value={branchFilter}
            onChange={(e) => {
              setBranchFilter(e.target.value);
              setPage(1);
            }}
            options={[
              { value: '', label: 'كل الفروع' },
              ...branches.map((b) => ({ value: b.id, label: b.name })),
            ]}
            className="sm:w-48"
          />
          <Button type="button" variant="secondary" onClick={handleExport}>
            تنزيل Excel
          </Button>
          <Button
            type="button"
            onClick={() => {
              setEditing(null);
              setFormOpen(true);
            }}
          >
            سلفة جديدة
          </Button>
        </div>
      </Card>

      <Card>
        {loading ? (
          <div className="flex justify-center py-12">
            <Spinner size={30} />
          </div>
        ) : !data || data.results.length === 0 ? (
          <EmptyState title="لا توجد سلف" description="لم يتم تسجيل أي سلف بعد" />
        ) : (
          <>
            <Table>
              <thead>
                <tr>
                  <Th>التاريخ</Th>
                  <Th>الموظف</Th>
                  <Th>المبلغ</Th>
                  <Th>الطريقة</Th>
                  <Th>الحالة</Th>
                  <Th>المسدد</Th>
                  <Th>المتبقي</Th>
                  <Th>إجراءات</Th>
                </tr>
              </thead>
              <tbody>
                {data.results.map((a) => (
                  <Tr key={a.id}>
                    <Td>{formatDate(a.date)}</Td>
                    <Td className="font-medium">
                      {a.employee_name}
                      <span className="block text-xs text-neutral-400">{a.branch_name}</span>
                    </Td>
                    <Td className="tabular-nums font-medium">{formatCurrency(a.amount)}</Td>
                    <Td>{ADVANCE_METHODS[a.method] || a.method}</Td>
                    <Td>
                      <Badge variant={badgeVariant(a.status)}>
                        {a.status_label || SALARY_ADVANCE_STATUSES[a.status]}
                      </Badge>
                    </Td>
                    <Td className="tabular-nums text-emerald-700">
                      {formatCurrency(a.recovered_amount)}
                    </Td>
                    <Td className="tabular-nums font-semibold text-red-600">
                      {formatCurrency(a.remaining_amount)}
                    </Td>
                    <Td>
                      <div className="flex flex-wrap items-center gap-2">
                        {a.status === 'PENDING' && (
                          <>
                            <Button type="button" size="sm" variant="subtle" onClick={() => doApprove(a)}>
                              اعتماد
                            </Button>
                            <Button
                              type="button"
                              size="sm"
                              variant="ghost"
                              onClick={() => setConfirm({ advance: a, action: 'reject' })}
                            >
                              رفض
                            </Button>
                          </>
                        )}
                        {a.status === 'APPROVED' && a.remaining_amount > 0 && (
                          <Button
                            type="button"
                            size="sm"
                            onClick={() => {
                              setRepayForm({
                                amount: String(a.remaining_amount),
                                method: a.method,
                                date: defaultDate,
                                notes: '',
                              });
                              setRepayOpen(a);
                            }}
                          >
                            سداد
                          </Button>
                        )}
                        <Button type="button" size="sm" variant="subtle" onClick={() => setDetail(a)}>
                          السدادات
                        </Button>
                        {a.recovered_amount === 0 && (
                          <>
                            <Button
                              type="button"
                              size="sm"
                              variant="ghost"
                              onClick={() => {
                                setEditing(a);
                                setFormOpen(true);
                              }}
                            >
                              تعديل
                            </Button>
                            <Button
                              type="button"
                              size="sm"
                              variant="ghost"
                              onClick={() => setConfirm({ advance: a, action: 'delete' })}
                            >
                              حذف
                            </Button>
                          </>
                        )}
                      </div>
                    </Td>
                  </Tr>
                ))}
              </tbody>
            </Table>
            <Pagination page={page} totalPages={totalPages} onChange={setPage} count={data.count} pageSize={pageSize} />
          </>
        )}
      </Card>

      <Modal
        open={formOpen}
        onClose={() => setFormOpen(false)}
        title={editing ? 'تعديل السلفة' : 'تسجيل سلفة جديدة'}
        maxWidth="max-w-2xl"
      >
        <AdvanceForm
          initial={editing}
          employees={employees}
          defaultDate={defaultDate}
          onSubmit={handleSubmit}
          onCancel={() => setFormOpen(false)}
        />
      </Modal>

      <Modal open={!!repayOpen} onClose={() => setRepayOpen(null)} title="سداد سلفة">
        {repayOpen && (
          <div className="space-y-4">
            <div className="rounded-xl bg-sand-100 px-4 py-3 text-sm space-y-1">
              <div className="flex justify-between">
                <span className="text-neutral-500">الموظف</span>
                <span className="font-medium">{repayOpen.employee_name}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-neutral-500">إجمالي السلفة</span>
                <span className="tabular-nums font-medium">{formatCurrency(repayOpen.amount)}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-neutral-500">المتبقي</span>
                <span className="tabular-nums font-medium text-red-600">
                  {formatCurrency(repayOpen.remaining_amount)}
                </span>
              </div>
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <Input
                label="مبلغ السداد"
                type="number"
                step="0.01"
                min="0"
                value={repayForm.amount}
                onChange={(e) => setRepayForm((f) => ({ ...f, amount: e.target.value }))}
              />
              <Input
                label="التاريخ"
                type="date"
                value={repayForm.date}
                onChange={(e) => setRepayForm((f) => ({ ...f, date: e.target.value }))}
              />
            </div>
            <Select
              label="طريقة السداد"
              value={repayForm.method}
              onChange={(e) => setRepayForm((f) => ({ ...f, method: e.target.value }))}
              options={Object.entries(ADVANCE_METHODS).map(([value, label]) => ({ value, label }))}
            />
            <Input
              label="ملاحظات"
              value={repayForm.notes}
              onChange={(e) => setRepayForm((f) => ({ ...f, notes: e.target.value }))}
            />
            <div className="flex justify-start gap-3">
              <Button type="button" onClick={doRepay} loading={actionLoading}>
                تسجيل السداد
              </Button>
              <Button type="button" variant="secondary" onClick={() => setRepayOpen(null)}>
                إلغاء
              </Button>
            </div>
          </div>
        )}
      </Modal>

      <Modal
        open={!!detail}
        onClose={() => setDetail(null)}
        title={detail ? `سدادات سلفة ${detail.employee_name}` : ''}
        maxWidth="max-w-2xl"
      >
        {detail && (
          <div className="space-y-4">
            {detail.installments.length === 0 ? (
              <EmptyState title="لا توجد سدادات" description="لم تُسجَّل أي سدادات على هذه السلفة" />
            ) : (
              <Table>
                <thead>
                  <tr>
                    <Th>التاريخ</Th>
                    <Th>المبلغ</Th>
                    <Th>الطريقة</Th>
                    <Th>من قسيمة</Th>
                    <Th>ملاحظات</Th>
                  </tr>
                </thead>
                <tbody>
                  {detail.installments.map((i) => (
                    <Tr key={i.id}>
                      <Td>{formatDate(i.date)}</Td>
                      <Td className="tabular-nums font-medium">{formatCurrency(i.amount)}</Td>
                      <Td>{ADVANCE_METHODS[i.method] || i.method}</Td>
                      <Td>{i.payslip ? `قسيمة #${i.payslip}` : 'سداد يدوي'}</Td>
                      <Td className="text-neutral-500">{i.notes || '-'}</Td>
                    </Tr>
                  ))}
                </tbody>
              </Table>
            )}
          </div>
        )}
      </Modal>

      <ConfirmDialog
        open={!!confirm}
        onClose={() => setConfirm(null)}
        onConfirm={doConfirmAction}
        loading={actionLoading}
        title={confirm?.action === 'reject' ? 'رفض السلفة' : 'حذف السلفة'}
        message={
          confirm?.action === 'reject'
            ? 'لن يتم خصم أي مبلغ من رواتب هذا الموظف. هل تريد المتابعة؟'
            : 'لا يمكن التراجع عن حذف السلفة. هل تريد المتابعة؟'
        }
      />
    </div>
  );
}
