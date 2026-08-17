# PlayBron

PlayStation klublari uchun multi-tenant bron SaaS. Rollar: SUPERADMIN, CLUB_ADMIN, STAFF, CUSTOMER.
To'liq spetsifikatsiya: `docs/BUILD-BRIEF.md`.

> **Loyihaning HOZIRGI holati, ochiq ishlar va qimmatga tushgan
> saboqlar: `docs/HOLAT.md`.** Yangi qurilmada yoki uzoq tanaffusdan
> keyin ishni shundan boshlang.

## Stack

Turborepo + pnpm.

- `api/` — **FastAPI + SQLAlchemy + Alembic + PostgreSQL 16 + Redis**.
  Test — **pytest** (`RUN_DB_TESTS=1` bilan; usiz DB testlari jimgina skip bo'ladi).
- `apps/admin/`, `apps/miniapp/` — React 19 + Vite.
- `apps/landing/` — **Astro** (to'liq statik, mijoz tomonida JS yo'q).
- `packages/ui` — SystemX design system (brief'dagi "Blue" eskirgan, manba `docs/designs/_ds/`).
- `packages/api-client` — umumiy API klienti va DTO'lar.
- `packages/config` — umumiy sozlamalar.

> Bu ro'yxat 2026-08-17 da HAQIQIY holatga moslandi. Avval bu yerda
> NestJS + Prisma + Fastify + Socket.IO + Next.js + vitest + `apps/api` +
> `packages/types` yozilgan edi — bularning BIRORTASI loyihada yo'q.
> Fayl har seansda avtomatik yuklangani uchun bu noto'g'ri ma'lumot
> har safar chalg'itardi.

## Buyruqlar

```bash
docker compose up -d                       # postgres, redis, minio
pnpm dev                                   # admin + miniapp + landing

cd api
python -m alembic upgrade head             # migratsiya
RUN_DB_TESTS=1 python -m pytest tests/ -q  # 169 test
python -m ruff check . && python -m mypy src/

# Migratsiya qo'shgandan keyin MAJBURIY (lokal superuser self-testlarni
# o'tkazib yuboradi, Render/VPS esa yuboradi — `docs/HOLAT.md` §4.1):
python scripts/check_render_shape.py
```

## Qat'iy qoidalar

- Pul — `bigint`, so'm, kasrsiz. Float yo'q. JSON javobda satr (`BigInt.prototype.toJSON`).
- Vaqt — DB'da UTC `timestamptz`, UI'da `Asia/Tashkent`, `date-fns-tz`.
- Vaqt hisoblari HECH QACHON server yoki brauzer mahalliy zonasiga tayanmaydi —
  doim `clubs.timezone` orqali (backend `ZoneInfo`, frontend `Intl.DateTimeFormat`).
- Tenant izolyatsiyasi — Postgres RLS + so'rov konteksti (`app.*` GUC'lari).
  Qo'lda `where club_id` yozib chetlab o'tilmaydi.
  Ilova `playbron_app` roli bilan ulanadi (`DATABASE_URL`), migratsiya egasi roli bilan
  (`DIRECT_URL`), platforma o'qishlari `playbron_platform` (BYPASSRLS) bilan.
- Yangi tenant-scoped jadval → o'sha migratsiyada `ENABLE`/`FORCE ROW LEVEL SECURITY` va
  `tenant_isolation` policy'si ham yoziladi.
- Bron to'qnashuvi — `bookings_no_overlap` EXCLUDE konstreyni. `23P01` → `409 SLOT_TAKEN`.
- Narx/hisob mantig'i bitta manbada — backend `modules/*/service.py`, frontend `packages/api-client`.
- Rang/spacing/typography faqat design tokenlar orqali. Hardcode qiymat yo'q.
- `any` yo'q. Matn literal yo'q — i18n resurslari (uz/ru/en).
- Migratsiyalar faqat oldinga.

## Tegilmaydi

`api/migrations/versions/**` (mavjudlari — migratsiyalar faqat oldinga),
`packages/ui/src/tokens/**`, `.env` va `deploy/.env.prod`

## Uslub

Birinchi tool chaqiruvidan oldin bir gapda nima qilayotganingni ayt. Ish davomida faqat muhim
topilma yoki yo'nalish o'zgarishida yoz. Oxirida natijadan boshla.
Subagent faqat haqiqatan mustaqil va parallellashadigan katta ish uchun.
Javoblar qisqa.
