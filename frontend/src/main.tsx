import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { BrowserRouter } from 'react-router-dom';
import App from './App';
import { LanguageProvider } from './i18n';
import './styles/tokens.css';
import './styles/base.css';
import './styles/animations.css';
/* Noto Sans Bengali — only downloaded when Bengali glyphs are on the page
   (unicode-range), so English mode costs nothing. */
import '@fontsource/noto-sans-bengali/400.css';
import '@fontsource/noto-sans-bengali/500.css';
import '@fontsource/noto-sans-bengali/600.css';
import '@fontsource/noto-sans-bengali/700.css';
/* Inter — only used by the indigo palette comparison variant
   (?palette=indigo); the @fontsource faces carry unicode-range subsets,
   so the files download only when Inter is actually applied. */
import '@fontsource/inter/400.css';
import '@fontsource/inter/500.css';
import '@fontsource/inter/600.css';
import '@fontsource/inter/700.css';

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <BrowserRouter>
      <LanguageProvider>
        <App />
      </LanguageProvider>
    </BrowserRouter>
  </StrictMode>,
);

/* Batch 5 — PWA service worker (arena spawn-probe pick a002): production
   only, never dev — a worker would serve stale dev assets. The worker
   caches only the public shell; /api and the SSE stream bypass it. */
if (import.meta.env.PROD && 'serviceWorker' in navigator) {
  window.addEventListener('load', () => {
    navigator.serviceWorker
      .register('/sw.js', { scope: '/' })
      .then((reg) => {
        const announce = () =>
          window.dispatchEvent(new CustomEvent('sw-update-available'));
        if (reg.waiting) announce();
        reg.addEventListener('updatefound', () => {
          const w = reg.installing;
          w?.addEventListener('statechange', () => {
            if (w.state === 'installed' && navigator.serviceWorker.controller)
              announce();
          });
        });
        document.addEventListener('visibilitychange', () => {
          if (!document.hidden) void reg.update();
        });
      })
      .catch(() => undefined);
  });
}
