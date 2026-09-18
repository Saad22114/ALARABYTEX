'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { KeyRound, LogIn, Layers } from 'lucide-react';
import { useAuth } from '@/components/providers/AuthProvider';
import { useToast } from '@/components/ui/Toast';
import Input from '@/components/ui/Input';
import Button from '@/components/ui/Button';

export default function LoginPage() {
  const { login } = useAuth();
  const router = useRouter();
  const { toast } = useToast();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!username.trim() || !password) {
      toast('error', 'يرجى إدخال اسم المستخدم وكلمة المرور');
      return;
    }
    setLoading(true);
    try {
      await login(username.trim(), password);
      toast('success', 'تم تسجيل الدخول بنجاح');
      router.replace('/');
      router.refresh();
    } catch (err: any) {
      toast('error', err?.message || 'تعذر تسجيل الدخول');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-sand-50 px-4">
      <div className="w-full max-w-md">
        <div className="mb-6 flex flex-col items-center">
          <div className="mb-3 rounded-2xl bg-gold-500/20 p-3">
            <Layers size={30} className="text-gold-500" />
          </div>
          <h1 className="text-2xl font-bold text-neutral-800">القماش العربي</h1>
          <p className="mt-1 text-sm text-neutral-500">نظام إدارة أعمال الأقمشة</p>
        </div>

        <form
          onSubmit={handleSubmit}
          className="space-y-4 rounded-2xl border border-sand-200 bg-surface p-6 shadow-sm"
        >
          <div className="flex items-center gap-2 text-neutral-700">
            <KeyRound size={18} className="text-brand-600" />
            <p className="font-medium">تسجيل الدخول</p>
          </div>
          <Input
            label="اسم المستخدم"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            placeholder="أدخل اسم المستخدم"
            autoComplete="username"
            dir="ltr"
            autoFocus
          />
          <Input
            label="كلمة المرور"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="أدخل كلمة المرور"
            autoComplete="current-password"
            dir="ltr"
          />
          <Button type="submit" className="w-full" loading={loading}>
            <LogIn size={18} />
            دخول
          </Button>
        </form>
      </div>
    </div>
  );
}