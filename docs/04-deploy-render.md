# Render'ga joylashtirish (vaqtinchalik muhit)

> Maqsad: haqiqiy HTTPS domen olish. Bu Telegram Login Widget va Mini App'ni
> ishlatishning yagona yo'li — Telegram `localhost` ni qabul qilmaydi.

## 1. Blueprint

Render Dashboard → **Blueprints** → **New Blueprint Instance** → `istamovx/playbron`.
`render.yaml` to'rtta resursni yaratadi:

| Resurs | Turi | Nomi |
|---|---|---|
| PostgreSQL 16 | database | `playbron-db` |
| Redis | keyvalue | `playbron-redis` |
| API (Docker) | web | `playbron-api` |
| Konsol (statik) | web | `playbron-admin` |
| Mini App (statik) | web | `playbron-miniapp` |

## 2. Qo'lda kiritiladigan o'zgaruvchilar

Blueprint ularni so'raydi (`sync: false`).

### `playbron-api`

| Kalit | Qiymat |
|---|---|
| `BOT_TOKEN` | @playbronbot tokeni |
| `ADMIN_BOT_TOKEN` | @playbronadminbot tokeni |
| `SUPER_ADMIN_TELEGRAM_IDS` | `611207125` |
| `CORS_ORIGINS` | `https://playbron-admin.onrender.com,https://playbron-miniapp.onrender.com` |

`JWT_SECRET` va `TG_WEBHOOK_SECRET` — Render o'zi yasaydi, tegilmaydi.

### `playbron-admin` va `playbron-miniapp`

| Kalit | Qiymat |
|---|---|
| `VITE_API_URL` | `https://playbron-api.onrender.com/api/v1` |

Manzillar birinchi deploydan keyin ma'lum bo'ladi — o'zgaruvchini kiritib,
statik saytlarni **qayta deploy** qilish kerak (Vite qiymatni build paytida
kodga singdiradi).

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

**Super adminni seed qilish** — birinchi deploydan keyin bir marta,
Render Shell'da:

```
python scripts/seed_super_admins.py
```

## 5. Bepul rejadagi cheklovlar

| Cheklov | Ta'siri |
|---|---|
| `CREATE ROLE` huquqi yo'q | `playbron_app` va `playbron_platform` rollari yaratilmaydi; ilova baza egasi roli bilan ulanadi. **RLS baribir ishlaydi** — jadvallarga `FORCE ROW LEVEL SECURITY` qo'llangan, u egaga ham tegishli |
| `BYPASSRLS` yo'q | Super admin cross-tenant o'qishi ishlamaydi (Faza 7 da kerak bo'ladi) |
| Xizmat 15 daqiqa harakatsizlikdan keyin uxlaydi | Birinchi so'rov ~30 soniya kutadi. Telegram webhook uchun bu muammo — Faza 6 da pullik rejaga o'tish yoki tashqi ping kerak |
| Postgres 90 kundan keyin o'chadi | Vaqtinchalik muhit; prod uchun boshqa reja |

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
5. `CORS_ORIGINS` va `VITE_API_URL` ni yangilash
