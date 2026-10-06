'use client';

import { useEffect } from 'react';
import { createPortal } from 'react-dom';
import { X } from 'lucide-react';

interface ImagePreviewProps {
  src: string | null;
  alt: string;
  onClose: () => void;
}

export default function ImagePreview({ src, alt, onClose }: ImagePreviewProps) {
  useEffect(() => {
    if (!src) return;
    const oldOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        event.stopImmediatePropagation();
        onClose();
      }
    };
    document.addEventListener('keydown', onKeyDown, true);
    return () => {
      document.removeEventListener('keydown', onKeyDown, true);
      document.body.style.overflow = oldOverflow;
    };
  }, [src, onClose]);

  if (!src) return null;
  return createPortal(
    <div className="fixed inset-0 z-[60] flex items-center justify-center p-4" role="presentation">
      <div className="absolute inset-0 bg-black/55 backdrop-blur-sm" onClick={onClose} />
      <div className="relative max-w-[min(420px,90vw)] max-h-[70vh] rounded-2xl bg-surface p-2 shadow-2xl animate-scale-in">
        <button
          type="button"
          onClick={onClose}
          aria-label="إغلاق معاينة الصورة"
          title="إغلاق"
          className="absolute -top-3 -right-3 z-10 rounded-full bg-white p-2 text-neutral-700 shadow-lg transition hover:bg-neutral-100"
        >
          <X size={20} />
        </button>
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img src={src} alt={alt} className="block max-h-[calc(70vh-1rem)] max-w-full rounded-xl object-contain" />
      </div>
    </div>,
    document.body,
  );
}
