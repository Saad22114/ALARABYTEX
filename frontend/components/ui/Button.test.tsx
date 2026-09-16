import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import Button from './Button';

describe('Button', () => {
  it('renders children and default styling', () => {
    render(<Button>احفظ</Button>);
    const btn = screen.getByRole('button', { name: 'احفظ' });
    expect(btn).toBeInTheDocument();
    expect(btn.className).toContain('bg-brand-600');
  });

  it('is disabled while loading', () => {
    render(<Button loading>حفظ</Button>);
    expect(screen.getByRole('button', { name: 'حفظ' })).toBeDisabled();
  });

  it('forwards click handlers', () => {
    const onClick = vi.fn();
    render(<Button onClick={onClick}>تأكيد</Button>);
    fireEvent.click(screen.getByRole('button', { name: 'تأكيد' }));
    expect(onClick).toHaveBeenCalledTimes(1);
  });
});