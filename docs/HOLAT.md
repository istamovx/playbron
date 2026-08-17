# PlayBron — loyiha holati va topshirish hujjati

> **Boshqa qurilmada ishlashni shu yerdan boshlang.**
> Sana: 2026-08-17. Oxirgi migratsiya: `0031_stations_bot_lookup`.
>
> Bu hujjat repo bilan **birga ko'chadi**. Undagi «Qimmatga tushgan
> saboqlar» bo'limi eng muhimi: har biri prod'da yoki soatlab
> nosozlik qidirish natijasida topilgan va har biri qaytadan
> takrorlanishi mumkin bo'lgan tuzoq.

---

## 1. Loyiha qisqacha

PlayStation klublari uchun multi-tenant bron SaaS. Rollar:
`SUPERADMIN`, `CLUB_ADMIN`, `STAFF`, `CUSTOMER`.

| Papka | Nima |
|---|---|
| `api/` | FastAPI + SQLAlchemy + Alembic + PostgreSQL 16 + Redis |
| `apps/admin/` | Konsol (xodim + klub admini + super admin), React 19 + Vite |
| `apps/miniapp/` | Mijoz Telegram Mini App, React 19 + Vite |
| `apps/landing/` | Marketing sayti, **Astro** (statik, nol JS) |
| `packages/ui/` | SystemX dizayn tizimi (tokenlar + komponentlar) |
| `packages/api-client/` | Umumiy API klienti va DTO'lar |
| `deploy/` | Hetzner VPS konfiguratsiyasi + zaxira tizimi |

Ikkita Telegram boti: **mijoz boti** (ro'yxatdan o'tish, bron, chek
yuborish) va **admin boti** (konsolga kirish, klub admini hisobotlari).

---

## 2. Hozirgi holat

### Jonli (production)

Hozircha **Render**'da: `api.playbron.uz`, `app.playbron.uz`,
`mini.playbron.uz`, `playbron.uz`.

### Hetzner VPS — tayyor, lekin hali o'tkazilmagan

Server olingan (Helsinki, CPX22). `deploy/` ichida to'liq
konfiguratsiya bor va sinovdan o'tgan, lekin **DNS hali Render'ga
qarab turibdi**.

Ko'chish tartibi: `deploy/README.md`.

### Nima ishlamayapti — Telegram botlari

**Alomat** (loyiha egasi, 2026-08-17): botga `/start` berilganda hech
qanday xabar kelmaydi; «Telegram ulash» esa chiqib-kirgandan keyin
uzilgan bo'lib ko'rinadi.

**NIMA TEKSHIRILGAN va CHIQARIB TASHLANGAN** (qaytarmang):

| Tekshirildi | Natija |
|---|---|
| Jonli frontend bundle eskimi | Yo'q — `telegram_linked`, bot diagnostikasi ekrani hammasi bor |
| `TelegramLinkPanel` holatni serverdan o'qiydimi | Ha — `GET /me` dan, mount'da |
| Backend `telegram_linked` qaytaradimi | Ha — `users/router.py::me()` → `staff_telegram` |
| Webhook endpointlari javob beradimi | Ha, ikkalasi ham; sekret tekshiriladi |
| Mijoz webhook'i sekretsiz 200 qaytaryapti | Bu ATAYLAB (Telegram navbati to'xtamasin), teshik emas |

**MUHIM aniqlik** (loyiha egasi): *«bot 1 marta ulandi, log outdan
keyin uzildi»*. Ya'ni bot yangilanishni QABUL QILGAN — webhook va
token joyida. Demak muammo o'qish/saqlash yo'lida.

**Topilgan haqiqiy nuqson.** Konsoldagi poll `stafflink.poll_link()`
orqali **Redis**ni o'qiydi, ulanish yozuvi esa **bazaga** ketadi —
ikki ALOHIDA manba. `approve_link()` Redis'ni darhol «ready» qilib
qo'yadi, shuning uchun `staff_telegram_link_confirm()` yiqilsa ham:

- konsol «Ulandi» deb ko'rsatardi,
- bot «ulandi» xabarini yuborardi,
- keyingi kirishda `/me` (`staff_telegram`) bo'sh bo'lgani uchun
  «ulanmagan» chiqardi.

Tashqaridan bu aynan «chiqqach uziladi» bo'lib ko'rinadi.

Tuzatildi (`_handle_link_start`): yozuv **haqiqatan paydo bo'lgani
tekshiriladi**; bo'lmasa foydalanuvchiga «ulandi» EMAS, «saqlanmadi»
xabari boradi va `log.error` yoziladi. Sinov ham qo'shildi —
`test_full_link_flow...` endi poll'dan keyin `/me` ni ham tekshiradi.

> Bu SILENT FAILURE ni ko'rinadigan qiladi, lekin baza yozuvi
> NEGA yiqilayotganini hali aniqlamaydi. Keyingi sessiyada prod
> logidan `staff_telegram_link_confirm yozuvni yaratmadi` qatorini
> qidiring — u chiqsa sabab RLS/GRANT, chiqmasa boshqa yo'nalish.

**Ikkinchi ehtimol** (hali chiqarib tashlanmagan): `main.py` lifespan
ikkala webhook'ni KETMA-KET ro'yxatdan o'tkazadi. Ikkala yuza bitta
botga qarasa — yoki `ADMIN_BOT_TOKEN` berilmasa (u holda
`admin_token()` `BOT_TOKEN` ga tushadi) — ikkinchi `setWebhook`
birinchisini BOSIB KETADI. Buni Sozlamalar ekrani endi aniq aytadi.

**Bosib ketish endi mumkin emas.** `main.py::register_webhooks()`
ikkala token bir xil bo'lsa admin webhook'ini ATAYLAB ro'yxatdan
o'tkazmaydi va sababni `log.error` bilan yozadi. Mijoz boti saqlanadi:
konsolga parol bilan ham kirish mumkin, mijozda esa botdan boshqa yo'l
yo'q. Ya'ni qaysi yuza tirik qolgani endi chaqiruvlar tartibiga yoki
tarmoq xatosiga bog'liq emas (`tests/test_webhook_registration.py`).

> **Ammo alomat bu ehtimolga QARSHI ishlaydi — buni e'tiborga oling.**
> Tartib: avval admin, keyin mijoz. Bitta bot bo'lsa OXIRGI chaqiruv
> yutadi, ya'ni **mijoz boti ishlab, konsol oqimi o'lishi** kerak edi.
> Kuzatilgani esa buning teskarisi: `/start` jim, konsol ulanishi bir
> marta ishlagan. Buning bitta izohi bor — o'sha start'da mijoz
> `setWebhook` chaqiruvi RAD ETILGAN yoki tarmoqqa yetib bormagan,
> natijada admin webhook'i o'z joyida qolgan. Shuning uchun log'dan
> `setWebhook rad etildi` va `Mijoz webhook'i ro'yxatdan o'tkazilmadi`
> qatorlarini ham qidiring — ular WARNING darajasida yoziladi.

**KEYINGI QADAM:** Konsol → **Sozlamalar → Telegram botlari**
(`GET /platform/bots`). Ekran to'rt holatdan birini aniq aytadi:

- «Ikkala yuza ham bitta botga qaragan» → Render'da `ADMIN_BOT_TOKEN`
  ni **boshqa** bot tokeniga qo'ying (bu tekshiruv `dc03c9b` da
  qo'shildi);
- «Webhook o'rnatilmagan» → servisni qayta ishga tushiring (webhook
  faqat API start'ida ro'yxatdan o'tadi);
- «Token rad etildi» → Render'dagi qiymat noto'g'ri;
- «Ishlayapti» (ikkalasi, HAR XIL username) → sabab boshqa joyda,
  chuqurroq qidirish kerak.

---

## 3. Qat'iy qoidalar (buzilmaydi)

- **Pul** — `bigint`, so'm, kasrsiz. Float yo'q. JSON'da satr.
- **Vaqt** — DB'da UTC `timestamptz`, UI'da `Asia/Tashkent`.
  Hech qachon server yoki brauzer mahalliy vaqtiga tayanmang —
  doim `clubs.timezone` orqali.
- **Tenant izolyatsiyasi** — Postgres RLS. Qo'lda `where club_id`
  yozib chetlab o'tilmaydi.
- Yangi tenant-scoped jadval → **o'sha migratsiyada** `FORCE ROW
  LEVEL SECURITY` va `tenant_isolation` policy'si ham yoziladi.
- **Bron to'qnashuvi** — `bookings_no_overlap` EXCLUDE konstreyni,
  `23P01` → `409 SLOT_TAKEN`.
- Rang/spacing/typography — faqat dizayn tokenlari.
- `any` yo'q. Matn literal yo'q (i18n: uz/ru/en).
- **Migratsiyalar faqat oldinga** (`downgrade()` → `NotImplementedError`).

### Tegilmaydi

`packages/ui/src/tokens/**`, mavjud migratsiyalar, `.env`.

---

## 4. Qimmatga tushgan saboqlar

> Bu bo'lim eng qimmatli qismi. Har biri haqiqiy nosozlikdan chiqqan.

### 4.1 RLS — takroriy tuzoqlar manbai

**`FORCE ROW LEVEL SECURITY` jadval EGASIGA HAM tegishli.**
`SECURITY DEFINER` faqat `current_user`ni almashtiradi, RLS'ni
o'chirmaydi. Faqat superuser yoki `BYPASSRLS` qochadi.

**Migratsiyalardagi `_self_test()` lokalda UMUMAN ISHLAMAYDI.**
`_exempt()` (`rolsuper OR rolbypassrls`) lokal superuser'da `True`
qaytaradi va test butunlay o'tkazib yuboriladi. Render'da esa
ishlaydi va yiqilsa deploy to'xtaydi.

> **Deploy oldidan MAJBURIY:** `python api/scripts/check_render_shape.py`
> — u `NOSUPERUSER/NOBYPASSRLS` ega bilan toza bazada migratsiyalarni
> yurgizadi. Faqat shunda self-testlar haqiqatan sinaladi.

**Boshqa RLS tuzoqlari:**

- Policy ichida boshqa jadvalga `JOIN`/subquery bo'lsa — **o'sha
  jadval ham** GUC'ni bilishi kerak, aks holda jimgina bo'sh qaytadi.
- Postgres `UPDATE` uchun qatorni topish bosqichida **SELECT
  policy'sini ham** qo'llaydi. Faqat `FOR UPDATE` bersangiz, UPDATE
  0 qatorga tegadi.
- `GRANT` va `RLS` — **ikki alohida qatlam**. GRANT bor, policy yo'q
  → bo'sh ro'yxat (xato emas). GRANT yo'q → `permission denied`.
- `app_club_role()` ni `memberships` policy'lari ichida chaqirmang —
  rekursiya. `app.club_role` GUC ishlatiladi.
- Test fixture'lari `_owner_engine()` bilan xom yozadi — GUC'siz.
  `conftest.py::rls_bypass()` shuning uchun bor.

### 4.2 Zaxira va tiklash

- **`pg_dump` SUPERUSER bilan yurishi shart.** Aks holda:
  `ERROR: query would be affected by row-level security policy`.
- **`pg_dump` rollarni OLMAYDI** — ular klaster darajasida. Toza
  serverga tiklash `role "playbron_platform" does not exist` bilan
  yiqiladi. Shuning uchun har zaxira yonida `.roles.sql` saqlanadi
  (`pg_dumpall --roles-only`) va tiklashda **birinchi** u qo'llanadi.
- Zaxira tekshiruvida **RLS policy'lari soni** ham nazorat qilinadi —
  ular tushmasa tiklangan bazada izolyatsiya yo'q bo'ladi.

### 4.3 Deploy

- **Render'da frontend va API ALOHIDA deploy bo'ladi.** Statik sayt
  chiqib, API yiqilsa — tugma paydo bo'ladi, lekin endpoint yo'q
  (404). Aynan shu «xodim buyurtmani bekor qilolmadi» nosozligining
  sababi edi.
- **API deploy yiqilsa Render ESKI nusxani jonli qoldiradi** va
  `healthz` 200 qaytaraveradi — tashqaridan hammasi joyida ko'rinadi.
  Bir kun bo'yi hech bir push prod'ga yetib bormagani shundan.

### 4.4 Frontend qurish

- **Turbo 2 "strict" env rejimida**: `turbo.json` `globalEnv` da
  e'lon qilinmagan o'zgaruvchi task'ka **yetib bormaydi** va kesh
  kalitiga kirmaydi. `SITE_URL` shu sababdan jimgina tashlanardi.
  `VITE_*` ni Turbo o'zi taniydi (freymvork inference).
- Vite `VITE_*` ni **build paytida** kodga singdiradi — qiymat
  o'zgarsa qayta yig'ish shart.

### 4.5 Vaqt zonasi

Mijozning «bu vaqt band» degan yolg'on xatosi **ikki qatlamli** edi:
backend kun oynasini naive datetime bilan hisoblardi (asyncpg uni
konteyner OS zonasida talqin qiladi), frontend esa brauzer zonasiga
tayanardi. Ikkalasi ham endi `clubs.timezone` orqali.

### 4.6 Kichik, lekin vaqt yeydiganlar

- Qator oxirini tekshirganda **`git cat-file`** ishlating —
  `git show` `core.autocrlf` filtrini qo'llaydi va yolg'on CRLF
  ko'rsatadi.
- `.gitignore` dagi `.env.*` qoidasi `*.env.prod.example` kabi
  **namunalarni ham yutadi** (`!.env.*.example` kerak).
- Aborted-transaction xatosi **haqiqiy sababni yashiradi** —
  `--log-cli-level=INFO` bilan oldingi bayonotni qidiring.
- Test fixture'lari bazada qoldiq qoldirishi mumkin; teardown'da
  `audit_log` FK (`NO ACTION`) uchun `purge_audit_actor()` kerak.

---

## 5. Ish oqimi

### Lokal ishga tushirish

```bash
docker compose up -d          # postgres, redis, minio
cd api && python -m alembic upgrade head
pnpm dev                      # hamma app
```

### Tekshiruv (commit oldidan)

```bash
cd api
python -m ruff check .
python -m mypy src/
RUN_DB_TESTS=1 python -m pytest tests/ -q      # 169 test

cd ..
pnpm --filter admin exec tsc --noEmit
pnpm --filter admin exec eslint src
```

### Migratsiya qo'shgandan keyin — MAJBURIY

```bash
python api/scripts/check_render_shape.py
```

### VPS'ga deploy

`deploy/README.md` — to'liq tartib. Qisqacha:
`bootstrap.sh` → `.env.prod` to'ldirish → DNS → `deploy.sh` →
`backup/install.sh`.

---

## 6. Ochiq ishlar

| # | Ish | Izoh |
|---|---|---|
| 9 | Kalendar/vaqt tanlash komponenti | qo'lda bron uchun |
| 19 | `stations` ga floor/tv/pads ustunlari | yangi migratsiya |
| 21 | Mahsulot tannarxi + inventar modeli | eng kattasi |
| 23 | Tasdiqlangan o'lik mock kodni olib tashlash | |
| 25 | Ishga tushirish oldidan to'liq rol/ekran sinovi | |
| 42 | Kassa: chekni OCR bilan solishtirish (bepul) | boshlanmagan |
| 55 | Auditdan qolgan MEDIUM/LOW topilmalar | ro'yxat vazifada |
| 56 | Prod audit: Sentry, log formati, konteyner root, pinning | deploy'ni to'xtatmaydi |

---

## 7. Faqat loyiha egasi qila oladigan ishlar

1. **Telegram bot tokenlari** — @BotFather'dan olib, Render (yoki
   VPS `.env.prod`) ga qo'yish. Ikkalasi **har xil bot** bo'lishi
   shart, aks holda ikkinchi `setWebhook` birinchisini bosib ketadi.
   Tokenni almashtirgach servis **qayta ishga tushishi kerak** —
   webhook faqat start'da ro'yxatdan o'tadi.
2. **DNS** — Hetzner'ga o'tkazish (5 ta A yozuv).
3. **`deploy/.env.prod`** — barcha sirlarni to'ldirish
   (`openssl rand -hex 32`).
4. **Hetzner IPv4** — server IPv6-only bo'lsa o'zgartirish shart:
   O'zbekistonda IPv6 qamrovi juda past, aks holda ilova
   foydalanuvchilarga umuman ochilmaydi.
5. **Storage Box** — zaxiraning tashqi nusxasi uchun (~€3.20/oy).

---

## 8. Foydali fayllar

| Fayl | Nima uchun |
|---|---|
| `CLAUDE.md` | Loyiha qoidalari (avtomatik yuklanadi) |
| `docs/BUILD-BRIEF.md` | To'liq spetsifikatsiya |
| `docs/01-architecture.md` | Arxitektura |
| `docs/05-auth-redesign.md` | Autentifikatsiya dizayni (qadamlar tartibi muhim) |
| `deploy/README.md` | VPS'ga ko'chish |
| `deploy/backup/README.md` | Zaxira va tiklash |
| `api/scripts/check_render_shape.py` | Deploy oldidan majburiy tekshiruv |
