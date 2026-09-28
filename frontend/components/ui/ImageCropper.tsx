'use client';

import React, { useCallback, useEffect, useRef, useState } from 'react';
import Modal from '@/components/ui/Modal';
import Button from '@/components/ui/Button';
import {
  AvatarCropRegion,
  clampView,
  centerView,
  cropRegionFromView,
  CropView,
  MAX_ZOOM,
  MIN_ZOOM,
  renderedSize,
  ZOOM_STEP,
} from '@/lib/avatarCrop';
import { AvatarSource } from '@/lib/avatarImage';
import { Minus, Plus, RefreshCw, Check, X } from 'lucide-react';

interface ImageCropperProps {
  open: boolean;
  source: AvatarSource | null;
  /** يُستدعى عند التأكيد — المنطقة كنِسَب 0..1 داخل الصورة الأصلية. */
  onConfirm: (region: AvatarCropRegion) => void;
  onCancel: () => void;
  /** true أثناء الحفظ: يعطّل التأكيد والإلغاء ويعرض مؤشر انتظار. */
  saving?: boolean;
}

/** ضلع مربّع القصّ على الشاشة (px). */
const STAGE = 280;

/** شفافية القناع الذي يظلم ما خارج مربّع القصّ. */
const DIM = 'rgba(0,0,0,0.55)';

export default function ImageCropper({
  open,
  source,
  onConfirm,
  onCancel,
  saving = false,
}: ImageCropperProps) {
  const [view, setView] = useState<CropView | null>(null);
  /** إزاحة مربّع القصّ داخل الشريط الأفقي — لازم لوضع القناع. */
  const [holeX, setHoleX] = useState(0);
  const dragRef = useRef<{ x: number; y: number; ox: number; oy: number } | null>(null);
  const observerRef = useRef<ResizeObserver | null>(null);

  // تهيئة العرض عند فتح المكوّن أو تغيّر الصورة
  useEffect(() => {
    if (open && source) setView(centerView(STAGE, source.width, source.height));
  }, [open, source]);

  /*
   * نقيس عرض الشريط عبر callback ref لا عبر effect: الشريط لا يُركَّب إلا بعد
   * أن تصبح `view` جاهزة (وهي تُضبط في useEffect)، فـ effect يعتمد على الحالة
   * كان يعمل قبل وجود العنصر فيبقى القياس صفراً. الـ callback ref يُستدعى عند
   * تركيب العنصر نفسه فيقيس في اللحظة الصحيحة، ويتابع تغيّر حجم النافذة.
   */
  const attachFrame = useCallback((node: HTMLDivElement | null) => {
    observerRef.current?.disconnect();
    observerRef.current = null;
    if (!node) return;
    const measure = () => setHoleX(Math.max(0, (node.clientWidth - STAGE) / 2));
    measure();
    const observer = new ResizeObserver(measure);
    observer.observe(node);
    observerRef.current = observer;
  }, []);

  useEffect(() => () => observerRef.current?.disconnect(), []);

  const update = useCallback((patch: Partial<CropView>) => {
    setView((prev) => (prev ? clampView({ ...prev, ...patch }) : prev));
  }, []);

  const zoomBy = useCallback(
    (delta: number) => update({ zoom: (view?.zoom ?? MIN_ZOOM) + delta }),
    [update, view?.zoom],
  );

  const reset = useCallback(() => {
    if (source) setView(centerView(STAGE, source.width, source.height));
  }, [source]);

  // ——— السحب بالفأرة واللمس ———
  const handlePointerDown = (e: React.PointerEvent) => {
    if (!view || saving) return;
    (e.currentTarget as HTMLElement).setPointerCapture?.(e.pointerId);
    dragRef.current = { x: e.clientX, y: e.clientY, ox: view.offsetX, oy: view.offsetY };
  };

  const handlePointerMove = (e: React.PointerEvent) => {
    const drag = dragRef.current;
    if (!drag || !view) return;
    // clientX/Y إحداثيات فيزيائية لا تتأثر باتجاه الصفحة (RTL)،
    // والإزاحة تُخزَّن بنفس الفضاء، فالفرق المباشر صحيح.
    update({
      offsetX: drag.ox + (e.clientX - drag.x),
      offsetY: drag.oy + (e.clientY - drag.y),
    });
  };

  const endDrag = (e: React.PointerEvent) => {
    (e.currentTarget as HTMLElement).releasePointerCapture?.(e.pointerId);
    dragRef.current = null;
  };

  // التنقل بالأسهم عند التركيز (إتاحة الوصول)
  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (!view || saving) return;
    const step = e.shiftKey ? 24 : 8;
    // نفس اتجاه السحب بالضبط: السهم يحرّك الصورة في الاتجاه المضغوط،
    // فيكشف عن الجهة المقابلة منها (كأن dragged بإصبع في ذلك الاتجاه).
    const map: Record<string, [number, number]> = {
      ArrowRight: [step, 0],
      ArrowLeft: [-step, 0],
      ArrowDown: [0, step],
      ArrowUp: [0, -step],
    };
    const delta = map[e.key];
    if (!delta) return;
    e.preventDefault();
    update({ offsetX: view.offsetX + delta[0], offsetY: view.offsetY + delta[1] });
  };

  // أبعاد العرض بنفس دالة الرسم النهائية — مصدر واحد للحقيقة
  const rendered = view
    ? renderedSize(STAGE, view.imageWidth, view.imageHeight, view.zoom)
    : null;

  // نمنع الإلغاء أثناء الرفع حتى لا تُحذف الصورة قبل حفظها
  const cancel = useCallback(() => {
    if (!saving) onCancel();
  }, [onCancel, saving]);

  return (
    <Modal
      open={open}
      onClose={cancel}
      title="قصّ الصورة"
      maxWidth="max-w-sm"
      footer={
        <>
          <Button
            onClick={() => view && onConfirm(cropRegionFromView(view))}
            loading={saving}
            disabled={!view}
          >
            <Check size={16} />
            حفظ الصورة
          </Button>
          <Button variant="secondary" onClick={cancel} disabled={saving}>
            <X size={16} />
            إلغاء
          </Button>
        </>
      }
    >
      {!open || !source || !view || !rendered ? (
        <p className="text-sm text-neutral-400 text-center py-8">جارٍ تجهيز الصورة…</p>
      ) : (
        <div className="space-y-4">
          <p className="text-xs text-neutral-500 text-center">
            اسحب الصورة لتحديد الجزء الظاهر داخل المربّع، واستخدم التكبير للتقرّب.
          </p>

          {/*
            الشريط: يقصّ الصورة على عرضه ويُظهرها كاملة حول المربّع، حتى يرى
            المستخدم ما سيستبعده. `overflow-hidden` هنا (وليس على المربّع) هو ما
            يوفّر القناع: المربّع فجوة في وسط الشريط، وما حوله يُظلَّم.
          */}
          <div
            ref={attachFrame}
            role="application"
            aria-label="منطقة قصّ الصورة — اسحبها أو استخدم الأسهم للتحريك"
            tabIndex={0}
            onKeyDown={handleKeyDown}
            onPointerDown={handlePointerDown}
            onPointerMove={handlePointerMove}
            onPointerUp={endDrag}
            onPointerCancel={endDrag}
            className="relative overflow-hidden rounded-2xl bg-neutral-900 cursor-grab active:cursor-grabbing touch-none select-none focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500"
            style={{ height: STAGE }}
          >
            {/* الصورة نفسها */}
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src={source.previewUrl}
              alt="معاينة الصورة قبل القصّ"
              draggable={false}
              className="absolute max-w-none pointer-events-none select-none"
              style={{
                width: rendered.width,
                height: rendered.height,
                left: holeX + view.offsetX,
                top: view.offsetY,
              }}
            />

            {/* القناع: مستطيلان على الجانبين فقط. رأسياً تغطّي الصورة الشريط
                بالكامل عند zoom>=1، فلا حاجة لقناع أعلى/أسفل. */}
            <div
              aria-hidden
              className="absolute inset-y-0 left-0 pointer-events-none"
              style={{ width: holeX, background: DIM }}
            />
            <div
              aria-hidden
              className="absolute inset-y-0 right-0 pointer-events-none"
              style={{ width: holeX, background: DIM }}
            />

            {/* حدود مربّع القصّ + شبكة الأثلاث */}
            <div
              aria-hidden
              className="absolute inset-y-0 pointer-events-none ring-1 ring-inset ring-white/50"
              style={{ left: holeX, width: STAGE }}
            >
              <div className="absolute inset-y-0 left-1/3 w-px bg-white/30" />
              <div className="absolute inset-y-0 right-1/3 w-px bg-white/30" />
              <div className="absolute inset-x-0 top-1/3 h-px bg-white/30" />
              <div className="absolute inset-x-0 bottom-1/3 h-px bg-white/30" />
            </div>
          </div>

          {/* شريط التكبير */}
          <div className="flex items-center gap-3">
            <button
              type="button"
              onClick={() => zoomBy(-ZOOM_STEP)}
              disabled={view.zoom <= MIN_ZOOM + 1e-9}
              aria-label="تصغير"
              className="p-2 rounded-lg border border-sand-200 text-neutral-600 hover:bg-sand-50 disabled:opacity-40 transition-colors"
            >
              <Minus size={16} />
            </button>

            <input
              type="range"
              min={MIN_ZOOM}
              max={MAX_ZOOM}
              step={ZOOM_STEP}
              value={view.zoom}
              onChange={(e) => update({ zoom: Number(e.target.value) })}
              aria-label="مستوى التكبير"
              className="flex-1 accent-brand-600 cursor-pointer"
            />

            <button
              type="button"
              onClick={() => zoomBy(ZOOM_STEP)}
              disabled={view.zoom >= MAX_ZOOM - 1e-9}
              aria-label="تكبير"
              className="p-2 rounded-lg border border-sand-200 text-neutral-600 hover:bg-sand-50 disabled:opacity-40 transition-colors"
            >
              <Plus size={16} />
            </button>

            <button
              type="button"
              onClick={reset}
              aria-label="إعادة الضبط"
              title="إعادة الضبط"
              className="p-2 rounded-lg border border-sand-200 text-neutral-600 hover:bg-sand-50 transition-colors"
            >
              <RefreshCw size={16} />
            </button>
          </div>

          <p className="text-[11px] text-neutral-400 text-center tabular-nums">
            التكبير {Math.round(view.zoom * 100)}% · النتيجة النهائية 256×256 بكسل
          </p>
        </div>
      )}
    </Modal>
  );
}
