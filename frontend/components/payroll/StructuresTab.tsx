'use client';

import { useCallback, useEffect, useState } from 'react';
import Button from '@/components/ui/Button';
import Card from '@/components/ui/Card';
import Badge from '@/components/ui/Badge';
import Table, { Th, Td, Tr } from '@/components/ui/Table';
import SearchInput from '@/components/ui/SearchInput';
import Select from '@/components/ui/Select';
import Modal from '@/components/ui/Modal';
import ConfirmDialog from '@/components/ui/ConfirmDialog';
import EmptyState from '@/components/ui/EmptyState';
import Spinner from '@/components/ui/Spinner';
import { useToast } from '@/components/ui/Toast';
import { Branch, SalaryStructure } from '@/types';
import {
  createSalaryStructure,
  deleteSalaryStructure,
  getPayrollEmployees,
  listSalaryStructures,
  updateSalaryStructure,
} from '@/services/payroll';
import { formatCurrency, formatDate } from '@/lib/format';
import SalaryStructureForm, { StructureEmployeeOption } from './SalaryStructureForm';

interface StructuresTabProps {
  branches: Branch[];
  month: string;
  onSaved: () => void;
}

export default function StructuresTab({ branches, month, onSaved }: StructuresTabProps) {
  const { toast } = useToast();
  const [rows, setRows] = useState<SalaryStructure[]>([]);
  const [employees, setEmployees] = useState<StructureEmployeeOption[]>([]);
  const [missing, setMissing] = useState<StructureEmployeeOption[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [branchFilter, setBranchFilter] = useState('');
  const [activeOnly, setActiveOnly] = useState('1');

  const [formOpen, setFormOpen] = useState(false);
  const [editing, setEditing] = useState<SalaryStructure | null>(null);
  const [deleting, setDeleting] = useState<SalaryStructure | null>(null);
  const [deleteLoading, setDeleteLoading] = useState(false);

  const load = useCallback(() => {
    setLoading(true);
    Promise.all([
      listSalaryStructures({
        page_size: 200,
        search: search || undefined,
        branch: branchFilter || undefined,
        active: activeOnly || undefined,
      }),
      getPayrollEmployees({ month, branch: branchFilter || undefined }),
    ])
      .then(([res, emps]) => {
        const filtered = res.results;
        setRows(filtered);
        const options = emps.rows.map((e) => ({
          id: e.employee,
          name: e.employee_name,
          branch_name: e.branch_name,
        }));
        setEmployees(options);
        const withStructure = new Set(filtered.map((s) => s.employee));
        setMissing(options.filter((o) => !withStructure.has(o.id)));
      })
      .catch((err) => toast('error', err.message))
      .finally(() => setLoading(false));
  }, [month, search, branchFilter, activeOnly, toast]);

  useEffect(() => {
    load();
  }, [load]);

  const handleSubmit = async (payload: Record<string, unknown>) => {
    try {
      if (editing) {
        await updateSalaryStructure(editing.id, payload);
        toast('success', 'تم تحديث هيكل الراتب');
      } else {
        await createSalaryStructure(payload as Partial<SalaryStructure>);
        toast('success', 'تم إنشاء هيكل الراتب');
      }
      setFormOpen(false);
      setEditing(null);
      load();
      onSaved();
    } catch (err: any) {
      toast('error', err.message);
      throw err;
    }
  };

  const handleDelete = async () => {
    if (!deleting) return;
    setDeleteLoading(true);
    try {
      await deleteSalaryStructure(deleting.id);
      toast('success', 'تم حذف هيكل الراتب');
      setDeleting(null);
      load();
      onSaved();
    } catch (err: any) {
      toast('error', err.message);
    } finally {
      setDeleteLoading(false);
    }
  };

  return (
    <div className="space-y-4">
      <Card className="!p-4">
        <div className="flex flex-wrap items-end gap-4">
          <div className="flex-1 min-w-[200px]">
            <SearchInput value={search} onChange={setSearch} placeholder="بحث باسم الموظف..." />
          </div>
          <Select
            value={branchFilter}
            onChange={(e) => setBranchFilter(e.target.value)}
            options={[
              { value: '', label: 'كل الفروع' },
              ...branches.map((b) => ({ value: b.id, label: b.name })),
            ]}
            className="sm:w-48"
          />
          <Select
            value={activeOnly}
            onChange={(e) => setActiveOnly(e.target.value)}
            options={[
              { value: '1', label: 'الفعّالة فقط' },
              { value: '', label: 'كل الهياكل' },
            ]}
            className="sm:w-40"
          />
          <Button
            type="button"
            onClick={() => {
              setEditing(null);
              setFormOpen(true);
            }}
          >
            هيكل جديد
          </Button>
        </div>
      </Card>

      {missing.length > 0 && (
        <div className="rounded-xl bg-amber-50 border border-amber-200 dark:bg-amber-500/10 dark:border-amber-500/25 px-4 py-3 text-sm text-amber-800 dark:text-amber-200">
          {missing.length} موظف بلا هيكل راتب: {missing.slice(0, 6).map((m) => m.name).join('، ')}
          {missing.length > 6 && '…'}
        </div>
      )}

      <Card>
        {loading ? (
          <div className="flex justify-center py-12">
            <Spinner size={30} />
          </div>
        ) : rows.length === 0 ? (
          <EmptyState
            title="لا توجد هياكل رواتب"
            description="أضف هيكل راتب لكل موظف ليظهر في المسيّرات"
            action={
              <Button
                type="button"
                onClick={() => {
                  setEditing(null);
                  setFormOpen(true);
                }}
              >
                هيكل جديد
              </Button>
            }
          />
        ) : (
          <Table>
            <thead>
              <tr>
                <Th>الموظف</Th>
                <Th>الفرع</Th>
                <Th>الأساسي</Th>
                <Th>البدلات</Th>
                <Th>الإجمالي</Th>
                <Th>معدل اليوم</Th>
                <Th>سريان</Th>
                <Th>إجراءات</Th>
              </tr>
            </thead>
            <tbody>
              {rows.map((s) => (
                <Tr key={s.id}>
                  <Td className="font-medium">
                    {s.employee_name}
                    {!s.is_active && (
                      <span className="mr-2">
                        <Badge variant="neutral">غير فعّال</Badge>
                      </span>
                    )}
                  </Td>
                  <Td>{s.branch_name || '-'}</Td>
                  <Td className="tabular-nums">{formatCurrency(s.base_salary)}</Td>
                  <Td className="tabular-nums">{formatCurrency(s.total_allowances)}</Td>
                  <Td className="tabular-nums font-semibold">{formatCurrency(s.gross)}</Td>
                  <Td className="tabular-nums text-neutral-500">{formatCurrency(s.daily_rate)}</Td>
                  <Td className="text-xs text-neutral-500">
                    {formatDate(s.effective_from)}
                    {s.effective_to ? ` — ${formatDate(s.effective_to)}` : ''}
                  </Td>
                  <Td>
                    <div className="flex items-center gap-2">
                      <Button
                        type="button"
                        size="sm"
                        variant="subtle"
                        onClick={() => {
                          setEditing(s);
                          setFormOpen(true);
                        }}
                      >
                        تعديل
                      </Button>
                      <Button
                        type="button"
                        size="sm"
                        variant="ghost"
                        onClick={() => setDeleting(s)}
                      >
                        حذف
                      </Button>
                    </div>
                  </Td>
                </Tr>
              ))}
            </tbody>
          </Table>
        )}
      </Card>

      <Modal
        open={formOpen}
        onClose={() => setFormOpen(false)}
        title={editing ? `تعديل هيكل ${editing.employee_name}` : 'هيكل راتب جديد'}
        maxWidth="max-w-2xl"
      >
        <SalaryStructureForm
          initial={editing}
          employees={employees}
          onSubmit={handleSubmit}
          onCancel={() => setFormOpen(false)}
        />
      </Modal>

      <ConfirmDialog
        open={!!deleting}
        onClose={() => setDeleting(null)}
        onConfirm={handleDelete}
        loading={deleteLoading}
        title="حذف هيكل الراتب"
        message="ستُحتسب المسيّرات الجديدة بدون هذا الهيكل. هل تريد المتابعة؟"
      />
    </div>
  );
}
