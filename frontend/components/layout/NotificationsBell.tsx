'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import Link from 'next/link';
import { AlertTriangle, Bell, BellRing, MessageSquareText, RefreshCw, Volume2, VolumeX, Wallet } from 'lucide-react';
import { getDashboardAlerts } from '@/services/dashboard';
import { DashboardAlertsResult } from '@/types';
import { formatCurrency, formatNumber } from '@/lib/format';
import { useCurrentEmployee } from '@/components/providers/CurrentEmployeeProvider';
import { AppNotification, getNotifications, markAllNotificationsRead, markNotificationRead } from '@/services/notifications';
import { useToast } from '@/components/ui/Toast';

export default function NotificationsBell() {
  const [open, setOpen] = useState(false);
  const [alerts, setAlerts] = useState<DashboardAlertsResult | null>(null);
  const [notifications, setNotifications] = useState<AppNotification[]>([]);
  const [unreadNotifications, setUnreadNotifications] = useState(0);
  const [soundEnabled, setSoundEnabled] = useState(false);
  const [desktopEnabled, setDesktopEnabled] = useState(false);
  const [desktopPermission, setDesktopPermission] = useState<NotificationPermission | 'unsupported'>('default');
  const boxRef = useRef<HTMLDivElement>(null);
  const initialNotificationLoad = useRef(true);
  const notificationsRef = useRef<AppNotification[]>([]);
  const soundEnabledRef = useRef(false);
  const desktopEnabledRef = useRef(false);
  const audioContextRef = useRef<AudioContext | null>(null);
  const { currentEmployee } = useCurrentEmployee();
  const { toast } = useToast();

  const load = useCallback(() => {
    getDashboardAlerts().then(setAlerts).catch(() => {});
  }, []);

  useEffect(() => {
    try {
      const sound = localStorage.getItem('qomash_notification_sound') === '1';
      const desktop = localStorage.getItem('qomash_notification_desktop') === '1';
      setSoundEnabled(sound);
      soundEnabledRef.current = sound;
      setDesktopEnabled(desktop && typeof window !== 'undefined' && 'Notification' in window && Notification.permission === 'granted');
      desktopEnabledRef.current = desktop && typeof window !== 'undefined' && 'Notification' in window && Notification.permission === 'granted';
    } catch {}
    setDesktopPermission(typeof window !== 'undefined' && 'Notification' in window ? Notification.permission : 'unsupported');
    return () => { void audioContextRef.current?.close().catch(() => {}); };
  }, []);

  const playChime = useCallback((force = false) => {
    if (!force && !soundEnabledRef.current) return;
    try {
      const AudioCtor = window.AudioContext || (window as Window & { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;
      if (!AudioCtor) return;
      const context = audioContextRef.current || new AudioCtor();
      audioContextRef.current = context;
      if (context.state === 'suspended') void context.resume();
      const now = context.currentTime;
      [880, 1174].forEach((frequency, index) => {
        const oscillator = context.createOscillator();
        const gain = context.createGain();
        const start = now + index * 0.13;
        oscillator.type = 'sine';
        oscillator.frequency.setValueAtTime(frequency, start);
        gain.gain.setValueAtTime(0.0001, start);
        gain.gain.exponentialRampToValueAtTime(0.12, start + 0.025);
        gain.gain.exponentialRampToValueAtTime(0.0001, start + 0.2);
        oscillator.connect(gain);
        gain.connect(context.destination);
        oscillator.start(start);
        oscillator.stop(start + 0.21);
      });
    } catch {}
  }, []);

  const toggleSound = () => {
    const enabled = !soundEnabled;
    setSoundEnabled(enabled);
    soundEnabledRef.current = enabled;
    try { localStorage.setItem('qomash_notification_sound', enabled ? '1' : '0'); } catch {}
    if (enabled) playChime(true);
  };

  const toggleDesktopNotifications = async () => {
    if (desktopEnabled) {
      setDesktopEnabled(false);
      desktopEnabledRef.current = false;
      try { localStorage.setItem('qomash_notification_desktop', '0'); } catch {}
      return;
    }
    if (!('Notification' in window)) {
      setDesktopPermission('unsupported');
      toast('error', 'هذا المتصفح لا يدعم إشعارات سطح المكتب');
      return;
    }
    const permission = Notification.permission === 'default'
      ? await Notification.requestPermission()
      : Notification.permission;
    setDesktopPermission(permission);
    const enabled = permission === 'granted';
    setDesktopEnabled(enabled);
    desktopEnabledRef.current = enabled;
    try { localStorage.setItem('qomash_notification_desktop', enabled ? '1' : '0'); } catch {}
    if (enabled) toast('success', 'تم تفعيل إشعارات المتصفح');
    else if (permission === 'denied') toast('error', 'إذن الإشعارات محظور من إعدادات المتصفح');
  };

  const showDesktopNotification = useCallback((item: AppNotification) => {
    if (!desktopEnabledRef.current || !('Notification' in window) || Notification.permission !== 'granted') return;
    const desktopNotification = new Notification(item.title, {
      body: item.body || 'لديك إشعار جديد في النظام',
      tag: `qomash-${item.id}`,
      silent: true,
    });
    desktopNotification.onclick = () => {
      window.focus();
      if (item.url && item.url.startsWith('/')) window.location.assign(item.url);
      desktopNotification.close();
    };
  }, []);

  const checkNotifications = useCallback(() => {
    if (!currentEmployee) {
      initialNotificationLoad.current = true;
      notificationsRef.current = [];
      setNotifications([]);
      setUnreadNotifications(0);
      return;
    }
    getNotifications().then((r) => {
      if (!initialNotificationLoad.current) {
        const previousIds = new Set(notificationsRef.current.map((item) => item.id));
        const fresh = r.results.filter((item) => !previousIds.has(item.id));
        if (fresh.length > 0) {
          playChime();
          if (document.visibilityState === 'visible') {
            if (fresh.length === 1) toast('info', fresh[0].title);
            else toast('info', `لديك ${fresh.length} إشعارات جديدة`);
          } else {
            fresh.slice(0, 3).forEach(showDesktopNotification);
          }
        }
      }
      initialNotificationLoad.current = false;
      notificationsRef.current = r.results;
      setNotifications(r.results);
      setUnreadNotifications(r.unread_count);
    }).catch(() => {});
  }, [currentEmployee, playChime, showDesktopNotification, toast]);

  useEffect(() => {
    load();
    checkNotifications();
    const alertsInterval = setInterval(load, 60000);
    const notificationsInterval = setInterval(checkNotifications, 15000);
    const onVisibilityChange = () => { if (document.visibilityState === 'visible') checkNotifications(); };
    document.addEventListener('visibilitychange', onVisibilityChange);
    return () => {
      clearInterval(alertsInterval);
      clearInterval(notificationsInterval);
      document.removeEventListener('visibilitychange', onVisibilityChange);
    };
  }, [load, checkNotifications]);

  const refresh = () => {
    load();
    checkNotifications();
  };

  const openNotification = async (item: AppNotification) => {
    if (!item.read_at) {
      await markNotificationRead(item.id).catch(() => {});
      setNotifications((current) => current.map((n) => n.id === item.id ? { ...n, read_at: new Date().toISOString() } : n));
      setUnreadNotifications((count) => Math.max(0, count - 1));
    }
    setOpen(false);
  };

  const markAllRead = async () => {
    await markAllNotificationsRead().catch(() => {});
    setNotifications((current) => current.map((n) => ({ ...n, read_at: n.read_at || new Date().toISOString() })));
    setUnreadNotifications(0);
  };

  useEffect(() => {
    const onClick = (e: MouseEvent) => {
      if (boxRef.current && !boxRef.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener('mousedown', onClick);
    return () => document.removeEventListener('mousedown', onClick);
  }, []);

  const count = (alerts?.low_stock_count || 0) + unreadNotifications;

  return (
    <div ref={boxRef} className="relative">
      <button
        onClick={() => setOpen((o) => !o)}
        aria-label="الإشعارات"
        className="relative p-2 rounded-xl hover:bg-sand-100 text-neutral-600 dark:text-neutral-300 transition-colors"
      >
        <Bell size={20} />
        {count > 0 && (
          <span className="absolute -top-1 -right-1 min-w-[18px] h-[18px] px-1 rounded-full bg-red-500 text-white text-[11px] font-bold flex items-center justify-center">
            {count}
          </span>
        )}
      </button>

      {open && (
        <div className="absolute left-0 mt-2 w-80 max-h-[70vh] overflow-hidden rounded-2xl bg-surface border border-sand-200 shadow-xl z-50 flex flex-col">
          <div className="flex items-center justify-between px-4 py-3 border-b border-sand-200">
            <span className="font-semibold text-sm text-neutral-800">الإشعارات</span>
            <div className="flex items-center gap-1">
              {unreadNotifications > 0 && <button onClick={markAllRead} className="text-[11px] text-brand-700 hover:underline">قراءة الكل</button>}
              <button onClick={refresh} aria-label="تحديث" className="p-1.5 rounded-lg hover:bg-sand-100 text-neutral-500"><RefreshCw size={14} /></button>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-2 border-b border-sand-100 p-3">
            <button type="button" onClick={toggleSound} className={`flex items-center justify-center gap-2 rounded-lg border px-2 py-2 text-xs font-medium transition ${soundEnabled ? 'border-brand-200 bg-brand-50 text-brand-700' : 'border-sand-200 text-neutral-500 hover:bg-sand-50'}`}>
              {soundEnabled ? <Volume2 size={15} /> : <VolumeX size={15} />}
              {soundEnabled ? 'الصوت مفعّل' : 'تفعيل الصوت'}
            </button>
            <button type="button" onClick={toggleDesktopNotifications} className={`flex items-center justify-center gap-2 rounded-lg border px-2 py-2 text-xs font-medium transition ${desktopEnabled ? 'border-brand-200 bg-brand-50 text-brand-700' : 'border-sand-200 text-neutral-500 hover:bg-sand-50'}`}>
              <BellRing size={15} />
              {desktopEnabled ? 'إشعار المتصفح مفعّل' : 'تفعيل إشعار المتصفح'}
            </button>
            {desktopPermission === 'denied' && <p className="col-span-2 text-[11px] text-amber-700">إذن المتصفح محظور. اسمح بالإشعارات لهذا الموقع من إعدادات المتصفح.</p>}
            {desktopPermission === 'unsupported' && <p className="col-span-2 text-[11px] text-neutral-400">إشعارات سطح المكتب غير مدعومة في هذا المتصفح أو الاتصال.</p>}
          </div>

          <div className="overflow-y-auto">
            <div className="border-b border-sand-100">
              {notifications.length === 0 ? (
                <p className="px-4 py-3 text-sm text-neutral-400">لا توجد إشعارات</p>
              ) : notifications.map((item) => (
                <Link key={item.id} href={item.url || '/'} onClick={() => openNotification(item)} className={`block px-4 py-3 border-b border-sand-50 hover:bg-sand-50 ${!item.read_at ? 'bg-brand-50/60' : ''}`}>
                  <div className="flex items-start gap-2">
                    <span className={`mt-1.5 w-2 h-2 rounded-full shrink-0 ${item.read_at ? 'bg-neutral-200' : 'bg-brand-600'}`} />
                    <span className="min-w-0 flex-1">
                      <span className="block text-sm font-semibold text-neutral-800">{item.title}</span>
                      {item.body && <span className="block mt-0.5 text-xs text-neutral-500 line-clamp-2">{item.body}</span>}
                      <span className="block mt-1 text-[10px] text-neutral-400">{new Date(item.created_at).toLocaleString('ar')}</span>
                    </span>
                  </div>
                </Link>
              ))}
            </div>
            {currentEmployee && (
              <Link
                href="/messages"
                onClick={() => setOpen(false)}
                className="flex items-center justify-between gap-2 px-4 py-3 border-b border-sand-100 hover:bg-sand-50 transition-colors"
              >
                <span className="flex items-center gap-2 text-xs text-neutral-500">
                  <MessageSquareText size={14} />
                  الرسائل
                </span>
                  <span className="text-xs text-neutral-400">فتح المحادثات</span>
              </Link>
            )}
            <div className="px-4 py-3 border-b border-sand-100">
              <div className="flex items-center gap-2 text-xs text-neutral-500 mb-2">
                <Wallet size={14} />
                ملخص اليوم
              </div>
              <div className="grid grid-cols-2 gap-2 text-sm">
                <div className="flex justify-between">
                  <span className="text-neutral-500">المبيعات</span>
                  <span className="tabular-nums font-medium">{formatCurrency(alerts?.today.sales ?? 0)}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-neutral-500">المصاريف</span>
                  <span className="tabular-nums font-medium">{formatCurrency(alerts?.today.expenses ?? 0)}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-neutral-500">دعم الشركاء</span>
                  <span className="tabular-nums font-medium">{formatCurrency(alerts?.today.support ?? 0)}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-neutral-500">سحب الشركاء</span>
                  <span className="tabular-nums font-medium">{formatCurrency(alerts?.today.withdraw ?? 0)}</span>
                </div>
                <div className="col-span-2 flex justify-between border-t border-sand-100 pt-2">
                  <span className="text-neutral-500">الصافي</span>
                  <span className={`tabular-nums font-bold ${(alerts?.today.net ?? 0) < 0 ? 'text-red-600' : 'text-brand-700'}`}>
                    {formatCurrency(alerts?.today.net ?? 0)}
                  </span>
                </div>
              </div>
            </div>

            <div className="px-4 py-3">
              <div className="flex items-center gap-2 text-xs text-neutral-500 mb-2">
                <AlertTriangle size={14} />
                نقص المخزون
              </div>
              {(alerts?.low_stock_count || 0) === 0 ? (
                <p className="text-sm text-neutral-400 py-2">لا توجد أصناف تحت الحد الأدنى</p>
              ) : (
                <ul className="space-y-1">
                  {alerts!.low_stock.map((a) => (
                    <li key={a.fabric}>
                      <Link
                        href="/warehouses"
                        onClick={() => setOpen(false)}
                        className="flex items-center justify-between gap-2 rounded-lg px-2 py-1.5 hover:bg-sand-50 transition-colors"
                      >
                        <span className="flex items-center gap-2 min-w-0">
                          <span className="font-medium text-sm text-neutral-700 truncate">{a.fabric_name}</span>
                          <span className="font-mono text-[10px] bg-sand-100 px-1.5 py-0.5 rounded text-neutral-500">{a.fabric_code}</span>
                        </span>
                        <span className="text-xs tabular-nums text-red-600 shrink-0">
                          {formatNumber(a.total_yards)} / {formatNumber(a.min_stock)}
                        </span>
                      </Link>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
