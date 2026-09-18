import type { Metadata } from 'next';
import { Cairo } from 'next/font/google';
import { ToastProvider } from '@/components/ui/Toast';
import ThemeProvider from '@/components/providers/ThemeProvider';
import SettingsProvider from '@/components/providers/SettingsProvider';
import CurrentEmployeeProvider from '@/components/providers/CurrentEmployeeProvider';
import AuthProvider from '@/components/providers/AuthProvider';
import AuthGate from '@/components/providers/AuthGate';
import './globals.css';

const cairo = Cairo({
  subsets: ['arabic', 'latin'],
  weight: ['300', '400', '500', '600', '700'],
  variable: '--font-cairo',
});

export const metadata: Metadata = {
  title: 'القماش العربي - نظام إدارة أعمال الأقمشة',
  description: 'نظام إدارة أعمال الأقمشة والمنسوجات',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ar" dir="rtl">
      <head>
        <script
          dangerouslySetInnerHTML={{
            __html: `try{var t=localStorage.getItem('qomash_theme');if(t)document.documentElement.dataset.theme=t;var d=localStorage.getItem('qomash_dark');var dark=d?d==='1':window.matchMedia('(prefers-color-scheme:dark)').matches;if(dark)document.documentElement.classList.add('dark')}catch(e){}`,
          }}
        />
      </head>
      <body className={`${cairo.variable} font-cairo bg-sand-50 text-neutral-800 antialiased`}>
        <ToastProvider>
          <ThemeProvider>
            <AuthProvider>
              <CurrentEmployeeProvider>
                <SettingsProvider>
                  <AuthGate>{children}</AuthGate>
                </SettingsProvider>
              </CurrentEmployeeProvider>
            </AuthProvider>
          </ThemeProvider>
        </ToastProvider>
      </body>
    </html>
  );
}
