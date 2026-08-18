# PlayBron — audit va gap-analiz

> Sana: 2026-08-17 · Commit: `d6f7dbe` · Oxirgi migratsiya: `0031_stations_bot_lookup`
> Metod: statik o'qish (kod o'zgartirilmagan, testlar ishga tushirilmagan —
> lokal muhitda `pytest` o'rnatilmagan, DB ko'tarilmagan).

**Eslatma.** Vazifada `docs/tz-playbron.md` tilga olingan — bunday fayl repoda
yo'q. Maqsadli TZ sifatida BUILD-BRIEF olindi. Agar boshqa, yangiroq TZ bo'lsa —
4-bo'lim natijalari qayta ko'rilishi kerak.

**2026-08-17, hisobotdan keyin:** BUILD-BRIEF `docs/archive/BUILD-BRIEF.md` ga
ko'chirildi (5-bo'lim tavsiyasi bajarildi), `CLAUDE.md` esa shu hisobot asosida
qayta tuzildi. Quyidagi matnda BUILD-BRIEF ga havolalar o'sha arxiv nusxasini
bildiradi.

---

## 0. Qisqacha xulosa

Kod bazasi **kutilganidan ancha sog'lom**. Bu "prototip" emas: RLS
izolyatsiyasi haqiqiy va migratsiyalar ichida o'z-o'zini sinaydi, bron
to'qnashuvi DB konstreyni bilan yopilgan, pul hamma joyda `bigint`, vaqt
zonasi `clubs.timezone` orqali, CI'da 164 ta integratsiya testi haqiqiy
`playbron_app` roli bilan yuradi.

Muammo **poydevorda emas, pul konturida**. Uch daraja — *nima sotildi*
(bron/buyurtma), *qancha pul olindi* (`bookings.paid_amount`), *kassada
qancha bo'lishi kerak* (smena) — uchta har xil, o'zaro bog'lanmagan usulda
hisoblanadi. Natijada hisobot, chek va kassa bir-biriga mos kelmaydi va bu
mos kelmaslikni ushlaydigan birorta test yo'q.

**Tavsiya: 0 dan boshlash EMAS. Gibrid refactor** — poydevor (auth, RLS,
tenancy, bron dvigateli, deploy) saqlanadi, pul qatlami (`payments` +
`bills` + smena bog'lami) qayta yoziladi. Asos 5-bo'limda.

---

## 1. Mavjud holat

### 1.1 Stek (haqiqiy)

| Qatlam | Texnologiya |
|---|---|
| Backend | FastAPI + SQLAlchemy (asosan xom SQL) + Alembic + PostgreSQL 16 + Redis |
| Konsol | `apps/admin` — React 19 + Vite, o'z routeri (`routes.ts`), Zustand |
| Mini App | `apps/miniapp` — React 19 + Vite, Zustand |
| Landing | `apps/landing` — Astro, to'liq statik |
| Umumiy | `packages/ui` (SystemX tokenlar), `packages/api-client` |
| Monorepo | Turborepo + pnpm; `api/` workspace'dan TASHQARIDA |
| Deploy | Render (jonli) + Hetzner VPS konfiguratsiyasi (`deploy/`, hali o'tkazilmagan) |

BUILD-BRIEF'dagi stek (NestJS, Prisma, Fastify, Socket.IO, Next.js, BullMQ,
MinIO, Payme/Click, Eskiz.uz SMS) **amalda qo'llanmagan** — hech biri repoda
yo'q. Bu ongli qaror bo'lgan (`CLAUDE.md` buni qayd etadi), lekin TZ hujjati
yangilanmagan: BUILD-BRIEF hali ham eski stekni buyuradi. Ikki manba
qarama-qarshi.

### 1.2 Hajm

| Qism | Fayl | Qator |
|---|---|---|
| `api/src` | 51 | ~10 440 |
| `api/tests` | 21 | ~5 906 |
| `api/migrations` | 31 | ~7 153 |
| `apps/admin` | 32 | ~10 715 |
| `apps/miniapp` | 22 | ~4 098 |
| `apps/landing` | 29 | ~3 713 |
| `packages/ui` | 22 | ~4 401 |
| `packages/api-client` | 6 | ~2 374 |
| **Jami** | ~214 | **~48 800** |

118 commit, 2026-08-13 → 2026-08-17 (besh kun). Ya'ni bu juda zich ishlangan,
lekin qisqa umr ko'rgan kod — texnik qarz hali "qotib qolmagan".

### 1.3 Migratsiyalar

31 ta, chiziqli zanjir (`0001` → `0031`), tarmoqlanish yo'q, `downgrade()`
qasddan `NotImplementedError`. Ko'pchiligi xom SQL (`op.execute`) — RLS
policy'lari va `SECURITY DEFINER` funksiyalari uchun boshqa yo'l yo'q.

**Kuchli tomon:** bir nechta migratsiya o'z ichida `_self_test()` yuritadi —
masalan `0009` haqiqatan ikkita kesishuvchi bron kiritib ko'radi va
`bookings_no_overlap` uni to'xtatmasa migratsiya yiqiladi. `0010`
`staff_telegram_link_confirm()` ni sinab ko'radi. Bu naqsh kam uchraydi va
qadrli.

**Zaif tomon:** self-testlar `rolsuper OR rolbypassrls` bo'lsa **jimgina
o'tkazib yuboriladi** — ya'ni lokalda hech qachon ishlamaydi.

> **Tuzatish (2026-08-17, hisobotdan keyin).** Bu bo'limning dastlabki
> variantida "`check_render_shape.py` CI'da chaqirilmaydi" deyilgan edi —
> noto'g'ri xulosa. CI'da alohida **`api-render-shape`** job'i bor:
> `NOSUPERUSER CREATEROLE NOCREATEDB NOBYPASSRLS` egasi bilan toza baza
> quradi, `alembic upgrade head` va butun test to'plamini shu yerda
> qayta yuritadi. Skript — o'sha job'ning LOKAL nusxasi (o'zining
> docstring'ida shunday yozilgan), deploy oldidan qo'lda yuritish uchun.
> Ya'ni invariant CI bilan majburlangan; qoplanmagan joy yo'q.

### 1.4 Testlar

164 ta test funksiyasi, hammasi `api/tests/`. CI (`.github/workflows/ci.yml`)
haqiqiy Postgres 16 + Redis 7 bilan, `DATABASE_URL` sifatida `playbron_app`
(NOSUPERUSER) roli bilan yuradi — ya'ni RLS invariantlari haqiqatan
sinaladi. `ruff` + `mypy` ham CI'da.

**Qoplangan:** auth (5 fayl, ~1 200 qator), RLS va policy invariantlari
(~570 qator), bron oqimi (838 qator), POS/buyurtma/chek yopish (648), bot
oqimlari (~700), platforma (506).

**Qoplanmagan — aynan pul turgan joylar:**

| Modul | Test |
|---|---|
| Smena (`finance/shifts.py`, 266 q.) | **0** |
| Xarajatlar (`finance/service.py`) | **0** |
| Hisobot/dashboard (`finance/reports.py`, 360 q.) | **0** |
| Stansiya CRUD | **0** |
| Frontend (hamma app) | **0** — birorta `*.test.*` fayl yo'q |

Sof birlik testi (narx formulasi, deposit qoidasi) umuman yo'q — hamma test
DB'ga tegadi va `RUN_DB_TESTS=1` siz **jimgina skip** bo'ladi. Ya'ni
`pytest -q` yashil chiqishi hech narsani anglatmaydi.

---

## 2. Ma'lumotlar modeli tahlili

### 2.1 Multi-tenancy — **qilingan, va yaxshi qilingan**

Sxema: `organizations` (tenant) → `clubs` → hamma domen jadvali `club_id`
bilan. Foydalanuvchi global (`users`), klubga bog'lanish `memberships`
orqali.

Izolyatsiya **Postgres RLS** bilan:

- 18 ta jadvalda `ENABLE` + `FORCE ROW LEVEL SECURITY`, 80 ta policy.
  `FORCE` — ya'ni jadval egasiga ham tegishli.
- Kontekst `SET LOCAL app.*` GUC'lari orqali (`core/context.py` +
  `core/db.py::session_scope()`), `contextvars` bilan so'rov bo'yicha
  izolyatsiya qilingan. `nestjs-cls` ning to'g'ri ekvivalenti.
- Uch xil DB roli: `playbron_app` (ilova, NOSUPERUSER/NOBYPASSRLS),
  ega roli (`DIRECT_URL`, migratsiya), `playbron_platform` (BYPASSRLS,
  platforma o'qishlari).
- Cross-tenant kerak bo'lgan tor joylar `SECURITY DEFINER` funksiya +
  bir martalik GUC "claim" bilan ochilgan (`app_booking_notify_claim`,
  `app_bot_lookup_claim`, `app_signup_claim`, …) — 29 ta shunday funksiya.
  Ya'ni teshik emas, nomlangan va cheklangan kanal.
- `app_club_role()` `memberships` policy'si ichida chaqirilmaydi (rekursiya
  oldini olish) — `0007` shu uchun bor.

Kodda qo'lda `WHERE club_id` yozilgan joylar bor, lekin ular **RLS o'rniga
emas, ustiga** — defense-in-depth sifatida. Bu qoidaga zid emas.

**Baho: SAQLASH.** Bu loyihaning eng qimmat va eng to'g'ri qismi. Qayta
yozish 2–3 hafta yeydi va natijasi yaxshiroq bo'lmaydi.

**Kichik topilma:** `plans` jadvalida RLS yo'q — bu to'g'ri (global
ma'lumotnoma). `shifts_staff_one_open_uk` indeksi `(staff_id) WHERE
status='open'` — **klub bo'yicha emas, global**. Ikki klubda ishlaydigan
xodim ikkala klubda bir vaqtda smena ocholmaydi. `memberships` esa ko'p
klubni ataylab qo'llab-quvvatlaydi — ziddiyat.

### 2.2 Pul — **saqlash to'g'ri, hisoblash noto'g'ri**

Saqlash bo'yicha da'vo yo'q. Hamma pul ustuni `bigint`, so'm, kasrsiz:
`stations.rate`, `bookings.rate_snapshot`, `bookings.prepaid_amount`,
`bookings.paid_amount`, `products.price`, `orders.total`,
`order_items.price_snapshot`, `expenses.amount`, `shifts.opening_cash`,
`shifts.counted_cash`, `shift_cash_movements.amount`, `plans.price_*`.
`Numeric`/`float` faqat `clubs.lat/lng` da (koordinata — o'rinli).
Musbat/nomanfiy CHECK konstreynlari deyarli hamma joyda bor.

Snapshot naqshi ham to'g'ri: `rate_snapshot`, `price_snapshot`,
`product_name` — narx keyin o'zgarsa eski hujjat o'zgarmaydi.

**Lekin `paid_amount` hech narsa bilan bog'lanmagan.** `pos/service.py::
close_bill()` hisoblangan `total` ni chiqaradi, so'ng xodim yuborgan
ixtiyoriy `paid_amount` ni **tekshirmasdan** yozadi (yagona shart:
`>= 0`). Chegirma, qarz, qisman to'lov tushunchasi yo'q — farq shunchaki
yo'qoladi va hech qayerda ko'rinmaydi.

### 2.3 Sessiya ↔ to'lov ↔ smena bog'liqligi — **eng jiddiy nuqson**

Uchta jadval o'rniga bitta `bookings` qatori uch rolni bajaradi: bron,
seans va chek. `sessions`, `bills`, `payments` jadvallari yo'q.

Bog'lam **FK bilan emas, vaqt oynasi bilan** qurilgan.
`finance/shifts.py::_expected_cash()`:

```sql
SELECT COALESCE(SUM(paid_amount), 0) FROM bookings
 WHERE club_id = :club_id AND closed_by = :staff AND payment_method = 'CASH'
   AND closed_at BETWEEN :opened AND :until
```

Ya'ni "bu smenaning puli" = "shu xodim shu vaqt oralig'ida yopgan bronlar".
`bookings.shift_id` yo'q. Bundan kelib chiqadigan aniq nuqsonlar:

1. **Alohida buyurtma kassaga umuman tushmaydi.** `orders.booking_id`
   nullable — bronsiz sotuv (o'tkinchi mijoz ichimlik oldi) mumkin.
   Bunday buyurtmada `payment_method` ham, `paid_amount` ham **yo'q** —
   `orders` jadvalida to'lov ustuni umuman mavjud emas. Natija: bu pul
   hisobotda **ko'rinadi** (`reports.py` `orders.total` ni qo'shadi), lekin
   smenaning kutilayotgan naqdiga **kirmaydi**. Kassada ortiqcha pul
   chiqadi, `variance` doim musbat.

2. **Naqd xarajat kassadan yechilmaydi.** `expenses` jadvali `shift_id` siz
   va `_expected_cash()` uni umuman o'qimaydi. Xodim naqd pulga suv sotib
   olsa — kassa kamayadi, kutilayotgan summa esa o'zgarmaydi. Xodim buni
   `shift_cash_movements` ga qo'lda yozsa to'g'ri chiqadi, lekin u holda
   bir xarajat **ikki joyda** turadi va hisobotda ikki marta hisoblanishi
   mumkin. Qaysi biri to'g'ri — hech qayerda belgilanmagan.

3. **Smenasiz yopilgan hisob yetimda qoladi.** `close_bill()` xodimda ochiq
   smena bor-yo'qligini tekshirmaydi. Smenadan tashqarida yopilgan chek
   hech qaysi smenaga tegishli bo'lmaydi va kassa hisobidan butunlay
   tushib qoladi.

4. **Smena yopilgandan keyingi tuzatish yo'qoladi.** Yopilgan smena uchun
   oyna `closed_at` bilan chegaralanadi — kechikkan yozuv hech qayerga
   tushmaydi.

5. **Hisobot va kassa har xil pulni sanaydi.** `reports.py::
   _revenue_expense_for_range()` o'yin daromadini
   `SUM(rate_snapshot * hours)` sifatida, **`lower(period)` bo'yicha**,
   `status='CONFIRMED'` bo'lgan hamma bron uchun hisoblaydi. Ya'ni:
   - Mijoz kelmagan, chek yopilmagan bron ham "bugungi daromad" da turadi;
   - Chegirma bilan yopilgan chek hisobotda to'liq narxda turadi;
   - Uzaytirilgan seans `hours` orqali to'g'ri chiqadi, lekin faqat
     `extend_booking()` chaqirilgan bo'lsa.

   Kassa esa `paid_amount` ni sanaydi. Ikkalasi bir xil son bermaydi va
   qaysi biri "haqiqiy daromad" ekani hujjatlashtirilmagan.

6. **To'lov tarixi yo'q.** `payment_method` bitta ustun — split to'lov
   (yarmi naqd, yarmi o'tkazma), qaytarim, depozit hisobga olish
   modellashtirilmagan. `prepaid_amount` bor, lekin `0009` izohiga ko'ra
   hamma yozuvda 0.

7. **O'tkazma cheki oqimi jadvalsiz qurilgan.** `payment_proof_status`
   (`PENDING`/`SUBMITTED`/`CONFIRMED`) `bookings` ustunida. Bitta bronga
   bitta chek — takroriy urinish, rad etish sababi, kim tasdiqlagani
   saqlanmaydi.

**Baho: QAYTA YOZISH.** Bu ustunlar to'plami emas, yetishmayotgan
entity — `payments`.

### 2.4 Bron kesishuvi — **to'g'ri hal qilingan**

```sql
ALTER TABLE bookings ADD CONSTRAINT bookings_no_overlap
  EXCLUDE USING gist (station_id WITH =, period WITH &&)
  WHERE (status IN ('PENDING', 'CONFIRMED'))
```

- `btree_gist` kengaytmasi `0009` da o'rnatiladi.
- `period` — `tstzrange`, alohida `starts_at`/`ends_at` emas. To'g'ri
  tanlov: EXCLUDE aynan shuni talab qiladi.
- `23P01` → `core/errors.py` global handler → `409 SLOT_TAKEN`.
- `extend_booking()` ataylab qo'lda tekshirmaydi — `UPDATE` ham konstreynga
  tushadi. To'g'ri fikr.
- Migratsiyaning o'zi ikkita kesishuvchi bron kiritib sinab ko'radi
  (`_assert_overlap_is_rejected()`), aks holda deploy to'xtaydi.
- Vaqt zonasi: kun oynasi `ZoneInfo(clubs.timezone)` orqali
  (`_local_day_window()`), frontend `Intl.DateTimeFormat({timeZone})` orqali
  (`miniapp/src/lib/slots.ts`). Ilgari mahalliy zonaga tayanish "yolg'on
  band" xatosini bergan — tuzatilgan.

Bu qismda tuzatiladigan narsa yo'q. Ikkita chekka holat bor — **ikkalasi ham
2026-08-17 da tuzatildi**, quyida asl tavsif va tuzatish:

- **Ish vaqti server tomonda tekshirilmaydi.** `_validate_window()` faqat
  davomiylik (1–6 soat), o'tmish (2 daq. grace) va 14 kun oldinga
  cheklaydi. `clubs.opens_at_min`/`closes_at_min` **umuman qaralmaydi** —
  bu filtr faqat mijoz brauzerida (`slots.ts`). API'ga to'g'ridan-to'g'ri
  murojaat qilib klub yopiq vaqtga bron qilsa bo'ladi.
  → **Tuzatildi:** `fits_opening_hours()` sof funksiyasi qo'shildi
  (yarim tundan o'tuvchi oynani ham to'g'ri hisoblaydi) va mijoz yo'lida
  chaqiriladi → `422 OUTSIDE_OPENING_HOURS`. Xodim yo'li ATAYLAB
  cheklanmagan. Qoplama — `tests/test_booking_window.py` (8 test, DB'siz).
- **Uzaytirish `hours` CHECK'ini buzishi mumkin.** `MAX_HOURS = 6`,
  `EXTEND_MAX_HOURS = 3`, DB'da esa `hours <= 12`. 6 soatlik bronni uch
  marta uzaytirsa `hours = 15` → `23514`, u `errors.py` da ishlanmagan
  (faqat `23P01` va `23505` bor) → xodimga 500.
  → **Tuzatildi:** `MAX_TOTAL_HOURS = 12` servis qatlamida tekshiriladi
  (`409 TOTAL_HOURS_EXCEEDED`), qo'shimcha ravishda `errors.py` ga
  `23514` → `422` va `23503` → `409` xaritasi qo'shildi, ya'ni endi
  HECH BIR konstreynt buzilishi 500 bermaydi. Qoplama —
  `test_repeated_extends_stop_at_db_hours_limit`.

### 2.5 Modelning boshqa chegaralari

| Nuqson | Ta'sir |
|---|---|
| `bookings.hours` — **butun son** | Yarim soatlik bron mumkin emas. Mijoz UI'da `SLOT_STEP = 30` — boshlanish 30 daq. tarmoqda, davomiylik esa faqat butun soat. TZ `slot_minutes = 30` va `min_booking_minutes = 60` talab qiladi |
| Tarif yo'q — narx `stations.rate` | Vaqt/kun bo'yicha narx (kechqurun qimmat, ish kuni arzon) mumkin emas. TZ'dagi `tariffs` + priority algoritmi butunlay yo'q |
| Xona yo'q — `stations.room_label` erkin matn | VIP xonani butunligicha bron qilish, xona bo'yicha filtr/hisobot yo'q |
| `clubs` da sozlama ustunlari yo'q | `deposit_percent`, `cancel_policy`, `max_advance_days`, `overtime_grace` — hammasi kodda konstanta (`MAX_ADVANCE_DAYS = 14`, `PREPAY_HOURS = 1`). Klub o'zi sozlay olmaydi, ya'ni SaaS sifatida bir xil qolipdagi klublargagina yaraydi |
| Seans holati yo'q | Check-in, haqiqiy boshlanish/tugash, pauza, overtime yo'q. "Live board" bandlikni `period` dan hisoblaydi — ya'ni rejadan, faktdan emas |
| `console_type` CHECK ro'yxati kodda qotirilgan | Yangi konsol → yangi migratsiya |
| Fon vazifalari yo'q | `asyncio.create_task`, scheduler, navbat — hech biri yo'q. Ya'ni: to'lanmagan bronni avto-bekor qilish, no-show belgilash, eslatma yuborish — **hech biri ishlamaydi**. Redis faqat replay himoyasi va bot nonce'lari uchun |
| Realtime yo'q | WebSocket/SSE yo'q, `live-board.tsx` 20 soniyalik `setInterval` polling |

---

## 3. TZ (BUILD-BRIEF) vs mavjud kod

### 3.1 Jadvallar

| TZ jadvali | Holat | Izoh |
|---|---|---|
| `clubs` | ✅ bor | `slug`, `photos[]`, `working_hours` jsonb, `commission_rate` yo'q |
| `club_settings` | ❌ yo'q | Sozlamalar kodda konstanta |
| `users` | ✅ bor | Kengaytirilgan: `kind` diskriminatori bilan "ikki dunyo" |
| `club_members` | ✅ `memberships` | Rollar `OWNER/ADMIN/STAFF` — TZ'da `CLUB_ADMIN/STAFF` |
| `rooms` | ❌ yo'q | `stations.room_label` matn sifatida |
| `stations` | ⚠️ soddalashtirilgan | `tv_inches`, `controllers_count`, `has_vr`, live `status` yo'q |
| `tariffs` | ❌ yo'q | Narx = `stations.rate`, flat |
| `packages` | ❌ yo'q | |
| `bookings` | ⚠️ boshqacha | `code`(QR), `players_count`, `room_id`, `package_id`, `deposit_*` yo'q; `CHECKED_IN`/`COMPLETED`/`NO_SHOW` holatlari yo'q |
| `sessions` | ❌ yo'q | `bookings` bilan qo'shib yuborilgan |
| `menu_categories` | ❌ yo'q | `products.category` matn |
| `menu_items` | ✅ `products` | `cost_price` yo'q → marja hisoblab bo'lmaydi (ochiq ish #21) |
| `orders` / `order_items` | ✅ bor | `session_id` o'rniga `booking_id`; to'lov ustunlari yo'q |
| `bills` | ❌ yo'q | `bookings` ustunlariga singdirilgan, `discount_amount` yo'q |
| `payments` | ❌ yo'q | **Eng katta yetishmovchilik** |
| `shifts` | ✅ bor | `expected_cash`/`difference` saqlanmaydi, har safar qayta hisoblanadi |
| `cash_movements` | ✅ `shift_cash_movements` | |
| `wallets` (bar_credit) | ❌ yo'q | TZ'ning asosiy "win-win" mexanikasi ishlamaydi |
| `loyalty_*` | ❌ yo'q | Miniapp'da bonus **mock konstantadan** ko'rsatiladi |
| `promo_codes` | ❌ yo'q | |
| `reviews` | ❌ yo'q | |
| `notifications` | ❌ yo'q | Telegram to'g'ridan-to'g'ri yuboriladi, jurnal yo'q |
| `audit_log` | ✅ bor | |
| — | ➕ `expenses` | TZ'da yo'q, kod'da bor (foydali qo'shimcha) |
| — | ➕ `organizations`, `plans`, `platform_payments` | SaaS qatlami — TZ buni yetarli qamramagan, kod to'g'ri qilgan |
| — | ➕ `staff_credentials/devices/invites/recovery_codes`, `auth_events`, `staff_telegram` | Auth qayta loyihalangan (`docs/05-auth-redesign.md`) |

### 3.2 Biznes qoidalari (TZ `<business_rules>`)

| # | Qoida | Holat |
|---|---|---|
| 1 | Deposit formulasi | ❌ `prepayAmount = rate × 1` — soddalashtirilgan, faqat frontend'da |
| 2 | To'lanmagan bron avto-bekor | ❌ fon vazifasi yo'q |
| 3 | Bekor qilish siyosati + bar_credit | ❌ yo'q; bekor qilish shunchaki status |
| 4 | Check-in (QR/kod) | ❌ yo'q |
| 5 | No-show | ❌ yo'q (`blacklist.tsx` ekrani bor, backend yo'q) |
| 6 | Overtime | ❌ yo'q; faqat qo'lda `extend` |
| 7 | Buyurtma faqat aktiv seansda | ⚠️ qisman — bronsiz buyurtma ham mumkin |
| 8 | Stock | ✅ bor (`0028`), `CANCELLED` da qaytadi, testi bor |
| 9 | Bill yopish formulasi | ❌ chegirma/depozit/bar_credit/loyalty yo'q |
| 10 | Loyalty | ❌ yo'q (miniapp'da mock) |
| 11 | Smena yopilmay yangisi ochilmaydi | ✅ qisman unikal indeks bilan (lekin klublararo) |
| 12 | Slot tarmog'i | ⚠️ faqat frontend'da |

### 3.3 Boshqa TZ talablari

| Talab | Holat |
|---|---|
| Payme / Click | ❌ yo'q. O'rniga: Telegram'ga chek rasmini yuborish + xodim ko'zi bilan tasdiqlash |
| Eskiz.uz SMS OTP | ❌ yo'q. Mijoz kirishi faqat Telegram orqali |
| Socket.IO realtime | ❌ yo'q → polling |
| Idempotency-Key | ❌ yo'q — bron yaratishda takroriy so'rov himoyasi yo'q |
| Cursor pagination | ❌ yo'q — ro'yxatlar to'liq qaytadi |
| OpenAPI | ⚠️ FastAPI avtomatik beradi, zod'dan generatsiya yo'q |
| i18n uz/ru/en | ⚠️ konsol: bor (`i18n.ts`, 217 q.). **Miniapp: yo'q** — matn to'g'ridan-to'g'ri kodda. Landing: uz/ru bor, en yo'q |
| Excel eksport | ❌ yo'q |
| Superadmin panel | ✅ bor va yaxshi ishlangan |

### 3.4 "Bor-u noto'g'ri" — eng muhim ro'yxat

1. **Daromad hisoboti** (`reports.py`) — rejalashtirilgan summani sanaydi,
   olingan pulni emas.
2. **Smena kassasi** (`shifts.py`) — bronsiz buyurtmani va naqd xarajatni
   ko'rmaydi.
3. **Chek yopish** (`close_bill`) — `paid_amount` ni tekshirmaydi.
4. **Miniapp hisobi** (`lib/bill.ts`) — `BONUS_POINTS`, `POINT_RATE`,
   `MENU` **mock'dan** olinadi va backend'dagi formuladan farq qiladi.
   `CLAUDE.md` ning "narx/hisob mantig'i bitta manbada" qoidasi buzilgan.
5. **Ish vaqti tekshiruvi** — faqat brauzerda.
6. **`blacklist.tsx`** — ekran bor, ma'lumot manbai yo'q (ataylab bo'shatilgan).
7. **`mock/club.ts`** (318 q.) — `TARIFFS_INIT`, `ROOMS_INIT`, `DEVICES_INIT`,
   `STAFF_INIT`, `PRODUCTS_INIT` — backend'da ekvivalenti yo'q entity'larning
   soxta ma'lumoti. Ochiq ish #23.

---

## 4. Modul bo'yicha qaror

| Modul | Qaror | Asos |
|---|---|---|
| **RLS / tenancy / GUC konteksti** (`core/db.py`, `core/context.py`, 80 policy) | **SAQLASH** | To'g'ri, sinovdan o'tgan, qayta yozish qimmat va foydasiz. Faqat yangi jadvallar uchun naqshni davom ettirish kerak |
| **Auth (ikki dunyo, refresh rotatsiya, staff provisioning)** | **SAQLASH** | 5 test fayli, ~1 200 qator qoplama. `users.kind` diskriminatori DB darajasida majburlangan. Bu qismga tegish — regressiya xavfi |
| **Bron dvigateli** (`bookings/service.py`) | **REFACTOR** | Yadro (EXCLUDE, tstzrange, timezone) to'g'ri. Qo'shiladi: server tomonda ish vaqti tekshiruvi, `23514` ishlash, `hours` → `duration_minutes`, holat mashinasi (`CHECKED_IN`/`COMPLETED`/`NO_SHOW`) |
| **Narx / tarif** | **QAYTA YOZISH** (yo'qdan qurish) | Hozir `stations.rate` flat. Tarif jadvali + interval bo'lish algoritmi + sof funksiya testlari kerak. Mavjud kodning bu yerda saqlanadigan qismi yo'q |
| **To'lov qatlami** | **QAYTA YOZISH** | `payments` + `bills` entity'lari yaratiladi, `bookings.paid_amount/payment_method/closed_*` ulardan hosila bo'ladi. Migratsiya bilan mavjud yozuvlar ko'chiriladi |
| **Smena / kassa** (`finance/shifts.py`) | **REFACTOR** (`payments` dan keyin) | Struktura to'g'ri (ochish/yopish/harakat/farq). Faqat manbani almashtirish kerak: vaqt oynasi → `payments.shift_id`. Kod hajmi kichik (266 q.), qayta yozishga arzimaydi |
| **Xarajatlar** (`finance/service.py`) | **REFACTOR** | `shift_id` va `payment_method` (naqd/bank) qo'shiladi, keyin kassa hisobiga ulanadi |
| **Hisobotlar** (`finance/reports.py`) | **QAYTA YOZISH** | Manba noto'g'ri (rejalashtirilgan summa). `payments` paydo bo'lgach mantiq butunlay boshqacha bo'ladi — 360 qatorning ozi qoladi |
| **POS / buyurtma / stock** (`pos/service.py`) | **REFACTOR** | Buyurtma, stock, bekor qilish mantig'i sog'lom va testlangan. `close_bill()` ajratib olinadi va `payments` ga o'tkaziladi; bronsiz buyurtmaga to'lov yozuvi qo'shiladi |
| **Platforma / superadmin** (`platform/*`) | **SAQLASH** | 506 qator test, mustaqil kontur, pul konturiga kam bog'liq |
| **Telegram botlar** (`bot/*`, `auth/telegram*`) | **REFACTOR** | Mantiq to'g'ri, lekin `docs/HOLAT.md` da hal qilinmagan nosozlik bor (bot `/start` ga javob bermaydi). Avval sabab topilsin, keyin qaror |
| **`packages/api-client`** | **SAQLASH** | 1 883 qator tipli endpoint qatlami — qayta yozish bekor mehnat. Model o'zgargani sari birga o'zgaradi |
| **`packages/ui` + tokenlar** | **SAQLASH** | Tegilmaydi ro'yxatida. Sifatli |
| **`apps/admin`** | **REFACTOR** | Ekranlar real API'ga ulangan. `mock/club.ts` olib tashlanadi, `blacklist.tsx`/`parts.tsx` backend paydo bo'lgach to'ldiriladi. Router va state — qoladi |
| **`apps/miniapp`** | **REFACTOR** | Bron oqimi real. Tuzatiladi: `lib/bill.ts` mock'dan uziladi va server hisobiga o'tadi, i18n qo'shiladi, `lib/slots.ts` dagi bandlik mantig'i server `availability` endpoint'iga ko'chiriladi |
| **`apps/landing`** | **SAQLASH** | Statik, mustaqil, ishlaydi |
| **Migratsiyalar** | **SAQLASH** (faqat oldinga) | Zanjir toza. Yangi ishlar `0032+` bilan |
| **Fon vazifalari (avto-bekor, no-show, eslatma)** | **YANGIDAN QURISH** | Hozir umuman yo'q. `arq`/`APScheduler` yoki oddiy `asyncio` looper — qaror kerak |
| **Realtime** | **KECHIKTIRISH** | Polling 20 s hozircha yetarli. SSE eng arzon yechim, Socket.IO shart emas |

---

## 5. Umumiy tavsiya

### Gibrid refactor. 0 dan boshlash asossiz.

**Nega 0 dan emas:**

1. Eng qimmat va eng xato qiladigan qism — **RLS izolyatsiyasi** — allaqachon
   to'g'ri va sinalgan. `docs/HOLAT.md` §4.1 dagi "qimmatga tushgan saboqlar"
   ro'yxati (FORCE ega'ga ham tegishli, policy ichidagi JOIN, UPDATE ning
   SELECT policy'siga bog'liqligi, GRANT ≠ RLS) — bularning har biri qayta
   qurishda **yana** to'lanadigan narx.
2. Auth ikki dunyoli qilib qayta loyihalangan, DB darajasida majburlangan,
   ~1 200 qator test bilan qoplangan.
3. Bron to'qnashuvi va vaqt zonasi — TZ'dagi eng nozik ikki nuqta — to'g'ri.
4. Nuqsonlar **lokalizatsiyalangan**: pul konturi (`payments` yo'qligi) va
   yetishmayotgan entity'lar (tarif, xona, sessiya). Bu arxitektura xatosi
   emas, qurilmagan qism. Kod tuzilishi (`modules/*/service.py`) ularni
   qo'shishga to'sqinlik qilmaydi.
5. Yosh: 5 kunlik kod, 118 commit. Qarz qotib qolmagan.

**Nega shunchaki "davom etish" ham yetarli emas:** hozirgi pul konturi
ustiga loyalty, depozit, onlayn to'lov qo'yilsa — nomuvofiqlik ko'payadi.
`payments` ni keyin kiritish har safar qimmatlashadi.

### Tartib

**0-bosqich — to'xtatuvchi ishlar (1–2 kun)**

- ~~`extend` → `23514`; server tomonda ish vaqti tekshiruvi~~ — **bajarildi
  2026-08-17** (§2.4 dagi izohlar).
- ~~`check_render_shape.py` ni CI'ga qo'shish~~ — **kerak emas**, CI'da
  `api-render-shape` job'i o'sha ishni bajaradi (§1.3 tuzatishi).
- Telegram bot nosozligini yopish (`docs/HOLAT.md` §2) — mijoz oqimi
  butunlay shunga bog'liq. **Yagona qolgan to'xtatuvchi ish.**

**1-bosqich — pul konturi — BAJARILDI (2026-08-18, `0032_payments`)**

`payments` jadvali (RLS + GRANT + self-test + backfill), `bookings.discount_amount`/
`debt_amount`, `expenses.shift_id`/`method`. `close_bill()` va bronsiz sotuv
`payments` yozadi va naqd uchun ochiq smenani talab qiladi; `_expected_cash()`
va `reports.py` shundan hisoblaydi (`planned_*` / `received_*` alohida).
Qoplama — `tests/test_money.py` (12 test). Quyidagi reja tarix uchun qoldirildi:

- `payments` jadvali: `club_id`, `shift_id`, `booking_id?`, `order_id?`,
  `kind` (FINAL/DEPOSIT/REFUND), `method`, `amount`, `created_by`, `created_at`.
  RLS + policy o'sha migratsiyada.
- `bills` (yoki `bookings` ustunlarini `bills` ga ko'chirish) —
  `discount_amount` bilan.
- `expenses.shift_id` + `expenses.method`.
- `close_bill()` → `payments` yozadi, `paid_amount ≠ total` bo'lsa aniq
  `discount` yoki `debt` sifatida yoziladi.
- Bronsiz buyurtma ham `payments` yozuvi oladi.
- `_expected_cash()` → `SUM(payments) WHERE shift_id = :id AND method='CASH'`
  − naqd xarajatlar.
- `reports.py` → `payments` asosida qayta yoziladi.
- **Testlar birinchi**: smena farqi, chegirmali chek, bronsiz sotuv, naqd
  xarajat — hozir 0 ta test bor joyda.

**2-bosqich — yetishmayotgan entity'lar (~1 hafta)**

`rooms`, `tariffs` (+ sof narx funksiyasi va uning testlari),
`club_settings` (konstantalarni DB'ga ko'chirish), `menu_categories`,
`products.cost_price`.

**3-bosqich — seans hayotiy sikli**

`CHECKED_IN`/`COMPLETED`/`NO_SHOW`, haqiqiy `started_at`/`ended_at`,
overtime, fon vazifalari (avto-bekor, no-show, eslatma).

**4-bosqich — TZ'ning qolgan qismi**

Onlayn to'lov (Payme/Click), `wallets`/bar_credit, loyalty, promokod,
sharhlar. Bularning hammasi `payments` ustiga qurilgani uchun 1-bosqichdan
keyin arzon.

**Doimiy:** har bosqichda frontend'ning mos qismi mock'dan uziladi;
miniapp i18n; birlik testlari uchun `pytest` ni DB'siz ishlaydigan qilib
ajratish.

### Hozirdanoq belgilash kerak bo'lgan ikki qaror

1. **BUILD-BRIEF.md eskirgan.** U hali ham NestJS/Prisma/Payme/Socket.IO ni
   buyuradi. Yo yangilanadi, yo "tarixiy" deb belgilanadi — aks holda har
   yangi sessiyada chalg'itadi (`CLAUDE.md` bilan aynan shu bo'lgan).
2. **"Daromad" ta'rifi.** Rejalashtirilgan (accrual) mi, olingan pul
   (cash) mi — ikkalasi ham kerak bo'lsa, hisobotda ikki alohida ko'rsatkich
   bo'lishi va shunday nomlanishi shart. Hozir bittasi ikkinchisining
   o'rnida turibdi.
