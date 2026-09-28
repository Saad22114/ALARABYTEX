/**
 * حساب هندسي للقصّ (crop) — **منطق خالص بلا DOM** ليسهل اختباره.
 *
 * Terminology:
 * - `stage`: ضلع مربّع العرض بالبكسل (مساحة القصّ المرئية).
 * - `zoom`: نسبة تكبير فوق مقياس «تغطية المربّع» (1 = الصورة تملأ المربّع تماماً).
 * - `offsetX/offsetY`: موضع الصورة داخل المربّع بالبكسل (≤ 0، يُقتص ما يكفي لتغطية).
 *
 * استُخرج من `avatarImage.ts` ومن مكوّن `ImageCropper` لأن نفس الحساب يحتاجه
 * العرض (لتحديد موضع `<img>`) والرسم النهائي على canvas — وفصله يمنع تطابقهما.
 */

/** مربّع القصّ كنِسَب من أبعاد الصورة الأصلية (0..1). */
export interface AvatarCropRegion {
  x: number;
  y: number;
  w: number;
  h: number;
}

/** الحالة الكاملة لعرض القصّ. */
export interface CropView {
  stage: number;
  imageWidth: number;
  imageHeight: number;
  zoom: number;
  offsetX: number;
  offsetY: number;
}

export const MIN_ZOOM = 1;
export const MAX_ZOOM = 4;
export const ZOOM_STEP = 0.1;

function clamp01(n: number): number {
  if (!Number.isFinite(n)) return 0;
  return Math.min(1, Math.max(0, n));
}

export function clampZoom(zoom: number): number {
  // NaN ليس قيمة有意义 → نرجع للحدّ الأدنى. أما ±Infinity فتُقصّ إلى الطرفين.
  if (Number.isNaN(zoom)) return MIN_ZOOM;
  return Math.min(MAX_ZOOM, Math.max(MIN_ZOOM, zoom));
}

/** مقياس الرسم عند zoom=1 — أصغر مقياس يغطّي المربّع بالكامل (cover). */
export function coverScale(
  stage: number,
  imageWidth: number,
  imageHeight: number,
): number {
  if (!(stage > 0) || !(imageWidth > 0) || !(imageHeight > 0)) return 1;
  return Math.max(stage / imageWidth, stage / imageHeight);
}

/** أبعاد الصورة كما تُعرض داخل المربّع (بالبكسل). */
export function renderedSize(
  stage: number,
  imageWidth: number,
  imageHeight: number,
  zoom: number,
): { width: number; height: number; scale: number } {
  const scale = coverScale(stage, imageWidth, imageHeight) * clampZoom(zoom);
  return { width: imageWidth * scale, height: imageHeight * scale, scale };
}

/** يمنع انزلاق الصورة خارج المربّع — يجب أن تغطّيه دائماً. */
export function clampOffset(
  offset: number,
  renderedLength: number,
  stage: number,
): number {
  if (!(stage > 0) || !(renderedLength > 0)) return 0;
  const min = stage - renderedLength; // سالب دائماً لأن coverScale يضمن التغطية
  return Math.min(0, Math.max(min, offset));
}

/** يقصّ الإزاحات والزoom إلى نطاق صالح — يُستدعى بعد أي تغيير. */
export function clampView(view: CropView): CropView {
  const zoom = clampZoom(view.zoom);
  const { width, height } = renderedSize(
    view.stage,
    view.imageWidth,
    view.imageHeight,
    zoom,
  );
  return {
    ...view,
    zoom,
    offsetX: clampOffset(view.offsetX, width, view.stage),
    offsetY: clampOffset(view.offsetY, height, view.stage),
  };
}

/** حالة البداية: الصورة موسّطة عند أقل تكبير. */
export function centerView(
  stage: number,
  imageWidth: number,
  imageHeight: number,
  zoom: number = MIN_ZOOM,
): CropView {
  const z = clampZoom(zoom);
  const { width, height } = renderedSize(stage, imageWidth, imageHeight, z);
  return {
    stage,
    imageWidth,
    imageHeight,
    zoom: z,
    offsetX: (stage - width) / 2,
    offsetY: (stage - height) / 2,
  };
}

/**
 * يحوّل حالة العرض إلى منطقة قصّ normalised داخل الصورة الأصلية.
 *
 * بكسل الصورة عند الإحداثي `cx` من المربّع هو `(cx - offset) / scale`،
 * لذلك بداية القصّ عند `cx = 0` تعطي `-offset / renderedLength` كنسبة.
 * الضلع `stage` يُترجم إلى `stage / renderedLength` — وهو دائماً مربّع
 * بالبكسل لأن المقياس موحّد على المحورين.
 */
export function cropRegionFromView(view: CropView): AvatarCropRegion {
  const { stage, imageWidth, imageHeight } = view;
  const { width, height } = renderedSize(
    stage,
    imageWidth,
    imageHeight,
    view.zoom,
  );
  const offsetX = clampOffset(view.offsetX, width, stage);
  const offsetY = clampOffset(view.offsetY, height, stage);
  return {
    x: clamp01(-offsetX / width),
    y: clamp01(-offsetY / height),
    w: clamp01(stage / width),
    h: clamp01(stage / height),
  };
}
