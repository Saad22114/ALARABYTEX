'use client';

import { useEffect } from 'react';

/** Refresh visible shared data periodically and when a user returns to the tab. */
export function useAutoRefresh(refresh: () => unknown, intervalMs = 30_000) {
  useEffect(() => {
    let running = false;
    const run = () => {
      if (running || document.visibilityState === 'hidden') return;
      running = true;
      try {
        const result = refresh();
        if (result instanceof Promise) void result.then(() => { running = false; }, () => { running = false; });
        else running = false;
      } catch {
        running = false;
      }
    };
    const timer = window.setInterval(run, intervalMs);
    document.addEventListener('visibilitychange', run);
    window.addEventListener('focus', run);
    return () => {
      window.clearInterval(timer);
      document.removeEventListener('visibilitychange', run);
      window.removeEventListener('focus', run);
    };
  }, [refresh, intervalMs]);
}
