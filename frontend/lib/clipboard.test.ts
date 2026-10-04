import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { copyText } from './clipboard';

/**
 * النسخُ إلى الحافظة اختبارٌ خطِرٌ لسببٍ لا يُرى: حين يفشلُ النسخُ
 * وتُدّعي الدالةُ نجاحاً كاذباً، يلصقُ الموظفُ رقماً قديماً في فاتورة
 * زبونٍ آخر. فكلُّ اختبارٍ هنا يُثبت أنَّ الفشلَ يُبلَّغُ بدل أن يُخفى،
 * وأنَّ العنصرَ المؤقّتَ لا يبقى معلَّقاً في الصفحة.
 */

/** يجعل execCommand متاحاً، ويلتقط ما كان في الحقل لحظة النسخ. */
function stubExecCommand(result: boolean | (() => boolean)) {
  const seen: string[] = [];
  const fn = vi.fn((cmd: string) => {
    const area = document.querySelector('textarea');
    if (area) seen.push(area.value);
    return typeof result === 'function' ? result() : result;
  });
  Object.defineProperty(document, 'execCommand', { value: fn, configurable: true });
  return { fn, seen };
}

describe('copyText', () => {
  beforeEach(() => {
    document.body.innerHTML = '';
  });

  afterEach(() => {
    Reflect.deleteProperty(document, 'execCommand');
  });

  it('uses the modern clipboard when the browser has one', async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    const ok = await copyText('0561 000009', { navigator: { clipboard: { writeText } } });
    expect(ok).toBe(true);
    expect(writeText).toHaveBeenCalledWith('0561 000009');
  });

  it('falls back when there is no navigator.clipboard at all, as on plain http', async () => {
    // هذا هو حالُ المحلّ على شبكةٍ داخلية: navigator.clipboard غيرُ معرَّف،
    // لا راجعاً ولا مرفوضاً. وهو ما كان يجعلُ الضغمةَ تفعلُ شيئاً ظاهراً.
    const { fn, seen } = stubExecCommand(true);
    const ok = await copyText('968 9911 2233', { navigator: null });
    expect(ok).toBe(true);
    expect(fn).toHaveBeenCalledWith('copy');
    expect(seen).toEqual(['968 9911 2233']);
  });

  it('falls back when the modern clipboard is refused', async () => {
    const writeText = vi.fn().mockRejectedValue(new Error('NotAllowedError'));
    const { fn } = stubExecCommand(true);
    const ok = await copyText('0561000009', { navigator: { clipboard: { writeText } } });
    expect(ok).toBe(true);
    expect(writeText).toHaveBeenCalled();
    expect(fn).toHaveBeenCalledWith('copy');
  });

  it('reports failure rather than pretending, when both routes are shut', async () => {
    stubExecCommand(false);
    const writeText = vi.fn().mockRejectedValue(new Error('denied'));
    const ok = await copyText('0561000009', { navigator: { clipboard: { writeText } } });
    expect(ok).toBe(false);
  });

  it('reports failure when the browser removed execCommand too', async () => {
    // متصفّحٌ حديثٌ أسقط الأمرَ القديم، وإذنُ الكتابةِ منتهٍ: لا شيء
    // ينفع، والواجهةُ يجب أن تقول «تعذّر النسخ» لا «تمّ».
    const writeText = vi.fn().mockRejectedValue(new Error('denied'));
    const ok = await copyText('0561000009', { navigator: { clipboard: { writeText } } });
    expect(ok).toBe(false);
  });

  it('survives an execCommand that throws', async () => {
    Object.defineProperty(document, 'execCommand', {
      value: () => { throw new Error('boom'); },
      configurable: true,
    });
    const ok = await copyText('0561000009', { navigator: null });
    expect(ok).toBe(false);
  });

  it('refuses to copy nothing', async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    const { fn } = stubExecCommand(true);
    expect(await copyText('   ', { navigator: { clipboard: { writeText } } })).toBe(false);
    expect(writeText).not.toHaveBeenCalled();
    expect(fn).not.toHaveBeenCalled();
  });

  it('copies the text as written, not a tidied version of it', async () => {
    // الرقمُ المنسوخُ هو ما سيراه المتلقّي، فتنقيتُه نيابةً عنه، كإسقاطِ
    // الفراغات مثلاً، تفصيلةٌ تغيّرُ ما عوّدناه عليه، ولا خِوَلَ عليها.
    const { seen } = stubExecCommand(true);
    await copyText('  05 61 000 009  ', { navigator: null });
    expect(seen).toEqual(['05 61 000 009']);
  });

  it('leaves no stray node in the page after copying', async () => {
    stubExecCommand(true);
    await copyText('0561000009', { navigator: null });
    expect(document.querySelector('textarea')).toBeNull();
    expect(document.body.innerHTML).toBe('');
  });

  it('leaves no stray node behind even when the copy failed', async () => {
    stubExecCommand(false);
    await copyText('0561000009', { navigator: null });
    expect(document.querySelector('textarea')).toBeNull();
  });

  it('gives the caret back to the field the user was in', async () => {
    // الطريقةُ القديمة تركّزُ حقلاً مؤقّتاً وتحذفه، فيخرج المؤشِّرُ من
    // الحقل الذي يكتب فيه الموظف. على محلٍّ بلا HTTPS، هذا ما يحدثُ في
    // كل ضغطةِ نسخ، وهذا أَولى ما يلاحَظ.
    stubExecCommand(true);
    const field = document.createElement('input');
    document.body.appendChild(field);
    field.focus();
    expect(document.activeElement).toBe(field);

    await copyText('0561000009', { navigator: null });
    expect(document.activeElement).toBe(field);
  });

  it('does not steal focus on the modern path either', async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    const field = document.createElement('input');
    document.body.appendChild(field);
    field.focus();
    await copyText('0561000009', { navigator: { clipboard: { writeText } } });
    expect(document.activeElement).toBe(field);
  });
});
