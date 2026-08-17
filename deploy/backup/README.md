# PlayBron — zaxira tizimi (Hetzner)

Kunlik `pg_dump`, tekshiruv, tashqi nusxa, eskisini tozalash va yiqilganda
Telegram xabari.

## Nega bunday qurilgan

Render'da baza **boshqariladigan** edi — zaxira Render zimmasida. Hetzner'da
bu butunlay sizga o'tadi. Shu sababli bu yerda uchta narsa ataylab bor:

| Qadam | Nega |
|---|---|
| **Tekshiruv** | Tekshirilmagan zaxira — zaxira emas. Skript `pg_restore --list` bilan arxivni to'liq o'qiydi, asosiy jadvallar **va RLS policy'lari** borligini talab qiladi (policy'lar tushmasa tiklangan bazada tenant izolyatsiyasi yo'q bo'ladi va buni hech kim sezmaydi). |
| **Rollar alohida** | `pg_dump` faqat bitta bazani oladi, rollar esa klaster darajasida. Ularsiz toza serverga tiklash `role "playbron_platform" does not exist` bilan yiqiladi — ya'ni aynan falokat paytida zaxira ishlamaydi. Har bir zaxira yonida `.roles.sql` saqlanadi. |
| **Tashqi nusxa** | Serverning O'ZIDAGI zaxira — zaxira emas. Disk ishdan chiqsa u ham ketadi. |
| **Yiqilganda xabar** | Jimgina to'xtagan zaxira eng yomoni: buni faqat tiklash kerak bo'lganda bilasiz. |

## MUHIM: qaysi rol bilan

`pg_dump` **SUPERUSER** (yoki `BYPASSRLS`) roli bilan yurishi **shart**.

Loyihada `FORCE ROW LEVEL SECURITY` yoqilgan va u jadval **egasiga ham**
tegishli. `pg_dump` ma'lumotni to'liq olish uchun `SET row_security = off`
qiladi — buni faqat superuser uddalaydi. Oddiy `playbron_app` roli bilan
zaxira quyidagicha yiqiladi (sinab ko'rilgan):

```
pg_dump: error: query failed: ERROR: query would be affected by
row-level security policy for table "users"
```

Ya'ni bo'sh zaxira **emas** — ochiq xato. Lekin baribir zaxira bo'lmaydi.
`docker-compose.yml` dagi `POSTGRES_USER` konteyner klasterining superuseri.

## O'rnatish

```bash
cd /opt/playbron/deploy/backup
sudo ./install.sh
sudo nano /etc/playbron/backup.env
sudo playbron-backup.sh          # birinchi zaxirani QO'LDA sinang
```

### Tashqi nusxa (Hetzner Storage Box)

Storage Box — oyiga ~€3.20 (1 TB). Zaxira uchun aynan mos.

```bash
ssh-keygen -t ed25519 -f /root/.ssh/playbron_backup -N ''
ssh-copy-id -p 23 -i /root/.ssh/playbron_backup u123456@u123456.your-storagebox.de
ssh -p 23 -i /root/.ssh/playbron_backup u123456@u123456.your-storagebox.de mkdir -p daily weekly monthly
```

So'ng `backup.env` da:

```
REMOTE_TARGET=u123456@u123456.your-storagebox.de:/home
REMOTE_SSH_PORT=23
```

### Shifrlash (ixtiyoriy)

Zaxirada mijoz ismi va telefon raqami bor. Tashqariga chiqarilsa
shifrlangani ma'qul:

```bash
apt-get install -y age
age-keygen -o /root/.config/playbron-age.key   # "Public key: age1..." chiqadi
chmod 600 /root/.config/playbron-age.key
```

Ochiq kalitni `AGE_PUBLIC_KEY` ga yozing.

> **Maxfiy kalitni yo'qotsangiz zaxirani ochib bo'lmaydi.** Uni serverdan
> TASHQARIDA ham saqlang (parol menejeri, qog'oz).

## Kundalik ishlatish

```bash
systemctl list-timers playbron-backup     # keyingi yurish qachon
journalctl -u playbron-backup -n 50       # oxirgi yurish natijasi
systemctl start playbron-backup           # hoziroq bir marta
ls -lh /var/backups/playbron/daily/       # mavjud zaxiralar
```

Jadval: har kuni **23:00 UTC = 04:00 Toshkent** (klublar yopilgandan keyin).
Server o'chiq bo'lsa — yoqilishi bilan o'tkazib yuborilgani bajariladi
(`Persistent=true`).

Saqlash muddati: 14 kunlik, 8 haftalik, 6 oylik nusxa.

## Tiklash

```bash
# MASHQ — ishlayotgan bazaga tegmaydi
playbron-restore.sh --into playbron_sinov /var/backups/playbron/daily/<fayl>

# HAQIQIY tiklash — joriy bazani almashtiradi
playbron-restore.sh /var/backups/playbron/daily/<fayl>
```

Haqiqiy tiklashda skript avval **joriy holatni** alohida faylga dump
qiladi — noto'g'ri zaxira tanlansa qaytib kelish uchun.

### Oyiga bir marta mashq qiling

Bu eng muhim odat. Tiklab ko'rilmagan zaxira — hali zaxira emas.

```bash
playbron-restore.sh --into playbron_sinov /var/backups/playbron/daily/<eng-yangisi>
docker compose exec postgres psql -U playbron -d playbron_sinov \
  -c "SELECT count(*) FROM bookings;" \
  -c "SELECT count(*) FROM pg_policies WHERE schemaname='public';"
docker compose exec postgres psql -U playbron -d postgres \
  -c "DROP DATABASE playbron_sinov WITH (FORCE);"
```

RLS policy'lar soni jonli baza bilan bir xil bo'lishi kerak — aks holda
tiklangan bazada tenant izolyatsiyasi buzilgan bo'ladi.

## Sinovdan o'tgani

Lokal muhitda uchidan-uchiga tekshirilgan (2026-08-17):

- `pg_dump` → tekshiruv → saqlash → tozalash — ishladi (172 KB, 443 obyekt)
- toza bazaga to'liq tiklandi
- **67 ta RLS policy** va **23 ta `FORCE RLS` jadval** saqlanib qoldi
- `alembic_version` to'g'ri tiklandi

## Nima zaxiralanMAYDI

- **Redis** — kesh va chegaralagich sanagichlari; yo'qolsa o'zi tiklanadi.
- **MinIO** — hozircha ishlatilmayapti (rasmlar Telegram'da, bazada faqat
  `file_id` saqlanadi).
- **`.env` va sirlar** — bularni alohida, parol menejerida saqlang.
  Zaxirada ular YO'Q.
