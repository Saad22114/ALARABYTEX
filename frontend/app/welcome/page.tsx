'use client';

import { useRouter } from 'next/navigation';
import WelcomeScreen from '@/components/auth/WelcomeScreen';
import { useAuth } from '@/components/providers/AuthProvider';
import { useSettings } from '@/components/providers/SettingsProvider';
import { LAST_SEEN_KEY } from '@/services/auth';

export default function WelcomePage() {
  const router = useRouter();
  const { session } = useAuth();
  const { settings } = useSettings();
  const me = session?.employee;

  // نفضّل القيمة المخزّنة عند الدخول على `session.last_seen_at`:
  // الأخيرة تتجدّد مع كل طلب `/auth/me/` فتعطي «الآن» بلا معنى.
  let lastSeen: string | null = null;
  if (typeof window !== 'undefined') {
    try {
      lastSeen = sessionStorage.getItem(LAST_SEEN_KEY) || null;
    } catch {}
  }
  if (!lastSeen) lastSeen = session?.last_seen_at ?? null;

  if (!me) return null;

  return (
    <WelcomeScreen
      name={me.name}
      avatar={me.avatar}
      avatarImage={me.avatar_image}
      businessName={settings?.business_name || ''}
      logo={settings?.logo || ''}
      lastSeen={lastSeen}
      onDone={() => router.replace('/')}
    />
  );
}