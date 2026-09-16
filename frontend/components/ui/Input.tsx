'use client';

import React from 'react';

interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  error?: string;
}

export default function Input({ label, error, className = '', type, inputMode, pattern, onKeyDown, ...props }: InputProps) {
  const isNumber = type === 'number';

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (isNumber && e.key.length === 1 && !/[0-9.]/.test(e.key)) {
      e.preventDefault();
    }
    onKeyDown?.(e);
  };

  return (
    <div className="space-y-1.5">
      {label && (
        <label className="block text-sm font-medium text-neutral-700">{label}</label>
      )}
      <input
        dir="rtl"
        type={type}
        inputMode={isNumber ? (inputMode ?? 'decimal') : inputMode}
        pattern={isNumber ? (pattern ?? '[0-9.]*') : pattern}
        onKeyDown={isNumber ? handleKeyDown : onKeyDown}
        className={`
          w-full rounded-xl border px-4 py-2.5 text-sm
          bg-surface text-neutral-800 placeholder:text-neutral-400
          border-sand-300 focus:border-brand-500 focus:ring-2 focus:ring-brand-100
          outline-none transition-colors duration-150
          ${error ? 'border-red-400 focus:border-red-500 focus:ring-red-100' : ''}
          ${className}
        `}
        {...props}
      />
      {error && <p className="text-xs text-red-500">{error}</p>}
    </div>
  );
}
