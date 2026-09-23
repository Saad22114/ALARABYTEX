export interface AvatarDef {
  emoji: string;
  bg: string;
}

/**
 * المكتبة المظبوطة — **بالضبط 30 رمزاً** منوّعة (حيوانات، طيور، بحر، وجوه،
 * قلوب، طبيعة/فضاء) — يجب أن يطابق محتواها وترتيبها مع:
 * AVATAR_EMOJI في backend/sale_sessions/avatars.py
 *
 * ملاحظة التطابق:
 * - أول 16 عنصراً **محجوزة** (ترتيباً ومحتوى) — تعتمد اختباراتٌ قائمة عليها.
 * - أي قيمة خارج القائمة (أو أي data:image/... URL) تُقبل أيضاً كصورة شخصية
 *   مرفوعة من الجهاز (انظر AccountAvatarView في الباكند).
 */
export const AVATARS: AvatarDef[] = [
  // ——— المجموعة الأصلية المحجوزة (16) ———
  { emoji: '🦁', bg: 'bg-amber-100' },
  { emoji: '🐯', bg: 'bg-orange-100' },
  { emoji: '🐻', bg: 'bg-yellow-100' },
  { emoji: '🐼', bg: 'bg-neutral-100' },
  { emoji: '🐨', bg: 'bg-slate-200' },
  { emoji: '🐸', bg: 'bg-green-100' },
  { emoji: '🐙', bg: 'bg-fuchsia-100' },
  { emoji: '🦊', bg: 'bg-rose-100' },
  { emoji: '🐺', bg: 'bg-stone-200' },
  { emoji: '🦄', bg: 'bg-violet-100' },
  { emoji: '🐧', bg: 'bg-cyan-100' },
  { emoji: '🦉', bg: 'bg-teal-100' },
  { emoji: '🐵', bg: 'bg-amber-100' },
  { emoji: '🐳', bg: 'bg-sky-100' },
  { emoji: '🦋', bg: 'bg-blue-100' },
  { emoji: '🐢', bg: 'bg-lime-100' },
  // ——— المجموعة الجديدة (14) — ميكس بين كل الأنواع ———
  // طيور
  { emoji: '🦅', bg: 'bg-orange-100' },
  { emoji: '🦚', bg: 'bg-teal-100' },
  { emoji: '🦩', bg: 'bg-pink-100' },
  // بحر
  { emoji: '🦈', bg: 'bg-slate-200' },
  { emoji: '🐠', bg: 'bg-orange-100' },
  { emoji: '🦑', bg: 'bg-fuchsia-100' },
  // وجوه
  { emoji: '😺', bg: 'bg-yellow-100' },
  { emoji: '🤓', bg: 'bg-amber-100' },
  { emoji: '😎', bg: 'bg-slate-200' },
  { emoji: '🥳', bg: 'bg-violet-100' },
  // قلوب
  { emoji: '❤️', bg: 'bg-red-100' },
  { emoji: '💙', bg: 'bg-blue-100' },
  // طبيعة / فضاء
  { emoji: '🍀', bg: 'bg-green-100' },
  { emoji: '🪐', bg: 'bg-indigo-100' },
];

export function avatarOf(avatar?: string | null): AvatarDef | null {
  if (!avatar || avatar.startsWith('data:image/') || avatar.startsWith('http')) return null;
  return AVATARS.find((a) => a.emoji === avatar) || null;
}
