import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import CopyButton from './CopyButton';

/**
 * هذا الزرُّ يَعِدُ الموظفَ بأنّ الرقمَ صار في يده. فإن قال «تمّ» وهو لم
 * يصِر، فالموظفُ يلصقُ في فاتورة زبونٍ آخر ما نسخه بالأمس. فالاختبارُ
 * هنا على أنّ يقول الصدقَ في الاتجاهين: نجاحاً كان أو فشلاً.
 */

function stubClipboard(writeText: (t: string) => Promise<void>) {
  const spy = vi.fn(writeText);
  Object.defineProperty(navigator, 'clipboard', {
    value: { writeText: spy },
    configurable: true,
  });
  return spy;
}

describe('CopyButton', () => {
  beforeEach(() => {
    vi.useRealTimers();
  });

  afterEach(() => {
    Reflect.deleteProperty(navigator, 'clipboard');
    vi.restoreAllMocks();
  });

  it('copies the number it was given', async () => {
    const writeText = stubClipboard(async () => {});
    render(<CopyButton value=" 0561 000009 " />);
    fireEvent.click(screen.getByRole('button'));
    await waitFor(() => expect(writeText).toHaveBeenCalledWith('0561 000009'));
  });

  it('says it worked only when it did', async () => {
    stubClipboard(async () => {});
    render(<CopyButton value="0561000009" />);
    fireEvent.click(screen.getByRole('button'));
    await screen.findByTitle('تمّ نسخ الرقم');
  });

  it('admits failure instead of claiming success', async () => {
    stubClipboard(async () => { throw new Error('denied'); });
    Object.defineProperty(document, 'execCommand', {
      value: () => false,
      configurable: true,
    });
    render(<CopyButton value="0561000009" />);
    fireEvent.click(screen.getByRole('button'));
    // The dangerous outcome is silence: a green tick and no clipboard.
    await screen.findByTitle('تعذّر نسخ الرقم');
    expect(screen.queryByTitle('تمّ نسخ الرقم')).toBeNull();
  });

  it('offers nothing at all when there is no number to copy', () => {
    const { container } = render(<CopyButton value="   " />);
    expect(container.querySelector('button')).toBeNull();
  });

  it('offers nothing when the number is missing entirely', () => {
    const { container } = render(<CopyButton value={null} />);
    expect(container.querySelector('button')).toBeNull();
  });

  it('keeps its own label until the worker presses it', () => {
    render(<CopyButton value="0561000009" />);
    expect(screen.getByRole('button')).toHaveAttribute('title', 'نسخ الرقم');
  });

  it('lets the caller name the thing being copied', () => {
    render(<CopyButton value="0561000009" title="نسخ رقم الزبون" />);
    expect(screen.getByRole('button')).toHaveAttribute('title', 'نسخ رقم الزبون');
  });

  it('announces the outcome to a screen reader, not just by colour', async () => {
    stubClipboard(async () => {});
    render(<CopyButton value="0561000009" />);
    fireEvent.click(screen.getByRole('button'));
    await screen.findByText('تمّ نسخ الرقم');
    const status = screen.getByRole('status');
    expect(status).toHaveAttribute('aria-live', 'polite');
  });

  it('returns to rest on its own so the column stays calm', async () => {
    vi.useFakeTimers();
    stubClipboard(async () => {});
    render(<CopyButton value="0561000009" />);
    await act(async () => {
      fireEvent.click(screen.getByRole('button'));
    });
    expect(screen.getByTitle('تمّ نسخ الرقم')).toBeTruthy();
    await act(async () => {
      vi.advanceTimersByTime(1700);
    });
    expect(screen.getByTitle('نسخ الرقم')).toBeTruthy();
    vi.useRealTimers();
  });

  it('does not warn twice for one number', async () => {
    const writeText = stubClipboard(async () => {});
    render(<CopyButton value="0561000009" />);
    const button = screen.getByRole('button');
    await act(async () => { fireEvent.click(button); });
    await act(async () => { fireEvent.click(button); });
    expect(writeText).toHaveBeenCalledTimes(2);
    expect(screen.queryByTitle('تعذّر نسخ الرقم')).toBeNull();
  });
});
