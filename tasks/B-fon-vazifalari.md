# B-bosqich — fon vazifalari

<context>
Kodda `scheduler`, `arq`, `celery`, `APScheduler`, `asyncio.create_task` —
nol uchrash. Shu sababli sakkizta funksiya ishlamaydi: to'lanmagan bronni
avto-bekor qilish, no-show belgilash, bron eslatmalari, egaga kunlik
xulosa, kassa farqi ogohlantirishi, tovar qoldig'i, obuna eslatmasi, bonus
muddati.

Bu bitta infratuzilma qarori bo'lib, u sakkizta bandni bir vaqtda ochadi.
</context>

<task>
## B0. Infratuzilma qarori

**Tanlov: `arq`.** Sabab: Redis allaqachon bor (`core/redis.py`), alohida
worker jarayoni bir nechta API instansiyasi bo'lganda vazifa ikki marta
bajarilishini oldini oladi, `docker-compose.yml` va `render.yaml` ga bitta
servis qo'shish yetarli.

APScheduler rad etiladi: u API jarayoni ichida yuradi va instansiya soni
1 dan oshsa har bir vazifa takrorlanadi. Bu aynan pul va bildirishnomaga
tegadigan joyda xavfli.

> **Bu qaror deploy'ga ta'sir qiladi — boshlashdan oldin tasdiqlansin.**
> Agar alohida servis qo'shish istalmasa, muqobil: APScheduler +
> `pg_try_advisory_lock` bilan yagona bajarilish kafolati. Unda B1
> boshqacha yoziladi, B2–B4 o'zgarmaydi.

## B1. Worker skeleti

- `api/src/playbron/worker/` moduli: `arq` `WorkerSettings`, Redis
  ulanishi `core/redis.py` dan.
- Har bir vazifa `core/db.py::session_scope()` ichida yuradi va **GUC
  kontekstini o'zi o'rnatadi** — fon vazifasida HTTP so'rovi yo'q, ya'ni
  `app.club_id` avtomatik kelmaydi. Klub bo'yicha aylanadigan vazifalar
  har klub uchun alohida kontekst ochadi.
- Vazifa cross-tenant o'qishi kerak bo'lsa — `SECURITY DEFINER` funksiya +
  nomlangan GUC claim (`docs/07-patterns.md` §2). Yangi `BYPASSRLS` roli
  qo'shilmaydi.
- Idempotentlik: har bir vazifa ikki marta yurganda bir xil natija
  berishi shart. Redis'da `job_id` bo'yicha qulf.
- `jobs` jadvali (`0034`): `kind`, `club_id`, `payload`, `status`,
  `run_at`, `attempts`, `last_error`. RLS + policy + GRANT + self-test
  o'sha migratsiyada.
- `docker-compose.yml` va `render.yaml` ga worker servisi.

## B2. `notifications` jadvali va yuborish qatlami

Hozir Telegram to'g'ridan-to'g'ri yuboriladi, iz qolmaydi.

- `notifications` (`0034`): `club_id`, `recipient_kind`, `recipient_id`,
  `channel`, `template`, `payload` jsonb, `status`, `sent_at`, `error`.
- Yuborish `core/telegram_api.py` ustida yagona servis orqali; har yuborish
  jurnalga tushadi.
- Takroriy yuborishning oldini olish: `(kind, entity_id)` bo'yicha unikal
  indeks — masalan bitta bron uchun "2 soat qoldi" eslatmasi bir marta.

## B3. Vazifalar

Har biri alohida commit, har biri testi bilan.

| Vazifa | Qoida |
|---|---|
| `expire_unpaid_bookings` | `PENDING` bron `club_settings.payment_window_min` dan oshsa `CANCELLED`. Sozlama yo'q bo'lsa vaqtincha konstanta, C-bosqichda DB'ga ko'chadi |
| `mark_no_show` | Boshlanish vaqtidan 15 daq. o'tgan, `CHECKED_IN` bo'lmagan bron → `NO_SHOW`. **D-bosqichga bog'liq** — holatlar hali yo'q, shuning uchun oxirgi navbatda |
| `booking_reminders` | 2 soat va 20 daqiqa oldin. `notifications` orqali |
| `daily_summary` | Klub vaqti bilan 09:00 da egaga: kechagi `received_revenue`, sessiyalar, band foizi |
| `shift_variance_alert` | Smena yopilganda `abs(variance) > club_settings.variance_limit` → egaga darhol |
| `low_stock_alert` | `products.stock_qty < min_stock` → menejerga. **`min_stock` ustuni yo'q — C-bosqichda qo'shiladi** |

Vaqt bo'yicha ishlaydigan har bir vazifa `clubs.timezone` ga tayanadi,
server zonasiga emas (CLAUDE.md §Vaqt).

## B4. Kuzatuv

- Vazifa yiqilsa `last_error` yoziladi va uch urinishdan keyin platforma
  jurnaliga tushadi.
- `/api/platform/jobs` — superadmin uchun oxirgi bajarilishlar ro'yxati.
</task>

<constraints>
`mark_no_show` va `low_stock_alert` bog'liqliklari yopilmaguncha yozilmaydi
— skeletini qoldirib, `docs/HOLAT.md` ga qayd et.
Bron holat mashinasi bu bosqichda o'zgartirilmaydi (D-bosqich ishi).
</constraints>

<output>
Har vazifa uchun alohida commit. `docs/HOLAT.md` da yangi "Fon vazifalari"
bo'limi: qaysi vazifa qaysi jadvalga tayanadi, qaysi biri hali bloklangan.
</output>
