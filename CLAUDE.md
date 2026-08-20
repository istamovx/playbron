# PlayBron — operatsion shartnoma

## Loyiha

PlayStation klublari uchun multi-tenant bron + kassa SaaS, O'zbekiston bozori.
Uch yuza: mijoz (Telegram Mini App), xodim va klub egasi (konsol), platforma egasi (superadmin).
Stek: FastAPI + SQLAlchemy (asosan xom SQL) + Alembic + PostgreSQL 16 + Redis; React 19 + Vite; Astro; Turborepo + pnpm.
`api/` pnpm workspace'dan TASHQARIDA — `pnpm` va `turbo` buyruqlari unga yetmaydi.
Jonli: Render. Hetzner VPS konfiguratsiyasi tayyor, DNS hali ko'chirilmagan.

## Hujjatlar ierarxiyasi

Ziddiyatda yuqoridagi g'olib. Pastdagini yuqoridagiga moslash uchun tuzatiladi.

1. `CLAUDE.md` — invariantlar. Bu fayl.
2. `docs/HOLAT.md` — hozirgi holat, ochiq ishlar, qimmatga tushgan saboqlar.
3. `docs/audit-report.md` — 2026-08-17 gap-analiz: modul qarorlari va bosqichlar tartibi.
4. Modul spetsifikatsiyalari — `docs/01-architecture.md`, `03-entitlements.md`, `04-deploy-render.md`, `05-auth-redesign.md`, `06-super-admin.md`, `07-patterns.md`, `DESIGN-HANDOFF.md`.
5. `docs/archive/**` — tarixiy. Qaror manbai sifatida ISHLATILMAYDI, havola berilmaydi.

Yangi qurilmada yoki uzoq tanaffusdan keyin ish `docs/HOLAT.md` dan boshlanadi.

## Komandalar

```bash
docker compose up -d                       # postgres, redis, minio
pnpm dev                                   # admin + miniapp + landing

cd api
python -m alembic upgrade head             # migratsiya
RUN_DB_TESTS=1 python -m pytest tests/ -q  # DB testlari; usiz JIMGINA skip
python -m ruff check . && python -m mypy src/
python scripts/check_render_shape.py       # migratsiya qo'shilgach MAJBURIY

cd ..
pnpm --filter admin exec tsc --noEmit
pnpm --filter admin exec eslint src
```

## Arxitektura xaritasi

| Papka | Nima |
|---|---|
| `api/src/playbron/core/` | DB sessiya + GUC, kontekst, xatolar, audit, parol, Telegram API, ratelimit |
| `api/src/playbron/modules/<m>/router.py` | HTTP: validatsiya, guard, marshrutlash |
| `api/src/playbron/modules/<m>/service.py` | Biznes mantiq va SQL |
| `api/src/playbron/models.py` | FAQAT 1-faza jadvallari (identity, tenancy, sessiya, tarif). Domen jadvallari ORM'da yo'q — xom SQL bilan ishlanadi |
| `api/migrations/versions/` | Alembic; RLS policy va `SECURITY DEFINER` funksiyalari shu yerda |
| `apps/admin/` | Konsol: xodim + klub egasi + superadmin, bitta SPA |
| `apps/miniapp/` | Mijoz Telegram Mini App |
| `apps/landing/` | Marketing sayti, Astro, statik |
| `packages/ui/` | SystemX dizayn tizimi; manba `docs/designs/_ds/` |
| `packages/api-client/` | Tipli API klient va DTO — frontend backendga faqat shu orqali murojaat qiladi |
| `packages/config/` | eslint va tsconfig presetlari |
| `deploy/` | Hetzner VPS + zaxira |

Modullar: `auth`, `bookings`, `bot`, `finance`, `platform`, `pos`, `staff`, `users`.

## Domen glossariyi

Kodda ishlatiladigan nom — chapda. Boshqa nom yozilmaydi.

| Tushuncha | Kodda |
|---|---|
| Tenant | `organizations` |
| Klub | `clubs` — hamma domen jadvali `club_id` bilan |
| Klub roli | `memberships.role` ∈ `OWNER` \| `ADMIN` \| `STAFF` |
| Platforma egasi | `super_admins` jadvali (rol emas, alohida jadval) |
| Mijoz | `users.kind = 'customer'`, `telegram_id` bilan tanaladi |
| Xodim identiteti | `users.kind = 'staff'`, `login` bilan tanaladi; Telegram `staff_telegram` da |
| O'yin joyi | `stations` (`code`, `console_type`, `rate`, `room_label`) |
| Bron = seans = chek | `bookings` — bitta qator uch rolni bajaradi; `sessions`/`bills` jadvallari YO'Q |
| To'lov | `payments` — har bir pul harakati bitta qator, `shift_id` FK bilan |
| To'lov turi | `payments.kind` ∈ `FINAL` \| `REFUND` |
| Hisob farqi | `bookings.discount_amount` (chegirma), `debt_amount` (qarz), `tip_amount` (qaytimsiz ortiqcha) |
| Bandlik oynasi | `bookings.period` (`tstzrange`) |
| Bar buyurtmasi | `orders` + `order_items`; menyu — `products` |
| Smena | `shifts` + `shift_cash_movements` |
| Xarajat | `expenses` |
| Bron manbai | `bookings.source` ∈ `MINIAPP` \| `STAFF` |
| Bron holati | `bookings.status` ∈ `PENDING` \| `CONFIRMED` \| `CANCELLED` |
| To'lov turi | `bookings.payment_method` ∈ `CASH` \| `TRANSFER` |

`CLUB_ADMIN`, `CUSTOMER`, `sessions`, `bills`, `rooms`, `tariffs`, `menu_items` —
bu nomlar kodda YO'Q. Arxivdagi hujjatlarda uchraydi, ishlatilmaydi.

---

# INVARIANTLAR — buzilmaydi

## Pul

- Pul ustuni `bigint`, so'm, kasrsiz. `numeric`, `float`, `double precision` pul uchun ishlatilmaydi.
- Pul JSON'da butun son sifatida qaytadi. Kasr yoki satr qaytaradigan endpoint merge qilinmaydi.
- Har bir pul ustuni `>= 0` yoki `> 0` CHECK konstreyni bilan yoziladi.
- Hujjatga tushgan narx snapshot ustuniga yoziladi (`rate_snapshot`, `price_snapshot`, `product_name`). Yopilgan hujjat narxini joriy jadvaldan JOIN bilan oladigan kod merge qilinmaydi.
- Narx va hisob formulasi bitta manbada — backend `modules/*/service.py`. Frontend formulani takrorlamaydi, server bergan summani ko'rsatadi.
- Naqd pul harakatining har bir manbai smenaga bog'lanadi. Smenaga bog'lanmagan yangi naqd yozuv merge qilinmaydi.
- Yopilgan smenaning hisobiga ta'sir qiladigan yozuv keyin o'zgartirilmaydi — `expected_cash` har o'qishda qayta hisoblanadi va tuzatish audit jurnalidagi farq bilan ziddiyatga tushardi.
- Hisoblangan `total` bilan olingan summa farqi sababi bilan birga yoziladi: kam bo'lsa `DISCOUNT` yoki `DEBT`, ko'p bo'lsa `TIP`. Sababsiz farqni qabul qiladigan kod merge qilinmaydi.
- Pul yozuvini bekor qilish uni O'CHIRMAYDI — teskari `REFUND` yozuvi qo'shiladi.
- Hisobot maydoni nomida rejalashtirilgan va olingan summa ajratiladi (`planned_*` / `received_*`). Ikkalasini bitta "daromad" nomi ostida berish merge qilinmaydi.
- Pul yoki sozlamaga tegadigan har amal `core/audit.py::log_action()` yozadi.

## Vaqt

- DB'da `timestamptz`, UTC. Naive `datetime` yozilmaydi.
- Bandlik oralig'i `tstzrange` ustunida saqlanadi, alohida `starts_at`/`ends_at` juftligida emas.
- Kalendar hisoblari `clubs.timezone` orqali: backend `zoneinfo.ZoneInfo`, frontend `Intl.DateTimeFormat({ timeZone })`.
- Server yoki brauzer mahalliy zonasiga tayanuvchi chaqiruv ishlatilmaydi: `datetime.now()` zonasiz, `date.today()`, `Date.getHours()`, `Date.setHours()`. `datetime.now(UTC)` ishlatiladi.
- `date-fns-tz` qo'shilmaydi — loyihada o'rnatilmagan, `Intl` yetarli.

## RLS va migratsiya

- Tenant-scoped jadvalda `club_id` ustuni bo'ladi; bolalar jadvalida ham takrorlanadi.
- Yangi tenant-scoped jadval o'sha migratsiyada `ENABLE` + `FORCE ROW LEVEL SECURITY`, policy va `GRANT` oladi. Uchtasidan biri yetishsa merge qilinmaydi.
- Filtrlash RLS orqali. Qo'lda `WHERE club_id` faqat RLS USTIGA qo'shimcha qatlam sifatida yoziladi, uning o'rniga emas.
- Cross-tenant o'qish `SECURITY DEFINER` funksiya + nomlangan GUC claim orqali ochiladi. Yangi `BYPASSRLS` roli qo'shilmaydi.
- Ulanish rollari: ilova `playbron_app` (`DATABASE_URL`), migratsiya ega roli (`DIRECT_URL`), platforma `playbron_platform` (`PLATFORM_DATABASE_URL`).
- Policy ichida JOIN yoki subquery bo'lsa — o'sha jadval ham GUC'ni biladi.
- Yangi so'rov mavjud jadvalni O'QISHNI boshlasa — o'sha jadvalning policy'si CHAQIRUVCHI rolni qamrab olishi tekshiriladi. Qamramasa `SELECT` xato bermaydi, JIMGINA 0 qator qaytaradi va hisob noto'g'ri chiqadi.
- `UPDATE` policy'si yozilganda `SELECT` policy'si ham yoziladi: Postgres qatorni topish bosqichida SELECT policy'sini qo'llaydi.
- `app_club_role()` `memberships` policy'lari ichida chaqirilmaydi — rekursiya. `app.club_role` GUC ishlatiladi.
- Migratsiya invariant yozsa — o'sha migratsiyada uni buzishga urinuvchi self-test ham yoziladi.
- Migratsiyalar faqat oldinga. `downgrade()` → `NotImplementedError`. Mavjud migratsiya tahrirlanmaydi.
- Migratsiya qo'shilgach `python api/scripts/check_render_shape.py` yuritiladi va natijasi javobda keltiriladi.

## Testlar

- Pul mantiqi o'zgarsa test bilan birga o'zgaradi. Testsiz pul o'zgarishi merge qilinmaydi.
- Sof hisob funksiyasi (narx, farq, deposit) DB'siz test bilan qoplanadi.
- Yangi endpoint uchun uchta test yoziladi: amal ishlaydi, boshqa klub ko'rmaydi, yetarli roli yo'q xodim `403` oladi.
- DB testlari `RUN_DB_TESTS=1` bilan yuritiladi. `RUN_DB_TESTS` siz olingan yashil `pytest` natijasi tasdiq sifatida keltirilmaydi.
- Test fixture'i xom yozganda `conftest.py::rls_bypass()` ishlatiladi va `NO FORCE` `finally` da qaytariladi.
- CI qizil bo'lsa merge qilinmaydi.

## Xatolar

- Har bir xato javobida barqaror `code` bo'ladi. Faqat matnli xato merge qilinmaydi.
- Biznes xatosi `core/errors.py::AppError(matn, code=...)` orqali chiqariladi. Router'da `HTTPException` yozilmaydi.
- Postgres sqlstate → HTTP xaritasi `core/errors.py` da: `23P01` → `409 SLOT_TAKEN`, `23505` → `409`, `23514` → `422`, `23503` → `409`.
- Yangi konstreynt qo'shilsa sqlstate xaritasi ham to'ldiriladi. Foydalanuvchiga 500 chiqaradigan konstreynt merge qilinmaydi.
- Bron to'qnashuvi ilova qatlamida emas, `bookings_no_overlap` EXCLUDE konstreyni bilan to'xtatiladi.
- Muvaffaqiyat xabari amal natijasi DB'da tasdiqlangandan keyin yuboriladi. Redis yoki keshdagi holatga qarab "bajarildi" deyilmaydi.

## Frontend

- Rang, spacing, typography faqat dizayn tokenlari orqali. Hardcode qiymat yo'q.
- `any` yo'q.
- Foydalanuvchiga ko'rinadigan matn i18n resursidan (uz/ru/en). Komponentda matn literali yo'q.
- Backendga murojaat faqat `packages/api-client` orqali. Ekranda `fetch` yozilmaydi.
- Yangi ekran mock ma'lumot bilan merge qilinmaydi. Backend hali yo'q bo'lsa — bo'sh holat ko'rsatiladi.
- Bandlik, narx yoki hisob mantig'i frontendga ko'chirilmaydi — server endpoint'i so'raladi.

---

## Naqshlar

Shablonlar: `docs/07-patterns.md`.

**Yangi tenant-scoped jadval** — bitta migratsiyada:
1. Jadval + `club_id` + CHECK konstreyntlari + indeks
2. `ENABLE` va `FORCE ROW LEVEL SECURITY`
3. Policy (rol bo'yicha; mijoz o'qishi kerak bo'lsa alohida `FOR SELECT`)
4. `GRANT` — `playbron_app` uchun jadval va sequence; kerak bo'lsa `playbron_platform`
5. Self-test
6. `check_render_shape.py`

**Yangi endpoint:**
1. `router.py` — Pydantic model, `Depends(require_owner|require_admin|require_staff)`, `_assert_path_matches_header()`
2. `service.py` — mantiq, SQL, `AppError`, `log_action()`
3. `packages/api-client/src/endpoints.ts` — tipli funksiya va DTO, `snake_case` → `camelCase`
4. Uchta test (§Testlar)

Bosqich briflari: `tasks/`. Sessiya boshida kerakli brifga `@` bilan
havola qilinadi, CLAUDE.md ga ko'chirilmaydi.

## Ma'lum texnik qarz

Batafsil: `docs/audit-report.md`. Yangi kod bu ro'yxatni uzaytirmaydi.

- Konsolda chegirma/qarz/tip tanlash va naqd xarajatni smenaga biriktirish UI'si yo'q — backend qo'llab-quvvatlaydi (`0032_payments.py`), POS ekrani hali doim to'liq summa yuboradi.
- Qisman qaytarim yo'q: `cancel_order()` bronsiz sotuvni TO'LIQ qaytaradi.
- `apps/miniapp/src/lib/bill.ts` bonus va prepay'ni `mock/data.ts` konstantalaridan oladi.
- `apps/admin/src/mock/club.ts` — backendda ekvivalenti yo'q entity'larning soxta ma'lumoti.
- `apps/miniapp` da i18n yo'q; landing'da `en` yo'q.
- Ish vaqti tekshiruvi FAQAT mijoz yo'lida. Xodim yo'li ataylab cheklanmagan — kech qolgan mijozni yozish uning qarori.
- Fon vazifalari yo'q: avto-bekor, no-show, eslatma ishlamaydi.
- Telegram botlari jonli muhitda javob bermaydi — `docs/HOLAT.md` §2.
- `mypy src/` 27 xato beradi (asosan `int | None` → `int`). CI'da mypy qadami YO'Q — faqat `ruff`. Yangi kod bu sonni oshirmaydi.

## Scope

- So'ralgan ish bajariladi, undan tashqariga chiqilmaydi. Yo'l-yo'lakay refactor qilinmaydi.
- Tegilmaydi: `api/migrations/versions/**` (mavjudlari), `packages/ui/src/tokens/**`, `.env`, `deploy/.env.prod`, `docs/archive/**`.
- Yondashuv noto'g'ri deb hisoblansa — bir gapda aytiladi va baribir so'ralganidek davom etiladi.
- Birinchi tool chaqiruvidan oldin bir gapda nima qilinayotgani aytiladi. Ish davomida faqat muhim topilma yoki yo'nalish o'zgarishida yoziladi. Javob natijadan boshlanadi.
- Subagent faqat haqiqatan mustaqil va parallellashadigan katta ish uchun.
- Javoblar qisqa.
