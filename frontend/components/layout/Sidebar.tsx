'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import {
  LayoutDashboard,
  Store,
  Truck,
  ContactRound,
  Banknote,
  ReceiptText,
  BarChart3,
  Settings,
  Layers,
  Boxes,
  X,
  Tags,
  Users,
  UserCog,
  Calculator,
  MessageSquareText,
  Palette,
} from 'lucide-react';
import { useSettings } from '@/components/providers/SettingsProvider';
import { useAuth } from '@/components/providers/AuthProvider';
import { logoUrl } from '@/services/settings';

const navItems = [
  { key: 'dashboard', href: '/', label: 'الرئيسية', icon: LayoutDashboard },
  { key: 'branches', href: '/branches', label: 'الفروع', icon: Store },
  { key: 'suppliers', href: '/suppliers', label: 'الموردون', icon: Truck },
  { key: 'customers', href: '/customers', label: 'الزبائن', icon: ContactRound },
  { key: 'partners', href: '/partners', label: 'الشركاء', icon: Users },
  { key: 'fabrics', href: '/fabrics', label: 'الأقمشة', icon: Tags },
  { key: 'sales', href: '/sales', label: 'المبيعات', icon: Banknote },
  { key: 'employees', href: '/employees', label: 'الموظفون', icon: UserCog },
  { key: 'warehouses', href: '/warehouses', label: 'المخازن', icon: Boxes },
  { key: 'expenses', href: '/expenses', label: 'المصاريف', icon: ReceiptText },
  { key: 'reports', href: '/reports', label: 'التقارير', icon: BarChart3 },
  { key: 'accounting', href: '/accounting', label: 'المحاسبة', icon: Calculator },
  { key: 'messages', href: '/messages', label: 'التواصل', icon: MessageSquareText },
  { key: 'themes', href: '/themes', label: 'الثيمات والتحكم', icon: Palette },
  { key: 'settings', href: '/settings', label: 'الإعدادات', icon: Settings },
];

interface SidebarProps {
  open: boolean;
  onClose: () => void;
}

export default function Sidebar({ open, onClose }: SidebarProps) {
  const pathname = usePathname();
  const { settings } = useSettings();
  const { session } = useAuth();

  const isActive = (href: string) => {
    if (href === '/') return pathname === '/';
    return pathname.startsWith(href);
  };

  const visible = (key: string): boolean => {
    const hidden = new Set([
      ...(session?.employee.hidden_sections || []),
      ...(settings?.hidden_sections || []),
    ]);
    if (hidden.has(key)) return false;
    if (key === 'dashboard') return true;
    // قسم «الثيمات والتحكم» مفتوح لكل الموظفين بغض النظر عن صلاحياتهم —
    // يظهر ما لم يُخفَ مركزياً من «أقسام القائمة» أو لكل موظف على حدة.
    if (key === 'themes') return true;
    const permissions = session?.employee.permissions;
    const perms = permissions ? permissions[key] : null;
    // الأقسام المقيدة بالنطاق: يظهر فرعُ الموظف في القائمة فقط بعد اكتمال
    // تحميل الإعدادات (المركزية) — يمنع الوميضَ الناتج عن إخفاءٍ مركزي
    // يُطبق متأخراً، ويُبقي الصفوف مقصورةً على نطاقه تطابقاً مع قاعدة الخلفية.
    const settingsReady = settings !== null;
    const hasScope =
      Boolean(session?.employee.branch) ||
      Boolean(session?.employee.allowed_branches?.length);
    if (settingsReady && hasScope && ['branches', 'sales', 'sessions'].includes(key))
      return true;
    return Boolean(perms && perms.view);
  };

  const visibleItems = navItems.filter((item) => visible(item.key));

  return (
    <>
      {open && (
        <div
          className="fixed inset-0 z-40 bg-black/50 lg:hidden"
          onClick={onClose}
          aria-hidden="true"
        />
      )}
      <aside
        className={`
          fixed right-0 top-0 bottom-0 w-72 bg-brand-950 text-[#f3f1ec] flex flex-col
          z-50 lg:z-40 no-print
          transition-transform duration-300 ease-in-out
          ${open ? 'translate-x-0' : 'translate-x-full'}
          lg:translate-x-0
        `}
      >
        <div className="px-6 py-6 border-b border-white/10">
          <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                {logoUrl(settings?.logo) ? (
                  <img
                    src={logoUrl(settings?.logo)}
                    alt="شعار الموقع"
                    className="w-9 h-9 rounded-xl object-contain bg-white p-0.5"
                  />
                ) : (
                  <div className="p-2 rounded-xl bg-gold-500/20">
                    <Layers size={24} className="text-gold-400" />
                  </div>
                )}
                <div>
                  <h1 className="text-xl font-bold text-white">{settings?.business_name || 'القماش العربي'}</h1>
                  <p className="text-xs text-[#d9d3c6]/60">نظام إدارة الأعمال</p>
                </div>
              </div>
            <button
              onClick={onClose}
              className="lg:hidden p-2 rounded-xl hover:bg-white/10 text-[#e8e4db] transition-colors"
              aria-label="إغلاق القائمة"
            >
              <X size={20} />
            </button>
          </div>
        </div>

        <nav className="flex-1 px-3 py-4 space-y-1 overflow-y-auto">
          {visibleItems.map((item) => {
            const active = isActive(item.href);
            const Icon = item.icon;
            return (
              <Link
                key={item.href}
                href={item.href}
                onClick={onClose}
                className={`
                  flex items-center gap-3 px-4 py-3 rounded-xl text-sm font-medium
                  transition-all duration-150
                  hover:translate-x-[-2px]
                  ${
                    active
                      ? 'bg-brand-700/60 text-white border-r-[3px] border-gold-400'
                      : 'text-[#e8e4db]/70 hover:bg-brand-800/50 hover:text-white'
                  }
                `}
              >
                <Icon size={20} />
                <span>{item.label}</span>
              </Link>
            );
          })}
        </nav>

        <div className="px-6 py-4 border-t border-white/10">
          <p className="text-[11px] text-[#d9d3c6]/40">إصدار النظام: 1.0.0</p>
        </div>
      </aside>
    </>
  );
}