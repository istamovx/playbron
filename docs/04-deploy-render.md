# Render'ga joylashtirish (vaqtinchalik muhit)

> Maqsad: haqiqiy HTTPS domen olish. Bu Telegram Login Widget va Mini App'ni
> ishlatishning yagona yo'li — Telegram `localhost` ni qabul qilmaydi.

## 1. Blueprint

Render Dashboard → **Blueprints** → **New Blueprint Instance** → `istamovx/playbron`.
`render.yaml` **beshta** resursni yaratadi — hammasi bepul rejada:

| Resurs | Turi | Nomi | Reja |
|---|---|---|---|
| PostgreSQL 16 | database | `playbron-db` | `free` |
| Redis | keyvalue | `playbron-redis` | `free` |
| API (Docker) | web | `playbron-api` | `free` |
| Konsol | static site | `playbron-admin` | bepul (CDN) |
| Mini App | static site | `playbron-miniapp` | bepul (CDN) |

Statik saytlarda `plan` yozilmagan — Render'da ular umuman bepul, server
sarflamaydi. Tasdiqlash oynasidagi umumiy summa **$0.00** bo'lishi kerak;
boshqa raqam chiqsa tasdiqlamang.

> **Region — eng ko'p xato shu yerda.** Baza, Redis va API `render.yaml` da
> `oregon` deb belgilangan va **uchalasi bir xil bo'lishi shart**: Render'ning
> ichki tarmog'i regionlar orasida ishlamaydi.
>
> Region xizmat yaratilgandan keyin **o'zgarmaydi**. Yaml'ni tahrirlash mavjud
> xizmatni ko'chirmaydi — uni o'chirib qayta yaratish kerak. Shuning uchun
> region'ni birinchi urinishdayoq to'g'ri qo'yish muhim.

## 2. Qo'lda kiritiladigan o'zgaruvchilar

Faqat **ikkitasi** — ikkalasi ham sir, shuning uchun `render.yaml` ga yozilmaydi
(repo ochiq). Blueprint ularni yaratishda so'raydi.

### `playbron-api`

| Kalit | Qiymat |
|---|---|
| `BOT_TOKEN` | @playbronbot tokeni |
| `ADMIN_BOT_TOKEN` | @playbronadminbot tokeni |

Qolgani avtomat:

- `JWT_SECRET`, `TG_WEBHOOK_SECRET`, `APP_DB_PASSWORD`, `PLATFORM_DB_PASSWORD` —
  Render `generateValue` bilan o'zi yasaydi. Oxirgi ikkitasi `playbron_app` /
  `playbron_platform` rollarining parollari: bo'lmasa `0001_core` zaif sukut
  ("app"/"platform") ishlatardi, `0004_role_passwords` esa mavjud rollarning
  parolini shu qiymatlarga almashtiradi
- `SUPER_ADMIN_TELEGRAM_IDS`, `CORS_ORIGINS` — `render.yaml` da qiymat sifatida turadi
- `DATABASE_URL`, `DIRECT_URL`, `PLATFORM_DATABASE_URL`, `REDIS_URL` — `fromDatabase` / `fromService`

### `playbron-admin` va `playbron-miniapp`

Hech narsa kiritilmaydi. `VITE_API_URL` `render.yaml` da turadi, shuning uchun
birinchi build'dayoq to'g'ri manzil bilan quriladi — **qayta deploy kerak emas**.

## 3. Telegram sozlamalari

**Konsol kirishi uchun @BotFather'da hech narsa sozlash shart emas.** Kirish
bot-start oqimi bilan ishlaydi: tugma `tg://resolve?domain=…&start=<nonce>`
deep-link bilan Telegram ilovasini ochadi, foydalanuvchi botda **Start**
bosadi, webhook tasdiqlaydi, konsol poll qilib sessiya oladi. `/setdomain`
faqat Login Widget uchun kerak edi — u endi ishlatilmaydi.

**Webhook avtomatik ro'yxatdan o'tadi.** API har start'da (env=prod bo'lsa)
`setWebhook` ni o'zi chaqiradi: manzil — `RENDER_EXTERNAL_URL` (Render o'zi
beradi) + `/api/v1/auth/telegram/webhook/admin`, sekret — `TG_WEBHOOK_SECRET`.
Buning uchun `ADMIN_BOT_TOKEN` kiritilgan bo'lishi kerak. Natija log'da:
`Admin bot webhook: …` yoki sabab bilan ogohlantirish.

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

### Rol parollari (xavfsizlik)

`0001_core` rollarni `APP_DB_PASSWORD` / `PLATFORM_DB_PASSWORD` env'laridan
yaratadi; env bo'lmasa sukut "app"/"platform" ishlatiladi. Avval `render.yaml`
da bu env'lar yo'q edi — jonli bazadagi LOGIN rollari zaif parol bilan qolgan.
Endi ikkalasi `generateValue: true` bilan turadi va `0004_role_passwords`
har deployda mavjud rollarning parolini env'dagi qiymatga tenglashtiradi
(env bo'sh bo'lsa — lokal dev — rol tegilmaydi).

Bazaga tashqi kirish ham yopildi: `render.yaml` da `playbron-db` uchun
`ipAllowList: []` turibdi, ya'ni bazaga faqat Render ichki tarmog'i (API
konteyner) yetadi. Tashqaridan `psql` kerak bo'lib qolsa — Dashboard →
`playbron-db` → Access Control'da yoki yaml'dagi ro'yxatga o'z IP'ingizni
**vaqtincha** qo'shib Manual Sync qilasiz, ish tugagach olib tashlaysiz.

Mavjud Blueprint instansiyada bu o'zgarishlar o'z-o'zidan qo'llanmaydi:
Blueprints → **Manual Sync** — yangi env'lar yasaladi va `ipAllowList`
qo'llanadi, keyingi deploy'da `0004` parollarni almashtiradi.

## 5. Bepul rejadagi cheklovlar

| Cheklov | Ta'siri |
|---|---|
| `CREATE ROLE` huquqi yo'q | `playbron_app` va `playbron_platform` rollari yaratilmaydi; ilova baza egasi roli bilan ulanadi. **RLS baribir ishlaydi** — jadvallarga `FORCE ROW LEVEL SECURITY` qo'llangan, u egaga ham tegishli |
| `BYPASSRLS` yo'q | Super admin cross-tenant o'qishi ishlamaydi (Faza 7 da kerak bo'ladi) |
| Xizmat 15 daqiqa harakatsizlikdan keyin uxlaydi | Birinchi so'rov ~30 soniya kutadi. Telegram webhook uchun bu muammo — Faza 6 da pullik rejaga o'tish yoki tashqi ping kerak |
| Postgres 90 kundan keyin o'chadi | Vaqtinchalik muhit; prod uchun boshqa reja |

## 5a. API ko'tarilmasa — nimadan boshlash

Render → `playbron-api` → **Logs**. Ilova ataylab aniq xabar bilan to'xtaydi:

| Log'dagi xabar | Sabab | Yechim |
|---|---|---|
| `failed to resolve host 'dpg-…'` (alembic traceback bilan) | **Region nomuvofiqligi** — API baza bilan boshqa regionda, ichki DNS hal bo'lmayapti | Pastga qarang |
| `new row violates row-level security policy for table "users"` | `FORCE ROW LEVEL SECURITY` jadval egasiga ham tegishli, migratsiya esa `app.*` GUC'larisiz yozmoqchi | `0002_seed` seed vaqtiga `FORCE` ni olib turadi. Xato qaytsa — eski image ishlayapti, qayta deploy |
| `CORS_ORIGINS prod uchun sozlanmagan (localhost qolgan)` | `render.yaml` dagi qiymat yo'qolgan yoki dashboard'da qo'lda o'zgartirilgan | `render.yaml` dagi qiymatni tiklab, qayta sync qilish |
| `BOT_TOKEN prod uchun majburiy` | Token kiritilmagan (qo'lda kiritiladigan qiymat) | @BotFather'dan olib Environment'ga qo'yish |
| `ADMIN_BOT_TOKEN prod uchun majburiy` | @playbronadminbot tokeni kiritilmagan — usiz konsol Login Widget imzosi doim `401 WIDGET_BAD_SIGNATURE` berardi | @BotFather'dan olib Environment'ga qo'yish |
| `TG_WEBHOOK_SECRET prod uchun majburiy` | Render generatsiya qilmagan | Qo'lda tasodifiy satr qo'yish |
| `JWT_SECRET kamida 32 bayt` | Qisqa qiymat kiritilgan | `openssl rand -hex 32` |
| `DEBUG prod'da yoqilgan bo'lmasligi kerak` | `DEBUG=true` qolgan | `false` qilish |

Belgilar: TLS ulanadi, lekin HTTP javob umuman kelmaydi (`curl` da `status=000`) —
konteyner start'da yiqilyapti yoki migratsiya bazaga ulanolmay kutyapti.

### Region nomuvofiqligini tuzatish

Log'da `psycopg.OperationalError: failed to resolve host 'dpg-…-a'` chiqsa, bu
baza o'chganini **anglatmaydi** — qisqa `dpg-…-a` manzili faqat Render'ning ichki
tarmog'ida, va faqat **bir xil region ichida** hal bo'ladi.

1. Har bir xizmatning Settings → Region qiymatini solishtiring (`playbron-db`,
   `playbron-redis`, `playbron-api`)
2. Qaysi biri boshqacha bo'lsa — o'shani **o'chirib qayta yarating**. Odatda bu
   API bo'ladi: u stateless, baza esa ma'lumot saqlaydi
3. Blueprints → **Manual Sync** — o'chirilgan xizmat `render.yaml` dagi region
   bilan qaytadan yaratiladi
4. `BOT_TOKEN` va `ADMIN_BOT_TOKEN` ni qayta kiriting — ular xizmat bilan birga
   o'chadi. `JWT_SECRET`/`TG_WEBHOOK_SECRET` avtomat qayta yasaladi

Bazaning tashqi manzili (`dpg-…-a.oregon-postgres.render.com`) ham yechim emas:
bazada va Redis'da `ipAllowList: []` turibdi — ikkalasi ham faqat ichki tarmoqda,
boshqa regiondagi ilova ularga baribir ulanolmaydi.

### Nega RLS xatolari lokalda chiqmaydi

Bu tuzoqni bilib qo'ying: `docker-compose` da `playbron` roli `POSTGRES_USER`
orqali yaratiladi, ya'ni u **superuser**. Superuser RLS'ni butunlay chetlab
o'tadi — `FORCE` ham unga ta'sir qilmaydi.

Render'ning bepul rejasida esa bu rol oddiy **ega** (owner). `FORCE ROW LEVEL
SECURITY` egaga tatbiq etiladi, shuning uchun lokalda muammosiz o'tgan migratsiya
yoki skript prod'da bloklanishi mumkin.

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
