'use client';

import { useEffect, useMemo, useState } from 'react';
import { QRCodeSVG } from 'qrcode.react';
import {
  Banknote, Copy, ExternalLink, Facebook, Ghost, Instagram, Link2,
  Music2, Phone, QrCode,
} from 'lucide-react';
import Card from '@/components/ui/Card';
import Button from '@/components/ui/Button';
import { useToast } from '@/components/ui/Toast';
import { getSalesLinks, SalesLinks } from '@/services/settings';

type SocialKey = 'instagram_url' | 'snapchat_url' | 'tiktok_url' | 'facebook_url';

const socialPlatforms: Array<{
  key: SocialKey;
  name: string;
  host: string;
  icon: typeof Instagram;
  iconClass: string;
  cardClass: string;
}> = [
  { key: 'instagram_url', name: 'انستجرام', host: 'instagram.com', icon: Instagram, iconClass: 'text-fuchsia-600', cardClass: 'from-fuchsia-50 to-white' },
  { key: 'snapchat_url', name: 'سناب شات', host: 'snapchat.com', icon: Ghost, iconClass: 'text-yellow-600', cardClass: 'from-yellow-50 to-white' },
  { key: 'tiktok_url', name: 'تيك توك', host: 'tiktok.com', icon: Music2, iconClass: 'text-neutral-800', cardClass: 'from-neutral-100 to-white' },
  { key: 'facebook_url', name: 'فيسبوك', host: 'facebook.com', icon: Facebook, iconClass: 'text-blue-600', cardClass: 'from-blue-50 to-white' },
];

function profileUrl(platform: (typeof socialPlatforms)[number], raw: string): string {
  const value = raw.trim();
  if (!value) return '';
  if (/^https?:\/\//i.test(value)) {
    try {
      const parsed = new URL(value);
      return parsed.protocol === 'http:' || parsed.protocol === 'https:' ? parsed.toString() : '';
    } catch {
      return '';
    }
  }
  const clean = value.replace(/^@/, '').replace(/^\/+|\/+$/g, '');
  if (!clean) return '';
  if (clean.includes('.') || clean.includes('/')) return `https://${clean}`;
  if (platform.key === 'snapchat_url') return `https://snapchat.com/add/${encodeURIComponent(clean)}`;
  if (platform.key === 'tiktok_url') return `https://tiktok.com/@${encodeURIComponent(clean)}`;
  return `https://${platform.host}/${encodeURIComponent(clean)}`;
}

function safeWebUrl(value: string): string {
  const raw = value.trim();
  if (!raw) return '';
  const candidate = /^https?:\/\//i.test(raw) ? raw : `https://${raw}`;
  try {
    const url = new URL(candidate);
    return url.protocol === 'http:' || url.protocol === 'https:' ? url.toString() : '';
  } catch {
    return '';
  }
}

export default function SalesLinksGuide() {
  const { toast } = useToast();
  const [links, setLinks] = useState<SalesLinks | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    getSalesLinks()
      .then((data) => { if (!cancelled) setLinks(data); })
      .catch((error: any) => { if (!cancelled) toast('error', error.message || 'تعذر تحميل روابط التواصل'); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [toast]);

  const socialLinks = useMemo(() => socialPlatforms.map((platform) => ({
    ...platform,
    url: profileUrl(platform, links?.[platform.key] || ''),
  })), [links]);
  const transferUrl = safeWebUrl(links?.bank_transfer_url || '');
  const transferPhone = links?.bank_transfer_phone?.trim() || '';

  const copyText = async (value: string, label: string) => {
    try {
      await navigator.clipboard.writeText(value);
      toast('success', `تم نسخ ${label}`);
    } catch {
      toast('error', 'تعذر النسخ من هذا الجهاز');
    }
  };

  return (
    <div className="space-y-5">
      <div className="relative overflow-hidden rounded-2xl border border-brand-800/10 bg-gradient-to-l from-brand-950 via-brand-900 to-brand-800 px-5 py-5 text-white shadow-sm sm:px-7">
        <div aria-hidden="true" className="absolute -left-12 -top-16 h-48 w-48 rounded-full bg-gold-300/10 blur-3xl" />
        <div className="relative flex flex-wrap items-center justify-between gap-4">
          <div>
            <p className="text-xs font-semibold tracking-wide text-gold-200">خدمة الزبائن</p>
            <h2 className="mt-1 text-xl font-bold">{links?.business_name || 'روابط التواصل والتحويل البنكي'}</h2>
            <p className="text-sm font-semibold text-white/85">روابط التواصل والتحويل البنكي</p>
            <p className="mt-1.5 text-sm text-white/65">اعرض الرمز للزبون ليتابع حساباتنا أو استخدم بيانات التحويل مباشرة.</p>
          </div>
          <div className="flex h-12 w-12 items-center justify-center rounded-2xl border border-white/15 bg-white/10 text-gold-200">
            <QrCode size={24} strokeWidth={1.8} />
          </div>
        </div>
      </div>

      {loading && <div className="rounded-xl border border-sand-200 bg-surface px-4 py-3 text-sm text-neutral-500">جارٍ تحميل الروابط…</div>}

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {socialLinks.map((social) => {
          const Icon = social.icon;
          return (
            <Card key={social.key} className="overflow-hidden !p-0">
              <div className={`border-b border-sand-100 bg-gradient-to-br ${social.cardClass} px-4 py-3`}>
                <div className="flex items-center gap-2.5">
                  <span className={`flex h-9 w-9 items-center justify-center rounded-xl bg-white shadow-sm ${social.iconClass}`}>
                    <Icon size={19} strokeWidth={1.9} />
                  </span>
                  <div>
                    <h3 className="text-sm font-bold text-neutral-800">{social.name}</h3>
                    <p className="text-[10px] text-neutral-500">امسح الرمز لفتح الحساب</p>
                  </div>
                </div>
              </div>
              <div className="flex min-h-[206px] flex-col items-center justify-center px-4 py-4">
                {social.url ? (
                  <>
                    <div className="rounded-2xl border border-sand-100 bg-white p-3 shadow-sm">
                      <QRCodeSVG value={social.url} size={142} level="H" includeMargin fgColor="#123d32" />
                    </div>
                    <p className="mt-3 w-full truncate text-center text-xs text-neutral-500" dir="ltr">{social.url.replace(/^https?:\/\//, '')}</p>
                    <div className="mt-3 flex w-full gap-2">
                      <a href={social.url} target="_blank" rel="noreferrer" className="inline-flex flex-1 items-center justify-center gap-1.5 rounded-lg border border-sand-200 px-3 py-2 text-xs font-medium text-neutral-600 transition hover:border-brand-300 hover:bg-brand-50 hover:text-brand-700">
                        <ExternalLink size={14} /> فتح الحساب
                      </a>
                      <button type="button" onClick={() => copyText(social.url, 'الرابط')} aria-label={`نسخ رابط ${social.name}`} className="inline-flex items-center justify-center rounded-lg border border-sand-200 px-3 py-2 text-neutral-500 transition hover:bg-sand-50 hover:text-neutral-800">
                        <Copy size={14} />
                      </button>
                    </div>
                  </>
                ) : (
                  <div className="flex flex-col items-center text-center">
                    <span className="flex h-14 w-14 items-center justify-center rounded-2xl bg-sand-50 text-neutral-300"><QrCode size={28} /></span>
                    <p className="mt-3 text-sm font-medium text-neutral-500">الرابط غير مضاف</p>
                    <p className="mt-1 text-xs text-neutral-400">أضفه من إعدادات النشاط</p>
                  </div>
                )}
              </div>
            </Card>
          );
        })}
      </div>

      <Card>
        <div className="flex flex-col gap-5 lg:flex-row lg:items-center lg:justify-between">
          <div className="flex items-start gap-3">
            <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-emerald-50 text-emerald-700"><Banknote size={21} /></span>
            <div>
              <h3 className="font-bold text-neutral-800">التحويل البنكي</h3>
              <p className="mt-1 text-sm text-neutral-500">شارك الرابط أو رقم الهاتف مع الزبون لإتمام الدفع.</p>
              <div className="mt-3 flex flex-wrap gap-x-6 gap-y-2">
                {transferPhone && (
                  <div className="flex items-center gap-2 text-sm">
                    <Phone size={15} className="text-brand-600" />
                    <span className="font-mono font-semibold text-neutral-800" dir="ltr">{transferPhone}</span>
                    <button type="button" onClick={() => copyText(transferPhone, 'رقم الهاتف')} aria-label="نسخ رقم هاتف التحويل" className="rounded-md p-1 text-neutral-400 hover:bg-sand-100 hover:text-neutral-700"><Copy size={14} /></button>
                  </div>
                )}
                {transferUrl && (
                  <a href={transferUrl} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1.5 text-sm font-medium text-brand-700 hover:text-brand-900">
                    <Link2 size={15} /> رابط التحويل <ExternalLink size={13} />
                  </a>
                )}
              </div>
              {!transferPhone && !transferUrl && <p className="mt-3 text-xs text-neutral-400">أضف بيانات التحويل من إعدادات النشاط.</p>}
            </div>
          </div>
          {transferUrl && (
            <Button variant="secondary" onClick={() => copyText(transferUrl, 'رابط التحويل')}>
              <Copy size={16} /> نسخ رابط التحويل
            </Button>
          )}
        </div>
      </Card>
    </div>
  );
}
