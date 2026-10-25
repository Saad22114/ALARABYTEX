'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import {
  LayoutDashboard,
  MapPinned,
  Truck,
  ContactRound,
  ShoppingCart,
  ReceiptText,
  ChartNoAxesCombined,
  Settings2,
  Layers,
  Warehouse,
  X,
  Scissors,
  UserCog,
  Calculator,
  CalendarClock,
  MessagesSquare,
  Palette,
  WalletCards,
  Landmark,
  CircleDollarSign,
  Handshake,
  QrCode,
} from 'lucide-react';
import { useLayoutEffect, useRef, useState } from 'react';
import { Fragment } from 'react';
import { useSettings } from '@/components/providers/SettingsProvider';
import { useAuth } from '@/components/providers/AuthProvider';
import { logoUrl } from '@/services/settings';

const navItems = [
  { key: 'dashboard', href: '/', label: 'الرئيسية', icon: LayoutDashboard, iconColor: 'text-sky-300' },
  { key: 'sales', href: '/sales', label: 'المبيعات', icon: ShoppingCart, iconColor: 'text-emerald-300' },
  { key: 'sales-links', href: '/sales-links', label: 'روابط التواصل والتحويل', icon: QrCode, iconColor: 'text-pink-300' },
  { key: 'warehouses', href: '/warehouses', label: 'المخازن', icon: Warehouse, iconColor: 'text-amber-300' },
  { key: 'branches', href: '/branches', label: 'الفروع', icon: MapPinned, iconColor: 'text-violet-300' },
  { key: 'expenses', href: '/expenses', label: 'المصاريف', icon: ReceiptText, iconColor: 'text-rose-300' },
  { key: 'reports', href: '/reports', label: 'التقارير', icon: ChartNoAxesCombined, iconColor: 'text-cyan-300' },
  { key: 'suppliers', href: '/suppliers', label: 'الموردون', icon: Truck, iconColor: 'text-orange-300' },
  { key: 'customers', href: '/customers', label: 'الزبائن', icon: ContactRound, iconColor: 'text-blue-300' },
  { key: 'fabrics', href: '/fabrics', label: 'الأقمشة', icon: Scissors, iconColor: 'text-lime-300' },
  { key: 'employees', href: '/employees', label: 'الموظفون', icon: UserCog, iconColor: 'text-indigo-300' },
  { key: 'attendance', href: '/attendance', label: 'الحضور', icon: CalendarClock, iconColor: 'text-teal-300' },
  { key: 'payroll', href: '/payroll', label: 'الرواتب', icon: WalletCards, iconColor: 'text-yellow-200' },
  { key: 'my-salary', href: '/my-salary', label: 'راتبي', icon: CircleDollarSign, iconColor: 'text-green-300' },
  { key: 'accounting', href: '/accounting', label: 'المحاسبة', icon: Calculator, iconColor: 'text-purple-300' },
  { key: 'machine_account', href: '/machine-account', label: 'التسويات المالية', icon: Landmark, iconColor: 'text-fuchsia-300' },
  { key: 'messages', href: '/messages', label: 'التواصل', icon: MessagesSquare, iconColor: 'text-cyan-200' },
  { key: 'themes', href: '/themes', label: 'الثيمات والتحكم', icon: Palette, iconColor: 'text-fuchsia-200' },
  { key: 'settings', href: '/settings', label: 'الإعدادات', icon: Settings2, iconColor: 'text-slate-200' },
  { key: 'partners', href: '/partners', label: 'الشركاء', icon: Handshake, iconColor: 'text-orange-200' },
];

// عناوين عرضية لتنظيم القائمة بصرياً؛ لا تغيّر الروابط أو الصلاحيات أو ترتيبها.
const navGroupTitles: Record<string, string> = {
  dashboard: 'نظرة عامة',
  sales: 'التشغيل اليومي',
  'sales-links': 'دليل الزبائن',
  suppliers: 'دليل المتجر',
  payroll: 'الموظفون والرواتب',
  accounting: 'الإدارة المالية',
  messages: 'التواصل والتحكم',
  partners: 'الشركاء',
};

interface SidebarProps {
  open: boolean;
  onClose: () => void;
}

export default function Sidebar({ open, onClose }: SidebarProps) {
  const pathname = usePathname();
  const navRef = useRef<HTMLElement>(null);
  const [logoPreviewOpen, setLogoPreviewOpen] = useState(false);
  const { settings } = useSettings();
  const { session } = useAuth();

  useLayoutEffect(() => {
    try {
      const saved = sessionStorage.getItem('sidebar-scroll-top');
      if (saved !== null && navRef.current) navRef.current.scrollTop = Number(saved) || 0;
    } catch {}
  }, [pathname]);

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
          fixed right-0 top-0 bottom-0 w-72 bg-gradient-to-b from-brand-900 via-brand-950 to-brand-950 text-[#f3f1ec] flex flex-col
          z-50 lg:z-40 no-print
          transition-transform duration-300 ease-in-out
          ${open ? 'translate-x-0' : 'translate-x-full'}
          lg:translate-x-0
        `}
      >
        <div className="relative overflow-hidden border-b border-white/[0.09] px-5 pb-5 pt-6 bg-gradient-to-br from-brand-800 via-brand-900 to-brand-950">
          <div aria-hidden="true" className="absolute -left-10 -top-16 h-40 w-40 rounded-full bg-brand-300/[0.12] blur-3xl" />
          <div aria-hidden="true" className="absolute bottom-0 right-0 h-px w-2/3 bg-gradient-to-l from-brand-300/45 to-transparent" />
          <div className="flex items-center justify-between">
              <div className="relative flex min-w-0 items-center gap-3">
                {logoUrl(settings?.logo) ? (
                  <button
                    type="button"
                    onClick={() => setLogoPreviewOpen(true)}
                    aria-label="عرض الشعار بحجم كبير"
                    className="h-[54px] w-[54px] shrink-0 rounded-[18px] border border-white/25 bg-white p-1 shadow-xl shadow-black/20 cursor-zoom-in focus:outline-none focus:ring-2 focus:ring-brand-300"
                  >
                    <img
                      src={logoUrl(settings?.logo)}
                      alt="شعار الموقع"
                      className="h-full w-full rounded-xl object-contain"
                    />
                  </button>
                ) : (
                  <div className="flex h-[54px] w-[54px] shrink-0 items-center justify-center rounded-[18px] border border-brand-300/25 bg-gradient-to-br from-brand-300/20 via-brand-400/10 to-white/[0.03] shadow-inner">
                    <Layers size={24} className="text-brand-200" strokeWidth={1.7} />
                  </div>
                )}
                <div className="min-w-0">
                  <div className="mb-1 flex items-center gap-1.5">
                    <span className="h-1.5 w-1.5 rounded-full bg-brand-300" />
                    <span className="text-[9px] font-semibold tracking-[0.2em] text-brand-100/80">Alaraby Tex</span>
                  </div>
                  <h1 className="truncate text-[15px] font-bold leading-5 text-white">{settings?.business_name || 'القماش العربي'}</h1>
                  <p className="mt-1 text-[10px] text-white/45">نظام إدارة الأعمال</p>
                </div>
              </div>
            <button
              onClick={onClose}
                    className="lg:hidden rounded-xl border border-white/10 bg-white/5 p-2 text-[#e8e4db] transition-colors hover:border-brand-300/30 hover:bg-brand-300/10"
              aria-label="إغلاق القائمة"
            >
              <X size={20} />
            </button>
          </div>
        </div>

        <nav
          ref={navRef}
          onScroll={(event) => {
            try { sessionStorage.setItem('sidebar-scroll-top', String(event.currentTarget.scrollTop)); } catch {}
          }}
          className="flex-1 overflow-y-auto px-3 pb-4 pt-3"
        >
          {visibleItems.map((item) => {
            const active = isActive(item.href);
            const Icon = item.icon;
            return (
              <Fragment key={item.href}>
                {navGroupTitles[item.key] && (
                  <div className="mb-1 mt-5 flex items-center gap-2 px-3 first:mt-1">
                    <span className="text-[9px] font-bold tracking-[0.13em] text-white/35">{navGroupTitles[item.key]}</span>
                    <span className="h-px flex-1 bg-white/[0.07]" />
                  </div>
                )}
                <Link
                  href={item.href}
                  onClick={onClose}
                  aria-current={active ? 'page' : undefined}
                  className={`
                    group relative mb-1 flex items-center gap-3 rounded-[13px] border px-3 py-2 text-[13px] font-medium
                    transition-all duration-200 hover:translate-x-[-2px] hover:border-brand-300/20 hover:bg-brand-300/[0.07]
                    ${active
                      ? 'border-brand-300/25 bg-gradient-to-l from-brand-300/[0.18] via-brand-400/[0.09] to-white/[0.025] text-white shadow-[inset_0_1px_0_rgba(255,255,255,0.06),0_5px_14px_rgba(0,0,0,0.16)]'
                      : 'border-transparent text-[#e8e4db]/60 hover:text-white/95'}
                  `}
                >
                  {active && <span aria-hidden="true" className="absolute right-0 top-1/2 h-7 w-[3px] -translate-y-1/2 rounded-l-full bg-gradient-to-b from-brand-200 via-brand-300 to-brand-500 shadow-lg shadow-brand-500/30" />}
                  <span className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-[11px] border transition-all duration-200 ${active ? `border-brand-200/25 bg-gradient-to-br from-brand-300/25 via-brand-400/15 to-white/[0.04] ${item.iconColor} shadow-[0_2px_10px_rgba(0,0,0,0.18)]` : `border-white/[0.045] bg-white/[0.025] ${item.iconColor} group-hover:border-brand-200/20 group-hover:bg-brand-300/[0.09] group-hover:text-white`}`}>
                    <Icon size={19} strokeWidth={active ? 2.05 : 1.8} />
                  </span>
                  <span className="min-w-0 flex-1 truncate">{item.label}</span>
                  {active && <span aria-hidden="true" className="h-1.5 w-1.5 shrink-0 rounded-full bg-brand-200 shadow-[0_0_8px_rgba(255,255,255,0.45)]" />}
                </Link>
              </Fragment>
            );
          })}
        </nav>

        <div className="border-t border-white/10 px-4 py-4">
          <div className="flex items-center justify-between rounded-xl border border-brand-300/15 bg-gradient-to-l from-brand-300/[0.09] via-white/[0.035] to-white/[0.015] px-3 py-2.5 shadow-inner shadow-white/[0.02]">
            <div className="flex items-center gap-2">
              <span className="h-2 w-2 rounded-full bg-brand-300 shadow-[0_0_8px_rgba(255,255,255,0.35)]" />
              <span className="text-[11px] font-medium text-white/55">نظام إدارة الأعمال</span>
            </div>
            <span className="rounded-md bg-white/[0.06] px-1.5 py-0.5 font-mono text-[9px] text-white/35">1.0.0</span>
          </div>
        </div>
      </aside>
      {logoPreviewOpen && logoUrl(settings?.logo) && (
        <div
          role="dialog"
          aria-modal="true"
          aria-label="صورة الشعار"
          className="fixed inset-0 z-[100] flex items-center justify-center bg-black/80 p-6"
          onClick={() => setLogoPreviewOpen(false)}
        >
          <button
            type="button"
            onClick={() => setLogoPreviewOpen(false)}
            aria-label="إغلاق الصورة"
            className="absolute right-5 top-5 rounded-full bg-white/15 p-3 text-white transition hover:bg-white/25 focus:outline-none focus:ring-2 focus:ring-white"
          >
            <X size={24} />
          </button>
          <img
            src={logoUrl(settings?.logo)}
            alt="شعار الموقع بحجم كبير"
            onClick={(event) => event.stopPropagation()}
            className="max-h-[90vh] max-w-[90vw] rounded-xl bg-white object-contain p-3 shadow-2xl"
          />
        </div>
      )}
    </>
  );
}
