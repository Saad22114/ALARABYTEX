'use client';

import { useState, useEffect, useLayoutEffect, useCallback } from 'react';
import Sidebar from './Sidebar';
import Header from './Header';
import { applyFontScale, loadFontScale } from '@/lib/fontScale';

export default function AppShell({ children }: { children: React.ReactNode }) {
  const [menuOpen, setMenuOpen] = useState(false);
  const closeMenu = useCallback(() => setMenuOpen(false), []);

  useLayoutEffect(() => {
    applyFontScale(loadFontScale());
  }, []);

  useEffect(() => {
    if (menuOpen) {
      document.body.style.overflow = 'hidden';
    } else {
      document.body.style.overflow = '';
    }
    return () => { document.body.style.overflow = ''; };
  }, [menuOpen]);

  return (
    <div className="min-h-screen bg-sand-50">
      <Sidebar open={menuOpen} onClose={closeMenu} />
      <div className="lg:mr-72 print:mr-0 print:max-w-full">
        <Header onMenuClick={() => setMenuOpen(true)} menuOpen={menuOpen} />
        <main className="app-main p-3 sm:p-6 lg:p-8 animate-fade-in">{children}</main>
      </div>
    </div>
  );
}
