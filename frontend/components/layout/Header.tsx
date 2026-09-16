'use client';

import { usePathname } from 'next/navigation';
import { Menu, Sun, Moon } from 'lucide-react';
import { formatArabicDate } from '@/lib/format';
import { useTheme } from '@/components/providers/ThemeProvider';
import NotificationsBell from './NotificationsBell';
import { useEffect, useState } from 'react';

const titles: Record<string, { title: string; subtitle?: string }> = {
  '/': { title: 'الرئيسية', subtitle: 'لوحة التحكم' },
  '/branches': { title: 'الفروع', subtitle: 'إدارة الفروع' },
  '/suppliers': { title: 'الموردون', subtitle: 'إدارة الموردين' },
  '/customers': { title: 'الزبائن', subtitle: 'تسجيل بيانات الزبائن والبحث بالهاتف' },
  '/fabrics': { title: 'الأقمشة', subtitle: 'ملف الأقمشة' },
  '/sales': { title: 'المبيعات', subtitle: 'تسجيل المبيعات وورديات البيع' },
  '/employees': { title: 'الموظفون', subtitle: 'إدارة الموظفين وربطهم بالفروع' },
  '/warehouses': { title: 'المخازن', subtitle: 'إدارة المخازن والأقمشة والمخزون' },
  '/expenses': { title: 'المصاريف', subtitle: 'تسجيل ومتابعة المصاريف' },
  '/reports': { title: 'التقارير', subtitle: 'التقارير المالية والإدارية' },
  '/accounting': { title: 'المحاسبة', subtitle: 'الدفاتر والقوائم المالية والخزينة' },
  '/messages': { title: 'التواصل', subtitle: 'الرسائل المباشرة بين الموظفين' },
  '/settings': { title: 'الإعدادات', subtitle: 'إعدادات النظام' },
};

interface HeaderProps {
  onMenuClick: () => void;
}

export default function Header({ onMenuClick }: HeaderProps) {
  const pathname = usePathname();
  const [mounted, setMounted] = useState(false);
  const today = formatArabicDate(new Date());
  const { dark, toggleDark } = useTheme();

  useEffect(() => {
    setMounted(true);
  }, []);

  let match = titles[pathname];
  if (!match) {
    if (pathname.startsWith('/branches/')) match = titles['/branches'];
    else if (pathname.startsWith('/suppliers/')) match = titles['/suppliers'];
    else match = titles['/'];
  }

  return (
    <header className="sticky top-0 z-30 bg-surface border-b border-sand-200 shadow-sm no-print">
      <div className="flex items-center justify-between px-4 sm:px-8 py-4 gap-3">
        <div className="flex items-center gap-3 min-w-0">
          <button
            onClick={onMenuClick}
            className="lg:hidden p-2 rounded-xl hover:bg-sand-100 text-neutral-600 transition-colors"
            aria-label="فتح القائمة"
          >
            <Menu size={22} />
          </button>
          <div className="min-w-0">
            <h2 className="text-lg sm:text-xl font-bold text-neutral-800 truncate">{match.title}</h2>
            {match.subtitle && (
              <p className="text-sm text-neutral-400 mt-0.5 hidden sm:block">{match.subtitle}</p>
            )}
          </div>
        </div>
        <div className="flex items-center gap-1 sm:gap-4 shrink-0">
          <button
            onClick={toggleDark}
            aria-label="تبديل الوضع الليلي"
            className="p-2 rounded-xl hover:bg-sand-100 text-neutral-600 dark:text-neutral-300 transition-colors"
          >
            {dark ? <Sun size={20} /> : <Moon size={20} />}
          </button>
          <NotificationsBell />
          {mounted && <span className="hidden md:inline text-sm text-neutral-500">{today}</span>}
          <div className="hidden md:block w-px h-6 bg-sand-200" />
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-full bg-brand-100 dark:bg-brand-500/20 flex items-center justify-center">
              <span className="text-brand-700 dark:text-brand-300 text-sm font-semibold">م</span>
            </div>
            <span className="hidden sm:inline text-sm font-medium text-neutral-600">عميل</span>
          </div>
        </div>
      </div>
    </header>
  );
}