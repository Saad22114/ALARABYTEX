import { describe, it, expect, beforeEach, vi } from 'vitest';
import { enterMovesFocus, EnterEvent } from './keyFlow';

/**
 * هذا ما يجعلُ البائعَ يكتبُ صنفاً بلا أن يرفعَ يده عن لوحة المفاتيح.
 * فالخطرُ ليس أن ينقصَ transferring، بل أن يفعلَ أكثرَ ممّا طُلب منه:
 * أن يضيفَ سلةً لم تكتمل، أو أن يبتلعَ Enterَ التي بها يختارُ كلمتَه
 * العربية. فالاختبارُ هنا على ما يجب ألّا يقع.
 */

function row(fields: string[]): HTMLElement {
  const root = document.createElement('div');
  root.innerHTML = fields.join('');
  document.body.appendChild(root);
  return root;
}

function press(el: HTMLElement, root: HTMLElement, opts: Partial<EnterEvent> = {}) {
  const preventDefault = vi.fn();
  const event: EnterEvent = {
    key: 'Enter',
    target: el,
    currentTarget: root,
    preventDefault,
    ...opts,
  };
  const moved = enterMovesFocus(event);
  return { moved, preventDefault };
}

describe('enterMovesFocus', () => {
  beforeEach(() => {
    document.body.innerHTML = '';
  });

  it('moves from the quantity to the price', () => {
    const root = row(['<input id="q" />', '<input id="p" />', '<input id="d" />']);
    const q = root.querySelector('#q') as HTMLInputElement;
    const p = root.querySelector('#p') as HTMLInputElement;
    q.focus();
    expect(press(q, root).moved).toBe(true);
    expect(document.activeElement).toBe(p);
  });

  it('moves on from a native select too, as the fabric picker is', () => {
    const root = row(['<select id="f"></select>', '<input id="q" />']);
    const f = root.querySelector('#f') as HTMLSelectElement;
    const q = root.querySelector('#q') as HTMLInputElement;
    expect(press(f, root).moved).toBe(true);
    expect(document.activeElement).toBe(q);
  });

  it('stops at the last field and never wraps back to the first', () => {
    // الالتفافُ هو فخُّ الأنظمة: آخرُ خانةٍ ثمّ Enterُ فترجعُ إلى الأولى
    // فيُعيد الموظفُ كتابةَ ما كتب، أو يظنّ أنّه بدأ صفاً جديداً.
    const root = row(['<input id="q" />', '<input id="d" />']);
    const d = root.querySelector('#d') as HTMLInputElement;
    d.focus();
    const { moved, preventDefault } = press(d, root);
    expect(moved).toBe(false);
    expect(preventDefault).not.toHaveBeenCalled();
    expect(document.activeElement).toBe(d);
  });

  it('leaves Enter alone while an Arabic word is being composed', () => {
    // Enterُ هنا ليست «انتقل» بل «أَثبِت الكلمة التي أختارها من قائمة
    // اللغة». ابتلاعُها يجعلُ كلّ كلمةٍ تحتاجُ ضغطةً ثانية.
    const root = row(['<input id="a" />', '<input id="b" />']);
    const a = root.querySelector('#a') as HTMLInputElement;
    const { moved, preventDefault } = press(a, root, { nativeEvent: { isComposing: true } });
    expect(moved).toBe(false);
    expect(preventDefault).not.toHaveBeenCalled();
  });

  it('leaves Shift+Enter alone, for the newline in a textarea', () => {
    const root = row(['<textarea id="t"></textarea>', '<input id="b" />']);
    const t = root.querySelector('#t') as HTMLTextAreaElement;
    expect(press(t, root, { shiftKey: true }).moved).toBe(false);
  });

  it('steps over a disabled field rather than focusing a dead one', () => {
    const root = row(['<input id="q" />', '<input id="p" disabled />', '<input id="d" />']);
    const q = root.querySelector('#q') as HTMLInputElement;
    const d = root.querySelector('#d') as HTMLInputElement;
    expect(press(q, root).moved).toBe(true);
    expect(document.activeElement).toBe(d);
  });

  it('stays inside its own row and cannot reach the next line', () => {
    const root = row(['<input id="q" />', '<input id="d" />']);
    const other = document.createElement('input');
    document.body.appendChild(other);
    const d = root.querySelector('#d') as HTMLInputElement;
    expect(press(d, root).moved).toBe(false);
    expect(document.activeElement).not.toBe(other);
  });

  it('cancels the default only when it actually moved', () => {
    const root = row(['<input id="q" />', '<input id="p" />']);
    const q = root.querySelector('#q') as HTMLInputElement;
    expect(press(q, root).preventDefault).toHaveBeenCalled();
  });

  it('ignores keys that are not Enter', () => {
    const root = row(['<input id="q" />', '<input id="p" />']);
    const q = root.querySelector('#q') as HTMLInputElement;
    for (const key of ['a', 'Tab', 'ArrowDown', 'Escape', ' ']) {
      expect(press(q, root, { key }).moved).toBe(false);
    }
  });

  it('does nothing when the focus is not on a field of the row, such as a button', () => {
    // الأزرارُ ليست في الحقل التالي، ولو التقطناها لأعطينا زرَّ نوعِ
    // البيع فعلاً غيرَ الذي عليه.
    const root = row(['<input id="q" />', '<button id="b">ياردة</button>']);
    const b = root.querySelector('#b') as HTMLButtonElement;
    const { moved, preventDefault } = press(b, root);
    expect(moved).toBe(false);
    expect(preventDefault).not.toHaveBeenCalled();
  });

  it('ignores a hidden input', () => {
    const root = row(['<input type="hidden" id="h" />', '<input id="q" />']);
    const h = root.querySelector('#h') as HTMLInputElement;
    expect(press(h, root).moved).toBe(false);
  });

  it('does not throw when the row is empty', () => {
    const root = row([]);
    expect(press(root, root).moved).toBe(false);
  });
});
