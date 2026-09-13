'use client';

interface SwitchProps {
  checked: boolean;
  onChange: (checked: boolean) => void;
  disabled?: boolean;
  size?: 'sm' | 'md';
  className?: string;
  'aria-label'?: string;
}

export default function Switch({ checked, onChange, disabled, size = 'md', className = '', ...rest }: SwitchProps) {
  const w = size === 'sm' ? 'w-9 h-5' : 'w-11 h-6';
  const dot = size === 'sm' ? 'w-4 h-4' : 'w-5 h-5';
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      disabled={disabled}
      onClick={() => onChange(!checked)}
      className={`
        relative inline-flex items-center rounded-full transition-colors duration-200
        ${w}
        ${checked ? 'bg-emerald-500' : 'bg-sand-300 dark:bg-neutral-600'}
        ${disabled ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'}
        ${className}
      `}
      {...rest}
    >
      <span className={`inline-flex w-full ${checked ? 'justify-end' : 'justify-start'}`}>
        <span
          className={`${dot} rounded-full bg-white shadow transition-transform duration-200`}
          style={{ margin: size === 'sm' ? 2 : 3 }}
        />
      </span>
    </button>
  );
}