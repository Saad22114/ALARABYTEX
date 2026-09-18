'use client';

import React, { useEffect } from 'react';
import { usePathname, useRouter } from 'next/navigation';
import { useAuth } from './AuthProvider';
import Spinner from '@/components/ui/Spinner';

export default function AuthGate({ children }: { children: React.ReactNode }) {
  const { status } = useAuth();
  const pathname = usePathname();
  const router = useRouter();
  const isLoginPage = pathname === '/login';

  useEffect(() => {
    if (status === 'guest' && !isLoginPage) {
      router.replace('/login');
    } else if (status === 'authed' && isLoginPage) {
      router.replace('/');
    }
  }, [status, isLoginPage, router]);

  const showApp = status === 'authed' && !isLoginPage;
  const showLogin = status === 'guest' && isLoginPage;

  if (showApp || showLogin) {
    return <>{children}</>;
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-sand-50">
      <Spinner size={40} />
    </div>
  );
}