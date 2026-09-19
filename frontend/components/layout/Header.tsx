'use client';

import { usePathname } from 'next/navigation';
import { Menu, Sun, Moon, LogOut } from 'lucide-react';
import { formatArabicDate } from '@/lib/format';
import { useTheme } from '@/components/providers/ThemeProvider';
import { useAuth } from '@/components/providers/AuthProvider';
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
  const [cardOpen, setCardOpen] = useState(false);
  const today = formatArabicDate(new Date());
  const { dark, toggleDark } = useTheme();
  const { employee, logout } = useAuth();

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
          <div className="relative flex items-center gap-2">
            <button
              onClick={() => setCardOpen((v) => !v)}
              className="flex items-center gap-2 p-1 rounded-xl hover:bg-sand-100 dark:hover:bg-white/5 transition-colors"
              aria-label="ملف الموظف"
              title="ملف الموظف"
            >
              <div className="w-8 h-8 rounded-full bg-brand-100 dark:bg-brand-500/20 flex items-center justify-center">
                <span className="text-brand-700 dark:text-brand-300 text-sm font-semibold">
                  {(employee?.name || 'م').trim().charAt(0)}
                </span>
              </div>
              <span className="hidden sm:inline text-sm font-medium text-neutral-600">{employee?.name || 'قيد الدخول'}</span>
            </button>

            {cardOpen && (
              <>
                <div className="fixed inset-0 z-40" onClick={() => setCardOpen(false)} />
                <div className="absolute top-full left-0 mt-2 w-64 rounded-2xl bg-white dark:bg-neutral-800 border border-sand-200 dark:border-neutral-700 shadow-xl z-50 p-4 text-right">
                  <div className="flex items-center gap-3 border-b border-sand-100 dark:border-neutral-700 pb-3">
                    <div className="w-11 h-11 rounded-full bg-brand-100 dark:bg-brand-500/20 flex items-center justify-center">
                      <span className="text-brand-700 dark:text-brand-300 text-lg font-semibold">
                        {(employee?.name || 'م').trim().charAt(0)}
                      </span>
                    </div>
                    <div className="min-w-0">
                      <p className="font-bold text-sm text-neutral-800 dark:text-neutral-100 truncate">{employee?.name}</p>
                      {employee?.username && (
                        <p className="text-xs text-neutral-400 truncate" dir="ltr">{employee.username}</p>
                      )}
                    </div>
                  </div>
                  <dl className="mt-3 space-y-2 text-sm">
                    <div className="flex items-center justify-between gap-2">
                      <dt className="text-neutral-400 text-xs">الدور</dt>
                      <dd className="font-medium text-neutral-700 dark:text-neutral-200">{employee?.role_label || '—'}</dd>
                    </div>
                    <div className="flex items-center justify-between gap-2">
                      <dt className="text-neutral-400 text-xs">الفرع</dt>
                      <dd className="font-medium text-neutral-700 dark:text-neutral-200">{employee?.branch_name || '—'}</dd>
                    </div>
                    <div className="flex items-center justify-between gap-2">
                      <dt className="text-neutral-400 text-xs">الهاتف</dt>
                      <dd className="font-medium text-neutral-700 dark:text-neutral-200 tabular-nums" dir="ltr">{employee?.phone || '—'}</dd>
                    </div>
                    <div className="flex items-center justify-between gap-2">
                      <dt className="text-neutral-400 text-xs">الحالة</dt>
                      <dd className="flex items-center gap-1.5 text-emerald-600 font-medium">
                        <span className="w-2 h-2 rounded-full bg-emerald-500" />
                        متصل
                      </dd>
                    </div>
                  </dl>
                  <button
                    onClick={() => {
                      logout().then(() => window.location.assign('/login'));
                    }}
                    className="mt-4 w-full flex items-center justify-center gap-2 rounded-xl bg-red-50 dark:bg-red-500/15 text-red-600 dark:text-red-400 px-3 py-2 text-sm font-medium hover:bg-red-100 dark:hover:bg-red-500/25 transition-colors"
                  >
                    <LogOut size={16} />
                    تسجيل الخروج
                  </button>
                </div>
              </>
            )}
          </div>
        </div>
      </div>
    </header>
  );
}