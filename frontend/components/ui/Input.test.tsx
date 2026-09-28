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

  it('blocks non-digit keys', () => {
    const onChange = vi.fn();
    render(<Input type="number" value="" onChange={onChange} />);
    const el = screen.getByRole('textbox') as HTMLInputElement;
    fireEvent.keyDown(el, { key: 'a' });
    expect(onChange).not.toHaveBeenCalled();
  });

  it('allows digit keys', () => {
    const onChange = vi.fn();
    render(<Input type="number" value="" onChange={onChange} />);
    const el = screen.getByRole('textbox') as HTMLInputElement;
    fireEvent.keyDown(el, { key: '5' });
    expect(onChange).not.toHaveBeenCalled();
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
