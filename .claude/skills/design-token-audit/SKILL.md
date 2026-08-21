---
name: design-token-audit
description: PlayBron frontend (apps/admin, apps/miniapp, apps/landing) o'zgargan yoki yangi fayllarni CLAUDE.md §Frontend invariantlariga qarshi tekshiradi — hardcode dizayn qiymati, `any`, i18n'siz matn, `fetch` bilan to'g'ridan-to'g'ri backend chaqiruvi, mock ma'lumot bilan yangi ekran, frontendga ko'chirilgan bandlik/narx mantig'i. Frontend kod yozilganda yoki review qilinganda ishlatiladi.
---

# Design token audit

PlayBron frontend kodini CLAUDE.md dagi `# Frontend` bo'limi invariantlariga
qarshi tekshiradi. Faqat review — kod o'zgartirmaydi, topilmalarni ro'yxatlaydi.

## Qamrov

`git diff` yoki ko'rsatilgan fayllar bo'yicha `apps/admin/`, `apps/miniapp/`,
`apps/landing/`, `packages/ui/` (tokenlardan tashqari — `packages/ui/src/tokens/**`
ga tegilmaydi, faqat undan foydalanish tekshiriladi).

## Tekshirish ro'yxati

1. **Hardcode qiymat** — inline rang (`#fff`, `rgb(...)`), spacing (`padding: 12px`),
   font o'lchami CSS/JSX ichida token o'rniga. `packages/ui` token'lariga
   (`docs/designs/_ds/`) mos import bo'lishi kerak.
2. **`any` turi** — TypeScript'da `any` ishlatilgan joy, shu jumladan
   `as any`, implicit any parametr.
3. **Matn literali** — foydalanuvchiga ko'rinadigan JSX/string matn i18n
   resursidan (`uz`/`ru`/`en`) emas, komponentda qattiq yozilgan. Landing'da
   `en` yo'qligi ma'lum qarz — yangi qarz qo'shilmasin.
4. **To'g'ridan-to'g'ri `fetch`** — ekranda `fetch(...)` yoki `axios` chaqiruvi;
   hammasi `packages/api-client` orqali bo'lishi kerak. Yangi endpoint
   qo'shilgan bo'lsa, `packages/api-client/src/endpoints.ts` da tipli funksiya
   va DTO (`snake_case` → `camelCase`) borligini tekshirish.
5. **Mock ma'lumot** — yangi ekran `apps/admin/src/mock/` yoki inline soxta
   massiv bilan merge qilinayotgan bo'lsa belgilash. Backend hali yo'q bo'lsa
   bo'sh holat (`empty state`) kerak, mock emas. Istisno:
   `apps/admin/src/mock/club.ts` (backendda ekvivalenti yo'q — ma'lum qarz,
   kengaytirilmaydi) va `mock/data.ts` dagi `ScreenId`/`TITLES` (dizayn
   konstantasi, soxta ma'lumot emas).
6. **Bandlik/narx mantig'i frontendda** — summani `rate * hours` kabi frontendda
   qayta hisoblash, sana/vaqt oralig'ini frontendda solishtirish. Server
   qaytargan qiymat ko'rsatilishi kerak (`bookings.play_amount`, quote
   endpoint).
7. **Mahalliy vaqt zonasi** — `Date.getHours()`, `Date.setHours()`,
   zonasiz `new Date()` bilan solishtirish. `Intl.DateTimeFormat({ timeZone })`
   yoki backenddan kelgan qiymat ishlatilishi kerak.
8. **`date-fns-tz`** import qilinsa — loyihada o'rnatilmagan, rad etiladi.

## Chiqish formati

Har topilma uchun: fayl:qator, invariant qaysi bandini buzgani, taklif
qilingan tuzatish (bitta gapda). Toza bo'lsa — "Topilma yo'q" deb aniq yoziladi,
bo'sh ro'yxatni sukut saqlab qoldirmaslik kerak.
