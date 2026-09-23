'use client';

import { useState, useEffect } from 'react';
import { Layers, LogIn } from 'lucide-react';
import Button from '@/components/ui/Button';
import Input from '@/components/ui/Input';
import { useAuth } from '@/components/providers/AuthProvider';
import { useToast } from '@/components/ui/Toast';
import { apiRequest } from '@/services/api';
import { logoUrl } from '@/services/settings';
import { LOGIN_PENDING_KEY } from '@/services/auth';

interface PublicSettings {
  business_name: string;
  logo: string;
  receipt_footer: string;
}

export default function LoginPage() {
  const { login } = useAuth();
  const { toast } = useToast();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [info, setInfo] = useState<PublicSettings | null>(null);

  useEffect(() => {
    apiRequest<PublicSettings>('/settings/public/')
      .then(setInfo)
      .catch(() => {});
  }, []);

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (submitting) return;
    setError('');
    if (!username.trim() || !password) {
      setError('أدخل اسم المستخدم وكلمة المرور');
      return;
    }
    setSubmitting(true);
    try {
      const session = await login(username.trim(), password);
      try {
        sessionStorage.setItem(LOGIN_PENDING_KEY, '1');
        sessionStorage.setItem('qomash_last_login', session.last_login || '');
      } catch {}
    } catch (err) {
      const message = err instanceof Error ? err.message : 'تعذر تسجيل الدخول';
      setError(message);
      toast('error', message);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-brand-950 via-brand-900 to-brand-800 p-4">
      <form
        onSubmit={onSubmit}
        className="w-full max-w-md bg-surface dark:bg-neutral-900 rounded-3xl shadow-2xl border border-white/40 dark:border-neutral-800 p-8 sm:p-10 space-y-6"
      >
        <div className="text-center space-y-3">
          <div className="mx-auto w-28 h-28 rounded-3xl bg-gold-500/20 flex items-center justify-center overflow-hidden">
            {info?.logo ? (
              <img src={logoUrl(info.logo)} alt="شعار النشاط" className="w-full h-full object-contain" />
            ) : (
              <Layers size={52} className="text-gold-500" />
            )}
          </div>
          <div>
            <h1 className="text-2xl font-bold text-neutral-800 dark:text-neutral-100">تسجيل الدخول</h1>
            <p className="text-sm text-neutral-400 mt-1">{info?.business_name || 'نظام إدارة الأعمال'}</p>
          </div>
        </div>

        {error && (
          <div className="rounded-xl bg-red-50 dark:bg-red-500/10 border border-red-200 dark:border-red-500/30 px-4 py-3 text-sm text-red-600 dark:text-red-400 text-center">
            {error}
          </div>
        )}

        <div className="space-y-4">
          <Input
            label="اسم المستخدم"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            placeholder="أدخل اسم المستخدم"
            autoComplete="username"
            autoFocus
          />
          <Input
            label="كلمة المرور"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="أدخل كلمة المرور"
            autoComplete="current-password"
          />
        </div>

        <Button type="submit" loading={submitting} className="w-full !py-3">
          {!submitting && <LogIn size={18} />}
          دخول
        </Button>
      </form>
    </div>
  );
}