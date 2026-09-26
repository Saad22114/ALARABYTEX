'use client';

import { useCallback, useEffect, useState } from 'react';
import Button from '@/components/ui/Button';
import Card from '@/components/ui/Card';
import Badge from '@/components/ui/Badge';
import Table, { Th, Td, Tr } from '@/components/ui/Table';
import Select from '@/components/ui/Select';
import Input from '@/components/ui/Input';
import Modal from '@/components/ui/Modal';
import ConfirmDialog from '@/components/ui/ConfirmDialog';
import EmptyState from '@/components/ui/EmptyState';
import Spinner from '@/components/ui/Spinner';
import { useToast } from '@/components/ui/Toast';
import { Branch, PayrollRun, PayrollSummary, Payslip } from '@/types';
import { PAYROLL_RUN_STATUSES } from '@/lib/constants';
import {
  approveRun,
  cancelRun,
  createRun,
  deleteRun,
  exportRun,
  exportRuns,
  getPayrollPreview,
  getPayrollSummary,
  getRun,
  listRuns,
  payRun,
  updatePayslip,
} from '@/services/payroll';
import { formatCurrency, formatDate } from '@/lib/format';
import PayslipForm from './PayslipForm';

const badgeVariant = (status: string) =>
  status === 'PAID'
    ? 'success'
    : status === 'APPROVED'
      ? 'warning'
      : status === 'CANCELLED'
        ? 'danger'
        : 'neutral';

interface RunsTabProps {
  month: string;
  onMonthChange: (month: string) => void;
  branches: Branch[];
  filterBranch: string;
  onFilterBranch: (v: string) => void;
  onStatement: (employeeId: number) => void;
}

export default function RunsTab({
  month,
  onMonthChange,
  branches,
  filterBranch,
  onFilterBranch,
  onStatement,
}: RunsTabProps) {
  const { toast } = useToast();
  const [runs, setRuns] = useState<PayrollRun[]>([]);
  const [summary, setSummary] = useState<PayrollSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState(false);

  const [createOpen, setCreateOpen] = useState(false);
  const [previewBranch, setPreviewBranch] = useState('');
  const [preview, setPreview] = useState<Awaited<ReturnType<typeof getPayrollPreview>> | null>(null);
  const [previewLoading, setPreviewLoading] = useState(false);

  const [detail, setDetail] = useState<PayrollRun | null>(null);
  const [editingPayslip, setEditingPayslip] = useState<Payslip | null>(null);
  const [confirm, setConfirm] = useState<{ run: PayrollRun; action: 'pay' | 'cancel' | 'delete' } | null>(
    null,
  );

  const load = useCallback(() => {
    setLoading(true);
    const params = { month, branch: filterBranch || undefined, page_size: 100 };
    Promise.all([getPayrollSummary(params), listRuns(params)])
      .then(([s, r]) => {
        setSummary(s);
        setRuns(r.results);
      })
      .catch((err) => toast('error', err.message))
      .finally(() => setLoading(false));
  }, [month, filterBranch, toast]);

  useEffect(() => {
    load();
  }, [load]);

  const loadPreview = useCallback(
    (branch: string) => {
      setPreviewLoading(true);
      getPayrollPreview({ month, branch: branch || undefined })
        .then(setPreview)
        .catch((err) => toast('error', err.message))
        .finally(() => setPreviewLoading(false));
    },
    [month, toast],
  );

  const openCreate = () => {
    setCreateOpen(true);
    setPreviewBranch(filterBranch);
    loadPreview(filterBranch);
  };

  const handleCreate = async () => {
    setActionLoading(true);
    try {
      const run = await createRun({ month, branch: previewBranch ? Number(previewBranch) : null });
      toast('success', 'تم إنشاء مسيّر الرواتب');
      setCreateOpen(false);
      setDetail(run);
      load();
    } catch (err: any) {
      toast('error', err.message);
    } finally {
      setActionLoading(false);
    }
  };

  const runAction = async (run: PayrollRun, action: 'approve' | 'pay' | 'cancel' | 'delete') => {
    setActionLoading(true);
    try {
      if (action === 'approve') await approveRun(run.id);
      if (action === 'pay') await payRun(run.id, run.payment_method);
      if (action === 'cancel') await cancelRun(run.id);
      if (action === 'delete') await deleteRun(run.id);
      const messages = {
        approve: 'تم اعتماد المسيّر',
        pay: 'تم صرف المسيّر وترحيل القيد المحاسبي',
        cancel: 'تم إلغاء المسيّر',
        delete: 'تم حذف المسيّر',
      };
      toast('success', messages[action]);
      setConfirm(null);
      setDetail(null);
      load();
    } catch (err: any) {
      toast('error', err.message);
    } finally {
      setActionLoading(false);
    }
  };

  const handleExportRun = async (run: PayrollRun) => {
    try {
      await exportRun(run.id, `كشف_رواتب_${run.month.slice(0, 7)}.xlsx`);
      toast('success', 'تم تنزيل كشف الرواتب');
    } catch (err: any) {
      toast('error', err.message);
    }
  };

  const handleExportRuns = async () => {
    try {
      await exportRuns({ month, branch: filterBranch || undefined });
      toast('success', 'تم تنزيل كشف المسيّرات');
    } catch (err: any) {
      toast('error', err.message);
    }
  };

  const handleSavePayslip = async (data: Record<string, unknown>) => {
    if (!editingPayslip) return;
    try {
      await updatePayslip(editingPayslip.id, data);
      toast('success', 'تم تحديث القسيمة');
      setEditingPayslip(null);
      if (detail) {
        const fresh = await getRun(detail.id);
        setDetail(fresh);
      }
      load();
    } catch (err: any) {
      toast('error', err.message);
    }
  };

  return (
    <div className="space-y-4">
      <Card className="!p-4">
        <div className="flex flex-wrap items-end gap-4">
          <Input
            label="الشهر"
            type="month"
            value={month.slice(0, 7)}
            onChange={(e) => onMonthChange(e.target.value ? `${e.target.value}-01` : month)}
            className="sm:w-48"
          />
          <Select
            label="الفرع"
            value={filterBranch}
            onChange={(e) => onFilterBranch(e.target.value)}
            options={[
              { value: '', label: 'كل الفروع' },
              ...branches.map((b) => ({ value: b.id, label: b.name })),
            ]}
            className="sm:w-48"
          />
          <div className="flex-1" />
          <Button type="button" onClick={handleExportRuns} variant="secondary">
            تنزيل المسيّرات
          </Button>
          <Button type="button" onClick={openCreate}>
            مسيّر جديد
          </Button>
        </div>
      </Card>

      {summary && (
        <div className="grid grid-cols-2 lg:grid-cols-5 gap-3 text-sm">
          <div className="rounded-xl bg-surface border border-sand-200 px-4 py-3">
            <span className="block text-xs text-neutral-500">موظفون</span>
            <span className="tabular-nums text-lg font-semibold">{summary.employees}</span>
          </div>
          <div className="rounded-xl bg-surface border border-sand-200 px-4 py-3">
            <span className="block text-xs text-neutral-500">إجمالي الرواتب</span>
            <span className="tabular-nums text-lg font-semibold">{formatCurrency(summary.gross)}</span>
          </div>
          <div className="rounded-xl bg-surface border border-sand-200 px-4 py-3">
            <span className="block text-xs text-neutral-500">الصافي</span>
            <span className="tabular-nums text-lg font-semibold text-emerald-700">
              {formatCurrency(summary.net)}
            </span>
          </div>
          <div className="rounded-xl bg-surface border border-sand-200 px-4 py-3">
            <span className="block text-xs text-neutral-500">سلف الشهر</span>
            <span className="tabular-nums text-lg font-semibold text-amber-600">
              {formatCurrency(summary.advances)}
            </span>
          </div>
          <div className="rounded-xl bg-red-50 border border-red-100 dark:bg-red-500/10 dark:border-red-500/25 px-4 py-3">
            <span className="block text-xs text-red-600">سلف مستحقة</span>
            <span className="tabular-nums text-lg font-semibold text-red-700 dark:text-red-300">
              {formatCurrency(summary.outstanding_advances)}
            </span>
          </div>
        </div>
      )}

      <Card>
        {loading ? (
          <div className="flex justify-center py-12">
            <Spinner size={30} />
          </div>
        ) : runs.length === 0 ? (
          <EmptyState
            title="لا توجد مسيّرات لهذا الشهر"
            description="أنشئ مسيّراً جديداً ليتم احتساب رواتب الشهر"
            action={
              <Button type="button" onClick={openCreate}>
                مسيّر جديد
              </Button>
            }
          />
        ) : (
          <Table>
            <thead>
              <tr>
                <Th>الشهر</Th>
                <Th>الفرع</Th>
                <Th>الحالة</Th>
                <Th>الموظفون</Th>
                <Th>الإجمالي</Th>
                <Th>الخصومات</Th>
                <Th>الصافي</Th>
                <Th>إجراءات</Th>
              </tr>
            </thead>
            <tbody>
              {runs.map((run) => (
                <Tr key={run.id}>
                  <Td className="font-medium">{run.month.slice(0, 7)}</Td>
                  <Td>{run.branch_name || 'كل الفروع'}</Td>
                  <Td>
                    <Badge variant={badgeVariant(run.status)}>
                      {run.status_label || PAYROLL_RUN_STATUSES[run.status]}
                    </Badge>
                  </Td>
                  <Td className="tabular-nums">{run.totals.employees}</Td>
                  <Td className="tabular-nums">{formatCurrency(run.totals.gross)}</Td>
                  <Td className="tabular-nums text-red-600">{formatCurrency(run.totals.deductions)}</Td>
                  <Td className="tabular-nums font-semibold">{formatCurrency(run.totals.net)}</Td>
                  <Td>
                    <div className="flex flex-wrap items-center gap-2">
                      <Button type="button" size="sm" variant="subtle" onClick={() => setDetail(run)}>
                        عرض
                      </Button>
                      {run.status === 'DRAFT' && (
                        <Button
                          type="button"
                          size="sm"
                          variant="subtle"
                          onClick={() => runAction(run, 'approve')}
                          disabled={actionLoading}
                        >
                          اعتماد
                        </Button>
                      )}
                      {run.status === 'APPROVED' && (
                        <Button
                          type="button"
                          size="sm"
                          onClick={() => setConfirm({ run, action: 'pay' })}
                          disabled={actionLoading}
                        >
                          صرف
                        </Button>
                      )}
                      {run.status !== 'PAID' && run.status !== 'CANCELLED' && (
                        <Button
                          type="button"
                          size="sm"
                          variant="ghost"
                          onClick={() => setConfirm({ run, action: 'cancel' })}
                          disabled={actionLoading}
                        >
                          إلغاء
                        </Button>
                      )}
                      <Button
                        type="button"
                        size="sm"
                        variant="ghost"
                        onClick={() => handleExportRun(run)}
                      >
                        Excel
                      </Button>
                    </div>
                  </Td>
                </Tr>
              ))}
            </tbody>
          </Table>
        )}
      </Card>

      {/* إنشاء مسيّر مع معاينة */}
      <Modal
        open={createOpen}
        onClose={() => setCreateOpen(false)}
        title={`مسيّر رواتب ${month.slice(0, 7)}`}
        maxWidth="max-w-4xl"
        footer={
          <>
            <Button type="button" onClick={handleCreate} loading={actionLoading}>
              إنشاء المسيّر
            </Button>
            <Button type="button" variant="secondary" onClick={() => setCreateOpen(false)}>
              إلغاء
            </Button>
          </>
        }
      >
        <div className="space-y-4">
          <Select
            label="الفرع"
            value={previewBranch}
            onChange={(e) => {
              setPreviewBranch(e.target.value);
              loadPreview(e.target.value);
            }}
            options={[
              { value: '', label: 'كل الفروع' },
              ...branches.map((b) => ({ value: b.id, label: b.name })),
            ]}
          />
          {previewLoading ? (
            <div className="flex justify-center py-8">
              <Spinner size={26} />
            </div>
          ) : !preview ? null : preview.rows.length === 0 ? (
            <EmptyState title="لا يوجد موظفون" description="لا يوجد موظفون في هذا النطاق" />
          ) : (
            <>
              <div className="grid grid-cols-2 sm:grid-cols-5 gap-3 text-sm">
                <div className="rounded-xl bg-sand-100 px-3 py-2">
                  <span className="block text-xs text-neutral-500">موظفون</span>
                  <span className="tabular-nums font-semibold">{preview.totals.employees}</span>
                </div>
                <div className="rounded-xl bg-sand-100 px-3 py-2">
                  <span className="block text-xs text-neutral-500">الأساسي</span>
                  <span className="tabular-nums font-semibold">
                    {formatCurrency(preview.totals.base_salary)}
                  </span>
                </div>
                <div className="rounded-xl bg-sand-100 px-3 py-2">
                  <span className="block text-xs text-neutral-500">البدلات</span>
                  <span className="tabular-nums font-semibold">
                    {formatCurrency(preview.totals.allowances)}
                  </span>
                </div>
                <div className="rounded-xl bg-sand-100 px-3 py-2">
                  <span className="block text-xs text-neutral-500">العمولات</span>
                  <span className="tabular-nums font-semibold">
                    {formatCurrency(preview.totals.commission)}
                  </span>
                </div>
                <div className="rounded-xl bg-amber-50 dark:bg-amber-500/10 px-3 py-2">
                  <span className="block text-xs text-amber-700">سلف قابلة للخصم</span>
                  <span className="tabular-nums font-semibold text-amber-800 dark:text-amber-300">
                    {formatCurrency(preview.totals.advances)}
                  </span>
                </div>
              </div>

              {preview.rows.some((r) => !r.has_structure) && (
                <div className="rounded-xl bg-amber-50 border border-amber-200 dark:bg-amber-500/10 dark:border-amber-500/25 px-4 py-3 text-sm text-amber-800 dark:text-amber-200">
                  يوجد موظفون بلا هيكل راتب — لن يُحتسب لهم راتب. أضف الهياكل من تبويب «هياكل الرواتب».
                </div>
              )}

              <Table>
                <thead>
                  <tr>
                    <Th>الموظف</Th>
                    <Th>الفرع</Th>
                    <Th>الأساسي</Th>
                    <Th>العمولة</Th>
                    <Th>سلف</Th>
                    <Th>الإجمالي</Th>
                  </tr>
                </thead>
                <tbody>
                  {preview.rows.map((r) => (
                    <Tr key={r.employee}>
                      <Td className="font-medium">
                        {r.employee_name}
                        {!r.has_structure && (
                          <span className="mr-2 text-xs text-amber-600">بلا هيكل</span>
                        )}
                      </Td>
                      <Td>{r.branch_name || '-'}</Td>
                      <Td className="tabular-nums">{formatCurrency(r.base_salary)}</Td>
                      <Td className="tabular-nums">{formatCurrency(r.commission_amount)}</Td>
                      <Td className="tabular-nums text-amber-600">
                        {formatCurrency(r.advances_total)}
                      </Td>
                      <Td className="tabular-nums font-semibold">{formatCurrency(r.gross)}</Td>
                    </Tr>
                  ))}
                </tbody>
              </Table>
            </>
          )}
        </div>
      </Modal>

      {/* تفاصيل المسيّر */}
      <Modal
        open={!!detail && !editingPayslip}
        onClose={() => setDetail(null)}
        title={detail ? `قسائم ${detail.month.slice(0, 7)} — ${detail.branch_name || 'كل الفروع'}` : ''}
        maxWidth="max-w-6xl"
      >
        {detail && (
          <div className="space-y-4">
            <div className="flex flex-wrap items-center gap-2">
              <Badge variant={badgeVariant(detail.status)}>
                {detail.status_label || PAYROLL_RUN_STATUSES[detail.status]}
              </Badge>
              <span className="text-sm text-neutral-500">
                {detail.approved_at && `اعتُمد ${formatDate(detail.approved_at)}`}
                {detail.paid_at && ` — صُرف ${formatDate(detail.paid_at)}`}
              </span>
              <div className="flex-1" />
              {detail.status === 'DRAFT' && (
                <Button
                  type="button"
                  size="sm"
                  onClick={() => runAction(detail, 'approve')}
                  disabled={actionLoading}
                >
                  اعتماد المسيّر
                </Button>
              )}
              {detail.status === 'APPROVED' && (
                <Button
                  type="button"
                  size="sm"
                  onClick={() => setConfirm({ run: detail, action: 'pay' })}
                  disabled={actionLoading}
                >
                  صرف المسيّر
                </Button>
              )}
              {detail.status !== 'PAID' && detail.status !== 'CANCELLED' && (
                <Button
                  type="button"
                  size="sm"
                  variant="ghost"
                  onClick={() => setConfirm({ run: detail, action: 'cancel' })}
                  disabled={actionLoading}
                >
                  إلغاء المسيّر
                </Button>
              )}
              <Button type="button" size="sm" variant="ghost" onClick={() => handleExportRun(detail)}>
                Excel
              </Button>
            </div>

            {detail.status === 'DRAFT' && (
              <div className="rounded-xl bg-amber-50 border border-amber-200 dark:bg-amber-500/10 dark:border-amber-500/25 px-4 py-3 text-sm text-amber-800 dark:text-amber-200">
                المسيّر في حالة مسودة — عدّل البدلات والخصومات قبل الاعتماد. الاعتماد يُثبّت القسائم.
              </div>
            )}

            <Table>
              <thead>
                <tr>
                  <Th>الموظف</Th>
                  <Th>الإجمالي</Th>
                  <Th>خصم سلفة</Th>
                  <Th>خصومات أخرى</Th>
                  <Th>الصافي</Th>
                  <Th>مصروف</Th>
                  <Th>إجراءات</Th>
                </tr>
              </thead>
              <tbody>
                {(detail.payslips || []).map((p) => (
                  <Tr key={p.id}>
                    <Td className="font-medium">
                      {p.employee_name}
                      <span className="block text-xs text-neutral-400">{p.branch_name}</span>
                    </Td>
                    <Td className="tabular-nums">{formatCurrency(p.gross)}</Td>
                    <Td className="tabular-nums text-amber-600">
                      {formatCurrency(p.advance_deduction)}
                    </Td>
                    <Td className="tabular-nums text-red-600">
                      {formatCurrency(p.total_deductions - p.advance_deduction)}
                    </Td>
                    <Td className="tabular-nums font-semibold">{formatCurrency(p.net_pay)}</Td>
                    <Td>{p.is_paid ? 'نعم' : 'لا'}</Td>
                    <Td>
                      <div className="flex items-center gap-2">
                        <Button
                          type="button"
                          size="sm"
                          variant="subtle"
                          onClick={() => onStatement(p.employee)}
                        >
                          كشف
                        </Button>
                        {detail.status === 'DRAFT' && (
                          <Button
                            type="button"
                            size="sm"
                            variant="ghost"
                            onClick={() => setEditingPayslip(p)}
                          >
                            تعديل
                          </Button>
                        )}
                      </div>
                    </Td>
                  </Tr>
                ))}
              </tbody>
            </Table>

            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-sm">
              <div className="rounded-xl bg-sand-100 px-3 py-2">
                <span className="block text-xs text-neutral-500">الإجمالي</span>
                <span className="tabular-nums font-semibold">
                  {formatCurrency(detail.totals.gross)}
                </span>
              </div>
              <div className="rounded-xl bg-sand-100 px-3 py-2">
                <span className="block text-xs text-neutral-500">الخصومات</span>
                <span className="tabular-nums font-semibold">
                  {formatCurrency(detail.totals.deductions)}
                </span>
              </div>
              <div className="rounded-xl bg-sand-100 px-3 py-2">
                <span className="block text-xs text-neutral-500">الصافي</span>
                <span className="tabular-nums font-semibold text-emerald-700">
                  {formatCurrency(detail.totals.net)}
                </span>
              </div>
              <div className="rounded-xl bg-sand-100 px-3 py-2">
                <span className="block text-xs text-neutral-500">خصم سلفة</span>
                <span className="tabular-nums font-semibold text-amber-600">
                  {formatCurrency(detail.totals.advances)}
                </span>
              </div>
            </div>
          </div>
        )}
      </Modal>

      {/* تعديل قسيمة */}
      <Modal
        open={!!editingPayslip}
        onClose={() => setEditingPayslip(null)}
        title={editingPayslip ? `قسيمة ${editingPayslip.employee_name}` : ''}
        maxWidth="max-w-3xl"
      >
        {editingPayslip && (
          <PayslipForm
            payslip={editingPayslip}
            onSubmit={handleSavePayslip}
            onCancel={() => setEditingPayslip(null)}
          />
        )}
      </Modal>

      <ConfirmDialog
        open={!!confirm}
        onClose={() => setConfirm(null)}
        onConfirm={() => confirm && runAction(confirm.run, confirm.action)}
        loading={actionLoading}
        title={
          confirm?.action === 'pay'
            ? 'صرف المسيّر'
            : confirm?.action === 'cancel'
              ? 'إلغاء المسيّر'
              : 'تأكيد'
        }
        message={
          confirm?.action === 'pay'
            ? 'سيُرحَّل قيد صرف الرواتب في المحاسبة، ولا يمكن التراجع عن ذلك. هل تريد المتابعة؟'
            : confirm?.action === 'cancel'
              ? 'سيُلغى المسيّر وتُسترجَع السلف المعتمدة له. هل تريد المتابعة؟'
              : ''
        }
      />
    </div>
  );
}
