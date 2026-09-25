'use client';

import { useEffect } from 'react';
import { usePathname, useRouter } from 'next/navigation';
import Spinner from '@/components/ui/Spinner';
import { useAuth } from './AuthProvider';

export default function AuthGate({ children }: { children: React.ReactNode }) {
  const { session, loading } = useAuth();
  const pathname = usePathname();
  const router = useRouter();

  const authed = Boolean(session);
  const isLogin = pathname === '/login';
  const isWelcome = pathname === '/welcome';
  const isChangePassword = pathname === '/change-password';
  const mustChange =
    Boolean(session?.employee?.must_change_password) ||
    (typeof window !== 'undefined' &&
      (() => {
        try {
          return sessionStorage.getItem('qomash_must_change') === '1';
        } catch {
          return false;
        }
      })());
  const toChangePassword = !loading && authed && mustChange && !isChangePassword;
  const toLogin = !loading && !authed && !isLogin;
  const toHome = !loading && authed && isLogin && !isWelcome && !mustChange;

  useEffect(() => {
    if (toLogin) router.replace('/login');
    else if (toChangePassword) router.replace('/change-password');
    else if (toHome) {
      // بعد تسجيل الدخول نمر على شاشة الترحيب إن وُجدت جلسة معلّقة للترحيب
      try {
        const pending = typeof window !== 'undefined' && sessionStorage.getItem('qomash_login_pending') === '1';
        router.replace(pending ? '/welcome' : '/');
        if (pending) sessionStorage.removeItem('qomash_login_pending');
      } catch {
        router.replace('/');
      }
    }
  }, [toLogin, toChangePassword, toHome, router]);

  if (loading || toLogin || toHome || toChangePassword) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-sand-50 dark:bg-neutral-950">
        <Spinner size={40} />
      </div>
    );
  }

  return <>{children}</>;
}