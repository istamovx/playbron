# PlayBron — Bosqich 0: Repo auditi va UI → ma'lumot xaritasi

> Holat: 2026-08-13. Bu hujjat kod o'qish orqali tuzildi, taxmin yo'q.
> Manba: `apps/`, `packages/`, `docs/designs/`.

---

## 0. Muhim tuzatish — topshiriqdagi taxminlar

Topshiriq «faqat frontend verstka (Vite + React), `src/pages/*.jsx`, react-router, Tailwind
className» deb taxmin qilgan edi. Repo aslida boshqacha; quyidagi jadval barcha keyingi
bo'limlarning asosi.

| Taxmin | Haqiqat |
|---|---|
| Bitta Vite app | **Turborepo + pnpm monorepo**: 2 ta app + 2 ta paket |
| `.jsx`, `src/pages/` | **TypeScript**, `.tsx`, `apps/<app>/src/screens/` |
| `src/data/*.js` | `apps/<app>/src/mock/*.ts` (3 fayl, 1 224 qator) |
| react-router | **Router yo'q.** Ekran Zustand'dagi `screen` maydoni bilan almashadi. URL yo'q, deep-link yo'q, `history` yo'q |
| Tailwind className | Tailwind import qilingan, **amalda ishlatilmaydi** (jami 12 ta className, ular ham layout utilitalari). Uslub — inline `style` + CSS custom property tokenlar |
| Landing bor | **Landing yo'q.** `CLAUDE.md` da `apps/landing` (Next.js 15) yozilgan, papka mavjud emas |
| npm | **pnpm 10.34.5** workspace |

**Muzlatish qoidasi shunga moslashtirilishi kerak.** Muzlatiladigan narsa —
`packages/ui/src/tokens/**`, `packages/ui/src/components/**` va ekranlardagi inline `style`
obyektlari; `className` va `tailwind.config` emas (ular deyarli bo'sh).

---

## 1. Repo auditi

### 1.1 Stack va versiyalar

| Qatlam | Texnologiya | Versiya |
|---|---|---|
| Monorepo | Turborepo | 2.5.8 |
| Paket menejeri | pnpm | 10.34.5 |
| Til | TypeScript (strict, `noUncheckedIndexedAccess`, `noUnusedLocals`) | 5.9.3 |
| UI | React + React DOM | 19.2.0 |
| Bundler | Vite | 6.3.6 |
| State | Zustand (+ `persist` middleware) | 5.0.8 |
| Server state | `@tanstack/react-query` — **faqat `miniapp` da o'rnatilgan, hech qayerda ishlatilmagan** | 5.90.5 |
| CSS | Tailwind 4 (`@tailwindcss/vite`) — **import qilingan, ishlatilmaydi** | 4.1.16 |
| Lint | ESLint + typescript-eslint | 9.39.1 / 8.46.4 |
| Test | **Yo'q.** `vitest` o'rnatilmagan, test fayli yo'q | — |

### 1.2 Papka strukturasi

```
Playbron/
├─ apps/
│  ├─ admin/          Vite app — klub konsoli (xodim + klub egasi), brauzer, desktop-first
│  │  └─ src/
│  │     ├─ app.tsx          shell: sessiya gate, rolga qarab menyu, drawer
│  │     ├─ main.tsx
│  │     ├─ mock/            data.ts (387 q.), club.ts (318 q.)
│  │     ├─ screens/         7 ta xodim + 7 ta klub egasi ekrani
│  │     └─ store/           board.ts, club.ts, session.ts
│  └─ miniapp/        Vite app — Telegram Mini App (mijoz)
│     └─ src/
│        ├─ app.tsx          telefon ramkasi, ekran routeri, MainButton/BackButton
│        ├─ lib/             telegram.ts (WebApp API), bill.ts (hisob funksiyalari)
│        ├─ mock/data.ts     519 qator
│        ├─ screens/         8 real + 2 placeholder
│        └─ store/app.ts     useApp + useProfile
├─ packages/
│  ├─ ui/             SystemX design system: 30+ komponent, 8 ta token fayli, styles.css
│  └─ config/         ESLint + TS konfiguratsiyasi
└─ docs/
   ├─ archive/BUILD-BRIEF.md  ARXIVLANGAN (2026-08-17) — NestJS + Prisma stack'ini tavsiflaydi
   ├─ DESIGN-HANDOFF.md
   └─ designs/              PlayBron Mijoz / Xodim / Xodim Mobil .dc.html + _ds/
```

### 1.3 Routing

**Router kutubxonasi yo'q.** Har ikkala app'da navigatsiya store maydoni orqali:

| App | Mexanizm | Fayl |
|---|---|---|
| admin | `useBoard.screen: ScreenId`, `setScreen()`; rolga qarab `NAV_STAFF` yoki `NAV_ADMIN` | `store/board.ts`, `mock/data.ts` |
| miniapp | `useApp.screen` + `stack: ScreenId[]` (push/pop), Telegram BackButton shu stack'ga ulangan | `store/app.ts` |

**Oqibatlari:** URL bo'yicha kirish yo'q, brauzer «orqaga» tugmasi ishlamaydi, `route guard`
qo'shib bo'lmaydi, to'lovdan qaytish (Click/Payme redirect) uchun ilinadigan nuqta yo'q.
To'lov oqimi uchun `admin` app'ga router kiritish **majburiy** (vizual o'zgarishsiz).

### 1.4 State management

| Store | Fayl | Persist | Nima saqlaydi |
|---|---|---|---|
| `useBoard` | `admin/store/board.ts` | yo'q | ekran, tanlangan stansiya, kassa savati, buyurtma holatlari, uzaytirish, yopilgan chek |
| `useClub` | `admin/store/club.ts` | **`playbron.club`** | klub ma'lumoti, tariflar, xonalar, qurilmalar, xodimlar, mahsulotlar, xarajatlar (to'liq CRUD) |
| `useSession` | `admin/store/session.ts` | **`playbron.console`** | login/parol sessiyasi, rol, 24 soatlik muddat |
| `useApp` | `miniapp/store/app.ts` | yo'q | ekran, stack, filtr, tanlangan slot, savat, buyurtmalar |
| `useProfile` | `miniapp/store/app.ts` | **`playbron.customer`** | ism, telefon, `registeredAt`, til, bildirishnoma va haptik sozlamalari, `signedIn` |

**Risk:** uchala `localStorage` kaliti mock ma'lumot bilan to'lgan. Real API ulanganda ular
tozalanmasa, eski struktura yangi kod bilan to'qnashadi — migratsiya yoki versiyalash kerak
(`persist` ning `version` + `migrate` opsiyasi hozir ishlatilmagan).

### 1.5 Styling tizimi

- **Tokenlar:** `packages/ui/src/tokens/` — 8 ta CSS fayl, ~350 ta custom property.
  `theme-light.css` to'liq yozilgan (134 qator) lekin **hech qayerda yoqilmagan** — ikkala app
  ham `data-theme="dark"` bilan qotirilgan.
- **Komponent uslubi:** inline `style` obyektlari, ranglar faqat `var(--token)` orqali.
  Hardcode rang yo'q (audit qilindi).
- **Utilita klasslari:** `packages/ui/src/styles.css` va `tokens/breakpoints.css` da —
  `ds-split`, `ds-scroll-x`, `ds-chart`, `ds-hide-xs`, `pb-tiles-4/5`, `pb-split-wide`,
  `pb-auth`, `pb-bar`, `pb-fill`, `pb-phone`, `pb-stage`.
- **Web zichlik qatlami:** `styles.css` ichida `--fs-*` tokenlari 16px minimal shriftga
  qayta belgilangan (mijoz talabi). Bu DS token fayllarini emas, ustidagi qatlamni o'zgartiradi.

### 1.6 UI kutubxonasi — `@playbron/ui`

| Guruh | Komponentlar |
|---|---|
| Primitivlar | `Icon`, `Button` (5 variant × 3 o'lcham), `Chip`, `Tag`, `StatusLine`, `Tabs`, `SegmentedControl` |
| Layout | `Panel` (notch/brackets/glow/dashed), `Grid`, `PageHeader`, `SidebarNav`, `UserMenu`, `EmptyState` |
| Ma'lumot | `MetricCell`, `StatTile`, `FieldRow`, `FieldLadder`, `Money`, `ProgressMeter`, `ActivityBars`, `EntityTable` |
| Forma | `Select`, `TextField` |
| Vaqt | `ServerClock`, `Countdown`, `ClubTime`, `toneForRemaining` |
| Domen funksiyalari | `formatSum`, `formatDuration`, `hhmmToMinutes`, `minutesToHhmm`, `prepayAmount`, `PREPAY_HOURS`, `NO_SHOW_MIN`, `GRACE_MIN`, `NOTIFY_BEFORE_MIN` |
| Hooklar | `useMedia`, `useNarrow` |

`EntityTable` 720px dan tor ekranda avtomatik kartaga aylanadi — barcha jadvalli ekranlar
mobil moslashuvni shundan oladi.

**Diqqat:** `packages/ui/src/format.ts` ichida biznes qoidalari yashiringan
(`prepayAmount`, `NO_SHOW_MIN`, `GRACE_MIN`). Backend kelganda bular server bilan bitta
manbadan kelishi kerak — hozir faqat frontendda.

### 1.7 Landing / marketing

**Mavjud emas.** Shu sababli:
- SEO muammosi hozircha yo'q — chunki sahifaning o'zi yo'q;
- Telegram Login Widget uchun joy yo'q;
- tarif tanlash va checkout oqimi uchun kirish nuqtasi yo'q.

Landing noldan quriladi. Vite SPA marketing sahifasi uchun SEO jihatdan zaif — tavsiya
`01-architecture.md` da.

### 1.8 Ekranlar ro'yxati

Jami **24 ekran** (22 tasi ishlaydi, 2 tasi placeholder), **3 rol** qamrab olingan
(xodim, klub egasi, mijoz). **Super admin va public/landing roli umuman yo'q.**

Legenda: L/E/X = Loading / Empty / Error holati bormi.

#### Konsol — kirish

| Ekran | Fayl | Rol | Ko'rsatadi | Amal | Mock data | Kerakli endpoint | L/E/X |
|---|---|---|---|---|---|---|---|
| Kirish | `apps/admin/src/screens/login.tsx` | Public | Login/parol formasi, demo hisoblar | Sessiya ochish | `store/session.ts` → `ACCOUNTS`, 2 obyekt | **Almashadi:** `POST /api/v1/auth/telegram/widget` | yo'q / — / bor (xato matni) |

#### Konsol — xodim

| Ekran | Fayl | Rol | Ko'rsatadi | Amal | Mock data | Kerakli endpoint | L/E/X |
|---|---|---|---|---|---|---|---|
| Live board | `screens/live-board.tsx` | Xodim | 10 xona kartasi, holat/taymer/mijoz, 5 hisoblagich, bandlik grafigi, tanlangan xona paneli | Xona tanlash, seansni uzaytirish, no-show belgilash, kassaga o'tish | `mock/data.ts` → `ST` (10), `NEXT`, `TONE`, `LABEL` | `GET /api/v1/clubs/{id}/board`, `POST /bookings/{id}/extend`, `POST /bookings/{id}/no-show` | yo'q / yo'q / yo'q |
| Timeline | `screens/timeline.tsx` | Xodim | Kunlik gantt (10:00–02:00), Kecha/Bugun/Ertaga | Kun almashtirish | `mock/data.ts` → `YESTERDAY`, `TOMORROW`, `ST[].hist` | `GET /api/v1/clubs/{id}/timeline?date=` | yo'q / yo'q / yo'q |
| Buyurtmalar | `screens/orders.tsx` | Xodim | 4 ustunli kanban: Yangi → Qabul → Tayyorlanmoqda → Yetkazildi | Holatni oldinga surish | `mock/data.ts` → `ORDERS`, `ORDER_FLOW` | `GET /api/v1/clubs/{id}/orders`, `PATCH /orders/{id}/status` | yo'q / bor / yo'q |
| Kassa | `screens/pos.tsx` | Xodim | Ochiq hisoblar, katalog + qidiruv, savat, hisob yakuni, to'lov usuli, chek | Mahsulot qo'shish, hisobni yopish, chek tasdiqlash | `mock/data.ts` → `MENU` (30), `STOCK`, `CARTS`, `BONUS` | `GET /clubs/{id}/bills`, `POST /bills/{id}/items`, `POST /bills/{id}/close` | yo'q / bor / yo'q |
| Smena | `screens/shift.tsx` | Xodim | Smena yakuni, naqd harakati, kirim/chiqim, StatTile'lar | Smenani yopish | `screens/shift.tsx` ichida `CASH_ROWS` | `GET /clubs/{id}/shifts/current`, `POST /shifts/{id}/close` | yo'q / yo'q / yo'q |
| Qora ro'yxat | `screens/blacklist.tsx` | Xodim | Bloklanganlar jadvali, kuzatuvdagilar, qoidalar, no-show statistikasi | Blokdan olish (tugma bor, mantiq yo'q) | fayl ichida `BLOCKED`, `WATCH`, `RULES`, `NS_STATS` | `GET /clubs/{id}/blocklist`, `DELETE /blocklist/{id}` | yo'q / bor / yo'q |

#### Konsol — klub egasi

| Ekran | Fayl | Rol | Ko'rsatadi | Amal | Mock data | Kerakli endpoint | L/E/X |
|---|---|---|---|---|---|---|---|
| Boshqaruv paneli | `screens/admin/dashboard.tsx` | Klub egasi | Bugungi tushum/foyda/seans/bandlik, soatlik grafik, qavat bo'yicha xonalar, bar savdosi, smenadagi xodimlar | — (faqat ko'rsatadi) | `mock/club.ts` → `totalsFor`, `seriesFor`, `useClub` | `GET /clubs/{id}/dashboard?date=` | yo'q / qisman / yo'q |
| Xodimlar | `screens/admin/staff.tsx` | Klub egasi | Xodimlar jadvali: ism, telefon, login, smena, holat, kassa | CRUD | `mock/club.ts` → `STAFF_INIT` (4) | `GET/POST/PATCH/DELETE /clubs/{id}/staff` | yo'q / bor / yo'q |
| Klub ma'lumoti · Umumiy | `screens/admin/club-info.tsx` | Klub egasi | Cover rasm, nom, manzil, telefon, tavsif, ish vaqti | Rasm yuklash (FileReader → dataURL), tahrirlash | `mock/club.ts` → `CLUB_INIT` | `GET/PATCH /clubs/{id}`, `POST /clubs/{id}/cover` | yo'q / — / bor |
| … · Tariflar | shu fayl | Klub egasi | Tarif nomi, vaqt oynasi, koeffitsiyent | CRUD | `TARIFFS_INIT` (3) | `GET/POST/PATCH/DELETE /clubs/{id}/rate-plans` | yo'q / bor / bor |
| … · Xonalar | shu fayl | Klub egasi | Xona, qavat, tur, konsol, ekran, joystik, soatlik va peak narx | CRUD | `ROOMS_INIT` (10) | `GET/POST/PATCH/DELETE /clubs/{id}/rooms` | yo'q / bor / bor |
| … · Qurilmalar | shu fayl | Klub egasi | Konsol/joystik/ekran, seriya, xona, holat | CRUD | `DEVICES_INIT` (8) | `GET/POST/PATCH/DELETE /clubs/{id}/devices` | yo'q / bor / bor |
| Mahsulotlar | `screens/admin/products.tsx` | Klub egasi | Katalog + reestr: narx, tannarx, qoldiq, sotilgan, foyda | CRUD + kirim (`restock`) | `mock/club.ts` → `PRODUCTS_INIT` (12) | `GET/POST/PATCH/DELETE /clubs/{id}/products`, `POST /products/{id}/restock` | yo'q / bor / bor |
| Hisobot | `screens/admin/reports.tsx` | Klub egasi | Kunlik/haftalik/oylik/yillik: tushum, xarajat, foyda, rentabellik, dinamika, tarkib, top mahsulot | Davr almashtirish | `mock/club.ts` → `totalsFor`, `seriesFor`, `EXPENSE_SHARE` | `GET /clubs/{id}/reports?period=` | yo'q / yo'q / yo'q |
| Xarajatlar | `screens/admin/expenses.tsx` | Klub egasi | Sana, modda, summa, izoh; moddalar bo'yicha taqsimot | CRUD | `mock/club.ts` → `EXPENSES_INIT` (7) | `GET/POST/PATCH/DELETE /clubs/{id}/expenses` | yo'q / bor / bor |
| Sozlamalar | `screens/admin/settings.tsx` | Klub egasi | Hisob, rol, sessiya muddati; parol almashtirish; ma'lumotni tiklash | Parol o'zgartirish, chiqish, reset | `store/session.ts` | **Almashadi:** Telegram profil, `POST /auth/logout` | yo'q / — / bor |

#### Mini App — mijoz

| Ekran | Fayl | Rol | Ko'rsatadi | Amal | Mock data | Kerakli endpoint | L/E/X |
|---|---|---|---|---|---|---|---|
| Ro'yxatdan o'tish | `apps/miniapp/src/screens/register.tsx` | Mijoz | Ism + telefon formasi; qaytganda «Kirish» kartasi | Profil yaratish / kirish | `store/app.ts` → `useProfile` | **Almashadi:** `POST /api/v1/auth/telegram/initdata` + `requestContact` | yo'q / — / bor |
| Klublar | `screens/clubs.tsx` | Mijoz | 4 klub kartasi: nom, manzil, masofa, reyting, narx, bo'sh joy | Saralash chiplari, klubga o'tish | `mock/data.ts` → `CLUBS` (4), `SORT_CHIPS` | `GET /api/v1/clubs?sort=&lat=&lng=` | yo'q / yo'q / yo'q |
| Klub | `screens/club.tsx` | Mijoz | Galereya, teglar, tavsif, xonalar va narxlar (bandlik chizig'i), sharhlar | Bron qilishga o'tish | `mock/data.ts` → `clubRooms()`, `clubTags()`, `REVIEWS` | `GET /clubs/{id}`, `GET /clubs/{id}/reviews` | yo'q / yo'q / yo'q |
| Vaqt tanlash | `screens/slots.tsx` | Mijoz | 14 kunlik sana tasmasi, xona turi va konsol filtri, davomiylik, slot to'ri, bo'sh xonalar | Sana/filtr/davomiylik/slot/xona tanlash | `mock/data.ts` → `bookedRanges()` (seedli generator), `freeStations()` | `GET /clubs/{id}/availability?date=&hours=&room=&console=` | yo'q / **bor** / yo'q |
| Tasdiqlash | `screens/pending.tsx` | Mijoz | **PLACEHOLDER** | — | — | `POST /bookings` | — |
| QR | `screens/pending.tsx` | Mijoz | **PLACEHOLDER** | — | — | `GET /bookings/{id}/qr` | — |
| Aktiv seans | `screens/session.tsx` | Mijoz | Qolgan vaqt, progress, 30/15 daqiqa ogohlantirishi, grace, bar menyusi, savat, buyurtmalar kuzatuvi | Uzaytirish, buyurtma yuborish, hisobga o'tish | `mock/data.ts` → `SESSION_*`, `MENU`, `orderStatusAt()` | `GET /bookings/active`, `POST /bookings/{id}/extend`, `POST /bookings/{id}/orders` | yo'q / bor / yo'q |
| Hisob | `screens/bill.tsx` | Mijoz | O'yin, bar, bron to'lovi, bonus, klubda to'lanadi; Naqd/O'tkazma; chek yuklash | To'lov usuli tanlash, chek yuborish | `lib/bill.ts` → `billOf()`, `mock/data.ts` → `CARD_FIELDS` | `GET /bookings/{id}/bill`, `POST /bills/{id}/receipt` | yo'q / bor / yo'q |
| Bronlarim | `screens/bookings.tsx` | Mijoz | Bot xabari (yopilgan hisob), bronlar kartochkalari, kechikish qoidasi | Bekor qilish (tugma bor, mantiq yo'q) | `mock/data.ts` → `MY_BOOKINGS` (4), `BILL_SUMMARY` | `GET /me/bookings`, `POST /bookings/{id}/cancel` | yo'q / yo'q / yo'q |
| Profil | `screens/profile.tsx` | Mijoz | Avatar, ism, telefon, statistika; 4 bo'limli menyu: shaxsiy ma'lumot, bildirishnoma, interfeys, chiqish | Tahrirlash, til, toggle'lar, chiqish | `mock/club.ts`… → `PROFILE_STATS`, `useProfile` | `GET/PATCH /me`, `GET /me/stats` | yo'q / — / bor |

### 1.9 Mock ma'lumot — joylashuvi va shakli

| Fayl | Qator | Nima bor |
|---|---|---|
| `apps/admin/src/mock/data.ts` | 387 | `CONSOLES` (5 konsol turi), `ST` (10 stansiya), `MENU` (30 mahsulot), `STOCK`, `ORDERS`, `CARTS`, `YESTERDAY`/`TOMORROW`, `NAV_STAFF`/`NAV_ADMIN`, `TITLES`, formatlash (`S`, `HM`, `CLK`, `DUR`) |
| `apps/admin/src/mock/club.ts` | 318 | `CLUB_INIT`, `TARIFFS_INIT`, `ROOMS_INIT`, `DEVICES_INIT`, `STAFF_INIT`, `PRODUCTS_INIT`, `EXPENSES_INIT`, `seriesFor()`, `totalsFor()`, `stockRow()` |
| `apps/miniapp/src/mock/data.ts` | 519 | `CLUBS` (4), `STATIONS` (9), `MENU` (10), `CONSOLES`, `bookedRanges()` (FNV+mulberry32 seedli), `freeStations()`, `MY_BOOKINGS`, `REVIEWS`, `BILL_SUMMARY`, `ORDER_FLOW` |

Shakli: barchasi **TypeScript literal massiv/obyekt**, tur bilan (`MockStation`, `Room`,
`Product`, …). Import — to'g'ridan-to'g'ri, hech qanday abstraksiya qatlami yo'q. Ya'ni
real API ga o'tishda har bir ekranning import satri almashadi.

### 1.10 Design tokenlar

#### Ranglar — asos

| Token | Qiymat | Izoh |
|---|---|---|
| `--void-0…7` | `#000000` → `#24242E` | Qorong'i ramka; `--void-1` = ilova foni |
| `--primary-100…800` | `#5700FF` → `#160040` | Brend binafsha |
| `--purple-100` | `#B661DE` | Aksent (`--violet-100/200` shunga taqaladi) |
| `--secondary-500` | `#32E197` | Yashil — bo'sh joy, ijobiy |
| `--yellow-100` | `#EDB07E` | Ogohlantirish |
| `--red-100` / `--red-200` | `#FF505D` / `#980043` | Xato, risk |

#### Ranglar — semantik

| Guruh | Tokenlar |
|---|---|
| Fon | `--bg-app`, `--bg-frame`, `--bg-grid` |
| Yuza | `--surface-panel`, `--surface-panel-quiet`, `--surface-card`, `--surface-raised`, `--surface-inset`, `--surface-field`, `--surface-hover`, `--surface-press`, `--surface-selected`, `--surface-accent`, `--surface-pop` |
| Chiziq | `--line-1…4` (8% → 40% oq), `--line-violet`, `--line-violet-soft` |
| Matn | `--text-title`, `--text-body`, `--text-muted`, `--text-dim`, `--text-label`, `--text-accent`, `--text-on-accent` |
| Chegara | `--border-panel`, `--border-control`, `--border-control-hover`, `--border-accent`, `--border-focus` |
| Holat | `--risk-none/low/med/high/crit/deep`, `--slot-free`, `--slot-free-bg`, `--slot-taken` |
| Grafik | `--chart-plot`, `--chart-track`, `--chart-neutral`, `--chart-guide`, `--chart-edge`, `--chart-heat-0…4`, `--chart-grid` |

#### Tipografika

| Token | Qiymat |
|---|---|
| `--font-display` / `--font-ui` | Chakra Petch |
| `--font-mono` | JetBrains Mono |
| `--font-icon` | Material Symbols Rounded |
| `--fs-micro … --fs-metric-lg` | DS: 9 / 10 / 11 / 12 / 13 / 14 / 16 / 18 / 38 / 44 px |
| **Web qatlam** (`styles.css`) | 16px minimalga ko'tarilgan: `--fs-micro…--fs-sm` = 16px, `--fs-md` 17, `--fs-base` 18, `--fs-lg` 20, `--fs-xl` 22, `--fs-2xl` 26, `--fs-3xl` 30, `--fs-metric` 44 |
| Og'irlik | `--fw-light` 300 … `--fw-bold` 700 |
| Qator balandligi | `--lh-tight` 1.05, `--lh-snug` 1.25, `--lh-normal` 1.45, `--lh-loose` 1.6 |
| Harf oralig'i | `--ls-label` .10em, `--ls-caps` .06em, `--ls-title` .02em, `--ls-metric` −.01em |
| Kompozit | `--type-page-title`, `--type-panel-title`, `--type-section`, `--type-body`, `--type-body-sm`, `--type-label`, `--type-control`, `--type-metric`, `--type-data`, `--type-data-xs` |

#### Spacing va geometriya

| Token | Qiymat |
|---|---|
| `--sp-0…16` | 0, 2, 4, 6, 8, 10, 12, 14, 16, 20, 24, 32, 40, 48 px |
| Boshqaruv balandligi (DS) | `--control-h-sm` 22, `--control-h` 26, `--control-h-md` 30, `--control-h-lg` 34 |
| Boshqaruv balandligi (web qatlam) | 30 / 34 / — / 42, `--field-h` 38 |
| Panel/karta | `--panel-pad` 14 (web: 16–26), `--card-pad` 12 (web: 16), `--gutter`, `--gap-panel`, `--gap-block`, `--gap-tight` (faqat `styles.css` da) |
| Kenglik | `--rail-w` 56, `--sidebar-w` 290, `--nav-w` 232–248, `--aside-w` 260–400 |

#### Radius, soya, harakat

| Token | Qiymat |
|---|---|
| `--r-0…4` | 0, 2, 3, 5, 8 px |
| `--r-frame` / `--r-pill` | 18px / 999px |
| `--notch` | 14px (HUD chamfer) |
| `--clip-tr` / `-tl` / `-br` / `-diag` | `polygon(...)` — 14px kesilgan burchak |
| `--shadow-panel` | `0 10px 30px rgba(0,0,0,.55)` |
| `--shadow-pop` | `0 18px 48px rgba(0,0,0,.7)` |
| `--glow-violet-sm/–/-lg` | `0 0 8px` / `0 0 18px` / `0 0 34px + 0 0 90px` rgba(87,0,255) |
| `--glow-risk`, `--glow-text` | qizil va oq halo |
| `--t-control` | background/border/color/box-shadow, `--dur-2` `--ease-out` |
| Animatsiya | `pb-rise` (ustun o'sishi), `pb-grow` (chiziq to'lishi), `pb-pulse` — `prefers-reduced-motion` bilan o'chadi |

#### Breakpointlar

| Token | Qiymat | Nima o'zgaradi |
|---|---|---|
| `--bp-xs` | 0 | — |
| `--bp-sm` | 600px | `.ds-hide-xs` yashirinadi |
| `--bp-md` | **905px** | `.ds-split` bitta ustunga; konsol sidebar → drawer |
| — | **720px** | `useNarrow()` — `EntityTable` kartaga aylanadi |
| — | 420 / 760 / 1100 / 1500px | `pb-tiles-4` va `pb-tiles-5` ustun soni |
| `--bp-lg` | 1240px | ba'zi yon panellar |
| `--bp-xl` | 1600px | `.pb-split-wide` ikki ustunga |
| Web zichlik | 1920 / 2560 / 3840px | shrift, boshqaruv balandligi, `--nav-w`, `--aside-w` o'sadi |

### 1.11 Dizayn manbai

`docs/designs/` — Claude Design'dan kelgan handoff:
`PlayBron Mijoz.dc.html`, `PlayBron Xodim.dc.html`, `PlayBron Xodim Mobil.dc.html`, `_ds/`.

**Bu manbada faqat 3 ta yuza bor.** Landing, super admin paneli, tarif/checkout va obuna
ekranlari uchun dizayn manbai **yo'q** — ular mavjud SystemX komponentlaridan yig'iladi.

### 1.12 i18n

**Qaror: loyiha o'zbek va rus tilida ishlaydi. Ingliz tili yo'q.**
(`CLAUDE.md` dagi «uz/ru/en» eskirgan — yangilanishi kerak.)

**Amalda:** i18n kutubxonasi yo'q, barcha matn kodda o'zbekcha literal. Profilda til
tanlash bor, tanlov `playbron.customer` da saqlanadi, lekin interfeysga ta'sir qilmaydi.
Til ro'yxatida **English** ham bor — olib tashlanadi (DCR-007).

Qamrov: Mini App, konsol, landing, Telegram bot xabarlari, AI Agent hisoboti — hammasi
ikki tilda.

---

## 2. UI → ma'lumot xaritasi

Endpointlar 1.8 dagi jadvalda ekran bo'yicha berilgan. Quyida ular talab qiladigan
**entity va maydonlar**.

| Entity | Asosiy maydonlar | Qaysi ekranlar ishlatadi |
|---|---|---|
| `users` | `id`, `telegram_id`, `username`, `first_name`, `phone`, `phone_verified_at`, `created_at` | Kirish, Ro'yxatdan o'tish, Profil, Xodimlar |
| `organizations` | `id`, `owner_user_id`, `name`, `status`, `created_at` | (yangi) Super admin, Checkout |
| `clubs` | `id`, `org_id`, `name`, `address`, `phone`, `cover_url`, `about`, `opens_at`, `closes_at`, `timezone`, `lat`, `lng`, `status` | Klublar, Klub, Klub ma'lumoti, Boshqaruv paneli |
| `memberships` | `user_id`, `club_id`, `role`, `status`, `created_at` | Xodimlar, konsolga kirish |
| `rooms` | `id`, `club_id`, `name`, `floor`, `kind`, `console_type_id`, `tv_inch`, `pads`, `rate_hour`, `status` | Live board, Timeline, Xonalar, Vaqt tanlash |
| `console_types` | `id`, `code`, `label`, `sort` | Xonalar, Qurilmalar, Klub, Vaqt tanlash |
| `devices` | `id`, `club_id`, `room_id`, `kind`, `model`, `serial`, `status` | Qurilmalar |
| `rate_plans` | `id`, `club_id`, `label`, `from_min`, `to_min`, `factor`, `weekday_mask` | Tariflar, narx hisobi |
| `bookings` | `id`, `club_id`, `room_id`, `client_user_id`, `starts_at`, `ends_at`, `status`, `code6`, `prepaid_amount`, `arrived_at`, `no_show_at` | Live board, Timeline, Vaqt tanlash, Bronlarim, Aktiv seans |
| `bills` | `id`, `booking_id`, `play_amount`, `bar_amount`, `prepaid_amount`, `bonus_amount`, `total`, `method`, `closed_at`, `closed_by` | Kassa, Hisob, Smena |
| `orders` / `order_items` | `id`, `bill_id`, `status`, `created_at` / `product_id`, `qty`, `unit_price` | Buyurtmalar, Aktiv seans, Kassa |
| `products` | `id`, `club_id`, `category`, `name`, `cost`, `price`, `is_active` | Mahsulotlar, Kassa, Aktiv seans |
| `stock_moves` | `id`, `product_id`, `kind` (`in`/`sale`/`writeoff`), `qty`, `at`, `ref` | Mahsulotlar reestri |
| `expenses` | `id`, `club_id`, `date`, `category`, `amount`, `note`, `created_by` | Xarajatlar, Hisobot |
| `shifts` | `id`, `club_id`, `staff_user_id`, `opened_at`, `closed_at`, `cash_in`, `cash_out` | Smena |
| `blocklist` / `no_shows` | `user_id`, `club_id` (yoki global), `count`, `reason`, `blocked_at` | Qora ro'yxat, Bron qilish |
| `reviews` | `id`, `club_id`, `user_id`, `rating`, `text`, `created_at` | Klub |
| `plans` | `code` (gold/platinium/infinite), `price`, `period`, `limits` | (yangi) Tariflar, Checkout |
| `subscriptions` | `id`, `org_id`, `plan_code`, `status`, `current_period_end`, `cancel_at` | (yangi) Obuna, Super admin |
| `payments` | `id`, `org_id`, `provider`, `provider_txn_id`, `amount`, `state`, `created_at` | (yangi) Checkout, Super admin |
| `notifications_outbox` | `id`, `user_id`, `kind`, `payload`, `state`, `attempts`, `sent_at` | Barcha bildirishnoma |
| `audit_log` | `id`, `actor_user_id`, `org_id`, `action`, `target`, `before`, `after`, `at` | (yangi) Super admin |

### 2.1 Loading / Empty / Error — umumiy holat

| Holat | Qamrov |
|---|---|
| **Loading** | **Hech qayerda yo'q.** Ma'lumot sinxron import qilingan, skeleton/spinner komponenti DS da ham yo'q |
| **Empty** | Qisman: `EntityTable` `empty` propi (7 ekran), Vaqt tanlashda «bo'sh vaqt yo'q», Buyurtmalarda bo'sh ustun, `EmptyState` komponenti mavjud lekin kam ishlatilgan |
| **Error** | Faqat forma validatsiyasi (`StatusLine tone="danger"`, 9 ekran). **Tarmoq xatosi, 401/403, qayta urinish — yo'q.** Error boundary yo'q |

Bu — keyingi fazadagi eng katta mexanik ish: 22 ta ekranga uch holat qo'shish.

---

## 3. Gap-analiz — biznes oqimi talab qiladigan, lekin UI da yo'q

| # | Ekran / imkoniyat | Nega kerak | Rol | Tarif |
|---|---|---|---|---|
| 1 | **Landing** (bosh sahifa, tariflar, klub uchun taklif) — `playbron.uz`, uz/ru, SEO noldan | Klub egasi tizimga kiradigan yagona eshik. Hozir umuman yo'q | Public | — |
| 2 | **Telegram Login Widget** bilan kirish | Landing'da egasi Telegram orqali kiradi; imzo bot token bilan tekshiriladi | Public → Klub egasi | — |
| 3 | **Tarif tanlash va checkout** | Gold/Platinium/Infinite tanlash, davr (oy/yil), summa, Click yoki Payme tanlash | Klub egasi | — |
| 4 | **To'lov natijasi sahifasi** | Click/Payme brauzerda ochiladi va qaytaradi; `success` / `pending` / `failed` uchun sahifa va Telegram'ga qaytish tugmasi kerak. **Router yo'qligi sababli hozir ilinadigan URL yo'q** | Klub egasi | — |
| 5 | **Tashkilot yaratish (onboarding)** | To'lovdan keyin: tashkilot nomi, birinchi klub, ish vaqti, xonalar — sehrgar | Klub egasi | Barchasi |
| 6 | **Obuna holati va uzaytirish** | Joriy tarif, tugash sanasi, qolgan kun, uzaytirish, tarif almashtirish, bekor qilish. **Tugashiga 3 kun qolganda boshqaruv panelida alert** | Klub egasi | Barchasi |
| 6a | **Merchant kalitlari** | Bron to'lovi klub hisobiga tushishi uchun egasi Click/Payme kalitlarini kiritadi | Klub egasi | Barchasi |
| 7 | **To'lovlar tarixi / hisob-faktura** | Obuna to'lovlari ro'yxati, holati, qaytarish | Klub egasi | Barchasi |
| 8 | **Limitga yetgan holat** | Xona/xodim/klub limiti tugaganda: bloklovchi holat + «tarifni ko'tarish» chaqiruvi. Hozir CRUD cheksiz | Klub egasi | Gold, Platinium |
| 9 | **Super admin — tashkilotlar** | Ro'yxat, holat, tarif, oxirgi to'lov; faollashtirish/to'xtatish, qo'lda tarif berish | Super admin | — |
| 10 | **Super admin — platforma tushumi** | Obuna pullari: MRR, yangi/uzaytirilgan/yo'qolgan, provayder kesimi. **Klub tushumi bilan aralashmaydi** | Super admin | — |
| 11 | **Super admin — klublar tushumi (agregat)** | Klublarning bron tushumi jamlanmasi — platforma sog'lig'i ko'rsatkichi | Super admin | — |
| 12 | **Super admin — obunalar** | Muddati tugayotganlar, `past_due`, `suspended`; qo'lda holat o'zgartirish | Super admin | — |
| 13 | **Super admin — audit log** | Kim, qachon, nima qildi (ayniqsa tenant to'xtatish va qo'lda tarif) | Super admin | — |
| 14 | **AI Agent sozlamalari** | Kunlik hisobot: vaqt, tarkib, qaysi klublar, yoqish/o'chirish | Klub egasi | **Infinite** |
| 15 | **Xodim taklif qilish oqimi** | Hozir xodim login/parol bilan yaratiladi. Telegram-only da: taklif havolasi / kod → xodim bot orqali qo'shiladi | Klub egasi | Barchasi |
| 16 | **Klub tanlash (ko'p klubli tashkilot)** | Bir tashkilotda bir necha klub bo'lsa — kontekst almashtirgich. Hozir bitta klub qotirilgan | Klub egasi, Xodim | Platinium, Infinite |
| 17 | **Mijoz: Tasdiqlash va QR** | Bron oqimining ikki bo'g'ini placeholder holida | Mijoz | — |
| 18 | **Mijoz: bron bekor qilish tasdig'i** | Tugma bor, oqim yo'q (qaytarish qoidasi bilan) | Mijoz | — |
| 19 | **Bildirishnoma sozlamalari (klub tomonda)** | Qaysi hodisada egaga/xodimga Telegram xabari ketishi | Klub egasi | Platinium, Infinite |
| 20 | **Xatolik va offline holatlari** | 401 (sessiya tugadi), 403 (tarif yetmaydi), 5xx, tarmoq yo'q | Barchasi | — |

### 3.1 Mavjud UI biznes modelga zid bo'lgan joylar

Bular «yetishmayotgan» emas — **mavjud va noto'g'ri**. Dizayn muzlatilgan bo'lgani uchun
ular `docs/design-change-requests.md` ga yozildi.

| Joy | Ziddiyat |
|---|---|
| `admin/screens/login.tsx` | Login + parol. Yangi qoida: **faqat Telegram**, parol yo'q |
| `admin/screens/admin/settings.tsx` | «Parolni almashtirish» bloki — Telegram auth'da ma'nosiz |
| `admin/screens/admin/staff.tsx` | Xodimga `login` maydoni beriladi — Telegram-only da `telegram_id`/taklif bo'lishi kerak |
| `miniapp/screens/register.tsx` | Ism + telefon qo'lda kiritiladi. To'g'risi: `initData` dan profil, telefon `requestContact` orqali |
| ~~`miniapp/screens/bill.tsx`, `confirm` oqimi~~ | **HAL QILINDI:** bron to'lovi ham Click/Payme orqali. Mavjud UI to'g'ri, o'zgarish kerak emas. Backendda ikki to'lov yuzasi ajratiladi (`01-architecture.md` §6.0) |
| `miniapp` til ro'yxati | `LANGS` da English bor — loyiha faqat uz/ru (DCR-007) |
| Pul turi | Frontendda `number`. `CLAUDE.md` `bigint` so'm talab qiladi |
| `docs/archive/BUILD-BRIEF.md` | NestJS + Prisma stack'ini tavsiflaydi — yangi Python qaroriga zid. 2026-08-17 da arxivlandi |
