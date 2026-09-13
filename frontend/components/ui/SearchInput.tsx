'use client';

import { Search } from 'lucide-react';

interface SearchInputProps {
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
}

export default function SearchInput({ value, onChange, placeholder = 'بحث...' }: SearchInputProps) {
  return (
    <div className="relative">
      <Search size={18} className="absolute right-3 top-1/2 -translate-y-1/2 text-neutral-400" />
      <input
        dir="rtl"
        type="text"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className="w-full rounded-xl border border-sand-300 pr-10 pl-4 py-2.5 text-sm bg-surface text-neutral-800 placeholder:text-neutral-400 focus:border-brand-500 focus:ring-2 focus:ring-brand-100 outline-none transition-colors"
      />
    </div>
  );
}
