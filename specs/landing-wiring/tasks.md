# Landing wiring — tasks

- [x] Spec written (specs/landing-wiring/spec.md)
- [x] Logo: layout.tsx `Logo` swaps lucide Compass -> /favicon.svg img; remove unused Compass import (plus the mobile topbar Compass at line 320, found during the work)
- [x] Delete public/compass.svg (unreferenced in src/)
- [x] App.tsx: import Terms + /terms route after /privacy
- [x] Landing.tsx footer: Terms link next to /privacy
- [x] i18n: termsLink in en.ts / bn.ts / dict.ts
- [x] npm run build green (fix any Terms.tsx TS errors)
- [x] CDP screenshots viewed: landing desktop, landing mobile 390px, /terms EN, /terms BN; 0 console errors
- [ ] Commit ONLY landing files; push via winreg-token + throwaway askpass
- [ ] Live verify after Render deploy: health 200, /terms 200, favicon loads; report commit + deploy id
