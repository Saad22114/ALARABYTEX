export const FONT_SCALE_STORAGE_KEY = 'qomash:ui-font-scale';
export const DEFAULT_FONT_SCALE = 100;
export const MIN_FONT_SCALE = 85;
export const MAX_FONT_SCALE = 120;
export const FONT_SCALE_STEP = 5;

export function normalizeFontScale(value: number): number {
  if (!Number.isFinite(value)) return DEFAULT_FONT_SCALE;
  return Math.min(MAX_FONT_SCALE, Math.max(MIN_FONT_SCALE, Math.round(value / FONT_SCALE_STEP) * FONT_SCALE_STEP));
}

export function applyFontScale(value: number): number {
  const normalized = normalizeFontScale(value);
  document.documentElement.style.setProperty('--app-font-scale', String(normalized / 100));
  return normalized;
}

export function loadFontScale(): number {
  try {
    const saved = localStorage.getItem(FONT_SCALE_STORAGE_KEY);
    return saved === null ? DEFAULT_FONT_SCALE : normalizeFontScale(Number(saved));
  } catch {
    return DEFAULT_FONT_SCALE;
  }
}
