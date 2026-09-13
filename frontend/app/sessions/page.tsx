'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import AppShell from '@/components/layout/AppShell';
import Spinner from '@/components/ui/Spinner';

export default function SessionsPage() {
  const router = useRouter();

  useEffect(() => {
    router.replace('/sales');
  }, [router]);

  return (
    <AppShell>
      <div className="flex justify-center py-12"><Spinner size={32} /></div>
    </AppShell>
  );
}