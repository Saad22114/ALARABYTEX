/**
 * تحميل صورة من جهاز المستخدم وتحويلها إلى الصورة الشخصية (avatar_image).
 *
 * لماذا التحويل في المتصفح؟ لأن الصورة تُخزَّن كنص base64 داخل قاعدة البيانات
 * وتُرسل مع كل استجابة تحتوي بيانات الموظف. لذلك نقصّها إلى مربّع صغير
 * ونضغطها بجودة معقولة قبل الرفع حتى لا تتضخم الحقول و Responses.
 *
 * المسار: ملف ← صورة محمّلة (مع معاينة) ← المستخدم يحدّد منطقة القصّ
 *        ← `renderCrop` يرسمها مربّعة 256px مضغوطة JPEG.
 */

import { AvatarCropRegion, cropRegionFromView, CropView } from './avatarCrop';

/** ضلع الصورة الناتجة بالبكسل — يكفي لأكبر حجم عرض للأفاتار (w-10) على شاشة 3x. */
const OUTPUT_SIZE = 256;

/** جودة ضغط JPEG (0..1). */
const OUTPUT_QUALITY = 0.82;

/** أقصى حجم للملف الأصلي قبل أي معالجة (MB) — حماية من تمديد المعالجة. */
const MAX_SOURCE_MB = 8;

/** أقصى حجم نهائي تقريبياً (KB) — يوافق حدّ الخادم (64KB بعد فك الترميز). */
const MAX_OUTPUT_KB = 60;

const ALLOWED_TYPES = ['image/jpeg', 'image/png', 'image/webp'];

/** صورة محمّلة + معاينة جاهزة للعرض في مكوّن القصّ. */
export interface AvatarSource {
  /** عنصر الصورة — يُستخدم للرسم على canvas. */
  image: HTMLImageElement;
  width: number;
  height: number;
  /** data URL للمعاينة فقط (لا يُرفع للخادم). */
  previewUrl: string;
}

export interface PreparedAvatarImage {
  dataUrl: string;
  /** الحجم النهائي بالكيلوبايت — للعرض في الواجهة. */
  sizeKb: number;
}

function loadImageElement(src: string): Promise<HTMLImageElement> {
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.onload = () => resolve(img);
    img.onerror = () =>
      reject(new Error('تعذّر قراءة الصورة — قد تكون الصيغة غير مدعومة'));
    img.src = src;
  });
}

function readAsDataUrl(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result || ''));
    reader.onerror = () => reject(new Error('تعذّر قراءة الملف'));
    reader.readAsDataURL(file);
  });
}

function dataUrlBytes(dataUrl: string): number {
  const comma = dataUrl.indexOf(',');
  if (comma < 0) return 0;
  const b64 = dataUrl.slice(comma + 1);
  return Math.floor((b64.length * 3) / 4);
}

/**
 * Step 1: يتحقّق من الملف ويعيده كصورة محمّلة جاهزة للقصّ.
 * لا يحوّل شيئاً — التحويل يعتمد على منطقة القصّ التي يختارها المستخدم.
 */
export async function loadAvatarSource(file: File): Promise<AvatarSource> {
  if (!ALLOWED_TYPES.includes(file.type)) {
    throw new Error('صيغة الصورة غير مدعومة — اختر ملف JPEG أو PNG أو WebP');
  }
  if (file.size > MAX_SOURCE_MB * 1024 * 1024) {
    throw new Error(`حجم الصورة يجب ألا يتجاوز ${MAX_SOURCE_MB} ميجابايت`);
  }

  const previewUrl = await readAsDataUrl(file);
  const image = await loadImageElement(previewUrl);
  const width = image.naturalWidth;
  const height = image.naturalHeight;
  if (!width || !height) {
    throw new Error('تعذّر قراءة الصورة — الملف قد يكون تالفاً');
  }
  return { image, width, height, previewUrl };
}

/**
 * Step 2: يرسم منطقة القصّ المختارة إلى data URL مربّع صغير وجاهز للرفع.
 *
 * يقبل `region` (نِسَب 0..1) مباشرةً، أو `view` (حالة العرض) ليحوّلها
 * عبر `cropRegionFromView` — حتى لا يختلف الحساب بين ما رآه المستخدم وما يُرسم.
 */
export function renderCrop(
  source: AvatarSource,
  regionOrView: AvatarCropRegion | CropView,
): PreparedAvatarImage {
  const region = isCropView(regionOrView)
    ? cropRegionFromView(regionOrView)
    : regionOrView;

  const canvas = document.createElement('canvas');
  canvas.width = OUTPUT_SIZE;
  canvas.height = OUTPUT_SIZE;
  const ctx = canvas.getContext('2d');
  if (!ctx) throw new Error('تعذّر تجهيز الصورة في المتصفح');
  ctx.imageSmoothingEnabled = true;
  ctx.imageSmoothingQuality = 'high';
  // خلفية بيضاء لأن JPEG لا يدعم الشفافية (مهم لصور PNG)
  ctx.fillStyle = '#ffffff';
  ctx.fillRect(0, 0, OUTPUT_SIZE, OUTPUT_SIZE);

  // نمنع أي منطقة خارج حدود الصورة (حزام أمان ضدّ البكسلات الشفافة)
  const x = Math.max(0, Math.min(1, region.x));
  const y = Math.max(0, Math.min(1, region.y));
  const w = Math.max(0, Math.min(1 - x, region.w));
  const h = Math.max(0, Math.min(1 - y, region.h));
  if (w <= 0 || h <= 0) throw new Error('منطقة القصّ غير صالحة');

  ctx.drawImage(
    source.image,
    x * source.width,
    y * source.height,
    w * source.width,
    h * source.height,
    0,
    0,
    OUTPUT_SIZE,
    OUTPUT_SIZE,
  );

  let dataUrl = canvas.toDataURL('image/jpeg', OUTPUT_QUALITY);
  let quality = OUTPUT_QUALITY;

  // خفّض الجودة تدريجياً إن تجاوز الناتج حدّ الخادم
  while (dataUrlBytes(dataUrl) > MAX_OUTPUT_KB * 1024 && quality > 0.4) {
    quality -= 0.1;
    dataUrl = canvas.toDataURL('image/jpeg', quality);
  }

  const bytes = dataUrlBytes(dataUrl);
  if (bytes > MAX_OUTPUT_KB * 1024) {
    throw new Error('تعذّر تصغير الصورة إلى الحجم المسموح — اختر صورة أصغر');
  }

  return { dataUrl, sizeKb: Math.max(1, Math.round(bytes / 1024)) };
}

function isCropView(value: AvatarCropRegion | CropView): value is CropView {
  return 'stage' in value;
}
