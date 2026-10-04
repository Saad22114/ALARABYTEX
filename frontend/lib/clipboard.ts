/**
 * نسخٌ إلى الحافظة، ليبقى بين الموظف والرقم ضغطةٌ واحدة.
 *
 * الواجهةُ الحديثة `navigator.clipboard` لا وجودَ لها إلّا في سياقٍ آمن:
 * HTTPS أو localhost. وهذا النظامُ يعملُ في محلّاتٍ تفتحه من شبكةٍ داخليةٍ
 * على http، فلا يكون `navigator.clipboard` معرَّفاً أصلاً. والطريقةُ القديمة
 * `document.execCommand` ما زالت تعملُ هناك، فاستعمالُ الاثنتين معاً ليس
 * ترفاً بل ضرورة.
 *
 * سببُ الرجوعِ إلى الثانية بعد فشلِ الأولى: إذنُ الكتابةِ يُمنحُ للموقع
 * مرّةً ثمّ يتلاشى، فيرفضُ المتصفحُ ما يقبلُه قبلُ دقائق. ولا نريد أن يقول
 * الموظف «تمّ النسخ» ثمّ يلصقَ في دفترِ زبونٍ آخر نصّاً قديماً.
 */

/** ما نحتاجُه من البيئة، مفصولاً ليسهل اختبارُه فوق jsdom. */
type ClipEnv = {
  navigator?: { clipboard?: { writeText(text: string): Promise<void> } } | null;
  document: Document;
};

function envFrom(real: Partial<ClipEnv> | undefined): ClipEnv {
  const given = real ?? {};
  const nav = 'navigator' in given
    ? given.navigator
    : typeof navigator === 'undefined' ? null : navigator;
  return { navigator: nav, document: given.document ?? document };
}

/**
 * الطريقةُ القديمة. المتصفّحُ يختارُ العنصرَ بنفسه ولا يقرأُ المحفظةَ مباشرةً،
 * فلمّا يُحجبُ كلٌّ من `navigator.clipboard` و`execCommand` نُبلغُ الفشلَ
 * صريحاً بدل أن ندّعي نجاحاً كاذباً.
 *
 * العنصرُ الخفيُّ يبقى في الصفحة، لأنّ iOS يرفضُ النسخَ من عنصرٍ خارج
 * الشاشة، ويُكتبُ فيه بـ`contentEditable` لأنّ iOS يرفضُ `select()` على
 * حقلٍ للقراءة وحده. وكلاهما يُنظَّف بعدها فلا يبقى في الصفحة نصٌّ غيرُ
 * مرئيٍّ بعد الضغطة.
 */
function copyBySelection(doc: Document, text: string): boolean {
  const area = doc.createElement('textarea');
  area.value = text;
  area.contentEditable = 'true';
  area.readOnly = false;
  area.setAttribute('aria-hidden', 'true');
  area.setAttribute('autocomplete', 'off');
  area.style.position = 'fixed';
  area.style.top = '0';
  area.style.left = '0';
  area.style.width = '1px';
  area.style.height = '1px';
  area.style.padding = '0';
  area.style.border = 'none';
  area.style.outline = 'none';
  area.style.boxShadow = 'none';
  area.style.background = 'transparent';
  area.style.opacity = '0';

  const body = doc.body;
  if (!body) return false;
  // الطريقةُ القديمة تُنتزعُ التركيزَ إلى الحقل المؤقّت، ولا تُعيده. فبدون
  // هذا، ينتهي أمرُ النسخُ بأن يكون المؤشِّرُ قد ضاع من الحقل الذي كان
  // الموظفُ يكتب فيه — وهو أسوأُ من ألّا ينسخ.
  const active = doc.activeElement as HTMLElement;
  body.appendChild(area);
  try {
    area.focus({ preventScroll: true });
    // setSelectionRange هي ما يجعل iOS يقبل النسخ؛ select وحدها لا تكفي.
    area.select();
    area.setSelectionRange(0, text.length);
    if (typeof doc.execCommand !== 'function') return false;
    return doc.execCommand('copy') === true;
  } catch {
    return false;
  } finally {
    body.removeChild(area);
    const restorable = active !== body && doc.contains(active)
      && typeof active.focus === 'function';
    if (restorable) {
      try {
        active.focus({ preventScroll: true });
      } catch {
        // عنصرٌ رحل بين الضغطة والإعادة؛ الإعادةُ إكرامٌ لا شرط.
      }
    }
  }
}

/**
 * ينسخُ نصاً، ويُرجعُ قادطةً بقدرَ نجح. فشلٍ صريحٌ خيرٌ من نجاحٍ كاذبؚ
 * لصقُ نصٍّ قديمٍ في فاتورةِ زبونٍ خطأٌ لا يُكتشَف.
 *
 * نصٌّ فارغٌ لا يُنسخ، لأنّ الضغطةَ عندها خطأُ المستخدم لا عطلٌ فينا،
 * وتُرجِعُ false لئلّا تقول الواجهةُ «تمّ النسخ» وهي لم تنسخ شيئاً.
 */
export async function copyText(text: string, real?: Partial<ClipEnv>): Promise<boolean> {
  const value = (text || '').trim();
  if (!value) return false;

  const env = envFrom(real);
  const modern = env.navigator && env.navigator.clipboard;
  if (modern && typeof modern.writeText === 'function') {
    try {
      await modern.writeText(value);
      return true;
    } catch {
      // إذنٌ منتهٍ، أو سياقٌ لم يذن بعد — نجرّبُ القديمة.
    }
  }
  try {
    return copyBySelection(env.document, value);
  } catch {
    return false;
  }
}
