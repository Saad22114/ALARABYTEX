import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import ImageCropper from '@/components/ui/ImageCropper';
import { AvatarSource } from '@/lib/avatarImage';
import { AvatarCropRegion } from '@/lib/avatarCrop';

/** ضلع مربّع القصّ كما هو معرَّف في المكوّن — نثبّته هنا لربط الحسابات بالاختبار. */
const STAGE = 280;

/** صورة عريضة 2:1 — الوحيدة التي تتيح سحباً أفقياً عند أدنى تكبير. */
const WIDE = { w: 2000, h: 1000 };

/** مقياس «تغطية المربّع» لهذه الصورة: max(280/2000, 280/1000) = 0.28. */
const WIDE_SCALE = 0.28;

function makeSource(width: number, height: number): AvatarSource {
  return {
    image: document.createElement('img'),
    width,
    height,
    previewUrl: 'data:image/png;base64,AAAA',
  };
}

/** إطار القصّ — يفشل بوضوح إن لم يُعرض. */
function frame(): HTMLElement {
  return screen.getByRole('application');
}

function preview(): HTMLImageElement {
  return screen.getByAltText('معاينة الصورة قبل القصّ') as HTMLImageElement;
}

function press(name: RegExp | string) {
  fireEvent.click(screen.getByRole('button', { name }));
}

/** ينقر «حفظ الصورة» ويعيد آخر منطقة مُبلَّغ عنها. */
function saveClicked(onConfirm: ReturnType<typeof vi.fn>): AvatarCropRegion {
  press(/حفظ الصورة/);
  return onConfirm.mock.calls.at(-1)?.[0] as AvatarCropRegion;
}

/** يسحب المؤشّر من نقطة إلى أخرى داخل إطار القصّ. */
function drag(fromX: number, fromY: number, toX: number, toY: number) {
  const el = frame();
  fireEvent.pointerDown(el, { pointerId: 1, clientX: fromX, clientY: fromY });
  fireEvent.pointerMove(el, { pointerId: 1, clientX: toX, clientY: toY });
  fireEvent.pointerUp(el, { pointerId: 1, clientX: toX, clientY: toY });
}

function setup(overrides: Partial<Parameters<typeof ImageCropper>[0]> = {}) {
  const onConfirm = vi.fn();
  const onCancel = vi.fn();
  render(
    <ImageCropper
      open
      source={makeSource(WIDE.w, WIDE.h)}
      onConfirm={onConfirm}
      onCancel={onCancel}
      {...overrides}
    />,
  );
  return { onConfirm, onCancel, save: () => saveClicked(onConfirm) };
}

describe('ImageCropper', () => {
  beforeEach(() => vi.clearAllMocks());

  describe('العرض', () => {
    it('يعرض الصورة بالحجم الذي يغطّي المربّع دون تشويه', () => {
      setup();
      expect(preview().style.width).toBe(`${WIDE.w * WIDE_SCALE}px`);
      expect(preview().style.height).toBe(`${WIDE.h * WIDE_SCALE}px`);
    });

    it('يبدأ موسّطاً: القصّ يلامس حافتي الصورة رأسياً', () => {
      const r = setup().save();
      expect(r.y).toBe(0);
      expect(r.h).toBe(1);
      // الصورة أعرض مرتين، فنأخذ نصفها الأوسط
      expect(r.x).toBeCloseTo(0.25, 6);
    });
  });

  describe('السحب', () => {
    it('السحب يميناً يُظهر جزءاً أيسر من الصورة', () => {
      const { save } = setup();
      const before = parseFloat(preview().style.left);
      drag(100, 100, 160, 100);
      // الإزاحة تتحرك نحو الصفر = الصورة تتحرك يميناً = نكشف يسارها
      expect(parseFloat(preview().style.left)).toBeGreaterThan(before);
      expect(save().x).toBeCloseTo(0.1428571, 5);
    });

    it('السحب يساراً يُظهر جزءاً أيمن من الصورة', () => {
      const { save } = setup();
      drag(100, 100, 40, 100);
      expect(save().x).toBeGreaterThan(0.25);
    });

    it('السحب رأسياً لا يخرج عن حدود الصورة', () => {
      const { save } = setup();
      // الصورة رأسياً = ضلع المربّع تماماً، فلا مجال للسحب أصلاً
      drag(100, 100, 100, 5000);
      const r = save();
      expect(r.y).toBe(0);
      expect(r.h).toBe(1);
    });

    it('لا يخرج القصّ عن حدود الصورة مهما طال السحب أفقياً', () => {
      const { save } = setup();
      drag(100, 100, 100, 100);
      const r = save();
      expect(r.x).toBeGreaterThanOrEqual(0);
      expect(r.x + r.w).toBeLessThanOrEqual(1 + 1e-9);
    });
  });

  describe('التكبير', () => {
    it('شريط التكبير يصغّر منطقة القصّ ويكبّر العرض', () => {
      const { save } = setup();
      const before = save();
      fireEvent.change(screen.getByLabelText('مستوى التكبير'), { target: { value: '3' } });
      expect(parseFloat(preview().style.width)).toBeCloseTo(WIDE.w * WIDE_SCALE * 3, 4);
      const after = save();
      expect(after.w).toBeLessThan(before.w);
      // يبقى مربّعاً بالبكسل في الصورة الأصلية
      expect(after.w * WIDE.w).toBeCloseTo(after.h * WIDE.h, 3);
    });

    it('التصغير معطّل عند الحدّ الأدنى والتكبير معطّل عند الأعلى', () => {
      setup();
      expect(screen.getByRole('button', { name: 'تصغير' })).toBeDisabled();
      expect(screen.getByRole('button', { name: 'تكبير' })).toBeEnabled();
      press('تكبير');
      expect(screen.getByRole('button', { name: 'تصغير' })).toBeEnabled();
      fireEvent.change(screen.getByLabelText('مستوى التكبير'), { target: { value: '4' } });
      expect(screen.getByRole('button', { name: 'تكبير' })).toBeDisabled();
    });

    it('إعادة الضبط تعيد الصورة موسّطة عند أدنى تكبير', () => {
      const { save } = setup();
      drag(100, 100, 40, 100);
      expect(save().x).toBeGreaterThan(0.25);
      press('إعادة الضبط');
      expect(save().x).toBeCloseTo(0.25, 6);
    });
  });

  describe('لوحة المفاتيح', () => {
    it('الأسهم تحرّك الصورة في اتجاه الضغط مثل السحب تماماً', () => {
      const { save } = setup();
      const renderedWidth = WIDE.w * WIDE_SCALE;
      // السهم خطوة 8px نحو بداية الصورة، فينقص قصّ x بمقدار 8/العرض
      fireEvent.keyDown(frame(), { key: 'ArrowRight' });
      expect(save().x).toBeCloseTo(0.25 - 8 / renderedWidth, 6);
      fireEvent.keyDown(frame(), { key: 'ArrowLeft' });
      expect(save().x).toBeCloseTo(0.25, 6); // عاد للمركز
    });

    it('Shift+السهم يتخطّى مسافة أكبر', () => {
      const { save } = setup();
      fireEvent.keyDown(frame(), { key: 'ArrowRight' });
      const normal = save().x;
      press('إعادة الضبط');

      fireEvent.keyDown(frame(), { key: 'ArrowRight', shiftKey: true });
      // إزاحة أكبر = نكشف جانباً أيسر أكثر = نِسَب x أصغر
      expect(save().x).toBeLessThan(normal);
    });

    it('يتجاهل المفاتيح الأخرى', () => {
      const { save } = setup();
      fireEvent.keyDown(frame(), { key: 'a' });
      fireEvent.keyDown(frame(), { key: 'Enter' });
      expect(save().x).toBeCloseTo(0.25, 6);
    });
  });

  describe('التأكيد والإلغاء', () => {
    it('المنطقة الافتراضية صالحة للحفظ دون أي تفاعل', () => {
      const { onConfirm, save } = setup();
      const r = save();
      expect(onConfirm).toHaveBeenCalledTimes(1);
      for (const v of [r.x, r.y, r.w, r.h]) {
        expect(Number.isFinite(v)).toBe(true);
        expect(v).toBeGreaterThanOrEqual(0);
      }
    });

    it('النقر على إلغاء يُبلَّغ به', () => {
      const { onCancel } = setup();
      press(/إلغاء/);
      expect(onCancel).toHaveBeenCalledTimes(1);
    });

    it('لا يُبلَّغ عن الإلغاء أثناء الحفظ', () => {
      const { onCancel } = setup({ saving: true });
      press(/إلغاء/);
      expect(onCancel).not.toHaveBeenCalled();
    });

    it('Escape لا يُغلق أثناء الحفظ', () => {
      const { onCancel } = setup({ saving: true });
      fireEvent.keyDown(document, { key: 'Escape' });
      expect(onCancel).not.toHaveBeenCalled();
    });
  });

  describe('الحالات الحدّية', () => {
    it('لا يعرض إطار القصّ بلا صورة', () => {
      setup({ source: null });
      expect(screen.queryByRole('application')).not.toBeInTheDocument();
      expect(screen.getByText('جارٍ تجهيز الصورة…')).toBeInTheDocument();
    });

    it('لا يعرض شيئاً إذا كان مغلقاً', () => {
      setup({ open: false });
      expect(screen.queryByRole('application')).not.toBeInTheDocument();
      expect(screen.queryByText('جارٍ تجهيز الصورة…')).not.toBeInTheDocument();
    });

    it('يتعامل مع الصور المربّعة والطويلة بلا انحراف', () => {
      for (const [w, h] of [
        [1000, 1000],
        [3000, 1000],
        [1000, 4000],
      ]) {
        const onConfirm = vi.fn();
        const { unmount } = render(
          <ImageCropper
            open
            source={makeSource(w, h)}
            onConfirm={onConfirm}
            onCancel={vi.fn()}
          />,
        );
        // سحب عبر حدود المربّع كله
        drag(100, 100, 900, 700);
        fireEvent.change(screen.getByLabelText('مستوى التكبير'), { target: { value: '4' } });
        const r = saveClicked(onConfirm);
        expect(r.w * w).toBeCloseTo(r.h * h, 3);
        expect(r.x).toBeGreaterThanOrEqual(0);
        expect(r.y).toBeGreaterThanOrEqual(0);
        expect(r.x + r.w).toBeLessThanOrEqual(1 + 1e-9);
        expect(r.y + r.h).toBeLessThanOrEqual(1 + 1e-9);
        unmount();
      }
    });
  });
});
