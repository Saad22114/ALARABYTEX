'use client';

import { useEffect, useMemo, useState } from 'react';
import { createPortal } from 'react-dom';
import { QRCodeSVG } from 'qrcode.react';
import {
  Banknote, Copy, ExternalLink, Facebook, Ghost, Instagram, Link2,
  Maximize2, Music2, Phone, QrCode, ScanLine, X,
} from 'lucide-react';
import Card from '@/components/ui/Card';
import Button from '@/components/ui/Button';
import { useToast } from '@/components/ui/Toast';
import { getSalesLinks, SalesLinks, salesQrImageUrl } from '@/services/settings';

type SocialKey = 'instagram_url' | 'snapchat_url' | 'tiktok_url' | 'facebook_url';

const socialPlatforms: Array<{
  key: SocialKey;
  name: string;
  host: string;
  icon: typeof Instagram;
  iconClass: string;
  cardClass: string;
  image?: string;
  qrKey?: 'instagram' | 'snapchat';
}> = [
  { key: 'instagram_url', name: 'انستجرام', host: 'instagram.com', icon: Instagram, iconClass: 'text-fuchsia-600', cardClass: 'from-fuchsia-50 to-white', image: '/images/sales-qr/instagram.jpeg', qrKey: 'instagram' },
  { key: 'snapchat_url', name: 'سناب شات', host: 'snapchat.com', icon: Ghost, iconClass: 'text-yellow-600', cardClass: 'from-yellow-50 to-white', image: '/images/sales-qr/snapchat.jpeg', qrKey: 'snapchat' },
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
  const [expandedQr, setExpandedQr] = useState<{ title: string; image?: string; url?: string } | null>(null);

  useEffect(() => {
    let cancelled = false;
    getSalesLinks()
      .then((data) => { if (!cancelled) setLinks(data); })
      .catch((error: any) => { if (!cancelled) toast('error', error.message || 'تعذر تحميل روابط التواصل'); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [toast]);

  useEffect(() => {
    if (!expandedQr) return;
    const closeOnEscape = (event: KeyboardEvent) => { if (event.key === 'Escape') setExpandedQr(null); };
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    document.addEventListener('keydown', closeOnEscape);
    return () => {
      document.removeEventListener('keydown', closeOnEscape);
      document.body.style.overflow = previousOverflow;
    };
  }, [expandedQr]);

  const socialLinks = useMemo(() => socialPlatforms.map((platform) => ({
    ...platform,
    url: profileUrl(platform, links?.[platform.key] || ''),
    qrImage: platform.qrKey && links?.qr_images?.[platform.qrKey]
      ? salesQrImageUrl(platform.qrKey, links.qr_images[platform.qrKey])
      : platform.image,
  })), [links]);
  const transferUrl = safeWebUrl(links?.bank_transfer_url || '');
  const transferPhone = links?.bank_transfer_phone?.trim() || '';
  const secondBankQr = links?.qr_images?.bank_transfer_2 || '';

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

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-5">
        {socialLinks.map((social) => {
          const Icon = social.icon;
          return (
            <Card key={social.key} className="group overflow-hidden !p-0 transition duration-300 hover:-translate-y-1 hover:shadow-lg">
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
              <div className="flex min-h-[230px] flex-col items-center justify-center px-4 py-4">
                {social.qrImage || social.url ? (
                  <>
                    <button type="button" onClick={() => setExpandedQr({ title: social.name, image: social.qrImage, url: social.url })} aria-label={`تكبير رمز ${social.name}`} className="group/qr relative overflow-hidden rounded-2xl border border-sand-100 bg-white p-2 shadow-sm transition hover:shadow-md focus:outline-none focus:ring-2 focus:ring-brand-400">
                      {social.qrImage ? (
                        <img src={social.qrImage} alt={`رمز QR لحساب ${social.name}`} width={180} height={180} className="h-40 w-40 rounded-xl object-contain transition duration-300 group-hover/qr:scale-[1.03]" />
                      ) : (
                        <QRCodeSVG value={social.url} size={160} level="H" includeMargin fgColor="#123d32" />
                      )}
                      <span className="absolute inset-x-2 bottom-2 flex items-center justify-center gap-1 rounded-lg bg-neutral-950/75 py-1.5 text-[10px] font-medium text-white opacity-0 transition group-hover/qr:opacity-100 group-focus/qr:opacity-100"><Maximize2 size={12} /> تكبير الرمز</span>
                    </button>
                    {social.url ? (
                      <>
                        <p className="mt-3 w-full truncate text-center text-xs text-neutral-500" dir="ltr">{social.url.replace(/^https?:\/\//, '')}</p>
                        <div className="mt-3 flex w-full gap-2">
                          <a href={social.url} target="_blank" rel="noreferrer" className="inline-flex flex-1 items-center justify-center gap-1.5 rounded-lg border border-sand-200 px-3 py-2 text-xs font-medium text-neutral-600 transition hover:border-brand-300 hover:bg-brand-50 hover:text-brand-700"><ExternalLink size={14} /> فتح الحساب</a>
                          <button type="button" onClick={() => copyText(social.url, 'الرابط')} aria-label={`نسخ رابط ${social.name}`} className="inline-flex items-center justify-center rounded-lg border border-sand-200 px-3 py-2 text-neutral-500 transition hover:bg-sand-50 hover:text-neutral-800"><Copy size={14} /></button>
                        </div>
                      </>
                    ) : <p className="mt-3 text-center text-xs text-neutral-400">امسح الرمز لفتح الحساب</p>}
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

        <Card className="group overflow-hidden !p-0 transition duration-300 hover:-translate-y-1 hover:shadow-lg">
          <div className="border-b border-sand-100 bg-gradient-to-br from-emerald-50 to-white px-4 py-3">
            <div className="flex items-center gap-2.5">
              <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-white text-emerald-600 shadow-sm"><Phone size={19} /></span>
              <div><h3 className="text-sm font-bold text-neutral-800">واتساب</h3><p className="text-[10px] text-neutral-500">امسح الرمز لبدء المحادثة</p></div>
            </div>
          </div>
          <div className="flex min-h-[230px] flex-col items-center justify-center px-4 py-4">
            <button type="button" onClick={() => setExpandedQr({ title: 'واتساب', image: links?.qr_images?.whatsapp ? salesQrImageUrl('whatsapp', links.qr_images.whatsapp) : '/images/sales-qr/whatsapp.jpeg' })} aria-label="تكبير رمز واتساب" className="group/qr relative overflow-hidden rounded-2xl border border-sand-100 bg-white p-2 shadow-sm transition hover:shadow-md focus:outline-none focus:ring-2 focus:ring-emerald-400">
              <img src={links?.qr_images?.whatsapp ? salesQrImageUrl('whatsapp', links.qr_images.whatsapp) : '/images/sales-qr/whatsapp.jpeg'} alt="رمز QR لواتساب" width={180} height={180} className="h-40 w-40 rounded-xl object-cover object-[center_41%] transition duration-300 group-hover/qr:scale-[1.03]" />
              <span className="absolute inset-x-2 bottom-2 flex items-center justify-center gap-1 rounded-lg bg-neutral-950/75 py-1.5 text-[10px] font-medium text-white opacity-0 transition group-hover/qr:opacity-100 group-focus/qr:opacity-100"><Maximize2 size={12} /> تكبير الرمز</span>
            </button>
            <p className="mt-3 text-center text-xs text-neutral-500">القماش العربي السعودي صلالة</p>
          </div>
        </Card>
      </div>

      <Card className="overflow-hidden !p-0">
        <div className="flex flex-col gap-5 bg-gradient-to-l from-emerald-50/80 via-white to-white p-5 lg:flex-row lg:items-center lg:justify-between">
          <div className="flex items-start gap-3">
            <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-emerald-50 text-emerald-700"><Banknote size={21} /></span>
            <div>
              <h3 className="font-bold text-neutral-800">التحويل البنكي</h3>
              <p className="mt-1 text-sm text-neutral-500">اعرض رمز التحويل أو شارك الرابط ورقم الهاتف مع الزبون.</p>
              <div className="mt-3 flex flex-wrap gap-x-6 gap-y-2">
                {transferPhone && (
                  <div className="flex items-center gap-2 text-sm">
                    <Phone size={15} className="text-brand-600" />
                    <span className="font-mono font-semibold text-neutral-800" dir="ltr">{transferPhone}</span>
                    <button type="button" onClick={() => copyText(transferPhone, 'رقم الهاتف')} aria-label="نسخ رقم هاتف التحويل" className="rounded-md p-1 text-neutral-400 hover:bg-sand-100 hover:text-neutral-700"><Copy size={14} /></button>
                  </div>
                )}
                {transferUrl && (
                  <a href={transferUrl} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1.5 text-sm font-medium text-brand-700 hover:text-brand-900"><Link2 size={15} /> رابط التحويل <ExternalLink size={13} /></a>
                )}
              </div>
              {!transferPhone && !transferUrl && <p className="mt-3 text-xs text-neutral-400">أضف بيانات التحويل من إعدادات النشاط.</p>}
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-4">
            <div className="flex flex-wrap items-start gap-4">
              <div className="flex flex-col items-center gap-1.5">
                <button type="button" onClick={() => setExpandedQr({ title: 'التحويل البنكي - بنك مسقط', image: links?.qr_images?.bank_transfer ? salesQrImageUrl('bank_transfer', links.qr_images.bank_transfer) : '/images/sales-qr/bank-transfer.jpeg' })} aria-label="تكبير رمز بنك مسقط" className="group/qr relative overflow-hidden rounded-xl border border-sand-200 bg-white p-1.5 shadow-sm transition hover:shadow-md focus:outline-none focus:ring-2 focus:ring-emerald-400">
                  <img src={links?.qr_images?.bank_transfer ? salesQrImageUrl('bank_transfer', links.qr_images.bank_transfer) : '/images/sales-qr/bank-transfer.jpeg'} alt="رمز QR للتحويل إلى بنك مسقط" width={120} height={120} className="h-24 w-24 rounded-lg object-contain transition duration-300 group-hover/qr:scale-[1.03]" />
                  <span className="absolute inset-x-1.5 bottom-1.5 flex items-center justify-center gap-1 rounded-md bg-neutral-950/75 py-1 text-[9px] font-medium text-white opacity-0 transition group-hover/qr:opacity-100 group-focus/qr:opacity-100"><Maximize2 size={11} /> تكبير</span>
                </button>
                <span className="text-[10px] font-medium text-neutral-500">بنك مسقط</span>
              </div>
              {secondBankQr && <div className="flex flex-col items-center gap-1.5">
                <button type="button" onClick={() => setExpandedQr({ title: 'التحويل البنكي الثاني', image: salesQrImageUrl('bank_transfer_2', secondBankQr) })} aria-label="تكبير رمز البنك الثاني" className="group/qr relative overflow-hidden rounded-xl border border-sand-200 bg-white p-1.5 shadow-sm transition hover:shadow-md focus:outline-none focus:ring-2 focus:ring-emerald-400">
                  <img src={salesQrImageUrl('bank_transfer_2', secondBankQr)} alt="رمز QR للتحويل البنكي الثاني" width={120} height={120} className="h-24 w-24 rounded-lg object-contain transition duration-300 group-hover/qr:scale-[1.03]" />
                  <span className="absolute inset-x-1.5 bottom-1.5 flex items-center justify-center gap-1 rounded-md bg-neutral-950/75 py-1 text-[9px] font-medium text-white opacity-0 transition group-hover/qr:opacity-100 group-focus/qr:opacity-100"><Maximize2 size={11} /> تكبير</span>
                </button>
                <span className="text-[10px] font-medium text-neutral-500">بنك إضافي</span>
              </div>}
            </div>
            {transferUrl && <Button variant="secondary" onClick={() => copyText(transferUrl, 'رابط التحويل')}><Copy size={16} /> نسخ رابط التحويل</Button>}
          </div>
        </div>
      </Card>

      {expandedQr && typeof document !== 'undefined' && createPortal(
        <div role="dialog" aria-modal="true" aria-label={`رمز ${expandedQr.title}`} className="fixed inset-0 z-[100] flex items-center justify-center bg-neutral-950/75 p-4 backdrop-blur-sm" onClick={() => setExpandedQr(null)}>
          <div className="relative w-full max-w-xl overflow-hidden rounded-3xl border border-white/20 bg-white p-5 shadow-2xl sm:p-7" onClick={(event) => event.stopPropagation()}>
            <div className="mb-5 flex items-center justify-between">
              <div><p className="text-xs font-semibold text-brand-700">Alaraby Tex</p><h3 className="mt-1 text-lg font-bold text-neutral-900">{expandedQr.title}</h3></div>
              <button type="button" onClick={() => setExpandedQr(null)} aria-label="إغلاق الرمز المكبر" className="rounded-xl border border-sand-200 p-2 text-neutral-500 transition hover:bg-sand-50 hover:text-neutral-900"><X size={20} /></button>
            </div>
            <div className="flex justify-center rounded-2xl bg-sand-50 p-4 sm:p-6">
              {expandedQr.image ? <img src={expandedQr.image} alt={`رمز QR ${expandedQr.title}`} width={680} height={680} className="max-h-[72vh] w-auto max-w-full rounded-xl object-contain shadow-sm" /> : expandedQr.url ? <QRCodeSVG value={expandedQr.url} size={640} level="H" includeMargin fgColor="#123d32" className="max-h-[72vh] max-w-full" /> : null}
            </div>
            <p className="mt-4 flex items-center justify-center gap-2 text-xs text-neutral-500"><ScanLine size={15} /> قرّب كاميرا الهاتف من الرمز للمسح</p>
          </div>
        </div>,
        document.body,
      )}
    </div>
  );
}
