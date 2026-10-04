/**
 * Enter ينقلُ إلى الحقل التالي في سطرِ البيع، ولا يحفظُ شيئاً.
 *
 * البائعُ يكتب صنفاً ثمّ الذي يليه، وهو يعودُ إلى الشاشة أربعَ مرّات في
 * الثانية. فلو ناقلَه Enterُ إلى الحقل التالي لَما احتاج المؤشِّرُ إلى
 * الشاشة أصلاً.
 *
 * وثلاثةُ أشياءٍ قُصدَ بها ألّا يفعل:
 *
 * - لا يحفظ. أصنافُ السلةِ كلُّها تُضافُ معاً، فيُجيب Enterُ وهو في أوّل
 *   خانةٍ فيضيف ما لم يكتمل. فالانتقالُ يتوقّفُ عند آخر خانةٍ في السطر،
 *   والحفظُ يبقى على زرِّه.
 *
 * - يتجاهلُ Shift+Enter، لأنّها في مربّع النصِّ سطرٌ جديد لا انتقال.
 *
 * - يتجاهلُ Enterَ أثناء التكوين. وهذا سطرُ واحدٌ قد يمرض في نظامٍ
 *   عربي: الضغطةُ التي تُثبِّتُ الكلمةَ التي يختارها الموظفُ من قائمةِ
 *   اللغة هي Enterُ نفسها. ولو ابتلعناها لَزمه مرّتان لكلّ كلمة.
 */

const FOCUSABLE = [
  'input:not([type="hidden"])',
  'select',
  'textarea',
  '[tabindex]:not([tabindex="-1"])',
].join(', ');

/** ما نحتاجُه من الحدث، شكلاً لا واجهةَ كاملة، فيختبرُه نصٌّ بسيط. */
export type EnterEvent = {
  key: string;
  shiftKey?: boolean;
  altKey?: boolean;
  target: EventTarget | null;
  currentTarget: EventTarget | null;
  nativeEvent?: { isComposing?: boolean };
  preventDefault(): void;
};

function usable(el: HTMLElement): boolean {
  if (el.hasAttribute('disabled')) return false;
  if (el.getAttribute('aria-hidden') === 'true') return false;
  if (el instanceof HTMLInputElement && el.type === 'hidden') return false;
  return true;
}

/**
 * يُرجع true حين نقلَ التركيز، وfalse حين لا شيءَ يستحقّ النقل. وfalse
 * إشارةٌ إلى أنّ الحدثَ تُركَ للمتصفّح يعمل، فلا يُمنع.
 */
export function enterMovesFocus(event: EnterEvent): boolean {
  if (event.key !== 'Enter') return false;
  if (event.shiftKey || event.altKey) return false;
  if (event.nativeEvent && event.nativeEvent.isComposing) return false;

  const root = event.currentTarget as HTMLElement | null;
  const from = event.target as HTMLElement | null;
  if (!root || !from || root === from) return false;
  if (!root.contains(from)) return false;

  const fields = Array.from(root.querySelectorAll<HTMLElement>(FOCUSABLE)).filter(usable);
  const at = fields.indexOf(from);
  // ولا التفافٌ إلى أوّل السطر. آخرُ حقلٍ في السطر هو آخرُ ما فيه،
  // وEnterُ بعدها تعني «فعلتُ ما ينبغي» لا «عدْ إلى أوّل».
  if (at < 0 || at + 1 >= fields.length) return false;

  event.preventDefault();
  fields[at + 1].focus();
  return true;
}
