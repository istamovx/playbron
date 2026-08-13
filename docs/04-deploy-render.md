# Render'ga joylashtirish (vaqtinchalik muhit)

> Maqsad: haqiqiy HTTPS domen olish. Bu Telegram Login Widget va Mini App'ni
> ishlatishning yagona yo'li — Telegram `localhost` ni qabul qilmaydi.

## 1. Blueprint

Render Dashboard → **Blueprints** → **New Blueprint Instance** → `istamovx/playbron`.
`render.yaml` **to'rtta** resursni yaratadi — hammasi bepul rejada. Baza
Render'da emas — Supabase'da (2a-bo'lim):

| Resurs | Turi | Nomi | Reja |
|---|---|---|---|
| Redis | keyvalue | `playbron-redis` | `free` |
| API (Docker) | web | `playbron-api` | `free` |
| Konsol | static site | `playbron-admin` | bepul (CDN) |
| Mini App | static site | `playbron-miniapp` | bepul (CDN) |

Statik saytlarda `plan` yozilmagan — Render'da ular umuman bepul, server
sarflamaydi. Tasdiqlash oynasidagi umumiy summa **$0.00** bo'lishi kerak;
boshqa raqam chiqsa tasdiqlamang.

> **Region — eng ko'p xato shu yerda.** Redis va API `render.yaml` da `oregon`
> deb belgilangan va **ikkalasi bir xil bo'lishi shart**: Render'ning ichki
> tarmog'i regionlar orasida ishlamaydi.
>
> Region xizmat yaratilgandan keyin **o'zgarmaydi**. Yaml'ni tahrirlash mavjud
> xizmatni ko'chirmaydi — uni o'chirib qayta yaratish kerak. Shuning uchun
> region'ni birinchi urinishdayoq to'g'ri qo'yish muhim.

## 2a. Supabase — baza

Nega Render emas: bepul Render Postgres 90 kunda **o'chadi**, Supabase'niki
muddatsiz (500MB gacha). Bonus: Supabase `CREATE ROLE` ga ruxsat beradi, ya'ni
`0001_core` dagi `_create_roles()` haqiqatan ishlaydi va ilova `playbron_app`
(RLS ostidagi rol) bilan ulanadi — arxitektura aynan shunga mo'ljallangan.

1. [supabase.com](https://supabase.com) → **New project**. Region — **West US**
   (API Oregon'da, yaqinlik latensiya uchun muhim). Loyiha paroli — bu `postgres`
   egasining paroli, kuchli qiling.
2. Ikkita qo'shimcha parol o'ylab toping: `APP_DB_PASSWORD` va
   `PLATFORM_DB_PASSWORD`. **Faqat harf, raqam, `-`, `_`** — parol
   `DATABASE_URL` ichiga kiradi, boshqa belgi URL'ni buzadi; migratsiya
   validatori ham (`_safe_password`) qo'shtirnoq va nuqtali vergulni rad etadi.
3. Project Settings → Database → Connection string → **Session pooler**
   (port **5432**, transaction pooler 6543 emas!). Undan uch satr yasaladi —
   host bir xil, foydalanuvchi har xil (`rol.PROJECT_REF` formati):

   | Env | Foydalanuvchi | Parol |
   |---|---|---|
   | `DIRECT_URL` | `postgres.REF` | loyiha paroli |
   | `DATABASE_URL` | `playbron_app.REF` | `APP_DB_PASSWORD` |
   | `PLATFORM_DATABASE_URL` | `playbron_platform.REF` | `PLATFORM_DB_PASSWORD` |

4. Beshala qiymatni (uch URL + ikki parol) Render → `playbron-api` →
   **Environment** ga kiriting. Birinchi deployda migratsiya rollarni shu
   parollar bilan yaratadi, keyin uvicorn `playbron_app` bilan ulanadi.

Nega session pooler: bepul rejada to'g'ridan-to'g'ri host IPv6-only (Render'dan
ishlamasligi mumkin), transaction pooler esa asyncpg'ning prepared
statement'lari bilan chiqishmaydi. `SET LOCAL app.*` (RLS konteksti) session
pooler'da to'g'ri ishlaydi — u tranzaksiya doirasida yashaydi.

## 2. Qo'lda kiritiladigan o'zgaruvchilar

Faqat **ikkitasi** — ikkalasi ham sir, shuning uchun `render.yaml` ga yozilmaydi
(repo ochiq). Blueprint ularni yaratishda so'raydi.

### `playbron-api`

| Kalit | Qiymat |
|---|---|
| `BOT_TOKEN` | @playbronbot tokeni |
| `ADMIN_BOT_TOKEN` | @playbronadminbot tokeni |

Bunga qo'shimcha — Supabase'ga oid beshta qiymat (2a-bo'lim): `DATABASE_URL`,
`DIRECT_URL`, `PLATFORM_DATABASE_URL`, `APP_DB_PASSWORD`, `PLATFORM_DB_PASSWORD`.
Ular ham sir, ham qo'lda kiritiladi.

Qolgani avtomat:

- `JWT_SECRET`, `TG_WEBHOOK_SECRET` — Render `generateValue` bilan o'zi yasaydi
- `SUPER_ADMIN_TELEGRAM_IDS`, `CORS_ORIGINS` — `render.yaml` da qiymat sifatida turadi
- `REDIS_URL` — `fromService` orqali ichki manzil

### `playbron-admin` va `playbron-miniapp`

Hech narsa kiritilmaydi. `VITE_API_URL` `render.yaml` da turadi, shuning uchun
birinchi build'dayoq to'g'ri manzil bilan quriladi — **qayta deploy kerak emas**.

## 3. Telegram sozlamalari

@BotFather'da:

```
/setdomain  →  @playbronadminbot  →  playbron-admin.onrender.com
```

Shundan keyin konsoldagi Login Widget ishlaydi va lokal `dev` tugmasi
kerak bo'lmaydi (u prod build'da umuman ko'rinmaydi).

Mini App uchun:

```
/newapp yoki /myapps  →  @playbronbot  →  Web App URL: https://playbron-miniapp.onrender.com
```

## 4. Migratsiya

Konteyner har ishga tushganda `alembic upgrade head` bajaradi (Dockerfile'dagi
`CMD`). Bepul rejada alohida `preDeployCommand` yo'q, shuning uchun shunday.

**Super admin avtomat seed bo'ladi.** `SUPER_ADMIN_TELEGRAM_IDS` `render.yaml` da
turgani uchun `0002_seed` migratsiyasi uni birinchi deployda o'zi yaratadi —
bepul rejada Render Shell yo'q, shuning uchun bu ataylab shunday qilingan.

Ro'yxat **keyin** o'zgarsa (yangi super admin qo'shildi), `0002_seed` qayta
ishlamaydi. U holda `render.yaml` dagi qiymatni yangilab, Shell bor muhitda:

```
python scripts/seed_super_admins.py
```

Skript idempotent — mavjud yozuvga tegmaydi.

## 5. Bepul rejadagi cheklovlar

| Cheklov | Ta'siri |
|---|---|
| `BYPASSRLS` yo'q (Supabase'da ham — u superuser talab qiladi) | Super admin cross-tenant o'qishi ishlamaydi (Faza 7 da kerak bo'ladi) |
| Xizmat 15 daqiqa harakatsizlikdan keyin uxlaydi | Birinchi so'rov ~30 soniya kutadi. Hozircha UptimeRobot har 5 daqiqada **`/readyz`** ni ping qilib uyg'oq tutadi — `/readyz` Postgres'ga ham tegadi, ya'ni Supabase ham "faol" hisoblanadi. Bepul instans-soat budjeti ~750 soat/oy — bitta doim uyg'oq xizmatga zo'rg'a yetadi. Faza 6 da baribir pullik rejaga o'tish to'g'ri |
| Supabase bepul loyihasi 1 hafta faoliyatsizlikda pauza bo'ladi | Yuqoridagi `/readyz` ping'i buni ham yopadi — har 5 daqiqada bazaga `SELECT 1` boradi |

## 5a. API ko'tarilmasa — nimadan boshlash

Render → `playbron-api` → **Logs**. Ilova ataylab aniq xabar bilan to'xtaydi:

| Log'dagi xabar | Sabab | Yechim |
|---|---|---|
| `failed to resolve host 'red-…'` (yoki Redis timeout) | **Region nomuvofiqligi** — API Redis bilan boshqa regionda, ichki DNS hal bo'lmayapti | Pastga qarang |
| `new row violates row-level security policy for table "users"` | `FORCE ROW LEVEL SECURITY` jadval egasiga ham tegishli, migratsiya esa `app.*` GUC'larisiz yozmoqchi | `0002_seed` seed vaqtiga `FORCE` ni olib turadi. Xato qaytsa — eski image ishlayapti, qayta deploy |
| `CORS_ORIGINS prod uchun sozlanmagan (localhost qolgan)` | `render.yaml` dagi qiymat yo'qolgan yoki dashboard'da qo'lda o'zgartirilgan | `render.yaml` dagi qiymatni tiklab, qayta sync qilish |
| `BOT_TOKEN prod uchun majburiy` | Token kiritilmagan (yagona qo'lda qiymat) | @BotFather'dan olib Environment'ga qo'yish |
| `TG_WEBHOOK_SECRET prod uchun majburiy` | Render generatsiya qilmagan | Qo'lda tasodifiy satr qo'yish |
| `JWT_SECRET kamida 32 bayt` | Qisqa qiymat kiritilgan | `openssl rand -hex 32` |
| `DEBUG prod'da yoqilgan bo'lmasligi kerak` | `DEBUG=true` qolgan | `false` qilish |

Belgilar: TLS ulanadi, lekin HTTP javob umuman kelmaydi (`curl` da `status=000`) —
konteyner start'da yiqilyapti yoki migratsiya bazaga ulanolmay kutyapti.

### Region nomuvofiqligini tuzatish

Ichki qisqa manzillar (`red-…`) faqat Render'ning ichki tarmog'ida, va faqat
**bir xil region ichida** hal bo'ladi. Redis'da `ipAllowList: []` turgani uchun
tashqi manzil varianti umuman yo'q — region mos bo'lishi shart.

1. `playbron-redis` va `playbron-api` ning Settings → Region qiymatini solishtiring
2. Qaysi biri boshqacha bo'lsa — o'shani **o'chirib qayta yarating**. Odatda bu
   API bo'ladi: u stateless
3. Blueprints → **Manual Sync** — o'chirilgan xizmat `render.yaml` dagi region
   bilan qaytadan yaratiladi
4. Qo'lda kiritilgan qiymatlarni qayta kiriting — ular xizmat bilan birga o'chadi:
   `BOT_TOKEN`, `ADMIN_BOT_TOKEN` va Supabase'ning beshta qiymati (2a-bo'lim).
   `JWT_SECRET`/`TG_WEBHOOK_SECRET` avtomat qayta yasaladi

Supabase baza tashqi internetda — unga region ta'sir qilmaydi, faqat latensiya
(shuning uchun West US tanlangan).

### Nega RLS xatolari lokalda chiqmaydi

Bu tuzoqni bilib qo'ying: `docker-compose` da `playbron` roli `POSTGRES_USER`
orqali yaratiladi, ya'ni u **superuser**. Superuser RLS'ni butunlay chetlab
o'tadi — `FORCE` ham unga ta'sir qilmaydi.

Boshqariladigan hostingda esa migratsiya yuritadigan rol oddiy **ega** (owner),
superuser emas — Supabase'dagi `postgres` ham shunday. `FORCE ROW LEVEL SECURITY`
egaga tatbiq etiladi, shuning uchun lokalda muammosiz o'tgan migratsiya yoki
skript prod'da bloklanishi mumkin.

Xulosa: RLS bilan bog'liq har qanday yozuv amalini lokal sinov **tasdiqlamaydi**.
Migratsiya `users`, `super_admins` yoki boshqa `FORCE` li jadvalga yozsa, u
`app.*` GUC'larini o'rnatishi yoki seed vaqtiga `NO FORCE` qilishi shart.

## 6. Tekshirish

```
GET https://playbron-api.onrender.com/healthz    → {"status":"ok"}
GET https://playbron-api.onrender.com/readyz     → postgres/redis "ok"
```

Konsol: `https://playbron-admin.onrender.com` → Telegram tugmasi ko'rinishi kerak.

## 7. Keyingi qadam — o'z domeni

`playbron.uz` tayyor bo'lganda:

1. Render → `playbron-admin` → Custom Domain → `app.playbron.uz`
2. `playbron-miniapp` → `mini.playbron.uz`
3. `playbron-api` → `api.playbron.uz`
4. @BotFather `/setdomain` ni yangilash
5. `render.yaml` dagi `CORS_ORIGINS` va ikkala `VITE_API_URL` ni yangi domenga
   o'zgartirib commit qilish — ular endi dashboard'da emas, yaml'da turadi
6. Statik saytlarni qayta deploy qilish (Vite `VITE_API_URL` ni build paytida
   kodga singdiradi, shuning uchun yangi qiymat faqat yangi build'da kuchga kiradi)
