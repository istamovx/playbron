# PlayBron — Claude Code Build Brief

> **ARXIV — 2026-08-17 da `docs/` dan bu yerga ko'chirildi. QAROR MANBAI EMAS.**
>
> Bu hujjatdagi stek (NestJS, Prisma, Fastify, Socket.IO, Next.js, BullMQ,
> MinIO, Payme/Click, Eskiz.uz) loyihada QO'LLANMAGAN — hech biri repoda yo'q.
> Domen modeli ham qisman boshqacha amalga oshirilgan (`sessions`, `bills`,
> `payments`, `rooms`, `tariffs` jadvallari yo'q).
>
> Amaldagi manba: `CLAUDE.md` (invariantlar), `docs/HOLAT.md` (holat),
> `docs/audit-report.md` (nima bor / nima yo'q). Bu fayl faqat dastlabki
> niyatni ko'rish uchun saqlanadi.

> Loyiha nomi `PlayBron` — o'zgartirsang, barcha joyda almashtir.

<context>
PlayStation o'yin klublari uchun multi-tenant SaaS bron platformasi. O'zbekiston bozori.

Biznes modeli — ikki tomonlama foyda:
- Klub: bo'sh vaqtlar to'ladi, deposit orqali no-show kamayadi, bar/snack savdosi seans ichida o'sadi.
- Mijoz: joy kafolatlangan, navbat yo'q, deposit yo'qolmaydi — bar balansiga aylanadi, bonus to'planadi.

Uch xil foydalanuvchi, uch xil interfeys:
- **Mijoz** → Telegram Mini App (asosiy kanal) + landing sahifadan web bron
- **Xodim** → dashboard'ning operativ qismi (live board, seanslar, buyurtmalar, kassa)
- **Klub egasi (Admin)** → dashboard'ning boshqaruv qismi (xonalar, tariflar, menyu, xodimlar, hisobotlar)
- **Superadmin** (platforma egasi) → klublarni tasdiqlash, obuna tariflari, global statistika

Hech qanday mavjud kod yo'q. Noldan quriladi.
</context>

<stack>
Monorepo: Turborepo + pnpm workspaces.

```
apps/
  api/        NestJS 11 (Fastify adapter) — yagona backend
  admin/      React 19 + Vite 6 — admin va xodim dashboard (bitta SPA, role bo'yicha routing)
  miniapp/    React 19 + Vite 6 — Telegram Mini App (mijoz)
  landing/    Next.js 15 App Router — marketing sayt + web bron (SSR/SEO)
packages/
  ui/         umumiy React komponentlar (Blue design system asosida)
  types/      zod schema'lar + TS tiplar, API contract manbai
  config/     eslint, tsconfig, tailwind preset
```

Backend: NestJS 11, PostgreSQL 16, Prisma 6, Redis 7 (cache + BullMQ queue + distributed lock), Socket.IO, MinIO (S3-mos rasm saqlash).

Frontend: TypeScript strict, TanStack Query v5, TanStack Router (admin), Zustand (faqat UI state), Tailwind CSS v4, react-hook-form + zod, Recharts, `@telegram-apps/sdk-react` (miniapp).

Tashqi servislar: Payme Merchant API, Click Shop API, Eskiz.uz (SMS OTP), Telegram Bot API.

Infra: Docker Compose (postgres, redis, minio, api), GitHub Actions CI.
</stack>

<multitenancy>
**Shared schema + `club_id` + Postgres RLS.** Schema-per-tenant EMAS — tenantlar ko'p va kichik, hamda platforma darajasidagi so'rovlar (klub qidiruv, global hisobot, mijozning bir nechta klubdagi bronlari) kerak.

Qoidalar:
- `clubs` va `users` dan tashqari har bir jadvalda `club_id uuid not null` bor.
- Har bir tenant-scoped jadvalda RLS policy: `USING (club_id = current_setting('app.club_id')::uuid)`.
- NestJS'da `nestjs-cls` bilan request-scoped context: interceptor JWT'dan `club_id` ni oladi, Prisma middleware har transaction boshida `SET LOCAL app.club_id` bajaradi.
- Superadmin uchun `app.bypass_rls = on` — alohida DB role orqali.
- Mijoz global entity: bitta `users` yozuvi bir nechta klubda bron qila oladi. `club_members` jadvali faqat STAFF va CLUB_ADMIN uchun.
</multitenancy>

<domain_model>
Pul birligi: **so'm, `bigint`, kasrsiz**. Hech qayerda float ishlatilmaydi.
Vaqt: DB'da `timestamptz` UTC, ko'rsatishda `Asia/Tashkent`. Klub sozlamasida timezone maydoni bor (kelajak uchun).

**clubs** — id, slug, name, description, address, lat, lng, phones[], working_hours (jsonb: hafta kunlari, 24/7 flag), photos[], status (PENDING/ACTIVE/SUSPENDED), plan (FREE/PRO), commission_rate, timezone, created_at

**club_settings** — club_id, deposit_percent (default 30), deposit_min (default 20000), deposit_round_to (1000), cancel_policy (jsonb: `[{hours_before: 3, refund_percent: 100}, {hours_before: 1, refund_percent: 50}, {hours_before: 0, refund_percent: 0, to_bar_credit: true}]`), slot_minutes (30), min_booking_minutes (60), max_advance_days (14), overtime_grace_minutes (10), auto_cancel_unpaid_minutes (15)

**users** — id, phone (unique), name, telegram_id (unique nullable), telegram_username, avatar_url, birth_date, language (uz/ru/en), is_blocked, created_at

**club_members** — id, club_id, user_id, role (CLUB_ADMIN | STAFF), permissions (jsonb), is_active

**rooms** — id, club_id, name, type (STANDARD | VIP | TOURNAMENT), capacity, description, photos[], sort_order, is_active
**stations** — id, club_id, room_id, code ("PS-01"), console_type (PS4 | PS4_PRO | PS5 | PS5_PRO), tv_inches, controllers_count, has_vr, status (FREE | OCCUPIED | RESERVED | MAINTENANCE), is_active

**tariffs** — id, club_id, name, scope (STATION | ROOM), target (console_type yoki room_type), days_mask (bitmask 1–127), time_from, time_to, price_per_hour, priority, valid_from, valid_to, is_active
  Narx hisoblash: intervalni tarif chegaralari bo'yicha bo'laklarga bo'lib, har bo'lakka eng yuqori `priority` li mos tarifni qo'llash. Mos tarif topilmasa → 422 `NO_TARIFF_FOR_SLOT`.

**packages** — id, club_id, name, hours, included_menu_items (jsonb), price, is_active — "2 soat + 2 ta ichimlik + chips" tipidagi kombo.

**bookings** — id, club_id, user_id, station_id, room_id (nullable, VIP butun xona bron qilinganda), starts_at, ends_at, players_count, base_price, package_id, deposit_amount, deposit_paid_at, status (PENDING | CONFIRMED | CHECKED_IN | COMPLETED | CANCELLED | NO_SHOW), source (MINIAPP | WEB | STAFF | PHONE), code (6 xonali, QR uchun), cancel_reason, cancelled_by, created_at

  **Kritik konstreyn** — overlap bo'lmasligi DB darajasida kafolatlanadi:
  ```sql
  CREATE EXTENSION IF NOT EXISTS btree_gist;
  ALTER TABLE bookings ADD CONSTRAINT bookings_no_overlap
    EXCLUDE USING gist (
      station_id WITH =,
      tstzrange(starts_at, ends_at, '[)') WITH &&
    ) WHERE (status IN ('PENDING','CONFIRMED','CHECKED_IN'));
  ```
  Application darajasidagi tekshiruv ham bo'ladi (foydalanuvchiga chiroyli xabar uchun), lekin yakuniy himoya — shu konstreyn. `23P01` xatosi `409 SLOT_TAKEN` ga map qilinadi.

**sessions** — id, club_id, booking_id (nullable — walk-in), station_id, user_id (nullable), started_at, planned_end_at, ended_at, started_by, ended_by, status (ACTIVE | PAUSED | FINISHED), total_minutes, play_amount
  Uzaytirish: `POST /sessions/:id/extend` — keyingi bron bilan to'qnashuvni tekshiradi, bo'sh bo'lsa `planned_end_at` ni suradi va bron yaratadi.

**menu_categories** — id, club_id, name, icon, sort_order
**menu_items** — id, club_id, category_id, name, description, price, cost_price, photo_url, stock_qty (nullable = cheksiz), is_available, sort_order

**orders** — id, club_id, session_id, station_id, user_id, status (NEW | ACCEPTED | PREPARING | DELIVERED | CANCELLED), placed_by (CUSTOMER | STAFF), note, total, created_at
**order_items** — id, order_id, menu_item_id, name_snapshot, price_snapshot, qty

**bills** — id, club_id, session_id, play_amount, orders_amount, discount_amount, promo_code_id, deposit_applied, bar_credit_applied, loyalty_applied, total_due, status (OPEN | PAID | VOID), closed_at, closed_by
**payments** — id, club_id, bill_id (nullable), booking_id (nullable), kind (DEPOSIT | FINAL | REFUND), method (CASH | CARD_TERMINAL | PAYME | CLICK | BAR_CREDIT | LOYALTY), amount, provider_txn_id, state (CREATED | PERFORMED | CANCELLED), raw_payload (jsonb), created_at

**shifts** — id, club_id, staff_id, opened_at, closed_at, cash_start, cash_end, expected_cash, difference, note
**cash_movements** — id, shift_id, type (IN | OUT), amount, reason, created_by

**wallets** — user_id, club_id, bar_credit, expires_at — bekor qilingan depozitdan qolgan kredit.
**loyalty_accounts** — user_id, club_id, points, tier (BRONZE | SILVER | GOLD), total_spent
**loyalty_transactions** — id, account_id, delta, reason, ref_id
**promo_codes** — id, club_id (nullable = global), code, type (PERCENT | FIXED | FREE_HOURS), value, min_amount, usage_limit, used_count, per_user_limit, valid_from, valid_to, is_active

**reviews** — id, club_id, user_id, booking_id, rating (1–5), comment, reply, created_at
**notifications** — id, user_id, channel (TELEGRAM | SMS), template, payload, status, sent_at, error
**audit_log** — id, club_id, actor_id, action, entity, entity_id, before (jsonb), after (jsonb), ip, created_at — pul va sozlamalarga tegadigan har bir amal yoziladi.
</domain_model>

<business_rules>
1. **Deposit hisobi**: `deposit = ceil(base_price * deposit_percent / 100 / round_to) * round_to`, `deposit_min` dan kam bo'lmaydi, `base_price` dan oshmaydi.
2. **PENDING bron** `auto_cancel_unpaid_minutes` ichida to'lanmasa BullMQ job avtomatik `CANCELLED` qiladi va slotni bo'shatadi.
3. **Bekor qilish**: `cancel_policy` bo'yicha qaytariladi. Qaytarilmaydigan qism `wallets.bar_credit` ga o'tadi (30 kun amal qiladi) — mijoz pulni yo'qotmaydi, klub daromadni saqlaydi. Bu loyihaning asosiy "win-win" mexanikasi.
4. **Check-in**: xodim QR yoki 6 xonali kodni skanerlaydi → `CHECKED_IN` → seans avtomatik boshlanadi, `deposit` bill'ga `deposit_applied` sifatida tushadi.
5. **No-show**: `starts_at + 20 daqiqa` da kelmasa job `NO_SHOW` qo'yadi, deposit klubda qoladi, slot bo'shaydi.
6. **Overtime**: `planned_end_at` dan keyin `overtime_grace_minutes` bepul, keyin joriy tarif bo'yicha daqiqama-daqiqa hisoblanadi.
7. **Menyu buyurtmasi** faqat `ACTIVE` seans ichida mumkin. Mijoz Mini App'dan yuboradi → xodim ekranida real-time chiqadi → `DELIVERED` bo'lgach bill'ga qo'shiladi.
8. **Stock**: `stock_qty` bor bo'lsa buyurtma `ACCEPTED` bo'lganda kamayadi, `CANCELLED` da qaytadi. Nolga tushsa `is_available` avtomatik false.
9. **Bill yopish**: `total_due = play_amount + orders_amount − discount − deposit_applied − bar_credit_applied − loyalty_applied`. Manfiy chiqsa 0 ga tenglashadi, ortiqchasi bar_credit ga qaytadi.
10. **Loyalty**: har 1000 so'm = 1 ball, 1 ball = 100 so'm chegirma. Tier: 500k → SILVER (5%), 2M → GOLD (10%).
11. **Smena yopilmasdan** yangi smena ochilmaydi. Farq `difference` da qayd etiladi va admin hisobotida ko'rinadi.
12. **Slot tarmog'i**: bronlar `slot_minutes` ga tekislanadi, minimal davomiylik `min_booking_minutes`.
</business_rules>

<api_and_auth>
REST, `/api/v1`, zod-dan generatsiya qilingan OpenAPI. Barcha ro'yxat endpointlari cursor pagination.

Auth uch xil kirish nuqtasi, bitta JWT chiqadi:
- **Web/mijoz**: telefon + SMS OTP (Eskiz.uz). OTP 6 xonali, 5 daqiqa, Redis'da, 3 urinish, telefon bo'yicha rate-limit.
- **Mini App**: `initData` ni bot tokeni bilan HMAC-SHA256 tekshirish, `auth_date` 24 soatdan eski bo'lmasligi. Tekshiruv o'tsa `telegram_id` bo'yicha user topiladi/yaratiladi. Parol yo'q.
- **Xodim/Admin**: telefon + parol (argon2) + majburiy `club_id` tanlash (bir kishi bir necha klubda ishlashi mumkin).

JWT payload: `{ sub, role, club_id, member_id }`. Access 15 daqiqa, refresh 30 kun (rotatsiya + Redis'da reuse detection). Guard'lar: `JwtGuard` → `ClubGuard` (club_id contextga yozadi) → `RolesGuard`.

Idempotency: to'lov va bron yaratishda `Idempotency-Key` header majburiy, natija Redis'da 24 soat.

Webhook'lar imzo bilan tekshiriladi, `raw_payload` saqlanadi, qayta ishlash idempotent.
</api_and_auth>

<payments>
Faqat **deposit** onlayn. Qolgan summa joyida (naqd yoki terminal) — xodim bill'da qo'lda belgilaydi.

**Payme Merchant API** (JSON-RPC, Basic auth): `CheckPerformTransaction`, `CreateTransaction`, `PerformTransaction`, `CancelTransaction`, `CheckTransaction`, `GetStatement`. Xato kodlari spetsifikatsiya bo'yicha (`-31050` va h.k.). `account.booking_id` orqali bog'lanadi.

**Click Shop API**: `Prepare` va `Complete` endpointlari, `sign_string` MD5 tekshiruvi.

Ikkalasi ham `PaymentProvider` interfeysi ortida — yangi provayder qo'shish bitta fayl. Provayder javobi kelguncha bron `PENDING`, `PerformTransaction`/`Complete` muvaffaqiyatli bo'lsa `CONFIRMED` va Telegram'ga tasdiq xabari ketadi.

Refund: `CancelTransaction` (Payme). Click'da qo'lda — admin panelda "qaytarildi" deb belgilanadi va audit log'ga yoziladi.
</payments>

<realtime>
Socket.IO, namespace `/club`, xona `club:{club_id}`, xodim va admin ulanadi.

Eventlar: `station.status_changed`, `booking.created`, `booking.cancelled`, `session.started`, `session.ending_soon` (10 daqiqa qolganda), `session.overtime`, `order.created`, `order.status_changed`, `shift.closed`.

Ulanishda JWT tekshiriladi, `club_id` mos kelmasa uziladi. Frontend'da qayta ulanish + TanStack Query cache invalidatsiyasi.
</realtime>

<telegram>
Bitta bot ikki vazifada:
1. **Mini App host** — `/start` tugmasi Mini App'ni ochadi. Deep link `?startapp=club_{slug}` to'g'ridan-to'g'ri klub sahifasiga olib boradi.
2. **Bildirishnoma kanali** — bron tasdiqlandi, 1 soat qoldi, seans 10 daqiqadan keyin tugaydi, bill yopildi, bar_credit muddati tugayapti.

Mini App ekranlari: klublar ro'yxati (masofa/reyting/bo'sh joy bo'yicha) → klub sahifasi (rasmlar, xonalar, narxlar, sharhlar) → sana + slot grid → stansiya tanlash → tasdiqlash va deposit → QR kod → aktiv seans (qolgan vaqt, menyu buyurtma, hisob) → mening bronlarim → balans va bonuslar → sharh qoldirish.

Telegram theme params (`--tg-theme-*`) design tokenlarga map qilinadi, light/dark avtomatik. `MainButton` va `BackButton` native ishlatiladi, o'z tugmalaring bilan dublikat qilinmaydi. Haptic feedback muhim amallarda.
</telegram>

<frontend>
**Design system**: mavjud "Blue" design system (Untitled UI v7 asosidagi CSS custom properties + Tailwind v4 theme mapping) `packages/ui` ga ko'chiriladi. Barcha rang, spacing, radius, shadow, typography faqat token orqali — hardcode qiymat yo'q. Uchala app bitta preset'dan foydalanadi.

**admin app** — role bo'yicha ikki navigatsiya daraxti, bitta kod bazasi:
- Xodim: *Live board* (stansiyalar gridi, rangli status, taymer), *Timeline* (kunlik gantt, drag bilan bron ko'chirish), *Buyurtmalar* (kanban), *Kassa* (POS: tez sotuv, bill yopish), *Smenam*
- Admin: *Dashboard* (KPI: daromad, band bo'lish %, o'rtacha chek, bar ulushi), *Bronlar*, *Xonalar va stansiyalar*, *Tariflar va paketlar*, *Menyu*, *Xodimlar*, *Mijozlar*, *Aksiya va promokodlar*, *Hisobotlar*, *Sozlamalar*

Live board va Timeline optimistik yangilanadi, socket eventi kelganda sinxronlanadi.

**landing app** (Next.js, SSR):
hero + bron qidiruv widget, "qanday ishlaydi" 3 qadam, klublar katalogi (`/klublar`, `/klub/[slug]` — SSG + ISR), narxlar, klub egalari uchun alohida sahifa va ariza formasi, FAQ, blog (ixtiyoriy), footer. Metadata, OG image, sitemap, JSON-LD (`LocalBusiness`), Lighthouse ≥ 90.

**i18n**: uz-Latin (default), ru, en. Barcha matn resurs fayllarida, komponentda literal yo'q. Sana/vaqt/pul formatlash `Intl` bilan.

**A11y**: klaviatura navigatsiyasi, focus ko'rinishi, kontrast AA, form xatolari `aria-describedby`.
</frontend>

<task>
Quyidagi tartibda bosqichma-bosqich qur. Har bosqich oxirida `pnpm build` va `pnpm test` toza o'tishi shart, keyin keyingisiga o't.

**P0 — Poydevor**
Turborepo skeleti, pnpm workspaces, TS strict, ESLint/Prettier, Docker Compose (postgres, redis, minio), `.env.example`, Prisma schema (yuqoridagi butun model), migratsiyalar, `btree_gist` va EXCLUDE konstreyn, RLS policy'lar, seed skript (1 ta demo klub, 2 xona, 8 stansiya, 3 tarif, 15 menyu pozitsiyasi, 20 mijoz, 50 tasodifiy bron), NestJS bootstrap + health check + Swagger.

**P1 — Auth va tenancy**
SMS OTP, Telegram initData, parol bilan kirish, JWT + refresh rotatsiya, guard'lar, `nestjs-cls` + Prisma middleware bilan RLS konteksti, `club_members` CRUD, audit log interceptor.

**P2 — Katalog va tariflar**
Rooms, stations, tariffs, packages CRUD. Narx kalkulyatori (interval bo'lish + priority) — bu sof funksiya, unit testlar bilan qoplanadi: kecha yarmidan o'tuvchi interval, hafta oxiri/ish kuni chegarasi, tarif topilmagan holat.

**P3 — Bron dvigateli**
Availability API (kun + stansiya bo'yicha bo'sh slotlar), bron yaratish (idempotent, konstreyn xatosini 409 ga map qilish), bekor qilish + refund siyosati + bar_credit, BullMQ joblari (unpaid auto-cancel, no-show, eslatma). Integration testlar: parallel ikki so'rov bitta slotga — bittasi 409 olishi shart.

**P4 — To'lovlar**
`PaymentProvider` abstraksiyasi, Payme va Click implementatsiyasi, webhook'lar, imzo tekshiruvi, idempotentlik, `payments` yozuvlari, sandbox testlari.

**P5 — Seans, buyurtma, kassa**
Check-in (QR/kod), session start/extend/finish, overtime hisobi, menyu va buyurtmalar, stock, bills, split to'lov (deposit + bar_credit + loyalty + naqd), shifts va cash_movements, Socket.IO gateway va barcha eventlar.

**P6 — Admin/Xodim dashboard**
`packages/ui` (Blue tokenlar), admin app skeleti, auth oqimi, role-based routing, Live board, Timeline, Bronlar, Buyurtmalar kanban, POS, Kassa/Smena, Katalog va Menyu CRUD ekranlari, Sozlamalar.

**P7 — Telegram Mini App**
Bot (bildirishnoma shablonlari, deep link), Mini App barcha ekranlari, theme va MainButton integratsiyasi, to'lov oqimi, QR ko'rsatish.

**P8 — Landing**
Next.js sayt, klublar katalogi ISR bilan, web bron oqimi (Mini App bilan bir xil API), SEO, i18n, klub egalari uchun ariza formasi.

**P9 — Hisobotlar va superadmin**
Daromad/band bo'lish/menyu hisobotlari (kunlik, haftalik, stansiya kesimida, peak hours heatmap), Excel eksport, superadmin paneli (klub tasdiqlash, plan, komissiya, global stats).
</task>

<constraints>
- Belgilangan stack va model bo'yicha ish ko'r. Boshqa kutubxona qo'shish kerak bo'lsa — bir qatorda sababini yozib qo'sh.
- Pul hisobi butun sonda (so'm). Float, `parseFloat`, `toFixed` pul ustida ishlatilmaydi.
- Vaqt DB'da UTC. Frontend'da `Asia/Tashkent`. Sana matematikasi `date-fns-tz` bilan.
- Har bir tenant-scoped so'rov RLS orqali filtrlanadi. Qo'lda `where: { club_id }` yozib RLS'ni chetlab o'tma.
- Business logic servislarda, controller faqat validatsiya va marshrutlash. Narx, deposit, cancel policy hisoblari — sof funksiyalar, `packages/types` ichida, ikkala tomon (API va frontend) bitta manbadan foydalanadi.
- Test: narx kalkulyatori, deposit/refund qoidalari, bron to'qnashuvi, to'lov webhook idempotentligi. Boshqa joyda test yozma.
- `any` yo'q. Prisma tiplari va zod inference ishlatiladi.
- Migratsiyalar faqat oldinga. Ishlab chiqilgan migratsiyani tahrirlama.
- Har bosqichda o'sha bosqich fayllarigagina teg. Oldingi bosqich kodini refactor qilish kerak bo'lsa — avval bir qatorda ayt.
- Do what was asked, at the size asked. Oddiy qarorlarni o'zing qabul qil; faqat talqinlar tubdan boshqa natijaga olib borsa so'ra. Yondashuv noto'g'ri deb hisoblasang — bir gapda ayt va baribir so'ralganidek davom et. Vazifani to'liq tugat, lekin undan tashqariga chiqma.
</constraints>

<output>
Har bosqich oxirida:
1. Bir gapda — nima ishlaydigan holga keldi.
2. Yaratilgan/o'zgartirilgan fayllar ro'yxati.
3. Ishga tushirish buyruqlari (agar yangi bo'lsa).
4. Keyingi bosqichga ta'sir qiladigan ochiq savol bo'lsa — maksimum 3 ta punkt.

Ish davomida faqat muhim topilma yoki yo'nalish o'zgarishida yoz. Har bir fayl haqida izoh berma.

Kutilayotgan yakuniy xabar shakli:

```
P3 tugadi — bron yaratish, bekor qilish va slot bandligi to'liq ishlaydi, parallel so'rovlar DB konstreyni bilan bloklanadi.

Yaratildi:
  apps/api/src/bookings/{bookings.controller,bookings.service,availability.service}.ts
  apps/api/src/bookings/jobs/{auto-cancel,no-show,reminder}.processor.ts
  packages/types/src/booking/{deposit,cancel-policy}.ts
  apps/api/test/bookings.e2e-spec.ts
O'zgardi:
  prisma/schema.prisma (bookings.code indeksi)

pnpm --filter api test → 24 passed

Ochiq savol: VIP xonani butun bron qilganda ichidagi stansiyalar alohida bron qilinishi bloklanadimi — hozir bloklanadi deb qildim.
```
</output>

<tone_preference>
Javoblar qisqa va aniq. Ogohlantirish va disklaymerlarni minimallashtir.
</tone_preference>
