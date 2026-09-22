import { EmployeePermissions, AppSection, RolePreset } from '@/types';

export function emptyPermissions(sections: AppSection[]): EmployeePermissions {
  return sections.reduce<EmployeePermissions>((acc, s) => {
    acc[s.key] = {
      view: s.key === 'dashboard',
      create: false,
      edit: false,
      delete: false,
      windows: (s.windows || []).map((w) => w.key),
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
      ...(perms[sectionKey] || { view: false, create: false, edit: false, delete: false, windows: [] }),
      [action]: value,
    },
  };
}

export function sectionWindows(perms: EmployeePermissions | null | undefined, sectionKey: string): string[] {
  const w = perms?.[sectionKey]?.windows;
  return Array.isArray(w) ? w : [];
}

export function hasWindow(perms: EmployeePermissions | null | undefined, sectionKey: string, windowKey: string): boolean {
  const w = perms?.[sectionKey]?.windows;
  if (!Array.isArray(w)) return true;
  return w.includes(windowKey);
}

export function toggleSectionWindow(perms: EmployeePermissions, sectionKey: string, windowKey: string): EmployeePermissions {
  const cur = perms[sectionKey] || { view: false, create: false, edit: false, delete: false };
  const windows = Array.isArray(cur.windows) ? [...cur.windows] : [];
  const next = windows.includes(windowKey)
    ? windows.filter((k) => k !== windowKey)
    : [...windows, windowKey];
  return { ...perms, [sectionKey]: { ...cur, windows: next } };
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
    const allWindows = (s.windows || []).map((w) => w.key);
    out[s.key] = {
      view: Boolean(cur?.view),
      create: Boolean(cur?.create),
      edit: Boolean(cur?.edit),
      delete: Boolean(cur?.delete),
      windows: Array.isArray(cur?.windows) ? cur.windows : allWindows,
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