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
  const toLogin = !loading && !authed && !isLogin;
  const toHome = !loading && authed && isLogin;

  useEffect(() => {
    if (toLogin) router.replace('/login');
    else if (toHome) router.replace('/');
  }, [toLogin, toHome, router]);

  if (loading || toLogin || toHome) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-sand-50 dark:bg-neutral-950">
        <Spinner size={40} />
      </div>
    );
  }

  return <>{children}</>;
}