import React from 'react';
import { avatarOf } from '@/lib/avatars';

type AvatarSize = 'xs' | 'sm' | 'md' | 'lg';

interface AvatarProps {
  name: string;
  avatar?: string | null;
  size?: AvatarSize;
  className?: string;
  title?: string;
  onClick?: () => void;
}

const sizeClasses: Record<AvatarSize, string> = {
  xs: 'w-6 h-6 text-[10px]',
  sm: 'w-8 h-8 text-sm',
  md: 'w-9 h-9 text-sm',
  lg: 'w-10 h-10 text-base',
};

const emojiFontSize: Record<AvatarSize, number> = {
  xs: 13,
  sm: 16,
  md: 18,
  lg: 20,
};

export default function Avatar({ name, avatar, size = 'md', className = '', title, onClick }: AvatarProps) {
  const def = avatar ? avatarOf(avatar) : null;
  return (
    <span
      role={onClick ? 'button' : undefined}
      title={title}
      onClick={(e) => {
        if (onClick) {
          e.stopPropagation();
          onClick();
        }
      }}
      className={`${sizeClasses[size]} rounded-full inline-flex items-center justify-center shrink-0 font-bold select-none ${
        def ? def.bg : 'bg-sand-200 dark:bg-sand-700 text-neutral-700 dark:text-neutral-200'
      } ${onClick ? 'cursor-pointer hover:ring-2 hover:ring-brand-500/50' : ''} ${className}`}
    >
      {def ? (
        <span style={{ fontSize: emojiFontSize[size], lineHeight: 1 }}>{def.emoji}</span>
      ) : (
        name.trim()[0] || '؟'
      )}
    </span>
  );
}