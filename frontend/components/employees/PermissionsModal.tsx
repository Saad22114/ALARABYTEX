'use client';

import { Fragment, useEffect, useMemo, useState } from 'react';
import Modal from '@/components/ui/Modal';
import Button from '@/components/ui/Button';
import Badge from '@/components/ui/Badge';
import { Check, X, EyeOff, Plus } from 'lucide-react';
import { AppSection, EmployeePermissions, EmployeeRole, RolePreset, SectionsInfo } from '@/types';
import {
  emptyPermissions, normalizePermissions, roleHiddenPreset, rolePermissionPreset,
  setPermission, toggleHidden, toggleSectionWindow, sectionWindows,
} from '@/lib/permissions';

interface BranchOption {
  id: number;
  name: string;
}

interface Props {
  open: boolean;
  employeeName: string;
  info: SectionsInfo | null;
  initialRole: EmployeeRole;
  initialPermissions: EmployeePermissions | null | undefined;
  initialHidden: string[];
  initialAllowedBranches: number[];
  branches: BranchOption[];
  saving: boolean;
  onClose: () => void;
  onSave: (data: {
    role: EmployeeRole;
    permissions: EmployeePermissions;
    hidden_sections: string[];
    allowed_branches: number[];
  }) => void;
}

const ROLE_COLORS: Record<string, string> = {
  admin: 'bg-red-50 text-red-600 border-red-200 dark:bg-red-500/10 dark:text-red-400',
  supervisor: 'bg-violet-50 text-violet-600 border-violet-200 dark:bg-violet-500/10 dark:text-violet-400',
  sales: 'bg-emerald-50 text-emerald-600 border-emerald-200 dark:bg-emerald-500/10 dark:text-emerald-400',
  viewer: 'bg-sky-50 text-sky-600 border-sky-200 dark:bg-sky-500/10 dark:text-sky-400',
  custom: 'bg-amber-50 text-amber-600 border-amber-200 dark:bg-amber-500/10 dark:text-amber-400',
};

const ACTION_LABELS: Record<string, { label: string }> = {
  view: { label: 'عرض' },
  create: { label: 'إضافة' },
  edit: { label: 'تعديل' },
  delete: { label: 'حذف' },
};

export default function PermissionsModal({
  open, employeeName, info, initialRole, initialPermissions, initialHidden,
  initialAllowedBranches, branches, saving, onClose, onSave,
}: Props) {
  const sections = info?.sections || [];
  const [role, setRole] = useState<EmployeeRole>('admin');
  const [perms, setPerms] = useState<EmployeePermissions>({});
  const [hidden, setHidden] = useState<string[]>([]);
  const [allowedBranches, setAllowedBranches] = useState<number[]>([]);

  useEffect(() => {
    if (open) {
      setRole(initialRole);
      const base = rolePermissionPreset(info?.roles?.[initialRole], sections);
      setPerms(normalizePermissions(initialPermissions, sections, base));
      setHidden(initialHidden?.length ? [...initialHidden] : roleHiddenPreset(info?.roles?.[initialRole]));
      setAllowedBranches(initialAllowedBranches?.length ? [...initialAllowedBranches] : []);
    }
  }, [open, initialRole, initialPermissions, initialHidden, initialAllowedBranches, info, sections.length]);

  const sectionList = useMemo(
    () => [...sections].sort((a, b) => Number(a.fixed) - Number(b.fixed)),
    [sections]
  );

  const visibleSectionCount = sections.filter((s) => !hidden.includes(s.key)).length;

  const handleRoleSelect = (roleKey: EmployeeRole) => {
    setRole(roleKey);
    const preset = info?.roles?.[roleKey];
    if (preset) {
      setPerms(rolePermissionPreset(preset, sections));
      setHidden(roleHiddenPreset(preset));
    }
  };

  const handleSet = (sectionKey: string, action: string, value: boolean) => {
    setPerms((prev) => setPermission(prev, sectionKey, action, value));
  };

  const handleToggleHidden = (sectionKey: string) => {
    setHidden((prev) => toggleHidden(prev, sectionKey));
  };

  const handleToggleWindow = (sectionKey: string, windowKey: string) => {
    setPerms((prev) => toggleSectionWindow(prev, sectionKey, windowKey));
  };

  const handleSelectAll = (all: boolean) => {
    const next = { ...perms };
    for (const s of sections) {
      next[s.key] = {
        view: all,
        create: all,
        edit: all,
        delete: all,
        windows: (s.windows || []).map((w) => w.key),
      };
    }
    setPerms(next);
  };

  return (
    <Modal open={open} onClose={onClose} title={`صلاحيات: ${employeeName}`} maxWidth="max-w-4xl">
      <div className="space-y-5">
        {/* Role presets */}
        <div>
          <p className="text-sm font-medium text-neutral-700 mb-2">الدور (قالب جاهز للصلاحيات)</p>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2">
            {Object.entries(info?.roles || {}).map(([key, preset]) => (
              <button
                key={key}
                type="button"
                onClick={() => handleRoleSelect(key as EmployeeRole)}
                className={`flex items-start gap-2.5 p-3 rounded-xl border text-right transition-all duration-150 ${
                  role === key
                    ? 'border-brand-600 ring-2 ring-brand-200 bg-brand-50 dark:bg-brand-500/10'
                    : 'border-sand-200 bg-surface hover:border-sand-300 dark:bg-neutral-800'
                }`}
              >
                <span className={`mt-0.5 rounded-lg border px-2 py-0.5 text-xs font-semibold whitespace-nowrap ${ROLE_COLORS[key] || ''}`}>
                  {preset.label}
                </span>
                <span className="text-xs text-neutral-500 leading-relaxed">{preset.description}</span>
              </button>
            ))}
          </div>
        </div>

        {/* Branch access */}
        <div>
          <p className="text-sm font-medium text-neutral-700 mb-2">فروع الموظف (يفتحها جميعاً)</p>
          {branches.length === 0 ? (
            <p className="text-xs text-neutral-400">لا توجد فروع مسجلة بعد — أضف فرعاً أولاً.</p>
          ) : (
            <div className="flex flex-wrap gap-2">
              {branches.map((b) => {
                const enabled = allowedBranches.includes(b.id);
                return (
                  <button
                    key={b.id}
                    type="button"
                    onClick={() =>
                      setAllowedBranches((prev) =>
                        enabled ? prev.filter((id) => id !== b.id) : [...prev, b.id]
                      )
                    }
                    className={`flex items-center gap-1.5 rounded-xl border px-3 py-1.5 text-sm transition-colors ${
                      enabled
                        ? 'border-brand-500 bg-brand-500/10 text-brand-700 dark:text-brand-300'
                        : 'border-sand-200 text-neutral-500 hover:border-sand-300 dark:border-neutral-700'
                    }`}
                  >
                    {enabled ? <Check size={14} /> : <Plus size={14} />}
                    {b.name}
                  </button>
                );
              })}
            </div>
          )}
          <p className="text-xs text-neutral-400 mt-2">
            الفرع الأساسي في بطاقة الموظف يُضاف تلقائياً إلى هذه القائمة عند الدخول — اختر هنا الفروع الإضافية التي يفتحها الموظف.
          </p>
        </div>

        {/* Quick actions */}
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <Badge variant="neutral">اسحب القوالب لإعادة تطبيق الدور على الصلاحيات</Badge>
            <Badge variant={visibleSectionCount === sections.length ? 'success' : 'warning'}>
              {visibleSectionCount} من {sections.length} أقسام ظاهرة
            </Badge>
          </div>
          <div className="flex items-center gap-2">
            <Button size="sm" variant="secondary" onClick={() => handleSelectAll(false)}>
              <X size={14} />
              تعطيل الكل
            </Button>
            <Button size="sm" variant="secondary" onClick={() => handleSelectAll(true)}>
              <Check size={14} />
              تفعيل الكل
            </Button>
          </div>
        </div>

        {/* Permissions matrix */}
        <div className="overflow-x-auto rounded-xl border border-sand-200">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-sand-50 dark:bg-neutral-800">
                <th className="p-2.5 text-right font-semibold text-neutral-700 sticky right-0 bg-sand-50 dark:bg-neutral-800 min-w-[140px]">القسم</th>
                <th className="p-2.5 text-center font-semibold text-neutral-500">عرض</th>
                <th className="p-2.5 text-center font-semibold text-neutral-500">إضافة</th>
                <th className="p-2.5 text-center font-semibold text-neutral-500">تعديل</th>
                <th className="p-2.5 text-center font-semibold text-neutral-500">حذف</th>
                <th className="p-2.5 text-center font-semibold text-neutral-500">إخفاء من القائمة</th>
              </tr>
            </thead>
            <tbody>
              {sectionList.map((sec) => (
                <Fragment key={sec.key}>
                  <tr className="border-t border-sand-100 dark:border-neutral-700">
                    <td className="p-2.5 font-medium text-neutral-800">
                      <span className="flex items-center gap-2">
                        {sec.label}
                        {sec.fixed && <span className="text-xs text-neutral-400 font-normal">(دائم)</span>}
                      </span>
                    </td>
                    {(['view', 'create', 'edit', 'delete'] as string[]).map((action) => {
                      const allowed = sec.actions.includes(action);
                      return (
                        <td key={action} className="p-2.5 text-center">
                          <button
                            type="button"
                            onClick={() => handleSet(sec.key, action, !perms[sec.key]?.[action as keyof EmployeePermissions[string]])}
                            disabled={!allowed}
                            className={`mx-auto flex h-7 w-7 items-center justify-center rounded-lg border transition-colors ${
                              !allowed
                                ? 'opacity-25 cursor-not-allowed'
                                : perms[sec.key]?.[action as keyof EmployeePermissions[string]]
                                  ? 'bg-emerald-500 border-emerald-500 text-white hover:bg-emerald-600'
                                  : 'border-sand-300 text-neutral-300 hover:border-sand-400 hover:text-neutral-400 dark:border-neutral-600'
                            }`}
                            title={`${ACTION_LABELS[action]?.label} ${sec.label}`}
                          >
                            <Check size={15} />
                          </button>
                        </td>
                      );
                    })}
                    {!sec.fixed && (
                      <td className="p-2.5 text-center">
                        <button
                          type="button"
                          onClick={() => handleToggleHidden(sec.key)}
                          className={`mx-auto flex h-7 w-7 items-center justify-center rounded-lg border transition-colors ${
                            hidden.includes(sec.key)
                              ? 'bg-neutral-600 border-neutral-600 text-white'
                              : 'border-sand-300 text-neutral-300 hover:border-sand-400 hover:text-neutral-400 dark:border-neutral-600'
                          }`}
                          title="إخفاء من القائمة الجانبية"
                        >
                          <EyeOff size={15} />
                        </button>
                      </td>
                    )}
                    {sec.fixed && <td className="p-2.5" />}
                  </tr>
                  {sec.windows && sec.windows.length > 0 && (
                    <tr className="border-t border-sand-100/50 dark:border-neutral-800 bg-sand-50/40 dark:bg-neutral-800/40">
                      <td className="px-2.5 py-2 text-xs font-medium text-neutral-400 whitespace-nowrap">النوافذ</td>
                      <td colSpan={5} className="px-2.5 py-2">
                        <div className="flex flex-wrap gap-1.5">
                          {sec.windows.map((w) => {
                            const enabled = sectionWindows(perms, sec.key).includes(w.key);
                            return (
                              <button
                                key={w.key}
                                type="button"
                                onClick={() => handleToggleWindow(sec.key, w.key)}
                                className={`flex items-center gap-1.5 rounded-lg border px-2 py-1 text-xs transition-colors ${
                                  enabled
                                    ? 'border-emerald-300 bg-emerald-500/10 text-emerald-700 dark:text-emerald-300'
                                    : 'border-sand-200 text-neutral-400 hover:border-sand-300 dark:border-neutral-700'
                                }`}
                                title={`عرض ${w.label}`}
                              >
                                {enabled ? <Check size={12} /> : <X size={12} />}
                                {w.label}
                              </button>
                            );
                          })}
                        </div>
                      </td>
                    </tr>
                  )}
                </Fragment>
              ))}
            </tbody>
          </table>
        </div>

        <p className="text-xs text-neutral-400">
          ملاحظة: الصلاحيات محفوظة في النظام وقابلة للتعديل في أي وقت — تُستخدم حالياً كبيانات إدارية لكل موظف.
        </p>

        <div className="flex items-center justify-end gap-3 pt-2">
          <Button variant="secondary" onClick={onClose}>إلغاء</Button>
          <Button loading={saving} onClick={() => onSave({ role, permissions: perms, hidden_sections: hidden, allowed_branches: allowedBranches })}>
            حفظ الصلاحيات
          </Button>
        </div>
      </div>
    </Modal>
  );
}