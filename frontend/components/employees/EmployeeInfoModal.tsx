'use client';

import { useCallback, useEffect, useState } from 'react';
import Modal from '@/components/ui/Modal';
import Avatar from '@/components/ui/Avatar';
import Badge from '@/components/ui/Badge';
import Spinner from '@/components/ui/Spinner';
import { AVATARS, avatarOf } from '@/lib/avatars';
import { getEmployeeProfile, updateAvatar } from '@/services/account';
import { EmployeeProfile } from '@/types';
import { useToast } from '@/components/ui/Toast';
import { Building2, Phone, Mail, User, Briefcase, Hash, CalendarDays, Check } from 'lucide-react';

interface EmployeeInfoModalProps {
  open: boolean;
  /** الموظف المعروض — إما شريك محادثة أو الذات */
  employee: { id: number; name: string; avatar?: string | null } | null;
  /** هل هذا الموظف هو الحساب الحالي؟ عندها يُتاح تغيير الأفاتار */
  isMe: boolean;
  onClose: () => void;
  onAvatarChanged?: (avatar: string) => void;
}

export default function EmployeeInfoModal({ open, employee, isMe, onClose, onAvatarChanged }: EmployeeInfoModalProps) {
  const { toast } = useToast();
  const [profile, setProfile] = useState<EmployeeProfile | null>(null);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    if (!open || !employee) return;
    setLoading(true);
    setProfile(null);
    try {
      setProfile(await getEmployeeProfile(employee.id));
    } catch (e: any) {
      toast('error', e?.message || 'تعذر تحميل معلومات الموظف');
    } finally {
      setLoading(false);
    }
  }, [open, employee, toast]);

  useEffect(() => {
    load();
  }, [load]);

  const handlePickAvatar = async (emoji: string) => {
    if (saving || emoji === profile?.avatar) return;
    setSaving(true);
    try {
      const res = await updateAvatar(emoji);
      setProfile((prev) => (prev ? { ...prev, avatar: res.employee.avatar } : prev));
      onAvatarChanged?.(res.employee.avatar);
      toast('success', 'تم تحديث الأفاتار');
    } catch (e: any) {
      toast('error', e?.message || 'تعذر تحديث الأفاتار');
    } finally {
      setSaving(false);
    }
  };

  const rows: Array<{ icon: React.ReactNode; label: string; value: string; ltr?: boolean }> = [];
  if (profile?.branch_name) rows.push({ icon: <Building2 size={15} />, label: 'الفرع', value: profile.branch_name });
  if (profile?.position) rows.push({ icon: <Briefcase size={15} />, label: 'المسمى الوظيفي', value: profile.position });
  if (profile?.department) rows.push({ icon: <User size={15} />, label: 'القسم', value: profile.department });
  if (profile?.phone) rows.push({ icon: <Phone size={15} />, label: 'الهاتف', value: profile.phone, ltr: true });
  if (profile?.email) rows.push({ icon: <Mail size={15} />, label: 'البريد', value: profile.email, ltr: true });
  if (profile?.employee_code) rows.push({ icon: <Hash size={15} />, label: 'رقم الموظف', value: profile.employee_code, ltr: true });
  if (profile?.hire_date) rows.push({ icon: <CalendarDays size={15} />, label: 'تاريخ التوظيف', value: String(profile.hire_date) });

  return (
    <Modal open={open} onClose={onClose} title="معلومات الموظف" maxWidth="max-w-md">
      {!open ? null : loading ? (
        <div className="flex justify-center py-10"><Spinner /></div>
      ) : !profile ? (
        <p className="text-sm text-neutral-400 text-center py-8">لا تتوفر بيانات</p>
      ) : (
        <div className="space-y-5">
          <div className="flex items-center gap-4">
            <Avatar name={profile.name} avatar={profile.avatar} size="lg" className="ring-2 ring-sand-200" />
            <div className="min-w-0">
              <p className="text-base font-semibold truncate">{profile.name}</p>
              <div className="flex flex-wrap items-center gap-1.5 mt-1">
                <Badge variant={profile.role === 'custom' ? 'neutral' : 'warning'}>{profile.role_label}</Badge>
                {isMe && <Badge variant="success">أنت</Badge>}
              </div>
            </div>
          </div>

          <div className="rounded-xl border border-sand-200 divide-y divide-sand-100">
            {rows.length === 0 && (
              <p className="text-xs text-neutral-400 px-4 py-3">لا توجد بيانات إضافية مسجلة</p>
            )}
            {rows.map((r) => (
              <div key={r.label} className="flex items-center justify-between gap-3 px-4 py-2.5">
                <span className="flex items-center gap-2 text-xs text-neutral-500 shrink-0">
                  <span className="text-brand-600">{r.icon}</span>
                  {r.label}
                </span>
                <span className={`text-sm text-neutral-700 font-medium truncate ${r.ltr ? 'tabular-nums' : ''}`} dir={r.ltr ? 'ltr' : undefined}>
                  {r.value}
                </span>
              </div>
            ))}
          </div>

          {isMe && (
            <div>
              <p className="text-xs font-medium text-neutral-500 mb-2">اختر أفاتارك</p>
              <div className="grid grid-cols-8 gap-2">
                {AVATARS.map((a) => {
                  const selected = profile.avatar === a.emoji;
                  return (
                    <button
                      key={a.emoji}
                      type="button"
                      onClick={() => handlePickAvatar(a.emoji)}
                      disabled={saving}
                      title={selected ? 'الأفاتار الحالي' : 'اختيار'}
                      className={`relative aspect-square rounded-xl flex items-center justify-center text-xl transition-all hover:scale-105 disabled:opacity-60 ${a.bg} ${
                        selected ? 'ring-2 ring-brand-600 ring-offset-1' : 'ring-1 ring-sand-200'
                      }`}
                    >
                      {a.emoji}
                      {selected && (
                        <span className="absolute -top-1 -left-1 w-4 h-4 rounded-full bg-brand-600 text-white flex items-center justify-center">
                          <Check size={11} />
                        </span>
                      )}
                    </button>
                  );
                })}
              </div>
              <p className="text-[11px] text-neutral-400 mt-2">
                {profile.avatar
                  ? `أفاتارك الحالي: ${avatarOf(profile.avatar)?.emoji ?? ''} — اضغط أي رمز للتغيير`
                  : 'لم تختر أفاتاراً بعد — اضغط أي رمز لتفعيله'}
              </p>
            </div>
          )}
        </div>
      )}
    </Modal>
  );
}