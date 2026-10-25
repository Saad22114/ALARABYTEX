'use client';

import { useState } from 'react';
import { RotateCcw, Upload } from 'lucide-react';
import Card from '@/components/ui/Card';
import Button from '@/components/ui/Button';
import { useSettings } from '@/components/providers/SettingsProvider';
import { useToast } from '@/components/ui/Toast';
import { removeSalesQrImage, SalesQrKey, salesQrImageUrl, uploadSalesQrImage } from '@/services/settings';

const qrItems: Array<{ key: SalesQrKey; title: string; imageField: 'instagram_qr_image' | 'snapchat_qr_image' | 'whatsapp_qr_image' | 'bank_transfer_qr_image' | 'bank_transfer_qr_image_2'; fallback?: string }> = [
  { key: 'instagram', title: 'انستجرام', imageField: 'instagram_qr_image', fallback: '/images/sales-qr/instagram.jpeg' },
  { key: 'snapchat', title: 'سناب شات', imageField: 'snapchat_qr_image', fallback: '/images/sales-qr/snapchat.jpeg' },
  { key: 'whatsapp', title: 'واتساب', imageField: 'whatsapp_qr_image', fallback: '/images/sales-qr/whatsapp.jpeg' },
  { key: 'bank_transfer', title: 'التحويل البنكي', imageField: 'bank_transfer_qr_image', fallback: '/images/sales-qr/bank-transfer.jpeg' },
  { key: 'bank_transfer_2', title: 'تحويل بنكي إضافي', imageField: 'bank_transfer_qr_image_2' },
];

export default function SalesQrImageManager() {
  const { settings, refreshSettings } = useSettings();
  const { toast } = useToast();
  const [busyKey, setBusyKey] = useState<SalesQrKey | null>(null);

  const upload = async (key: SalesQrKey, file?: File) => {
    if (!file) return;
    if (!['image/png', 'image/jpeg', 'image/webp'].includes(file.type)) {
      toast('error', 'اختر صورة PNG أو JPG أو WEBP');
      return;
    }
    if (file.size > 5 * 1024 * 1024) {
      toast('error', 'حجم الصورة يجب ألا يتجاوز 5 ميجابايت');
      return;
    }
    setBusyKey(key);
    try {
      await uploadSalesQrImage(key, file);
      await refreshSettings();
      toast('success', 'تم تحديث رمز QR بنجاح');
    } catch (error: any) {
      toast('error', error?.message || 'تعذر رفع الصورة');
    } finally {
      setBusyKey(null);
    }
  };

  const restore = async (key: SalesQrKey) => {
    setBusyKey(key);
    try {
      await removeSalesQrImage(key);
      await refreshSettings();
      toast('success', 'تمت استعادة صورة QR الافتراضية');
    } catch (error: any) {
      toast('error', error?.message || 'تعذر استعادة الصورة الافتراضية');
    } finally {
      setBusyKey(null);
    }
  };

  return (
    <Card title="صور رموز QR" subtitle="غيّر صور التواصل والتحويل التي تظهر في صفحة الروابط والصفحة الرئيسية.">
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {qrItems.map((item) => {
          const storedPath = settings?.[item.imageField] || '';
          const imageSrc = storedPath ? salesQrImageUrl(item.key, storedPath) : item.fallback;
          const busy = busyKey === item.key;
          return (
            <div key={item.key} className="overflow-hidden rounded-2xl border border-sand-200 bg-white">
              <div className="flex h-44 items-center justify-center bg-sand-50 p-3">
                {imageSrc ? <img src={imageSrc} alt={`رمز QR ${item.title}`} width={180} height={180} className={`h-36 w-36 rounded-xl ${item.key === 'whatsapp' ? 'object-cover object-[center_41%]' : 'object-contain'} shadow-sm`} /> : <div className="flex h-36 w-36 flex-col items-center justify-center gap-2 rounded-xl border border-dashed border-sand-300 text-neutral-400"><Upload size={23} /><span className="text-[11px]">لم تُضف صورة بعد</span></div>}
              </div>
              <div className="space-y-3 p-3">
                <p className="text-center text-sm font-semibold text-neutral-800">{item.title}</p>
                <label className={`relative flex cursor-pointer items-center justify-center gap-2 rounded-xl bg-brand-700 px-3 py-2 text-xs font-semibold text-white transition hover:bg-brand-800 ${busy ? 'pointer-events-none opacity-60' : ''}`}>
                  <Upload size={14} /> {busy ? 'جارٍ الحفظ…' : 'اختيار صورة جديدة'}
                  <input type="file" accept="image/png,image/jpeg,image/webp" className="absolute inset-0 h-full w-full cursor-pointer opacity-0" disabled={busy} onChange={(event) => { void upload(item.key, event.currentTarget.files?.[0]); event.currentTarget.value = ''; }} />
                </label>
                {storedPath && <Button variant="secondary" className="w-full justify-center" disabled={busy} onClick={() => void restore(item.key)}><RotateCcw size={14} /> {item.key === 'bank_transfer_2' ? 'إزالة الصورة' : 'استعادة الصورة الأصلية'}</Button>}
              </div>
            </div>
          );
        })}
      </div>
      <p className="mt-3 text-xs text-neutral-400">الصور المدعومة PNG وJPG وWEBP، بحد أقصى 5 ميجابايت للصورة.</p>
    </Card>
  );
}
