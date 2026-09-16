import { EmployeePermissions, AppSection, RolePreset } from '@/types';

export function emptyPermissions(sections: AppSection[]): EmployeePermissions {
  return sections.reduce<EmployeePermissions>((acc, s) => {
    acc[s.key] = {
      view: s.key === 'dashboard',
      create: false,
      edit: false,
      delete: false,
    };
    return acc;
  }, {});
}

export function permissionValue(perms: EmployeePermissions, sectionKey: string, action: string): boolean {
  return Boolean(perms?.[sectionKey]?.[action as keyof EmployeePermissions[string]]);
}

export function setPermission(
  perms: EmployeePermissions,
  sectionKey: string,
  action: string,
  value: boolean
): EmployeePermissions {
  return {
    ...perms,
    [sectionKey]: {
      ...(perms[sectionKey] || { view: false, create: false, edit: false, delete: false }),
      [action]: value,
    },
  };
}

export function normalizePermissions(
  perms: EmployeePermissions | null | undefined,
  sections: AppSection[],
  fallback: EmployeePermissions
): EmployeePermissions {
  if (!perms) return fallback;
  const out: EmployeePermissions = {};
  for (const s of sections) {
    const cur = perms[s.key];
    out[s.key] = {
      view: Boolean(cur?.view),
      create: Boolean(cur?.create),
      edit: Boolean(cur?.edit),
      delete: Boolean(cur?.delete),
    };
  }
  return out;
}

export function rolePermissionPreset(preset: RolePreset | undefined, sections: AppSection[]): EmployeePermissions {
  return normalizePermissions(preset?.permissions, sections, emptyPermissions(sections));
}

export function roleHiddenPreset(preset: RolePreset | undefined): string[] {
  return preset?.hidden_sections || [];
}

export function sectionIsHidden(hidden: string[], sectionKey: string, fixed: boolean): boolean {
  if (fixed) return false;
  return hidden.includes(sectionKey);
}

export function toggleHidden(hidden: string[], sectionKey: string): string[] {
  return hidden.includes(sectionKey) ? hidden.filter((k) => k !== sectionKey) : [...hidden, sectionKey];
}