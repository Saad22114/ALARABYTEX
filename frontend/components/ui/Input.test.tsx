import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import Input, { sanitizeNumeric } from './Input';

describe('sanitizeNumeric', () => {
  it('keeps plain digits', () => {
    expect(sanitizeNumeric('12345', true)).toBe('12345');
    expect(sanitizeNumeric('12345', false)).toBe('12345');
  });

  it('keeps a single decimal separator in decimal mode', () => {
    expect(sanitizeNumeric('12.50', true)).toBe('12.50');
    expect(sanitizeNumeric('12,50', true)).toBe('12.50');
  });

  it('drops a second decimal separator', () => {
    expect(sanitizeNumeric('1.2.3', true)).toBe('1.23');
  });

  it('drops the decimal separator entirely in int mode', () => {
    expect(sanitizeNumeric('12.5', false)).toBe('125');
    expect(sanitizeNumeric('12,5', false)).toBe('125');
  });

  it('strips letters and symbols', () => {
    expect(sanitizeNumeric('12a3', true)).toBe('123');
    expect(sanitizeNumeric('12-3', true)).toBe('123');
    expect(sanitizeNumeric('1e5', true)).toBe('15');
    expect(sanitizeNumeric('12$', true)).toBe('12');
  });

  it('converts Arabic-Indic and Persian digits to Latin', () => {
    expect(sanitizeNumeric('١٢٣', true)).toBe('123');
    expect(sanitizeNumeric('۱۲۳', true)).toBe('123');
  });

  it('converts the Arabic decimal separator', () => {
    expect(sanitizeNumeric('١٢٫٥', true)).toBe('12.5');
  });

  it('handles empty and separator-only input', () => {
    expect(sanitizeNumeric('', true)).toBe('');
    expect(sanitizeNumeric('.', true)).toBe('.');
  });
});

describe('Input numeric behaviour', () => {
  it('renders a tel input with decimal keypad for type="number"', () => {
    render(<Input type="number" value="" onChange={() => {}} />);
    const el = screen.getByRole('textbox') as HTMLInputElement;
    expect(el.type).toBe('tel');
    expect(el.inputMode).toBe('decimal');
  });

  it('renders a digits-only keypad for numeric="int"', () => {
    render(<Input type="number" numeric="int" value="" onChange={() => {}} />);
    const el = screen.getByRole('textbox') as HTMLInputElement;
    expect(el.inputMode).toBe('numeric');
    expect(el.pattern).toBe('[0-9]*');
  });

  // fireEvent returns false when the handler called preventDefault. That is the
  // only honest way to test this: jsdom inserts no text on keydown, so an
  // "onChange was not called" assertion passes whether the key was blocked or
  // not -- which is exactly how the decimal point stayed blocked unnoticed.
  it('blocks letter keys', () => {
    render(<Input type="number" value="" onChange={() => {}} />);
    const el = screen.getByRole('textbox') as HTMLInputElement;
    expect(fireEvent.keyDown(el, { key: 'a' })).toBe(false);
  });

  it('allows digit keys', () => {
    render(<Input type="number" value="" onChange={() => {}} />);
    const el = screen.getByRole('textbox') as HTMLInputElement;
    expect(fireEvent.keyDown(el, { key: '5' })).toBe(true);
  });

  it('leaves navigation and editing keys alone', () => {
    render(<Input type="number" value="" onChange={() => {}} />);
    const el = screen.getByRole('textbox') as HTMLInputElement;
    for (const key of ['Backspace', 'Delete', 'ArrowLeft', 'ArrowRight',
                       'Home', 'End', 'Tab', 'Enter']) {
      expect(fireEvent.keyDown(el, { key })).toBe(true);
    }
  });

  it('sanitizes pasted text via sanitizeNumeric', () => {
    // The paste handler calls sanitizeNumeric; test the function directly
    expect(sanitizeNumeric('12a3.45', true)).toBe('123.45');
  });

  it('clamps to min on blur', () => {
    const onChange = vi.fn();
    render(<Input type="number" numeric="int" min={1} value="0" onChange={onChange} />);
    const el = screen.getByRole('textbox') as HTMLInputElement;
    fireEvent.blur(el);
    expect(onChange).toHaveBeenCalled();
  });

  it('does not clamp when empty', () => {
    const onChange = vi.fn();
    render(<Input type="number" numeric="int" min={1} value="" onChange={onChange} />);
    const el = screen.getByRole('textbox') as HTMLInputElement;
    fireEvent.blur(el);
    expect(onChange).not.toHaveBeenCalled();
  });

  it('leaves non-numeric inputs untouched', () => {
    render(<Input value="" onChange={() => {}} />);
    const el = screen.getByRole('textbox') as HTMLInputElement;
    expect(el.type).toBe('text');
    expect(el.inputMode).toBe('');
  });
});

/**
 * «اريد اكتب 1.4 يكتب 14» — the dot is the whole meaning of a decimal field.
 *
 * The keypad was already right (inputMode="decimal"), and the sanitiser already
 * kept one dot. The keydown guard in between rejected every single-character key
 * that was not a digit, so on any keyboard that emits a key event for the
 * decimal key -- Android's decimal pad does -- the dot never arrived.
 */
describe('the decimal point', () => {
  it('is not blocked in a decimal field', () => {
    render(<Input type="number" value="" onChange={() => {}} />);
    const el = screen.getByRole('textbox') as HTMLInputElement;
    expect(fireEvent.keyDown(el, { key: '.' })).toBe(true);
  });

  it('is accepted in whichever form the keyboard sends it', () => {
    render(<Input type="number" value="" onChange={() => {}} />);
    const el = screen.getByRole('textbox') as HTMLInputElement;
    for (const key of [',', '٫', '٬', '،']) {
      expect(fireEvent.keyDown(el, { key })).toBe(true);
    }
  });

  it('is still blocked where the field is a whole number', () => {
    render(<Input type="number" numeric="int" value="" onChange={() => {}} />);
    const el = screen.getByRole('textbox') as HTMLInputElement;
    expect(fireEvent.keyDown(el, { key: '.' })).toBe(false);
  });

  it('still blocks letters and arithmetic keys', () => {
    render(<Input type="number" value="" onChange={() => {}} />);
    const el = screen.getByRole('textbox') as HTMLInputElement;
    for (const key of ['a', 'e', '-', '+', '$', '*', '/']) {
      expect(fireEvent.keyDown(el, { key })).toBe(false);
    }
  });

  it('reads 1 . 4 as 1.4', () => {
    // Assert on what the page receives, not on el.value: a controlled input
    // with a no-op onChange is re-rendered back to "", so the DOM value says
    // nothing about what the field decided.
    const seen: string[] = [];
    render(<Input type="number" value="" onChange={(e) => seen.push(e.target.value)} />);
    const el = screen.getByRole('textbox') as HTMLInputElement;
    expect(fireEvent.keyDown(el, { key: '.' })).toBe(true);
    fireEvent.change(el, { target: { value: '1.4' } });
    expect(seen).toEqual(['1.4']);
  });

  it('collapses a second dot rather than letting it through', () => {
    // Letting the key through must not mean letting nonsense through: the
    // sanitiser is still the only gate on what ends up in the database.
    const seen: string[] = [];
    render(<Input type="number" value="" onChange={(e) => seen.push(e.target.value)} />);
    const el = screen.getByRole('textbox') as HTMLInputElement;
    fireEvent.change(el, { target: { value: '1.4.5' } });
    expect(seen).toEqual(['1.45']);
  });

  it('drops the dot in an int field at the value level too', () => {
    const seen: string[] = [];
    render(
      <Input type="number" numeric="int" value="" onChange={(e) => seen.push(e.target.value)} />
    );
    const el = screen.getByRole('textbox') as HTMLInputElement;
    fireEvent.change(el, { target: { value: '1.4' } });
    expect(seen).toEqual(['14']);
  });

  });
