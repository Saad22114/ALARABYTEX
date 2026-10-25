'use client';

import AppShell from '@/components/layout/AppShell';
import SalesLinksGuide from '@/components/sales/SalesLinksGuide';
import { useAuth } from '@/components/providers/AuthProvider';
import { useSettings } from '@/components/providers/SettingsProvider';
import { QrCode } from 'lucide-react';

export default function SalesLinksPage() {
  const { session } = useAuth();
  const { settings } = useSettings();
  const employee = session?.employee;
  const canView = Boolean(
    employee?.permissions?.['sales-links']?.view &&
    !employee?.hidden_sections?.includes('sales-links') &&
    !settings?.hidden_sections?.includes('sales-links')
  );

  return (
    <AppShell>
      <div className="space-y-5">
        <div className="flex items-center gap-3">
          <span className="flex h-12 w-12 items-center justify-center rounded-2xl bg-brand-50 text-brand-700"><QrCode size={24} /></span>
          <div>
            <h1 className="text-xl font-bold text-neutral-900">روابط التواصل والتحويل</h1>
            <p className="mt-1 text-sm text-neutral-500">رموز التواصل وبيانات التحويل لمشاركتها مع الزبائن</p>
          </div>
        </div>
        {canView ? (
          <SalesLinksGuide />
        ) : (
          <div className="rounded-2xl border border-sand-200 bg-surface px-5 py-8 text-center text-sm text-neutral-500">ليس لديك صلاحية لعرض هذا القسم.</div>
        )}
      </div>
    </AppShell>
  );
}
