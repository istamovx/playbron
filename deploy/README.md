# PlayBron — Hetzner VPS'ga joylashtirish

Render'dan ko'chish uchun to'liq konfiguratsiya: Docker Compose, Caddy
(avtomatik HTTPS), deploy skriptlari va zaxira.

## Nima o'zgaradi (Render → VPS)

| | Render | Hetzner VPS |
|---|---|---|
| Baza rollari | **bitta** (bepul rejada `CREATE ROLE` yo'q) | **uchta, ajratilgan** |
| `staff_credentials` | ilova roliga ko'rinardi | ilova rolidan **yopiq** |
| HTTPS | Render beradi | Caddy o'zi oladi/yangilaydi |
| Zaxira | Render zimmasida | **bizda** (`backup/`) |
| Migratsiya | har deployda avtomatik | deploy skriptida, **alohida qadam** |

Eng muhim yutuq — **rollar ajratildi**. Render bepul rejasida ilova baza
egasi bilan ulanardi va `ALLOW_SINGLE_DB_ROLE=1` shu cheklovni oshkora
qabul qilardi. O'z serverimizda superuser bor, ya'ni `0001_core.py`
`playbron_app` va `playbron_platform` rollarini to'liq yarata oladi va
parol xeshlari ilova rolidan yashiriladi.

> **`ALLOW_SINGLE_DB_ROLE` ni bu yerda QO'YMANG.** U qo'yilsa himoya
> qatlami keraksiz yo'qoladi.

## Fayllar

```
deploy/
  bootstrap.sh              serverni bir marta tayyorlaydi (docker, firewall, swap)
  deploy.sh                 yangi versiyani chiqaradi
  build-web.sh              frontendni konteynerda yig'adi -> www/
  docker-compose.prod.yml   prod stack
  Caddyfile                 teskari proksi + avtomatik HTTPS
  .env.prod.example         sozlama shabloni
  backup/                   zaxira tizimi (alohida README)
```

## O'rnatish

### 1. Server

```bash
ssh root@<server-ip>
apt-get update && apt-get install -y git
git clone <repo-url> /opt/playbron
cd /opt/playbron/deploy && ./bootstrap.sh
```

`bootstrap.sh`: Docker, `ufw` (faqat 22/80/443), 2 GB swap, Asia/Tashkent
vaqt zonasi, avtomatik xavfsizlik yangilanishlari.

### 2. Sozlama

```bash
cp deploy/.env.prod.example deploy/.env.prod
chmod 600 deploy/.env.prod
nano deploy/.env.prod
```

Har bir parol/sekret uchun **alohida** tasodifiy qiymat:

```bash
openssl rand -hex 32
```

To'ldirish shart: `DB_OWNER_PASSWORD`, `APP_DB_PASSWORD`,
`PLATFORM_DB_PASSWORD`, `JWT_SECRET`, `TG_WEBHOOK_SECRET`, `BOT_TOKEN`,
`ADMIN_BOT_TOKEN`.

### 3. DNS

Beshta A yozuv serverga qaratiladi:

```
playbron.uz   www   app   mini   api   →   <server-ip>
```

**Tarqalganini tekshiring** — DNS kelmasdan Caddy sertifikat ololmaydi:

```bash
for h in playbron.uz www.playbron.uz app.playbron.uz mini.playbron.uz api.playbron.uz; do
  echo "$h -> $(dig +short "$h")"
done
```

### 4. Ishga tushirish

```bash
cd /opt/playbron/deploy && ./deploy.sh
```

### 5. Zaxira

```bash
cd /opt/playbron/deploy/backup && ./install.sh
```

## Kundalik ish

```bash
cd /opt/playbron/deploy
C="docker compose -f docker-compose.prod.yml --env-file .env.prod"

./deploy.sh              # yangi versiya
$C ps                    # holat
$C logs -f api           # loglar
$C restart api           # qayta ishga tushirish
```

## Ko'chish tartibi (uzilishsiz)

DNS'ni oxirida o'tkazing — shunda Render ishlab turaveradi:

1. Serverni tayyorlang va `deploy.sh` ni yurgizing.
   Sertifikat olish uchun DNS kerak, shuning uchun avval **bitta** yozuvni
   (masalan `api2.playbron.uz`) sinov uchun qarating yoki `/etc/hosts`
   bilan tekshiring.
2. **Ma'lumotni ko'chiring** — Render bazasidan dump olib, yangisiga tiklang:
   ```bash
   # Render dashboard'dan External Database URL oling
   docker run --rm postgres:16-alpine pg_dump -Fc "<render-external-url>" > /tmp/render.dump
   cd /opt/playbron/deploy/backup
   playbron-restore.sh /tmp/render.dump
   ```
3. Ikkala tomonda ham tekshiring: kirish, bron, kassa.
4. DNS TTL'ni pasaytiring (300s), keyin yozuvlarni yangi IP'ga o'tkazing.
5. Telegram webhook'lari yangi manzilga o'tishi uchun API'ni qayta ishga
   tushiring (`PUBLIC_URL` allaqachon `api.playbron.uz`), so'ng
   **Sozlamalar → Telegram botlari** ekranida holatni tekshiring.
6. Render xizmatlarini bir necha kun **to'xtatib** turing (o'chirmang) —
   muammo chiqsa DNS'ni qaytarish mumkin bo'lsin.

## Diqqat qilinadigan joylar

**Sertifikat.** Caddy `caddydata` volumida saqlaydi. Volumeni o'chirsangiz
sertifikat qaytadan olinadi — Let's Encrypt haftalik chegarasi bor
(bir domenga 5 ta muvaffaqiyatsiz urinish/soat). Sinash uchun
`Caddyfile` dagi `acme_ca` staging qatorini yoqing.

**Portlar.** `docker-compose.prod.yml` da Postgres va Redis portlari
**ochilmagan**. Ildizdagi dev `docker-compose.yml` da esa ochiq — uni
serverda ISHLATMANG.

**Migratsiya.** `deploy.sh` uni API'dan oldin, alohida bir martalik
konteynerda yurgizadi. Yiqilsa deploy to'xtaydi va **eski nusxa ishlab
turaveradi**.

**Zaxira `pg_dump` roli.** SUPERUSER bo'lishi shart — `FORCE RLS` egaga
ham tegishli. Tafsilot: `backup/README.md`.

**`SUPER_ADMIN_PASSWORD`.** Ishlatib bo'lgach `.env.prod` dan
**o'chiring** — aks holda parol serverdagi faylda ochiq turaveradi.
Standart yo'l: `api/scripts/set_staff_password.py`.
