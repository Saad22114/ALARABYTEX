'use client';

import { useRouter } from 'next/navigation';
import WelcomeScreen from '@/components/auth/WelcomeScreen';
import { useAuth } from '@/components/providers/AuthProvider';
import { useSettings } from '@/components/providers/SettingsProvider';

export default function WelcomePage() {
  const router = useRouter();
  const { session } = useAuth();
  const { settings } = useSettings();
  const me = session?.employee;

  let lastLogin: string | null = session?.last_login ?? null;
  if (!lastLogin && typeof window !== 'undefined') {
    try {
      lastLogin = sessionStorage.getItem('qomash_last_login') || null;
    } catch {}
  }

  if (!me) return null;

  return (
    <WelcomeScreen
      name={me.name}
      avatar={me.avatar}
      businessName={settings?.business_name || ''}
      logo={settings?.logo || ''}
      lastLogin={lastLogin}
      onDone={() => router.replace('/')}
    />
  );
}