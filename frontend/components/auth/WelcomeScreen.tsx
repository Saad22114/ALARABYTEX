'use client';

import { useEffect } from 'react';
import { Layers } from 'lucide-react';
import { logoUrl } from '@/services/settings';
import { formatArabicDate } from '@/lib/format';

function greetingForHour(hour: number): string {
  if (hour >= 5 && hour < 12) return 'صباح الخير';
  if (hour >= 12 && hour < 18) return 'مساء الخير';
  return 'مرحبا';
}

function currentArabicTime(date: Date): string {
  return date.toLocaleTimeString('ar-EG-u-nu-latn', {
    hour: '2-digit',
    minute: '2-digit',
  });
}

export default function WelcomeScreen({
  name,
  avatar,
  businessName,
  logo,
  lastLogin,
  onDone,
}: {
  name: string;
  avatar: string;
  businessName: string;
  logo: string;
  lastLogin?: string | null;
  onDone: () => void;
}) {
  useEffect(() => {
    const t = setTimeout(onDone, 2200);
    return () => clearTimeout(t);
  }, [onDone]);

  const greeting = greetingForHour(new Date().getHours());

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-brand-950 via-brand-900 to-brand-800 p-4">
      <div className="text-center space-y-6 animate-fade-in max-w-md w-full">
        <div className="mx-auto w-24 h-24 rounded-3xl bg-gold-500/20 flex items-center justify-center overflow-hidden ring-4 ring-gold-500/20">
          {logo ? (
            <img src={logoUrl(logo)} alt="شعار النشاط" className="w-full h-full object-contain p-2" />
          ) : (
            <Layers size={44} className="text-gold-500" />
          )}
        </div>

        <div>
          <p className="text-gold-400 text-lg font-semibold mb-1">{businessName || 'نظام إدارة الأعمال'}</p>
          <h1 className="text-3xl font-bold text-white">{greeting}، {name}</h1>
        </div>

        {avatar && (
          <div className="text-6xl leading-none" aria-hidden>
            {avatar}
          </div>
        )}

        <div className="mx-auto w-fit rounded-2xl bg-white/10 border border-white/10 backdrop-blur px-5 py-3">
          {lastLogin ? (
            <p className="text-sm text-[#f3f1ec]">
              آخر تسجيل دخول: <span className="font-semibold tabular-nums">{currentArabicTime(new Date(lastLogin))}</span>{' '}
              — <span className="font-semibold">{formatArabicDate(new Date(lastLogin))}</span>
            </p>
          ) : (
            <p className="text-sm text-[#f3f1ec]">أهلاً بك في أول تسجيل دخول</p>
          )}
        </div>
      </div>
    </div>
  );
}