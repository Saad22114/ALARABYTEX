import '@testing-library/jest-dom/vitest';

/**
 * jsdom لا ينفّذ ResizeObserver، بينما المتصفحات الحديثة تنفّذه.
 * نوفّر بديلاً بسيطاً حتى تتمكن المكوّنات التي تراقب الحجم من العمل في الاختبارات.
 */
if (typeof globalThis.ResizeObserver === 'undefined') {
  class ResizeObserverStub {
    observe() {}
    unobserve() {}
    disconnect() {}
  }
  globalThis.ResizeObserver = ResizeObserverStub as unknown as typeof ResizeObserver;
}
