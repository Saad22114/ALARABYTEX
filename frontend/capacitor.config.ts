import type { CapacitorConfig } from '@capacitor/cli';

const config: CapacitorConfig = {
  appId: 'com.alarabytex.mobile',
  appName: 'Alaraby Tex',
  webDir: 'www',
  server: {
    // The APK loads the already deployed website, which uses the same Render API/database.
    url: process.env.CAPACITOR_SERVER_URL || 'https://alarabytex-frontend-lnex.onrender.com',
    cleartext: false,
    allowNavigation: ['alarabytex-frontend-lnex.onrender.com'],
    errorPath: 'index.html',
  },
  android: {
    allowMixedContent: false,
  },
};

export default config;
