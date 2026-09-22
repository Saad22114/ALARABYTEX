export interface AvatarDef {
  emoji: string;
  bg: string;
}

export const AVATARS: AvatarDef[] = [
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
];

export function avatarOf(avatar?: string | null): AvatarDef | null {
  if (!avatar) return null;
  return AVATARS.find((a) => a.emoji === avatar) || null;
}