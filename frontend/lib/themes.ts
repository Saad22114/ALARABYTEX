export interface ThemePreset {
  id: string;
  name: string;
  swatch: string; // css color usable as background preview, e.g. '#1e6b56'
  description: string;
}

export const THEME_PRESETS: ThemePreset[] = [
  { id: 'green', name: 'أخضر', swatch: '#1e6b56', description: 'اللون الأساسي الافتراضي' },
  { id: 'blue', name: 'أزرق', swatch: '#2563eb', description: 'مهني وهادئ' },
  { id: 'violet', name: 'بنفسجي', swatch: '#7c3aed', description: 'أنيق وعصري' },
  { id: 'rose', name: 'وردي', swatch: '#e11d48', description: 'دافئ وحيوي' },
  { id: 'amber', name: 'ذهبي', swatch: '#d97706', description: 'فاخر وذهبي' },
];

export const STORAGE_KEYS = {
  theme: 'qomash_theme',
  dark: 'qomash_dark',
  settings: 'qomash_settings',
};