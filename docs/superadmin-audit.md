# Super admin (platform) qatlami — inventarizatsiya va tuzatish rejasi

> A bosqichi, 2026-08-18. Faqat o'qish — bu hujjat yozilganda kod tegilmagan.
> Maqsad holat: loyiha egasi bergan «Platform (super admin)» invariantlari.
> Batafsil spetsifikatsiya: `docs/06-super-admin.md` (2026-08-15, qisman eskirgan).

## 0. Lug'at moslashtirish

Berilgan invariant bloki Supabase lug'atida yozilgan. Bu loyihada Supabase
yo'q — FastAPI + SQLAlchemy (xom SQL) + Alembic + PostgreSQL. Invariantlarning
MAZMUNI saqlanadi, nomlari loyiha lug'atiga o'tkaziladi (`CLAUDE.md`
§Domen glossariyi: «Kodda ishlatiladigan nom — chapda. Boshqa nom yozilmaydi»).

| Blokdagi nom | Bu loyihada | Izoh |
|---|---|---|
| `platform.*` schema | YO'Q — hammasi `public` | Yaratilishi kerak, §2.1 |
| `platform.admins` | `public.super_admins` | Jadval bor, schema noto'g'ri |
| `platform.is_admin()` | `app_platform()` | Mavjud, lekin semantikasi boshqa — §2.3 |
| `auth.uid()` | `app_user_id()` GUC | Supabase konsepsiyasi, ekvivalenti bor |
| `service_role` kaliti | `PLATFORM_DATABASE_URL` | Server-only env, klientda yo'q |
| `platform.audit_log` | `public.audit_log` | Umumiy, tenant bilan bo'lishilgan |
| `platform.tenant_usage` | YO'Q | Aggregat view umuman yaratilmagan |
| `/api/platform/*` | `/api/v1/platform/*` | Versiya prefiksi loyiha konvensiyasi |

**A bosqichining birinchi xulosasi:** invariantlarni CLAUDE.md ga qo'shishdan
oldin ular shu jadval bo'yicha qayta yozilishi kerak, aks holda ular
diff bo'yicha tekshirib bo'lmaydigan qoidaga aylanadi (`CLAUDE.md` talabi).
Taklif qilingan matn — §5.

---

## 1. Fayllar jadvali

### 1.1 Backend — yadro

| Yo'l | Vazifasi | Muammo |
|---|---|---|
| `api/src/playbron/core/db.py` | `platform_engine` (`playbron_platform` roli), `platform_scope()`, `platform_write_scope()` — ikkalasi `SET LOCAL app.platform='true'` qo'yadi | Muammo yo'q. `is_super_admin` oldindan tekshiriladi, `platform_scope()` da `SET TRANSACTION READ ONLY`. Bu qatlam SOG'LOM |
| `api/src/playbron/deps.py` | `require_super_admin` (404 qaytaradi, IP allowlist), `platform_db`, `platform_write_db` | Muammo yo'q. `platform_db` → `require_super_admin` ga bog'liq, ya'ni har bir `/platform/*` endpoint serverda tekshiriladi |
| `api/src/playbron/core/context.py` | `is_super_admin: bool` — tenant kontekstining bir maydoni | Platform huquqi tenant kontekstiga ko'chgan. O'zi xavfli emas (faqat o'qiladi), lekin frontendgacha rol sifatida oqadi — §1.4 |
| `api/src/playbron/core/security.py:60` | JWT ga `"sa": is_super_admin` claim'i yoziladi; `sa_access_ttl_sec` alohida TTL | Platform huquqi TENANT tokeni ichida tashiladi. Token o'g'irlansa platform paneli ham ochiladi |
| `api/src/playbron/core/super_admin_bootstrap.py` | `SUPER_ADMIN_PASSWORD` env'idan super admin hisobini va `super_admins` qatorini ILOVA START'ida yaratadi | **Eng jiddiy topilma.** Runtime yozish yo'li; ustiga `ALTER TABLE super_admins NO FORCE ROW LEVEL SECURITY` ni ish vaqtida bajaradi |
| `api/src/playbron/modules/auth/service.py:94` | `is_super_admin()` — `super_admins` dan o'qiydi, login javobiga qo'shadi | Muammo yo'q, manba to'g'ri jadval |

### 1.2 Backend — platform moduli

| Yo'l | Vazifasi | Muammo |
|---|---|---|
| `api/src/playbron/modules/platform/router.py` | 9 endpoint, `prefix="/platform"`, `main.py:179` da `API_PREFIX` bilan ulanadi | Prefiks `/api/v1/platform/*`. Guard'lar joyida |
| `api/src/playbron/modules/platform/service.py` | Statistika, tashkilot ro'yxati/detali, to'lov yozuvi, hisobot, loglar, bot holati | Xom tenant satrlarini o'qiydi (`bookings`, `payments`, `users`) — aggregat view yo'q |
| `api/scripts/seed_super_admins.py` | `SUPER_ADMIN_TELEGRAM_IDS` bo'yicha seed, `DIRECT_URL` bilan | Skript — ma'muriy yo'l, endpoint emas. Chegaraviy holat |
| `api/scripts/set_staff_password.py` | Parolni stdin'dan o'rnatadi | Muammo yo'q — standart yo'l |

### 1.3 Migratsiyalar

| Yo'l | Vazifasi | Muammo |
|---|---|---|
| `0001_core.py:136` | `super_admins` jadvali (`user_id` PK → `users`), `super_admins_self` policy | `public` schema'sida |
| `0002_seed.py` | Boshlang'ich super adminlar | — |
| `0015_platform_stats.py:48` | `app_platform()` funksiyasi + `organizations`/`clubs`/`bookings` uchun `platform_read` | `bookings` xom satrlari ochilgan |
| `0016_platform_org_admin.py` | `platform_payments` jadvali + `platform_all` policy; `users_platform_read` | `platform_payments` — sof platform jadvali, lekin `public` da |
| `0017_platform_org_plan.py` | `organizations_platform_write` (UPDATE) | — |
| `0018_platform_log_read.py` | `audit_log`, `auth_events` uchun platform o'qish | — |
| `0029_platform_read_gaps.py` | `memberships`, `stations` uchun platform o'qish | — |
| `0030_suspend_revokes_sessions.py:102` | `refresh_tokens` — `IF NOT app_platform() THEN` | — |
| `0032_payments.py:238` | `payments_platform_read` | **Xom to'lov satrlari ochilgan** |
| `0033_rooms_tariffs.py` | `rooms`/`tariffs` platform o'qish | — |

**Bazadagi haqiqiy holat** (13 policy, `pg_policies` dan):

```
audit_log   | audit_log_platform_read        | SELECT
auth_events | auth_events_platform_read      | SELECT
bookings    | bookings_platform_read         | SELECT   ← invariant #5 buziladi
clubs       | clubs_platform_read            | SELECT
memberships | memberships_platform_read      | SELECT
organizations | organizations_platform_read  | SELECT
organizations | organizations_platform_write | UPDATE
payments    | payments_platform_read         | SELECT   ← invariant #5 buziladi
platform_payments | platform_payments_platform_all | ALL
rooms       | rooms_platform_read            | SELECT
stations    | stations_platform_read         | SELECT
tariffs     | tariffs_platform_read          | SELECT
users       | users_platform_read            | SELECT   ← invariant #5 buziladi
```

Schema ro'yxati: **faqat `public`**. `platform` schema'si umuman yo'q.

### 1.4 Frontend

| Yo'l | Vazifasi | Muammo |
|---|---|---|
| `apps/admin/src/store/session.ts:16` | `export type Role = 'STAFF' \| 'CLUB_ADMIN' \| 'SUPER_ADMIN'` | **Platform huquqi TENANT ROLI sifatida modellashtirilgan** — invariant #1 ning to'g'ridan-to'g'ri buzilishi |
| `apps/admin/src/store/session.ts:110` | `topRole()` — `superAdmin` bo'lsa `'SUPER_ADMIN'` qaytaradi | Rol ierarxiyasi soxta: super admin `OWNER` dan «yuqori» ko'rinadi |
| `apps/admin/src/mock/data.ts:247` | `NAV_SUPER_ADMIN` — menyu | Ma'lumot to'g'ri joyda emas (`mock/`), lekin bu mavjud qarz |
| `apps/admin/src/screens/platform*.tsx` (5 ta) | Panel ekranlari | Guard faqat rol bo'yicha — server tekshiruvi bor, ya'ni bu YAGONA himoya emas. Invariant #6 bajarilgan |
| `packages/api-client/src/types.ts:7` | `Role = 'OWNER' \| 'ADMIN' \| 'STAFF'` — `SUPER_ADMIN` YO'Q | Klient paketi TO'G'RI, admin ilovasi undan chetlashgan |

`CLUB_ADMIN` — `CLAUDE.md` da «kodda YO'Q» deb yozilgan nom, lekin
`session.ts:16` da hali turibdi. Alohida qarz.

### 1.5 Testlar

| Yo'l | Qamrov | Muammo |
|---|---|---|
| `api/tests/test_platform.py` | 12 test: cross-tenant statistika, tashkilot ro'yxati/detali, to'lov, hisobot; salbiy — oddiy egaga 404 | Endpoint darajasida. **Policy darajasida ijobiy/salbiy juftlik YO'Q** |
| `api/tests/test_policy_invariants.py` | 6 test — rekursiya, scope, RETURNING | `app_platform()` policy'lari umuman qamralmagan |
| `api/tests/test_super_admin_bootstrap.py` | Bootstrap oqimi | Xavfsizlik emas, funksionallik testi |

---

## 2. Gap jadvali — invariant → hozirgi holat → farq

| # | Invariant | Hozirgi holat | Farq |
|---|---|---|---|
| 1 | Platform ma'lumotlari faqat `platform.*` schema'sida; `public.*` da platform ustuni yo'q | `platform` schema'si YO'Q. `super_admins`, `platform_payments` — `public` da | **BUZILGAN.** Schema yaratilib, ikkala jadval ko'chiriladi |
| 2 | Platform huquqi faqat `platform.admins` orqali; tenant jadvalida `is_super_admin` ustuni yo'q | `users` da ustun YO'Q — alohida `super_admins` jadvali. LEKIN huquq JWT `sa` claim'i va frontend `Role='SUPER_ADMIN'` orqali tenant rol tizimiga oqadi | **QISMAN.** Jadval to'g'ri, modellashtirish noto'g'ri |
| 3 | RLS'da tekshiruv faqat `platform.is_admin()` orqali; inline yozilmaydi | 13 policy'ning HAMMASI `app_platform()` ishlatadi, inline subquery yo'q | **BAJARILGAN** (nom farqi). Ogohlantirish: `app_platform()` GUC o'qiydi, `super_admins` ni TEKSHIRMAYDI — ishonch ilova qatlamida |
| 4 | `platform.admins` ga yozish faqat migratsiya orqali; runtime endpoint yo'q | Endpoint YO'Q — bu qism bajarilgan. Lekin `super_admin_bootstrap.py` ilova START'ida yozadi va `ALTER TABLE ... NO FORCE RLS` bajaradi; `seed_super_admins.py` skripti ham yozadi | **BUZILGAN.** Runtime yozish + runtime DDL |
| 5 | Super admin `payments`, `bookings`, `customers` satrlarini o'qimaydi; faqat aggregat view | `bookings_platform_read`, `payments_platform_read`, `users_platform_read` — uchalasi ham XOM satrlarga `FOR SELECT`. Aggregat view yo'q | **BUZILGAN — eng katta risk** |
| 6 | Endpointlar `/api/platform/*` da, serverda tekshiriladi; frontend guard yagona himoya emas | `/api/v1/platform/*`, `platform_db` → `require_super_admin` → 404 + IP allowlist | **BAJARILGAN** (prefiks versiyali) |
| 7 | `service_role` kaliti klient bundle'ga chiqmaydi | `PLATFORM_DATABASE_URL` faqat serverda; frontend `/api/v1/platform/*` orqali boradi | **BAJARILGAN** |
| 8 | Impersonation: TTL ≤ 30 daq, `reason` majburiy, audit, doimiy banner | Glass rejimi `docs/06-super-admin.md` da batafsil loyihalangan, lekin **QURILMAGAN**: `glass_sessions` jadvali yo'q, `app_glass_*()` funksiyalari yo'q, endpoint yo'q. `deps.py:103` da eski `if ctx.is_super_admin: return` chetlab o'tish yo'li ALLAQACHON olib tashlangan | **YO'Q.** Buzilish emas — funksiya mavjud emas. Invariant B bosqichida qurilsa kuchga kiradi |
| 9 | Har bir `is_admin()` policy'si uchun ijobiy va salbiy test | 13 policy, 0 ta policy-darajasidagi juftlik. Faqat endpoint testlari | **BUZILGAN** |

**Yakun: 9 invariantdan 5 tasi buzilgan, 3 tasi bajarilgan, 1 tasi
(impersonation) hali qurilmagan.**

---

## 3. Sindiruvchi o'zgarishlar

| O'zgarish | Nima buziladi | Yumshatish |
|---|---|---|
| `super_admins` → `platform.admins` ga ko'chirish | `0001` dagi `super_admins_self` policy, `auth/service.py::is_super_admin()`, `seed_super_admins.py`, `super_admin_bootstrap.py`, `test_super_admin_bootstrap.py`, `conftest.py` fixture'lari | Ko'chirish migratsiyada `ALTER TABLE ... SET SCHEMA` bilan; `public.super_admins` nomi ostida VIEW qoldirilmaydi (yarim holat yaratardi), o'rniga hamma o'quvchi bitta commit'da yangilanadi |
| `platform_payments` → `platform.payments` | `0016`/`0017` policy'lari, `platform/service.py`, `test_platform.py` (3 test) | Yuqoridagi bilan bir xil migratsiyada |
| `bookings`/`payments`/`users` platform o'qishini YOPISH | `platform/service.py` dagi statistika, hisobot va tashkilot detali so'rovlari — hozir aynan shu jadvallardan o'qiydi. `test_platform.py` ning 6 tasi | Avval `platform.tenant_usage` aggregat view'i quriladi va servis unga o'tkaziladi, KEYIN policy'lar tushiriladi. Teskari tartib panelni ishlamay qoldiradi |
| `Role` dan `SUPER_ADMIN` ni olib tashlash | `apps/admin/src/app.tsx` navigatsiyasi, `screens/shift.tsx`, `mock/data.ts::NAV_SUPER_ADMIN`, `store/session.ts` | Rol o'rniga alohida `isSuperAdmin` bayrog'i (u `session.ts:124` da ALLAQACHON bor) — navigatsiya shunga o'tkaziladi |
| `super_admin_bootstrap.py` ni olib tashlash | Render bepul rejasida Shell yo'q — loyiha egasi bu yo'lni ATAYLAB tanlagan (2026-08-15). Olib tashlansa prod'da super admin parolini o'rnatish yo'li qolmaydi | **Bu qaror loyiha egasiniki.** Reja variantni beradi, o'zi hal qilmaydi — §4, 6-qadam |

**Migratsiyalar faqat oldinga** (`CLAUDE.md`): `downgrade()` → `NotImplementedError`.
Loyiha egasi «har bir migratsiya `down` bilan» dedi — bu mavjud invariant bilan
ZIDDIYAT. Reja loyihaning o'z qoidasiga ergashadi; boshqacha bo'lsin desangiz ayting.

---

## 4. Tuzatish rejasi

Har bir qadam — alohida commit, testlar yashil, tenant funksionali o'zgarmaydi.

| # | Qadam | Tegadigan fayllar | Migratsiya |
|---|---|---|---|
| 1 | **Invariantlarni CLAUDE.md ga yozish** (§5 dagi moslashtirilgan matn) | `CLAUDE.md`, `docs/06-super-admin.md` (havola) | yo'q |
| 2 | **`platform` schema'si + `platform.is_admin()`** — schema yaratiladi, `app_platform()` uning ichida `platform.is_admin()` sifatida takrorlanadi, `GRANT USAGE` beriladi. Eski `app_platform()` hali turadi (policy'lar undan foydalanmoqda) | `0036_platform_schema.py` | HA |
| 3 | **`super_admins` → `platform.admins`, `platform_payments` → `platform.payments`** — `SET SCHEMA`, policy'lar qayta yoziladi, o'quvchi kod yangilanadi | `0037_platform_tables.py`, `auth/service.py`, `platform/service.py`, `core/super_admin_bootstrap.py`, `scripts/seed_super_admins.py`, `tests/conftest.py`, `tests/test_platform.py`, `tests/test_super_admin_bootstrap.py` | HA |
| 4 | **`platform.tenant_usage` aggregat view** — klub/tashkilot kesimida bron soni, tushum yig'indisi, faol xodim soni. Xom satr chiqmaydi. `SECURITY INVOKER` emas, `SECURITY DEFINER` funksiya orqali (RLS'ni chetlab o'tmasdan) | `0038_tenant_usage.py`, `platform/service.py` | HA |
| 5 | **`bookings`/`payments`/`users` platform policy'larini TUSHIRISH** — faqat 4-qadam tugagach. Statistika va hisobot `tenant_usage` dan o'qiydi | `0039_platform_read_narrowing.py`, `platform/service.py` | HA |
| 6 | **Runtime yozish yo'lini yopish** — `super_admin_bootstrap.py` dagi `ALTER TABLE ... NO FORCE RLS` olib tashlanadi va yozish `SECURITY DEFINER` funksiya orqali qilinadi; yoki modul butunlay o'chiriladi (**loyiha egasi qarori**) | `core/super_admin_bootstrap.py`, `main.py`, `0040_platform_admin_grant.py` | HA |
| 7 | **Frontendda rolni ajratish** — `Role` dan `SUPER_ADMIN` olib tashlanadi, navigatsiya `isSuperAdmin` bayrog'iga o'tadi; `CLUB_ADMIN` ham tozalanadi | `apps/admin/src/store/session.ts`, `app.tsx`, `mock/data.ts`, `screens/shift.tsx` | yo'q |
| 8 | **Policy testlari** — 13 policy'ning har biriga ijobiy (platform ko'radi) va salbiy (tenant/anonim ko'rmaydi) juftlik | `api/tests/test_platform_policies.py` (yangi) | yo'q |
| 9 | **Impersonation (glass rejimi)** — `platform.glass_sessions`, TTL ≤ 30 daq, majburiy `reason`, `platform.audit_log` yozuvi, UI banner | `0041_glass_sessions.py`, `deps.py`, `modules/platform/glass.py`, `apps/admin/**` | HA |

**Tavsiya:** 9-qadam alohida ish sifatida ajratilsin — u yangi funksiya,
qolgan sakkiztasi esa mavjud qatlamni tuzatish. 1–8 qadamlar tenant
funksionaliga umuman tegmaydi.

---

## 5. CLAUDE.md ga taklif qilinadigan matn

```markdown
## Platform (super admin)

Platform roli — tenant roli EMAS. Bu chegara buzilgan o'zgarish merge qilinmaydi.

- Platform jadvallari `platform` schema'sida. `public` jadvalida platform ustuni yaratilmaydi.
- Platform huquqi faqat `platform.admins` orqali. Tenant `users`/`memberships` da `is_super_admin` kabi ustun yaratilmaydi va `Role` turiga `SUPER_ADMIN` qo'shilmaydi.
- RLS'da platform tekshiruvi faqat `platform.is_admin()` orqali. Policy ichiga inline subquery yozilmaydi.
- `platform.admins` ga INSERT/UPDATE faqat migratsiya yoki `SECURITY DEFINER` funksiya orqali. Runtime endpoint va runtime `ALTER TABLE` yo'q.
- Super admin `bookings`, `payments`, `users` XOM satrlarini o'qimaydi — faqat `platform.tenant_usage` aggregati.
- Platform endpointlari `/api/v1/platform/*` prefiksida va serverda `require_super_admin` bilan tekshiriladi. Frontend guard yagona himoya emas.
- `PLATFORM_DATABASE_URL` klient bundle'iga chiqmaydi. Platform amallari faqat server tomonda.
- Impersonation (glass): TTL ≤ 30 daqiqa, `reason` majburiy, `platform.audit_log` ga yoziladi, UI'da doimiy banner. Glass tokenida `sa=false`.
- `platform.is_admin()` ishlatilgan har bir policy uchun ijobiy va salbiy test. Testsiz policy merge qilinmaydi.

Batafsil: `docs/06-super-admin.md`, holat: `docs/superadmin-audit.md`.
```

---

## 6. Ochiq savollar (B bosqichidan oldin javob kerak)

1. **`super_admin_bootstrap.py`** — o'chiriladimi yoki `SECURITY DEFINER`
   funksiya orqali xavfsizlantiriladimi? Render bepul rejasida Shell yo'q,
   siz bu yo'lni bilib turib tanlagansiz (2026-08-15).
2. **`downgrade()`** — «har bir migratsiya `down` bilan» talabingiz
   `CLAUDE.md` dagi «migratsiyalar faqat oldinga» invarianti bilan
   ziddiyatda. Qaysi biri kuchda qoladi?
3. **9-qadam (glass)** shu ishga kiradimi yoki alohida ajratiladimi?
