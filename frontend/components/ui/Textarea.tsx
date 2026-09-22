'use client';

import React from 'react';

interface TextareaProps extends React.TextareaHTMLAttributes<HTMLTextAreaElement> {
  label?: string;
  error?: string;
}

export default function Textarea({ label, error, className = '', required, ...props }: TextareaProps) {
  return (
    <div className="space-y-1.5">
      {label && (
        <label className="block text-sm font-medium text-neutral-700">
          {label}
          {required && <span className="text-red-500"> *</span>}
        </label>
      )}
      <textarea
        dir="rtl"
        required={required}
        className={`
          w-full rounded-xl border px-4 py-2.5 text-sm
          bg-surface text-neutral-800 placeholder:text-neutral-400
          border-sand-300 focus:border-brand-500 focus:ring-2 focus:ring-brand-100
          outline-none transition-colors duration-150 resize-y min-h-[80px]
          ${error ? 'border-red-400 focus:border-red-500 focus:ring-red-100' : ''}
          ${className}
        `}
        {...props}
      />
      {error && <p className="text-xs text-red-500">{error}</p>}
    </div>
  );
}
