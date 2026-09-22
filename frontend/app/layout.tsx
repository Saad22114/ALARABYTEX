import type { Metadata } from 'next';
import {
  Cairo, IBM_Plex_Sans_Arabic, Amiri, Noto_Sans_Arabic,
  Almarai, Tajawal, Rubik, Changa, Mada,
} from 'next/font/google';
import { ToastProvider } from '@/components/ui/Toast';
import ThemeProvider from '@/components/providers/ThemeProvider';
import SettingsProvider from '@/components/providers/SettingsProvider';
import FontProvider from '@/components/providers/FontProvider';
import CurrentEmployeeProvider from '@/components/providers/CurrentEmployeeProvider';
import AuthProvider from '@/components/providers/AuthProvider';
import AuthGate from '@/components/providers/AuthGate';
import './globals.css';

const cairo = Cairo({
  subsets: ['arabic', 'latin'],
  weight: ['300', '400', '500', '600', '700'],
  variable: '--font-cairo',
});

const ibm = IBM_Plex_Sans_Arabic({
  subsets: ['arabic', 'latin'],
  weight: ['300', '400', '500', '600', '700'],
  variable: '--font-ibm',
});

const amiri = Amiri({
  subsets: ['arabic', 'latin'],
  weight: ['400', '700'],
  variable: '--font-amiri',
});

const noto = Noto_Sans_Arabic({
  subsets: ['arabic'],
  weight: ['300', '400', '500', '600', '700'],
  variable: '--font-noto',
});

const almarai = Almarai({
  subsets: ['arabic'],
  weight: ['300', '400', '700', '800'],
  variable: '--font-almarai',
});

const tajawal = Tajawal({
  subsets: ['arabic'],
  weight: ['400', '500', '700', '900'],
  variable: '--font-tajawal',
});

const rubik = Rubik({
  subsets: ['arabic', 'latin'],
  weight: ['400', '500', '600', '700'],
  variable: '--font-rubik',
});

const changa = Changa({
  subsets: ['arabic'],
  weight: ['400', '500', '600', '700'],
  variable: '--font-changa',
});

const mada = Mada({
  subsets: ['arabic', 'latin'],
  weight: ['400', '500', '700', '900'],
  variable: '--font-mada',
});

export const metadata: Metadata = {
  title: 'القماش العربي - نظام إدارة الأعمال',
  description: 'نظام إدارة الأعمال والمنسوجات',
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
      <body className={`${cairo.variable} ${ibm.variable} ${amiri.variable} ${noto.variable} ${almarai.variable} ${tajawal.variable} ${rubik.variable} ${changa.variable} ${mada.variable} bg-sand-50 text-neutral-800 antialiased`}>
        <AuthProvider>
          <AuthGate>
            <ToastProvider>
              <ThemeProvider>
                <FontProvider>
                  <CurrentEmployeeProvider>
                    <SettingsProvider>{children}</SettingsProvider>
                  </CurrentEmployeeProvider>
                </FontProvider>
              </ThemeProvider>
            </ToastProvider>
          </AuthGate>
        </AuthProvider>
      </body>
    </html>
  );
}
