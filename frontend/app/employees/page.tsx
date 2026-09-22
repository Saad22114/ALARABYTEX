'use client';

import { useState, useEffect, useMemo } from 'react';
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
import StatCard from '@/components/ui/StatCard';
import PermissionsModal from '@/components/employees/PermissionsModal';
import { ShieldCheck, Plus, Pencil, Trash2, UserRoundPlus, Users, UserCheck, UserX, Shield } from 'lucide-react';
import { Employee, EmployeeRole, SectionsInfo, EmployeePermissions } from '@/types';
import {
  listEmployees,
  createEmployee,
  updateEmployee,
  deleteEmployee,
} from '@/services/sessions';
import { getSectionsInfo } from '@/services/sections';
import { listBranches } from '@/services/branches';
import { useToast } from '@/components/ui/Toast';
import { useUrlState } from '@/lib/useUrlState';

interface EmployeeForm {
  name: string;
  phone: string;
  branch: number | null;
  notes: string;
  is_active: boolean;
  commission_active: boolean;
  commission_percent: number;
  role: EmployeeRole;
  username: string;
  password: string;
  department: string;
  position: string;
  email: string;
  employee_code: string;
  multi_branch_access: boolean;
  birth_date: string;
  civil_id: string;
  address: string;
  hire_date: string;
  base_salary: string;
  cloneFrom: number | null;
  permissions: EmployeePermissions | null;
  hiddenSections: string[] | null;
}

const MANAGER_ROLES: EmployeeRole[] = ['admin', 'supervisor'];

const ROLE_BADGE_VARIANT: Record<string, 'success' | 'warning' | 'neutral' | 'danger'> = {
  admin: 'danger',
  supervisor: 'warning',
  sales: 'success',
  viewer: 'neutral',
  custom: 'neutral',
};

const ROLE_OPTIONS = [
  { value: 'admin', label: 'مدير النظام' },
  { value: 'supervisor', label: 'مشرف' },
  { value: 'sales', label: 'مندوب مبيعات' },
  { value: 'viewer', label: 'مشاهد' },
  { value: 'custom', label: 'مخصص' },
];

const emptyForm = (): EmployeeForm => ({
  name: '',
  phone: '',
  branch: null,
  notes: '',
  is_active: true,
  commission_active: false,
  commission_percent: 0,
  role: 'admin',
  username: '',
  password: '',
  department: '',
  position: '',
  email: '',
  employee_code: '',
  multi_branch_access: false,
  birth_date: '',
  civil_id: '',
  address: '',
  hire_date: '',
  base_salary: '',
  cloneFrom: null,
  permissions: null,
  hiddenSections: null,
});

export default function EmployeesPage() {
  const { toast } = useToast();

  const [employees, setEmployees] = useState<Employee[]>([]);
  const [branches, setBranches] = useState<Array<{ id: number; name: string }>>([]);
  const [sectionsInfo, setSectionsInfo] = useState<SectionsInfo | null>(null);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useUrlState('q', '');
  const [filterBranch, setFilterBranch] = useUrlState('branch', '');
  const [filterRole, setFilterRole] = useUrlState('role', '');

  const [modalOpen, setModalOpen] = useState(false);
  const [form, setForm] = useState<EmployeeForm>(emptyForm());
  const [editing, setEditing] = useState<Employee | null>(null);
  const [saving, setSaving] = useState(false);

  const [deleting, setDeleting] = useState<Employee | null>(null);
  const [deleteLoading, setDeleteLoading] = useState(false);

  const [permsTarget, setPermsTarget] = useState<Employee | null>(null);
  const [permsSaving, setPermsSaving] = useState(false);

  const fetchData = () => {
    let cancelled = false;
    setLoading(true);
    listEmployees({
      page_size: 100,
      search: search || undefined,
      branch: filterBranch || undefined,
    })
      .then((res) => { if (!cancelled) setEmployees(res.results); })
      .catch((err) => { if (!cancelled) toast('error', err.message); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  };

  useEffect(fetchData, [search, filterBranch]);

  useEffect(() => {
    let cancelled = false;
    listBranches({ page_size: 100 })
      .then((res) => { if (!cancelled) setBranches(res.results); })
      .catch(() => {});
    return () => { cancelled = true; };
  }, []);

  useEffect(() => {
    let cancelled = false;
    getSectionsInfo()
      .then((res) => { if (!cancelled) setSectionsInfo(res); })
      .catch(() => {});
    return () => { cancelled = true; };
  }, []);

  const stats = useMemo(() => {
    return {
      total: employees.length,
      active: employees.filter((e) => e.is_active).length,
      inactive: employees.filter((e) => !e.is_active).length,
      sales: employees.filter((e) => e.role === 'sales' && e.is_active).length,
    };
  }, [employees]);

  const filtered = useMemo(() => {
    if (!filterRole) return employees;
    return employees.filter((e) => e.role === filterRole);
  }, [employees, filterRole]);

  const openModal = (emp?: Employee) => {
    setEditing(emp || null);
    setForm(emp
      ? {
          name: emp.name,
          phone: emp.phone,
          branch: emp.branch,
          notes: emp.notes,
          is_active: emp.is_active,
          commission_active: emp.commission_active,
          commission_percent: Number(emp.commission_percent ?? 0),
          role: emp.role,
          username: emp.username || '',
          password: '',
          department: emp.department || '',
          position: emp.position || '',
          email: emp.email || '',
          employee_code: emp.employee_code || '',
          multi_branch_access: emp.multi_branch_access,
          birth_date: emp.birth_date || '',
          civil_id: emp.civil_id || '',
          address: emp.address || '',
          hire_date: emp.hire_date || '',
          base_salary: String(emp.base_salary ?? 0),
          cloneFrom: null,
          permissions: null,
          hiddenSections: null,
        }
      : emptyForm());
    setModalOpen(true);
  };

  const handleCloneChange = (id: number) => {
    const src = employees.find((e) => e.id === id);
    setForm((prev) => {
      if (!src) return { ...prev, cloneFrom: id };
      return {
        ...prev,
        cloneFrom: id,
        role: src.role,
        permissions: src.permissions,
        hiddenSections: src.hidden_sections || [],
      };
    });
  };

  const buildPayload = () => {
    const { cloneFrom, permissions, hiddenSections, ...base } = form;
    const payload: Partial<Employee> = {
      ...base,
      base_salary: Number(base.base_salary || 0),
      birth_date: base.birth_date || null,
      hire_date: base.hire_date || null,
    };
    if (permissions && hiddenSections) {
      payload.permissions = permissions;
      payload.hidden_sections = hiddenSections;
    }
    return payload;
  };

  const handleSave = async () => {
    if (!form.name.trim()) {
      toast('error', 'يرجى إدخال اسم الموظف');
      return;
    }
    if (!form.branch && !MANAGER_ROLES.includes(form.role)) {
      toast('error', 'يرجى اختيار الفرع');
      return;
    }
    setSaving(true);
    try {
      if (editing) {
        await updateEmployee(editing.id, buildPayload());
        toast('success', 'تم تحديث بيانات الموظف');
      } else {
        await createEmployee(buildPayload());
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

  const handleSavePermissions = async (data: {
    role: EmployeeRole;
    permissions: EmployeePermissions;
    hidden_sections: string[];
    allowed_branches: number[];
  }) => {
    if (!permsTarget) return;
    setPermsSaving(true);
    try {
      await updateEmployee(permsTarget.id, {
        role: data.role,
        permissions: data.permissions,
        hidden_sections: data.hidden_sections,
        allowed_branches: data.allowed_branches,
      });
      toast('success', 'تم حفظ صلاحيات الموظف');
      setPermsTarget(null);
      fetchData();
    } catch (err: any) {
      toast('error', err.message);
    } finally {
      setPermsSaving(false);
    }
  };

  return (
    <AppShell>
      <div className="space-y-6">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <h1 className="text-2xl font-bold">الموظفون</h1>
            <Badge variant="neutral">{stats.total} موظف</Badge>
          </div>
          <Button onClick={() => openModal()}>
            <UserRoundPlus size={18} />
            إضافة موظف
          </Button>
        </div>

        {/* Stats */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          <StatCard
            icon={<Users size={20} />}
            label="إجمالي الموظفين"
            value={String(stats.total)}
          />
          <StatCard
            icon={<UserCheck size={20} />}
            iconBg="bg-emerald-50 text-emerald-600"
            label="موظفون نشطون"
            value={String(stats.active)}
          />
          <StatCard
            icon={<Shield size={20} />}
            iconBg="bg-amber-50 text-amber-600"
            label="مندوبو مبيعات"
            value={String(stats.sales)}
            sub="نشطون"
          />
          <StatCard
            icon={<UserX size={20} />}
            iconBg="bg-neutral-100 text-neutral-500"
            label="موقوفون"
            value={String(stats.inactive)}
          />
        </div>

        {/* Filters */}
        <Card className="!p-4">
          <div className="flex flex-wrap items-end gap-3">
            <div className="flex-1 min-w-[200px]">
              <SearchInput value={search} onChange={(v) => setSearch(v)} placeholder="بحث بالاسم أو الهاتف أو الفرع..." />
            </div>
            <Select
              value={filterBranch}
              onChange={(e) => { setFilterBranch(e.target.value); }}
              options={[{ value: '', label: 'كل الفروع' }, ...branches.map((b) => ({ value: b.id, label: b.name }))]}
              className="w-full sm:w-48"
            />
            <Select
              value={filterRole}
              onChange={(e) => setFilterRole(e.target.value)}
              options={[{ value: '', label: 'كل الأدياردة' }, ...ROLE_OPTIONS]}
              className="w-full sm:w-48"
            />
          </div>
        </Card>

        <Card>
          {loading ? (
            <div className="flex justify-center py-12"><Spinner size={32} /></div>
          ) : filtered.length === 0 ? (
            <EmptyState
              title="لا يوجد موظفون"
              description="أضف موظفاً ياردةبطه بفرع ليتمكن من فتح وردية بيع"
            />
          ) : (
            <div className="overflow-x-auto">
              <Table>
                <thead>
                  <tr>
                    <Th>الموظف</Th>
                    <Th>الفرع</Th>
                    <Th>الدور</Th>
                    <Th>العمولة</Th>
                    <Th>الصلاحيات</Th>
                    <Th>الأقسام</Th>
                    <Th>الحالة</Th>
                    <Th>إجراءات</Th>
                  </tr>
                </thead>
                <tbody>
                  {filtered.map((emp) => {
                    const permsCount = emp.permissions
                      ? Object.values(emp.permissions).filter((p) => p && p.view).length
                      : 0;
                    const hiddenCount = emp.hidden_sections?.length || 0;
                    const initials = emp.name.trim().split(/\s+/).slice(0, 2).map((w) => w[0]).join('');
                    return (
                      <Tr key={emp.id}>
                        <Td>
                          <div className="flex items-center gap-3">
                            <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-brand-100 text-brand-700 font-bold text-sm dark:bg-brand-500/15 dark:text-brand-300">
                              {initials}
                            </div>
                            <div>
                              <p className="font-medium">{emp.name}</p>
                              <p className="text-xs text-neutral-400 tabular-nums" dir="ltr">{emp.phone || '—'}</p>
                            </div>
                          </div>
                        </Td>
                        <Td>{emp.branch_name}</Td>
                        <Td>
                          <Badge variant={ROLE_BADGE_VARIANT[emp.role] || 'neutral'}>{emp.role_label}</Badge>
                        </Td>
                        <Td>
                          {emp.commission_active && Number(emp.commission_percent) > 0 ? (
                            <Badge variant="warning">عمولة {emp.commission_percent}%</Badge>
                          ) : (
                            <span className="text-xs text-neutral-400">بدون</span>
                          )}
                        </Td>
                        <Td>
                          <span className="text-sm text-neutral-600 tabular-nums">
                            {permsCount} قسم مُفعّل
                          </span>
                        </Td>
                        <Td>
                          {hiddenCount > 0 ? (
                            <Badge variant="warning">{hiddenCount} مخفي</Badge>
                          ) : (
                            <Badge variant="success">الكل ظاهر</Badge>
                          )}
                        </Td>
                        <Td>
                          <Badge variant={emp.is_active ? 'success' : 'neutral'}>
                            {emp.is_active ? 'نشط' : 'موقوف'}
                          </Badge>
                        </Td>
                        <Td>
                          <div className="flex items-center gap-1">
                            <button
                              onClick={() => setPermsTarget(emp)}
                              className="p-1.5 rounded-lg hover:bg-brand-50 text-brand-600 dark:hover:bg-brand-500/15 dark:text-brand-400 transition-colors"
                              title="إدارة الصلاحيات"
                            >
                              <ShieldCheck size={16} />
                            </button>
                            <button onClick={() => openModal(emp)} className="p-1.5 rounded-lg hover:bg-amber-50 text-amber-600 dark:hover:bg-amber-500/15 dark:text-amber-400 transition-colors">
                              <Pencil size={15} />
                            </button>
                            <button onClick={() => setDeleting(emp)} className="p-1.5 rounded-lg hover:bg-red-50 text-red-500 dark:hover:bg-red-500/15 dark:text-red-400 transition-colors">
                              <Trash2 size={15} />
                            </button>
                          </div>
                        </Td>
                      </Tr>
                    );
                  })}
                </tbody>
              </Table>
            </div>
          )}
        </Card>

        <Modal open={modalOpen} onClose={() => setModalOpen(false)} title={editing ? 'تعديل موظف' : 'إضافة موظف'} maxWidth="max-w-lg">
          <div className="space-y-4">
            <div className="rounded-xl bg-sand-50 border border-sand-200 p-4 space-y-3">
              <p className="text-xs font-medium text-neutral-500">البيانات الأساسية</p>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <Input
                  label="اسم الموظف"
                  required
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
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <Select
                  label={MANAGER_ROLES.includes(form.role) ? 'الفرع (اختياري)' : 'الفرع'}
                  required={!MANAGER_ROLES.includes(form.role)}
                  value={form.branch ?? ''}
                  onChange={(e) => setForm({ ...form, branch: e.target.value === '' ? null : Number(e.target.value) })}
                  options={[
                    ...(MANAGER_ROLES.includes(form.role) ? [{ value: '', label: 'بدون فرع' }] : []),
                    ...branches.map((b) => ({ value: b.id, label: b.name })),
                  ]}
                  placeholder={MANAGER_ROLES.includes(form.role) ? undefined : 'اختر الفرع'}
                />
                <Select
                  label="الدور"
                  value={form.role}
                  onChange={(e) => setForm({ ...form, role: e.target.value as EmployeeRole })}
                  options={ROLE_OPTIONS}
                />
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <Input
                  label="المسمى الوظيفي"
                  value={form.position}
                  onChange={(e) => setForm({ ...form, position: e.target.value })}
                  placeholder="مثال: بائع أول"
                />
                <Input
                  label="القسم"
                  value={form.department}
                  onChange={(e) => setForm({ ...form, department: e.target.value })}
                  placeholder="مثال: قسم المبيعات"
                />
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <Input
                  label="رقم الموظف (كود)"
                  value={form.employee_code}
                  onChange={(e) => setForm({ ...form, employee_code: e.target.value })}
                  placeholder="مثال: EMP-001"
                  dir="ltr"
                />
                <Input
                  label="البريد الإلكتروني"
                  type="email"
                  value={form.email}
                  onChange={(e) => setForm({ ...form, email: e.target.value })}
                  placeholder="name@example.com"
                  dir="ltr"
                />
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <Input
                  label="تاريخ الميلاد"
                  type="date"
                  value={form.birth_date}
                  onChange={(e) => setForm({ ...form, birth_date: e.target.value })}
                />
                <Input
                  label="الرقم المدني / الهوية"
                  value={form.civil_id}
                  onChange={(e) => setForm({ ...form, civil_id: e.target.value })}
                  placeholder="مثال: 123456789"
                  dir="ltr"
                />
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <Input
                  label="تاريخ التوظيف"
                  type="date"
                  value={form.hire_date}
                  onChange={(e) => setForm({ ...form, hire_date: e.target.value })}
                />
                <Input
                  label="الراتب الأساسي"
                  type="number"
                  min="0"
                  step="0.01"
                  value={form.base_salary}
                  onChange={(e) => setForm({ ...form, base_salary: e.target.value })}
                  placeholder="0.00"
                  dir="ltr"
                />
              </div>
              <Input
                label="العنوان"
                value={form.address}
                onChange={(e) => setForm({ ...form, address: e.target.value })}
                placeholder="العنوان الكامل..."
              />
              <Textarea
                label="ملاحظات"
                value={form.notes}
                onChange={(e) => setForm({ ...form, notes: e.target.value })}
                placeholder="ملاحظات اختيارية..."
              />
            </div>

            <div className="rounded-xl bg-sand-50 border border-sand-200 p-4 space-y-3">
              <p className="text-xs font-medium text-neutral-500">بيانات تسجيل الدخول</p>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <Input
                  label="اسم المستخدم"
                  value={form.username}
                  onChange={(e) => setForm({ ...form, username: e.target.value })}
                  placeholder={editing ? (form.username || 'لا يوجد حساب بعد') : 'يُولَّد تلقائياً عند التعارض'}
                  dir="ltr"
                />
                <Input
                  label={editing ? 'كلمة المرور الجديدة' : 'كلمة المرور'}
                  type="password"
                  value={form.password}
                  onChange={(e) => setForm({ ...form, password: e.target.value })}
                  placeholder={editing ? 'اتركها فارغة للإبقاء على الحالية' : 'الافتراضية: Qomash@123'}
                  dir="ltr"
                />
              </div>
              <p className="text-xs text-neutral-500">
                {editing
                  ? 'عدّل اسم المستخدم لتغييره — وأدخل كلمة مرور جديدة فقط إن أردت تغييرها.'
                  : 'اتركهما فارغين لتوليد الحساب تلقائياً (اسم المستخدم = الهاتف أو الاسم، كلمة المرور الافتراضية).'}
              </p>
            </div>

            {!editing && (
              <div className="rounded-xl bg-sand-50 border border-sand-200 p-4 space-y-3">
                <p className="text-xs font-medium text-neutral-500">استنساخ الصلاحيات</p>
                <Select
                  label="استنساخ الدور والصلاحيات من موظف"
                  value={form.cloneFrom ?? ''}
                  onChange={(e) => handleCloneChange(Number(e.target.value))}
                  options={employees.map((e) => ({ value: e.id, label: `${e.name} — ${e.role_label}` }))}
                  placeholder="اختر الموظف المصدر (اختياري)"
                />
                {form.cloneFrom && (
                  <p className="text-xs text-neutral-500">
                    سيتم نسخ الدور والصلاحيات والأقسام المخفية من الموظف المحدد — يمكنك تعديلها بعد الحفظ من زر الصلاحيات.
                  </p>
                )}
              </div>
            )}

            <div className="rounded-xl bg-sand-50 border border-sand-200 p-3 space-y-3">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium text-neutral-700">عمولة على المبيعات</p>
                  <p className="text-xs text-neutral-500 mt-0.5">
                    تُحسب تلقائياً من إجمالي الوردية عند إغلاقها
                  </p>
                </div>
                <input
                  type="checkbox"
                  checked={form.commission_active}
                  onChange={(e) => setForm({ ...form, commission_active: e.target.checked })}
                  className="h-4 w-4 accent-brand-600"
                />
              </div>
              {form.commission_active && (
                <Input
                  label="نسبة العمولة (%)"
                  type="number"
                  min="0"
                  max="100"
                  step="0.1"
                  value={form.commission_percent}
                  onChange={(e) => setForm({ ...form, commission_percent: Number(e.target.value) })}
                />
              )}
            </div>

            <div className="rounded-xl bg-sand-50 border border-sand-200 p-3 space-y-3">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium text-neutral-700">دخول متعدد الفروع</p>
                  <p className="text-xs text-neutral-500 mt-0.5">
                    يتيح للموظف فتح ورديات في أكثر من فرع
                  </p>
                </div>
                <input
                  type="checkbox"
                  checked={form.multi_branch_access}
                  onChange={(e) => setForm({ ...form, multi_branch_access: e.target.checked })}
                  className="h-4 w-4 accent-brand-600"
                />
              </div>
              {editing && (
                <div className="flex items-center justify-between border-t border-sand-200 pt-3">
                  <span className="text-sm font-medium text-neutral-700">موظف نشط</span>
                  <input
                    type="checkbox"
                    checked={form.is_active}
                    onChange={(e) => setForm({ ...form, is_active: e.target.checked })}
                    className="h-4 w-4 accent-brand-600"
                  />
                </div>
              )}
            </div>

            {!editing && (
              <div className="rounded-xl bg-sand-50 border border-sand-200 p-3 text-xs text-neutral-500 flex items-start gap-2">
                <Shield size={14} className="mt-0.5 shrink-0 text-brand-600" />
                يُنشأ الموظف بصلاحيات الدور المختار — يمكنك تعديل الصلاحيات لاحقاً من زر الصلاحيات في الجدول.
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

        <PermissionsModal
          open={!!permsTarget}
          employeeName={permsTarget?.name || ''}
          info={sectionsInfo}
          initialRole={permsTarget?.role || 'admin'}
          initialPermissions={permsTarget?.permissions}
          initialHidden={permsTarget?.hidden_sections || []}
          initialAllowedBranches={permsTarget?.allowed_branches || []}
          branches={branches}
          saving={permsSaving}
          onClose={() => setPermsTarget(null)}
          onSave={handleSavePermissions}
        />

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