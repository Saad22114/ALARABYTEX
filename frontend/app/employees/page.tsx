'use client';

import { useState, useEffect } from 'react';
import AppShell from '@/components/layout/AppShell';
import Card from '@/components/ui/Card';
import Button from '@/components/ui/Button';
import Table, { Th, Td, Tr } from '@/components/ui/Table';
import SearchInput from '@/components/ui/SearchInput';
import Input from '@/components/ui/Input';
import Textarea from '@/components/ui/Textarea';
import Select from '@/components/ui/Select';
import Modal from '@/components/ui/Modal';
import ConfirmDialog from '@/components/ui/ConfirmDialog';
import EmptyState from '@/components/ui/EmptyState';
import Spinner from '@/components/ui/Spinner';
import Badge from '@/components/ui/Badge';
import { Plus, Pencil, Trash2, UserRoundPlus } from 'lucide-react';
import { Employee } from '@/types';
import {
  listEmployees,
  createEmployee,
  updateEmployee,
  deleteEmployee,
} from '@/services/sessions';
import { listBranches } from '@/services/branches';
import { useToast } from '@/components/ui/Toast';

interface EmployeeForm {
  name: string;
  phone: string;
  branch: number | null;
  notes: string;
  is_active: boolean;
}

const emptyForm = (): EmployeeForm => ({ name: '', phone: '', branch: null, notes: '', is_active: true });

export default function EmployeesPage() {
  const { toast } = useToast();

  const [employees, setEmployees] = useState<Employee[]>([]);
  const [branches, setBranches] = useState<Array<{ id: number; name: string }>>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');

  const [modalOpen, setModalOpen] = useState(false);
  const [form, setForm] = useState<EmployeeForm>(emptyForm());
  const [editing, setEditing] = useState<Employee | null>(null);
  const [saving, setSaving] = useState(false);

  const [deleting, setDeleting] = useState<Employee | null>(null);
  const [deleteLoading, setDeleteLoading] = useState(false);

  const fetchData = () => {
    let cancelled = false;
    setLoading(true);
    listEmployees({ page_size: 100, search: search || undefined })
      .then((res) => { if (!cancelled) setEmployees(res.results); })
      .catch((err) => { if (!cancelled) toast('error', err.message); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  };

  useEffect(fetchData, [search]);

  useEffect(() => {
    let cancelled = false;
    listBranches({ page_size: 100 })
      .then((res) => { if (!cancelled) setBranches(res.results); })
      .catch(() => {});
    return () => { cancelled = true; };
  }, []);

  const openModal = (emp?: Employee) => {
    setEditing(emp || null);
    setForm(emp
      ? { name: emp.name, phone: emp.phone, branch: emp.branch, notes: emp.notes, is_active: emp.is_active }
      : emptyForm());
    setModalOpen(true);
  };

  const handleSave = async () => {
    if (!form.name.trim()) {
      toast('error', 'يرجى إدخال اسم الموظف');
      return;
    }
    if (!form.branch) {
      toast('error', 'يرجى اختيار الفرع');
      return;
    }
    setSaving(true);
    try {
      if (editing) {
        await updateEmployee(editing.id, { ...form, branch: form.branch! });
        toast('success', 'تم تحديث بيانات الموظف');
      } else {
        await createEmployee({ ...form, branch: form.branch! });
        toast('success', 'تم إضافة الموظف بنجاح');
      }
      setModalOpen(false);
      fetchData();
    } catch (err: any) {
      toast('error', err.message);
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async () => {
    if (!deleting) return;
    setDeleteLoading(true);
    try {
      await deleteEmployee(deleting.id);
      toast('success', 'تم حذف الموظف');
      setDeleting(null);
      fetchData();
    } catch (err: any) {
      toast('error', err.message);
    } finally {
      setDeleteLoading(false);
    }
  };

  return (
    <AppShell>
      <div className="space-y-6">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <h1 className="text-2xl font-bold">الموظفون</h1>
          </div>
          <Button onClick={() => openModal()}>
            <UserRoundPlus size={18} />
            إضافة موظف
          </Button>
        </div>

        <Card className="!p-4">
          <div className="flex flex-wrap items-end gap-4">
            <div className="flex-1 min-w-[200px]">
              <SearchInput value={search} onChange={(v) => setSearch(v)} placeholder="بحث بالاسم أو الهاتف أو الفرع..." />
            </div>
          </div>
        </Card>

        <Card>
          {loading ? (
            <div className="flex justify-center py-12"><Spinner size={32} /></div>
          ) : employees.length === 0 ? (
            <EmptyState
              title="لا يوجد موظفون بعد"
              description="أضف موظفاً واربطه بفرع ليتمكن من فتح وردية بيع"
            />
          ) : (
            <Table>
              <thead>
                <tr>
                  <Th>الاسم</Th>
                  <Th>الهاتف</Th>
                  <Th>الفرع</Th>
                  <Th>الحالة</Th>
                  <Th>إجراءات</Th>
                </tr>
              </thead>
              <tbody>
                {employees.map((emp) => (
                  <Tr key={emp.id}>
                    <Td className="font-medium">{emp.name}</Td>
                    <Td className="tabular-nums" dir="ltr">{emp.phone || '-'}</Td>
                    <Td>{emp.branch_name}</Td>
                    <Td>
                      <Badge variant={emp.is_active ? 'success' : 'neutral'}>
                        {emp.is_active ? 'نشط' : 'موقوف'}
                      </Badge>
                    </Td>
                    <Td>
                      <div className="flex items-center gap-1">
                        <button onClick={() => openModal(emp)} className="p-1.5 rounded-lg hover:bg-amber-50 text-amber-600 dark:hover:bg-amber-500/15 dark:text-amber-400 transition-colors">
                          <Pencil size={15} />
                        </button>
                        <button onClick={() => setDeleting(emp)} className="p-1.5 rounded-lg hover:bg-red-50 text-red-500 dark:hover:bg-red-500/15 dark:text-red-400 transition-colors">
                          <Trash2 size={15} />
                        </button>
                      </div>
                    </Td>
                  </Tr>
                ))}
              </tbody>
            </Table>
          )}
        </Card>

        <Modal open={modalOpen} onClose={() => setModalOpen(false)} title={editing ? 'تعديل موظف' : 'إضافة موظف'} maxWidth="max-w-md">
          <div className="space-y-4">
            <Input
              label="اسم الموظف"
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
              placeholder="مثال: محمد عبدالله"
            />
            <Input
              label="رقم الهاتف"
              value={form.phone}
              onChange={(e) => setForm({ ...form, phone: e.target.value })}
              placeholder="05xxxxxxxx"
              dir="ltr"
            />
            <Select
              label="الفرع"
              value={form.branch ?? ''}
              onChange={(e) => setForm({ ...form, branch: Number(e.target.value) })}
              options={branches.map((b) => ({ value: b.id, label: b.name }))}
              placeholder="اختر الفرع"
            />
            <Textarea
              label="ملاحظات"
              value={form.notes}
              onChange={(e) => setForm({ ...form, notes: e.target.value })}
              placeholder="ملاحظات اختيارية..."
            />
            {editing && (
              <div className="flex items-center justify-between">
                <span className="text-sm font-medium text-neutral-700">موظف نشط</span>
                <input
                  type="checkbox"
                  checked={form.is_active}
                  onChange={(e) => setForm({ ...form, is_active: e.target.checked })}
                  className="h-4 w-4 accent-brand-600"
                />
              </div>
            )}
            <div className="flex items-center justify-end gap-2 pt-2">
              <Button variant="secondary" onClick={() => setModalOpen(false)}>إلغاء</Button>
              <Button onClick={handleSave} loading={saving}>
                {editing ? 'حفظ التعديلات' : 'إضافة الموظف'}
              </Button>
            </div>
          </div>
        </Modal>

        <ConfirmDialog
          open={!!deleting}
          onClose={() => setDeleting(null)}
          onConfirm={handleDelete}
          loading={deleteLoading}
          message="هل أنت متأكد من حذف هذا الموظف؟ لا يمكن حذف موظف لديه ورديات بيع."
        />
      </div>
    </AppShell>
  );
}