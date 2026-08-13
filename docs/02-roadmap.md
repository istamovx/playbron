# PlayBron — Yo'l xaritasi

> Hajm birligi: **S** ≈ 1–2 kun, **M** ≈ 3–5 kun, **L** ≈ 1–2 hafta, **XL** ≈ 2–4 hafta
> (bitta ishlab chiquvchi uchun). Dizayn muzlatilgan qoidasi barcha fazalarda amal qiladi.

---

## Umumiy ko'rinish

| # | Faza | Hajm | Bog'liq |
|---|---|---|---|
| 0 | Audit va arxitektura | M | — |
| **1** | **Backend skeleti + auth + tenancy** | **L** | 0 |
| 2 | Frontend ma'lumot qatlami (mock → API) | M | 1 |
| 3 | Klub domeni: xona, tarif, mahsulot, xarajat | L | 1, 2 |
| 4 | Bron va kassa | L | 3 |
| 5 | Landing + tarif + to'lov + obuna | L | 1 |
| 6 | Telegram botlar va bildirishnomalar | M | 4, 5 |
| 7 | Super admin paneli | M | 5 |
| 8 | AI Agent (Infinite) | M | 6, 7 |
| 9 | Sifat: i18n, testlar, monitoring, deploy | L | barchasi |

---

## Faza 0 — Audit va arxitektura ✅

**Maqsad:** Repo holatini aniq bilish, arxitektura qarorlarini yozib qo'yish.
**Fayllar:** `docs/00-audit.md`, `docs/01-architecture.md`, `docs/02-roadmap.md`,
`docs/03-entitlements.md`, `docs/design-change-requests.md`.
**Tugash mezoni:** To'rt hujjat tasdiqlangan, bloklovchi savollarga javob olingan.
**Hajm:** M.

---

## Faza 1 — Backend skeleti + auth + tenancy ✅

**Maqsad:** Ishlaydigan API, Telegram auth va RLS bilan tenant izolyatsiyasi.

### Bajarildi — 2026-08-13

| Tugash mezoni | Holat |
|---|---|
| `initData` bilan token olinadi, soxta imzo rad etiladi | ✅ 21 test + haqiqiy `@playbronbot` tokeni bilan tekshirildi |
| Ikki tenant bir so'rovda boshqa-boshqa ma'lumot oladi | ✅ `test_rls.py` — 4 test |
| `alembic upgrade head` toza bazada xatosiz | ✅ 9 jadval, 8 policy, 3 rol |

**Ishlab chiqarish paytida topilgan va tuzatilgan xatolar:**

1. `ContextVar` sukut qiymati o'zgaruvchan obyekt edi — bir so'rovning `user_id` si
   boshqasiga sizib o'tishi mumkin edi.
2. Kirish tranzaksiyasida `SET LOCAL app.user_id` yangilanmasdi — refresh token yozuvi
   RLS bilan rad etilardi.
3. O'g'irlangan token aniqlanganda barcha tokenlarni bekor qilish **ishlamasdi**: UPDATE
   RLS ostida 0 qatorga tegardi va `raise` tranzaksiyani qaytarardi. Endi alohida
   tranzaksiyada, to'g'ri kontekst bilan.
4. `logout` marshruti `public_db` ga bog'langan edi — tranzaksiya token ochilishidan
   oldin boshlanib, RLS `WITH CHECK` yozishga yo'l bermasdi.
5. Refresh rotatsiyasida qulf yo'q edi — bir vaqtda kelgan ikki so'rov bitta tokendan
   ikkita amal qiluvchi sessiya yasardi. `SELECT … FOR UPDATE` qo'shildi.
6. `app.org_id` hech qachon to'ldirilmasdi — xodim o'z klubining tarifini ko'ra olmasdi.
7. `Membership` da `users` ga ikkita FK bor edi (`user_id`, `invited_by`) — ORM
   munosabati noaniq, ilova ishga tushmasdi.
8. `JWT_SECRET` uzunligi tekshirilmasdi — prod'da 32 baytdan qisqa kalit bilan
   ishga tushmaydigan qilindi.

### Adversarial audit — 4 mustaqil linza (RLS, auth, DB, API)

48 topilma, 8 tasi ko'p ovozli tekshiruvdan o'tdi va **tuzatildi**
(`migrations/versions/0003_rls_hardening.py` + `core/config.py` + `deps.py`):

| Darajasi | Muammo | Yechim |
|---|---|---|
| **Kritik** | `ENV` o'rnatilmasa sozlama `local` ga tushardi va JWT repo'dagi ochiq `dev-only-change-me` bilan imzolanardi — istalgan kishi super admin tokeni yasay olardi | `env` sukut qiymati `prod`; `jwt_secret` sukut qiymati butunlay olib tashlandi; kalit uzunligi va `DEBUG`/`CORS` prod'da majburiy tekshiriladi |
| Yuqori | `organizations` INSERT — har kim o'ziga `status='active'`, `plan_code='infinite'` tashkilot yasab, to'lovni chetlab o'tardi | INSERT policy'si `status='pending' AND plan_code IS NULL` ga cheklandi; `UPDATE (status, plan_code)` grant'i olib tashlandi |
| Yuqori | `clubs_write` faqat `org_id` bo'yicha edi — bitta klubdagi STAFF qo'shni klubni o'chira va `payment_credentials` ni o'ziga yo'naltira olardi | Yozish `app_club_role()` bilan OWNER/ADMIN ga va faol klubga bog'landi; `DELETE` grant'i olib tashlandi |
| Yuqori | `clubs.payment_credentials` — `status='active'` klub anonim o'qilardi, RLS ustun darajasida ishlamaydi | Ustun `club_payment_credentials` jadvaliga ko'chirildi, o'z policy'si bilan (faqat OWNER, o'z tashkiloti) |
| Yuqori | `require_super_admin` IP allowlist'i `X-Forwarded-For` bilan chetlab o'tilardi | Faqat haqiqiy peer IP; proksi ortida uvicorn `--proxy-headers --forwarded-allow-ips` bilan yuritiladi |
| O'rta | `audit_log` append-only emas edi — aktor o'z izini o'chira olardi | SELECT + INSERT policy'lari; `UPDATE`/`DELETE` grant'i olib tashlandi |
| O'rta | `clubs_read` va `memberships` `status` ni tekshirmasdi — bo'shatilgan xodim kirishda davom etardi | Ikkala policy'ga `status = 'active'` sharti |
| O'rta | `ALTER DEFAULT PRIVILEGES` fail-open edi — RLS'siz qo'shilgan yangi jadval avtomatik ochilardi | Sukut imtiyozlar bekor qilindi; `test_every_table_has_rls` qo'riqchi testi |

Har bir teshik uchun hujum stsenariysini takrorlaydigan test yozildi
(`tests/test_rls_hardening.py`, 8 test).

**Yakuniy holat:** 29 test o'tadi, `ruff` toza, 27 punktli uchidan-uchiga tekshiruv yashil.

**Qolgan qarz:**
- `JWT_SECRET` 18 bayt — prod'dan oldin `openssl rand -hex 32` (lokalda ogohlantirish
  chiqadi, prod'da ilova umuman ishga tushmaydi).
- `TG_WEBHOOK_SECRET` bo'sh — Faza 6 da kerak, prod'da majburiy.
- `test_real_initdata_sample` hali `skip` — haqiqiy Mini App `initData` namunasi kerak.
- Auditning 40 ta topilmasi **tekshirilmay qoldi** (sessiya limiti) — ular orasida
  haqiqiylari bo'lishi mumkin, keyingi fazada qayta yugurtiriladi.

**Tegiladigan fayllar (yangi):**
```
api/src/playbron/{main,core/*,modules/auth/*,modules/users/*,modules/orgs/*}
api/migrations/0001_users_orgs_clubs_memberships.py   (RLS policy bilan)
api/migrations/0002_seed_plans_consoles_superadmins.py
docker-compose.yml (postgres, redis, api)
```

**Ish:**
1. FastAPI skeleti, `core/config`, `core/db` (`SET LOCAL` kontekst), `core/errors`.
2. Alembic; birinchi migratsiyada `users`, `organizations`, `clubs`, `memberships`
   + RLS policy'lar + `playbron_app` va `playbron_platform` rollari.
3. `POST /auth/telegram/initdata` va `POST /auth/telegram/widget` — HMAC tekshiruvi,
   TTL, replay himoyasi (Redis).
4. JWT access + refresh rotatsiya; `GET /me`, `GET /me/entitlements` (hozircha statik plan).
5. Super admin seed va allowlist.

**Tugash mezoni:**
- Telegram'dan kelgan `initData` bilan token olinadi, soxta imzo rad etiladi.
- Ikki xil foydalanuvchi bir xil so'rovda **boshqa-boshqa** klub ma'lumotini oladi (RLS testi).
- `alembic upgrade head` toza bazada xatosiz ishlaydi.

**Hajm:** L. **Bog'liq:** Faza 0.

---

## Faza 2 — Frontend ma'lumot qatlami

**Maqsad:** Mock importlarni almashtirish uchun qatlam qurish. **Vizual o'zgarish yo'q.**

**Tegiladigan fayllar:**
```
packages/api-client/*                      (yangi paket: fetch, tur, xato)
apps/admin/src/api/*, apps/miniapp/src/api/*
apps/admin/src/app.tsx                     (QueryClientProvider)
apps/miniapp/src/app.tsx
apps/admin/src/screens/**                  (faqat import satri + holat)
apps/miniapp/src/screens/**
```

**Ish:**
1. `@playbron/api-client` — OpenAPI'dan tur generatsiyasi, `fetch` o'ramchisi,
   token yangilash, yagona xato formati.
2. TanStack Query ikkala app'da yoqiladi (miniapp'da allaqachon o'rnatilgan).
3. **Router**: `apps/admin` ga `react-router` kiritiladi — URL, deep-link va to'lovdan
   qaytish uchun zarur. Ekranlar o'zgarmaydi, faqat `screen` state URL bilan sinxronlanadi.
4. Har bir ekranga **loading / empty / error** holati — mavjud DS komponentlari bilan
   (`Panel` + `StatusLine` + `EmptyState`), yangi vizual element kiritmasdan.
5. `localStorage` migratsiyasi: `playbron.club` / `playbron.customer` / `playbron.console`
   kalitlariga `version` qo'shiladi va eskisi tozalanadi.

**Tugash mezoni:** Bitta ekran (masalan «Xodimlar») to'liq API'dan ishlaydi, qolganlari
mock'da qoladi; uch holat ko'rinadi; brauzer «orqaga» tugmasi ishlaydi.

**Hajm:** M. **Bog'liq:** Faza 1.

---

## Faza 3 — Klub domeni

**Maqsad:** Klub egasi kabinetidagi barcha CRUD real bo'ladi.

**Tegiladigan fayllar:**
```
api/src/playbron/modules/clubs/*, inventory/*, finance/*
api/migrations/0003_rooms_rate_plans_devices.py
api/migrations/0004_products_stock_expenses_shifts.py
apps/admin/src/screens/admin/*             (import + holat)
apps/admin/src/store/club.ts               (persist → server state)
```

**Ish:** Xona, vaqt tarifi, qurilma, mahsulot, kirim/reestr, xarajat, smena — CRUD +
entitlement tekshiruvi (`check_limit`). Cover rasm yuklash (MinIO/S3).

**Tugash mezoni:** `useClub` store'i o'chadi, ma'lumot serverdan keladi; limit tugaganda
`403 LIMIT_REACHED` UI'da to'g'ri ko'rinadi.

**Hajm:** L. **Bog'liq:** Faza 1, 2.

---

## Faza 4 — Bron va kassa

**Maqsad:** Tizimning yuragi — bron, seans, hisob.

**Tegiladigan fayllar:**
```
api/migrations/0005_bookings_exclude_constraint.py   (btree_gist + EXCLUDE)
api/migrations/0006_bills_orders_items.py
api/src/playbron/modules/bookings/*, bills/*
api/src/playbron/jobs/{reminders,no_show}.py
apps/miniapp/src/screens/{slots,session,bill,bookings}.tsx
apps/miniapp/src/screens/confirm.tsx, qr.tsx        (YANGI — hozir placeholder)
apps/admin/src/screens/{live-board,timeline,orders,pos,shift,blacklist}.tsx
```

**Ish:**
1. `bookings` + `EXCLUDE` konstreynt; `23P01` → `409 SLOT_TAKEN`.
2. Mavjudlik endpointi (`/availability`) — hozirgi `bookedRanges()` mantiqini serverga.
3. Bron oqimi: yaratish → bron to'lovi → QR → kelish → seans → hisob → yopish.
4. **Tasdiqlash va QR ekranlari** — mavjud DS komponentlaridan yig'iladi.
5. No-show job (`NO_SHOW_MIN` = 10 daqiqa), eslatma job (30/15 daqiqa), grace (10 daqiqa).
6. Kassa: buyurtma holat mashinasi, hisob yopish, `stock_moves` avtomatik yozilishi.

**Tugash mezoni:** Ikki foydalanuvchi bir vaqtda bir xonani bron qilsa — biri `409` oladi.
Mijoz bron qiladi, xodim board'da ko'radi, hisob yopiladi, reestr kamayadi.

**Hajm:** L. **Bog'liq:** Faza 3.

---

## Faza 5 — Landing + tarif + to'lov + obuna

**Maqsad:** Klub egasi tizimga o'zi kira oladi va pul to'laydi.

**Tegiladigan fayllar:**
```
apps/landing/*                             (YANGI app)
api/src/playbron/modules/billing/*, payments/click/*, payments/payme/*
api/migrations/0007_subscriptions_payments.py
api/src/playbron/jobs/subscription_check.py
apps/admin/src/screens/billing/*           (YANGI: obuna, to'lovlar, limitlar)
apps/admin/src/screens/onboarding/*        (YANGI: tashkilot yaratish sehrgari)
```

**Ish:**
1. Landing — `playbron.uz`, **uz/ru**, bosh sahifa + tariflar + Telegram Login Widget.
   **SEO noldan**: statik pre-render (Astro yoki Vite SSG, SPA emas), har til uchun
   alohida URL (`/` va `/ru`), `hreflang`, `sitemap.xml`, `robots.txt`, Open Graph,
   `LocalBusiness`/`SoftwareApplication` schema.org razmetkasi.
2. Checkout: tarif + davr + provayder → to'lov havolasi. **Sinov davri yo'q** — tashkilot
   `pending` holatda yaratiladi, birinchi to'lovdan keyin `active`.
3. Click va Payme callback endpointlari — **ikki marshrut**: obuna (platforma hisobi) va
   bron (klub hisobi). Holat mashinasi, idempotentlik, webhook xavfsizligi
   (`01-architecture.md` §6 dagi `[TEKSHIRISH]` punktlari avval yopiladi).
4. Obuna holat mashinasi + kunlik scheduler + eslatmalar: **tugashiga 3 kun qolganda**
   Telegram xabari va boshqaruv panelidagi alert.
5. Onboarding sehrgari: tashkilot → birinchi klub → xonalar → merchant kalitlari.
6. Limit holatlari UI'da.

**Tugash mezoni:** Sinov to'lovi (provayder sandbox) obunani `active` qiladi; qayta
yuborilgan webhook ikkinchi yozuv yaratmaydi; muddat tugaganda holat o'zi o'zgaradi.

**Hajm:** L. **Bog'liq:** Faza 1 (mustaqil — 3/4 bilan parallel ketishi mumkin).

---

## Faza 6 — Telegram botlar va bildirishnomalar

**Maqsad:** Barcha aloqa Telegram orqali.

**Tegiladigan fayllar:**
```
api/src/playbron/modules/telegram/{bots,handlers,webhook,outbox}.py
api/migrations/0008_notifications_outbox.py
apps/miniapp/src/lib/telegram.ts           (requestContact oqimi)
apps/miniapp/src/screens/register.tsx      (qayta ishlanadi — DCR-002)
```

**Ish:** Ikki bot, webhook + navbat, `requestContact`, outbox pattern, rate limit,
bloklangan foydalanuvchi bilan ishlash, Mini App'ni rol bo'yicha marshrutlash.

**Tugash mezoni:** Bron eslatmasi 30 va 15 daqiqada keladi; bot bloklangan bo'lsa xabar
`blocked` bo'ladi va qayta urinilmaydi; telefon `requestContact` orqali tasdiqlanadi.

**Hajm:** M. **Bog'liq:** Faza 4, 5.

---

## Faza 7 — Super admin paneli

**Maqsad:** Platforma egasi tizimni boshqaradi.

**Tegiladigan fayllar:**
```
api/src/playbron/modules/platform/*        (BYPASSRLS pool)
api/migrations/0009_audit_log.py
apps/admin/src/screens/platform/*          (YANGI: tashkilotlar, obunalar, tushum, audit)
apps/admin/src/mock/data.ts                (NAV_PLATFORM qo'shiladi)
```

**Ish:** Tashkilotlar ro'yxati va holati, obunalar, platforma tushumi (a), klublar tushumi
agregati (b) — **alohida panellarda**, audit log, tenant to'xtatish/faollashtirish, qo'lda
tarif berish, xavfli amallar uchun botdan tasdiq kodi.

**Tugash mezoni:** Super admin bo'lmagan foydalanuvchi `/platform/*` ga 404 oladi; har bir
amal audit log'da; ikki tushum aralashmaydi.

**Hajm:** M. **Bog'liq:** Faza 5.

---

## Faza 8 — AI Agent

**Maqsad:** Infinite tarifidagi egaga kunlik hisobot.

**Tegiladigan fayllar:**
```
api/src/playbron/modules/ai_agent/*
api/migrations/0010_daily_club_stats.py
api/src/playbron/jobs/ai_daily_report.py
apps/admin/src/screens/admin/ai-agent.tsx  (YANGI: sozlamalar)
```

**Ish:** Kunlik agregat jadval, scheduler, LLM chaqiruvi (strukturaviy JSON kiradi,
qisqa matn chiqadi), admin bot orqali yuborish, sozlamalar ekrani, entitlement gate.

**Tugash mezoni:** Infinite tashkilot har kuni belgilangan vaqtda hisobot oladi;
Gold/Platinium olmaydi; sozlamada o'chirilsa kelmaydi.

**Hajm:** M. **Bog'liq:** Faza 6, 7.

---

## Faza 9 — Sifat

**Maqsad:** Prod'ga chiqishga tayyorlik.

**Ish:**
- **i18n**: **uz/ru** resurslari (English yo'q — DCR-007), profildagi til tanlash haqiqiy
  ishlaydi. Qamrov: Mini App, konsol, landing, bot xabarlari, AI Agent hisoboti.
  Hozir barcha matn kodda o'zbekcha literal.
- **Testlar**: backend — auth, RLS izolyatsiyasi, `EXCLUDE` konstreynt, to'lov
  idempotentligi, obuna holat mashinasi; frontend — hisob funksiyalari (`billOf`,
  `prepayAmount`, `freeStations`).
- Sentry, Prometheus, `/healthz`, backup va tiklash sinovi.
- Yuklama sinovi: board va availability endpointlari.

**Tugash mezoni:** CI yashil, RLS testi oqishni ushlaydi, backup tiklash sinovi o'tdi.

**Hajm:** L. **Bog'liq:** barchasi.

---

## Tavsiya: **Faza 1 dan boshlanadi**

Sabab: auth va tenancy — qolgan hamma narsaning poydevori; ular tayyor bo'lmaguncha
hech qaysi ekranni real ma'lumotga ulab bo'lmaydi va noto'g'ri tanlangan izolyatsiya
modeli keyin butun bazani qayta yozishga majbur qiladi.

### Parallel ketishi mumkin

- **Faza 5** (landing + to'lov) Faza 1 dan keyin **3/4 bilan parallel** — ular boshqa
  modullarga tegadi.
- **Faza 2** ning router qismi Faza 1 tugashini kutmaydi.

### Kritik yo'l

```
1 → 2 → 3 → 4 → 6 → 8
     └→ 5 → 7 ─────┘
```
