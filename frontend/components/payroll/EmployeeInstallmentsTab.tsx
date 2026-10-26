'use client';

import { useCallback, useEffect, useState } from 'react';
import { Plus, Pause, Play } from 'lucide-react';
import Button from '@/components/ui/Button';
import Card from '@/components/ui/Card';
import EmptyState from '@/components/ui/EmptyState';
import Input from '@/components/ui/Input';
import Modal from '@/components/ui/Modal';
import Select from '@/components/ui/Select';
import Spinner from '@/components/ui/Spinner';
import Table, { Th, Td, Tr } from '@/components/ui/Table';
import { useToast } from '@/components/ui/Toast';
import { formatCurrency, formatDate } from '@/lib/format';
import { createEmployeeInstallment, listEmployeeInstallments, updateEmployeeInstallment } from '@/services/payroll';
import type { EmployeeInstallmentPlan } from '@/types';
import type { StructureEmployeeOption } from './SalaryStructureForm';

export default function EmployeeInstallmentsTab({ employees, defaultMonth }: { employees: StructureEmployeeOption[]; defaultMonth: string }) {
  const { toast } = useToast();
  const [plans, setPlans] = useState<EmployeeInstallmentPlan[]>([]);
  const [loading, setLoading] = useState(true);
  const [open, setOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const [form, setForm] = useState({ employee: '', description: '', total_amount: '', monthly_amount: '', start_month: defaultMonth || new Date().toLocaleDateString('en-CA').slice(0, 7), notes: '' });

  const load = useCallback(() => {
    setLoading(true);
    listEmployeeInstallments({ page_size: 200 })
      .then((result) => setPlans(result.results))
      .catch((error) => toast('error', error.message))
      .finally(() => setLoading(false));
  }, [toast]);

  useEffect(() => { load(); }, [load]);

  const save = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!form.employee || !form.description.trim() || Number(form.total_amount) <= 0 || Number(form.monthly_amount) <= 0) {
      toast('error', 'أكمل بيانات القسط وتأكد أن المبالغ أكبر من صفر');
      return;
    }
    setSaving(true);
    try {
      await createEmployeeInstallment({
        employee: Number(form.employee), description: form.description.trim(),
        total_amount: Number(form.total_amount), monthly_amount: Number(form.monthly_amount),
        start_month: `${form.start_month}-01`, notes: form.notes,
      });
      toast('success', 'تم تسجيل القسط وسيبدأ الخصم من الشهر المحدد');
      setOpen(false);
      setForm((old) => ({ ...old, description: '', total_amount: '', monthly_amount: '', notes: '' }));
      load();
    } catch (error: any) { toast('error', error.message); }
    finally { setSaving(false); }
  };

  const toggle = async (plan: EmployeeInstallmentPlan) => {
    try {
      await updateEmployeeInstallment(plan.id, { is_active: !plan.is_active });
      toast('success', plan.is_active ? 'تم إيقاف القسط' : 'تم تفعيل القسط');
      load();
    } catch (error: any) { toast('error', error.message); }
  };

  return (
    <div className="space-y-4">
      <Card>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div><h2 className="text-lg font-semibold text-neutral-900">أقساط الموظفين</h2><p className="mt-1 text-sm text-neutral-500">خصم شهري مستقل عن السلف، ويتوقف تلقائياً عند اكتمال المبلغ.</p></div>
          <Button onClick={() => setOpen(true)}><Plus size={16} className="ml-2" /> قسط جديد</Button>
        </div>
      </Card>
      <Card>
        {loading ? <div className="flex justify-center py-10"><Spinner size={28} /></div> : plans.length === 0 ? (
          <EmptyState title="لا توجد أقساط مسجلة" description="أضف قسطاً لموظف ليُخصم شهرياً من راتبه حتى السداد." />
        ) : (
          <div className="overflow-x-auto"><Table><thead><tr><Th>الموظف</Th><Th>البيان</Th><Th>الإجمالي</Th><Th>القسط الشهري</Th><Th>المسدد</Th><Th>المتبقي</Th><Th>بدء الخصم</Th><Th>الحالة</Th><Th>إجراء</Th></tr></thead><tbody>
            {plans.map((plan) => <Tr key={plan.id}>
              <Td><div className="font-medium">{plan.employee_name}</div><div className="text-xs text-neutral-500">{plan.branch_name}</div></Td>
              <Td>{plan.description}</Td><Td>{formatCurrency(plan.total_amount)}</Td><Td>{formatCurrency(plan.monthly_amount)}</Td>
              <Td>{formatCurrency(plan.paid_amount)}</Td><Td className="font-semibold">{formatCurrency(plan.remaining_amount)}</Td>
              <Td>{formatDate(plan.start_month)}</Td>
              <Td><span className={plan.is_active && plan.remaining_amount > 0 ? 'text-emerald-700' : 'text-neutral-500'}>{plan.remaining_amount <= 0 ? 'مكتمل' : plan.is_active ? 'مستمر' : 'متوقف'}</span></Td>
              <Td>{plan.remaining_amount > 0 && <Button size="sm" variant="secondary" onClick={() => toggle(plan)}>{plan.is_active ? <><Pause size={14} className="ml-1" /> إيقاف</> : <><Play size={14} className="ml-1" /> تفعيل</>}</Button>}</Td>
            </Tr>)}
          </tbody></Table></div>
        )}
      </Card>
      <Modal open={open} onClose={() => setOpen(false)} title="تسجيل قسط للموظف">
        <form onSubmit={save} className="space-y-4">
          <Select label="الموظف" value={form.employee} onChange={(e) => setForm({ ...form, employee: e.target.value })} options={employees.map((employee) => ({ value: employee.id, label: employee.branch_name ? `${employee.name} — ${employee.branch_name}` : employee.name }))} placeholder="اختر الموظف" />
          <Input label="بيان القسط" value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} placeholder="مثال: جهاز أو مشتريات" />
          <div className="grid gap-3 sm:grid-cols-2"><Input label="إجمالي المبلغ" type="number" min="0.01" step="0.01" value={form.total_amount} onChange={(e) => setForm({ ...form, total_amount: e.target.value })} /><Input label="الخصم الشهري" type="number" min="0.01" step="0.01" value={form.monthly_amount} onChange={(e) => setForm({ ...form, monthly_amount: e.target.value })} /></div>
          <Input label="بدء الخصم من شهر" type="month" value={form.start_month} onChange={(e) => setForm({ ...form, start_month: e.target.value })} />
          <Input label="ملاحظات" value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} />
          <div className="flex justify-end gap-2"><Button type="button" variant="secondary" onClick={() => setOpen(false)}>إلغاء</Button><Button type="submit" loading={saving}>حفظ القسط</Button></div>
        </form>
      </Modal>
    </div>
  );
}
