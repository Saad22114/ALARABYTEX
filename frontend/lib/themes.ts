export interface ThemePreset {
  id: string;
  name: string;
  swatch: string; // css color usable as background preview, e.g. '#1e6b56'
  description: string;
}

export interface FontPreset {
  id: string;
  name: string;
  description: string;
}

export const FONT_PRESETS: FontPreset[] = [
  { id: 'cairo', name: 'Cairo', description: 'الخط الافتراضي — عصري وواضح' },
  { id: 'ibm', name: 'IBM Plex Sans Arabic', description: 'سانس بلا سيري — أنيق وحديث' },
  { id: 'amiri', name: 'Amiri', description: 'سيري كلاسيكي بروح الخط النسخي' },
  { id: 'noto', name: 'Noto Sans Arabic', description: 'سانس موحد واضح وقابل للقراءة' },
  { id: 'almarai', name: 'Almarai', description: 'خط عربي حديث وواضح للواجهات' },
  { id: 'tajawal', name: 'Tajawal', description: 'خط عربي عصري ونظيف' },
  { id: 'rubik', name: 'Rubik', description: 'خط هندسي متوازن يدعم العربية' },
  { id: 'changa', name: 'Changa', description: 'خط عربي عريض وبارز' },
  { id: 'mada', name: 'Mada', description: 'خط عربي رفيع وأنيق' },
];

export const FONT_SCALE_OPTIONS = [
  { value: 90, label: 'صغير' },
  { value: 100, label: 'عادي' },
  { value: 115, label: 'متوسط' },
  { value: 130, label: 'كبير' },
  { value: 150, label: 'كبير جداً' },
];

export const THEME_PRESETS: ThemePreset[] = [
  { id: 'green', name: 'أخضر', swatch: '#1e6b56', description: 'اللون الأساسي الافتراضي' },
  { id: 'blue', name: 'أزرق', swatch: '#2563eb', description: 'مهني وهادئ' },
  { id: 'violet', name: 'بنفسجي', swatch: '#7c3aed', description: 'أنيق وعصري' },
  { id: 'rose', name: 'وردي', swatch: '#e11d48', description: 'دافئ وحيوي' },
  { id: 'amber', name: 'ذهبي', swatch: '#d97706', description: 'فاخر وذهبي' },
  { id: 'cyan', name: 'سماوي', swatch: '#0d9488', description: 'منعش وهادئ' },
  { id: 'orange', name: 'برتقالي', swatch: '#ea580c', description: 'مفعم بالطاقة' },
  { id: 'red', name: 'أحمر', swatch: '#dc2626', description: 'جريء وقوي' },
  { id: 'pink', name: 'زهري', swatch: '#be185d', description: 'ناعم ومشرق' },
  { id: 'indigo', name: 'نيلي', swatch: '#4f46e5', description: 'غامق ومركز' },
  { id: 'teal', name: 'أخضر مائي', swatch: '#059669', description: 'طبيعي وساحلي' },
  { id: 'fuchsia', name: 'فوشيا', swatch: '#c026d3', description: 'مبهرج وعصري' },
  { id: 'lime', name: 'ليموني', swatch: '#65a30d', description: 'مشمس وحيوي' },
  { id: 'slate', name: 'رمادي أردوازي', swatch: '#475569', description: 'محايد واحترافي' },
  { id: 'maroon', name: 'نبيذي', swatch: '#7f1d1d', description: 'عميق وأنيق' },
  { id: 'burgundy', name: 'برغندي', swatch: '#800020', description: 'غامق وفاخر' },
  { id: 'lilac', name: 'ليلكي', swatch: '#9564DD', description: 'بنفسجي ناعم' },
  { id: 'forest', name: 'أخضر غابة', swatch: '#2A835F', description: 'طبيعي وهادئ' },
  { id: 'plum', name: 'خوخي داكن', swatch: '#601D49', description: 'أرجواني غامق' },
  { id: 'navy', name: 'كحلي', swatch: '#253C6D', description: 'أزرق داكن رسمي' },
  { id: 'beige', name: 'بيج', swatch: '#f5f5dc', description: 'عاجي فاتح وهادئ' },
];

export const STORAGE_KEYS = {
  theme: 'qomash_theme',
  dark: 'qomash_dark',
  font: 'qomash_font',
  fontScale: 'qomash_font_scale',
  settings: 'qomash_settings',
};