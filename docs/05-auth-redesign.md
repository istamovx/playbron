# 05 — Auth qayta qurilishi: ikki dunyo

> **Holat:** yakuniy dizayn. Amalga oshirishga tayyor.
> **O'rnini bosadi:** `docs/01-architecture.md` §2 («Identity va auth») va
> `docs/design-change-requests.md` dagi DCR-001, DCR-002, DCR-003, DCR-004.
> **Asos:** «Ikki dunyo auth» dizayni (`0005_two_worlds_auth`), unga raqobatchi
> dizaynlarning tuzilmaviy va ergonomik yechimlari singdirilgan.
> **Til:** hujjat o'zbekcha; mahsulot matnlari uz/ru (DCR-007 bajariladi).

Bu hujjat kod emas. Har bir sonli qiymat yonida **sabab** turadi. Telegram Bot API
ning aniq metod nomlari, maydonlari va imzo formulalari `[TEKSHIRISH]` belgisi bilan
ko'rsatilgan — ular **rasmiy hujjatdan** olinadi, xotiradan yozilmaydi.

---

## 1. Qaror va sabab

### 1.1 Qaror

Autentifikatsiya **ikkita mustaqil dunyoga** bo'linadi:

| | Mijoz dunyosi | Xodim dunyosi |
|---|---|---|
| Kim | CUSTOMER | STAFF, ADMIN, OWNER, SUPER_ADMIN |
| Identifikator | `telegram_id` | `login` |
| Sir | yo'q (Telegram imzosi) | Argon2id parol |
| Telegram roli | **identifikatsiya** | faqat **yetkazish kanali** (OTP, bildirishnoma) |
| Kirish yuzasi | Mini App, ekransiz | Konsol, login+parol formasi |
| Ro'yxatdan o'tish | butunlay `@playbronbot` ichida | taklif + konsol |

Ikki dunyo **bitta `users` jadvalini bo'lishadi**, lekin o'zgarmas `kind`
diskriminatori bilan ajratiladi va bu ajratish uch qatlamda majburlanadi:
DB konstreyntlari → RLS policy'lari → JWT klaymi. Bitta qatlam unutilsa qolgan
ikkitasi ushlab qoladi.

### 1.2 Nega bitta `users` jadvali

`users` ni ikkiga bo'lish (`users` + `staff_accounts`) rad etildi. Beshta
tashqi kalit unga tayanadi — `memberships.user_id`, `memberships.invited_by`,
`super_admins.user_id`, `organizations.owner_user_id`, `refresh_tokens.user_id`,
`audit_log.actor_user_id` — va `0001_core.py` dagi `app_user_id()`,
`0003_rls_hardening.py` dagi `app_club_role()` shu bitta identifikatorga qurilgan.
Ajratish quyidagilarni keltirib chiqarardi:

- oltita FK polimorf bo'lib qolardi (referensial yaxlitlik yo'qoladi) yoki ikkiga
  ko'payardi;
- har bir RLS policy'sining ikki varianti yozilardi;
- `service.sign_in`, `rotate_refresh`, `_to_session` ikki nusxaga bo'linardi.

Diskriminator + kompozit FK bir xil kafolatni sezilarli arzonroq beradi.

### 1.3 Nega parol qaytadi

`docs/01-architecture.md` §2 dagi «Parol yo'q, email yo'q» qoidasi mijoz uchun
to'g'ri va **saqlanadi**. Xodim uchun u ish sharoitiga to'g'ri kelmaydi:

1. **Smena boshidagi tezlik.** Kassachi kuniga bir necha marta konsolga kiradi.
   Telegram deep-link + poll oqimi har safar ilova almashtirishni talab qiladi.
2. **Telegramga qattiq bog'liqlik.** Telefoni tugagan, internet yo'q yoki
   akkaunt bloklangan xodim ishlay olmasligi qabul qilinmaydi.
3. **Bot birinchi yozolmaydi.** Telegram cheklovi tufayli xodimga OTP yuborish
   uchun u **oldin** botni `/start` qilgan bo'lishi shart. Bu cheklov aynan
   identifikatsiya kanalida turgani uchun tiklashni ham sindiradi.

Shuning uchun xodim uchun **parol — birlamchi omil**, Telegram — ikkinchi omil va
tiklash kanali. Mijoz uchun **Telegram — yagona omil**, parol umuman yo'q.

### 1.4 Nega ikki dunyoni aralashtirish xavfli

Bugungi kodda haqiqiy imtiyoz oshirish yo'li bor va u dizaynning asosiy sababi:

```
Mini App (mijoz yuzasi)
  → POST /auth/telegram/initdata
  → service.sign_in()          (service.py:252)
  → set_telegram_scope()       → app.telegram_id = <telegram_id>
  → users_self policy          (0001_core.py, _rls())
        USING (id = app_user_id()
               OR (app_telegram_id() <> 0 AND telegram_id = app_telegram_id()))
  → upsert_user()              → XODIM qatorini qaytaradi
  → load_memberships()         → rollar yuklanadi (shartsiz)
  → is_super_admin()           → true bo'lishi mumkin
  → issue_tokens()             → to'liq konsol sessiyasi, PAROLSIZ
```

Ustiga `deps.py:79` dagi `if ctx.is_super_admin: return` — `require_role()` ning
erta qaytishi: super adminning Telegram akkaunti qo'lga tushsa, u Mini App orqali
butun platformani ochadi. Ikki dunyo qarori aynan shu zanjirni uzadi.

---

## 2. Ikki dunyo chegarasi

### 2.1 Chegara qanday majburlanadi (uch qatlam)

**1-qatlam — ma'lumot invarianti (eng kuchli).**
`kind='staff'` bo'lgan qatorda `telegram_id` **har doim NULL**. Xodimning Telegrami
alohida `staff_telegram` jadvalida yashaydi. Demak `users_self` policy'sining
`telegram_id = app_telegram_id()` shoxi xodim qatoriga **hech qachon** tegmaydi:
`NULL = X` → NULL → qator ko'rinmaydi. Bu predikat emas, ma'lumotning o'zi —
kelajakdagi dev uni tasodifan buzolmaydi.

**2-qatlam — RLS policy'si.**
Shunga qaramay `users_self` qayta yoziladi va Telegram shoxiga `AND kind='customer'`
qo'shiladi. Ikki mustaqil sabab bitta natijani beradi (belt-and-braces).

**3-qatlam — kompozit FK va token klaymi.**
`memberships` va `super_admins` faqat `kind='staff'` ga bog'lanadi (kompozit FK).
Access tokenda `aud` klaymi bor va u `pyjwt` ning **o'z** `decode(audience=...)`
mexanizmi bilan tekshiriladi — klaym yo'q bo'lsa kutubxona o'zi fail-closed
bo'ladi, qo'lda `if` yozilmaydi.

### 2.2 Bir odam ikkala dunyoda bo'la oladi

Bitta jismoniy odam ham mijoz (o'z Telegrami bilan bron qiladi), ham xodim
(login/parol bilan ishlaydi) bo'lishi mumkin — bu **ikki alohida `users` qatori,
ikki alohida sessiya**. `staff_telegram.telegram_id` va `users.telegram_id`
mustaqil makonlar, shuning uchun bitta Telegram akkaunt ikkalasida ham bo'la oladi.
Bu biznes qarorining to'g'ridan-to'g'ri aksi: mijoz sessiyasi hech qachon xodim
vakolatini bermaydi va aksincha.

### 2.3 Ikki bot, ikki vazifa

| | `@playbronbot` (`BOT_TOKEN`) | `@playbronadminbot` (`ADMIN_BOT_TOKEN`) |
|---|---|---|
| Mini App | Bor (mijoz) | **Yo'q** |
| `initData` tekshiruvi | `POST /auth/customer/miniapp` — **faqat shu token** | Endpoint mavjud emas |
| Ro'yxatdan o'tish | Mijoz: `/start` → ism → kontakt | Xodim: `/start inv_…` → kontakt |
| OTP | **Hech qachon** | Yagona OTP kanali |
| Bildirishnoma | Mijoz: bron, hisob | Xodim: kirish ogohlantirishi, obuna |
| Webhook | `/telegram/webhook/main` | `/telegram/webhook/admin` |
| Webhook sekreti | `MAIN_BOT_WEBHOOK_SECRET` | `ADMIN_BOT_WEBHOOK_SECRET` |

**Qat'iy taqiq:** `initData` imzosini «ikkala token bilan urinib ko'rish» —
u ikki dunyoni bitta imzo maydonida birlashtirardi. `_widget_token()` va butun
Login Widget yo'li o'chadi.

`[TEKSHIRISH]` `initData` imzo formulasi (`data_check_string`, kalit hosil qilish
tartibi, `WebAppData` konstantasining aniq yozilishi) `api/src/playbron/modules/auth/telegram.py`
faylining boshidagi blok bo'yicha rasmiy hujjatdan tasdiqlanadi. Xotiradan
yozilmaydi.

### 2.4 Reliz darvozasi — `initData` ichidagi `signature`

Hozirgi `_data_check_string()` (`telegram.py:59-61`) faqat `hash` maydonini
chetga oladi. Yangi Telegram mijozlari `initData` ichida qo'shimcha Ed25519
`signature` maydonini yuborishi mumkin; agar u HMAC hisobiga **kirmasligi** kerak
bo'lsa, bugungi kod haqiqiy `initData` da 401 beradi. Mijoz dunyosida kirish
ekrani **yo'q**, ya'ni bu tiklab bo'lmaydigan tiqilish.

`[TEKSHIRISH]` `api/tests/test_telegram_auth.py::test_real_initdata_sample` hozir
`skip` holatida. **U yoqilmaguncha prod'ga chiqilmaydi** — bu reliz darvozasi,
tavsiya emas.

---

## 3. Ma'lumotlar modeli

Migratsiya: `api/migrations/versions/0005_two_worlds_auth.py`,
`down_revision = "0004_role_passwords"`, `downgrade()` → `NotImplementedError`
(uy qoidasi: migratsiyalar faqat oldinga).

### 3.1 `users` — o'zgarishlar

| Ustun | Tur | Izoh |
|---|---|---|
| `kind` | `text NOT NULL DEFAULT 'customer'` | `CHECK (kind IN ('customer','staff'))`. Sukut ataylab **imtiyozsiz** tomonda |
| `login` | `text NULL` | faqat xodimda |
| `status` | `text NOT NULL DEFAULT 'active'` | `CHECK (status IN ('invited','active','disabled'))` |
| `display_name` | `text NULL` | botda tasdiqlangan ism (quyida, §3.7) |
| `telegram_id` | `bigint NULL` | `NOT NULL` **olib tashlanadi** |

**CHECK konstreyntlari (ikki dunyo invarianti):**

```
users_kind_customer_ck:
    kind <> 'customer' OR (telegram_id IS NOT NULL AND login IS NULL)

users_kind_staff_ck:
    kind <> 'staff'    OR (login IS NOT NULL AND telegram_id IS NULL)

users_login_shape_ck:
    login IS NULL OR login ~ '^[a-z0-9._-]{3,32}$'
```

`login` faqat ASCII kichik harf, raqam va uchta belgi: homoglif bilan boshqa
xodimga o'xshab olishning oldi olinadi. Uzunlik 3..32 — 3 dan qisqasi to'qnashuv
va taxminni osonlashtiradi, 32 dan uzuni indeks va UI'da foydasiz.

**Indekslar** (mavjud `users_telegram_id_uk` DROP qilinadi):

```
UNIQUE (telegram_id)   WHERE kind = 'customer'
UNIQUE (lower(login))  WHERE kind = 'staff'
UNIQUE (id, kind)                                  -- kompozit FK uchun
INDEX  (phone)         WHERE kind = 'customer'     -- telefon egaligini o'tkazish uchun
```

`lower(login)` funksional indeks — `citext` kengaytmasi talab qilinmaydi
(boshqariladigan hostingda `CREATE EXTENSION` huquqi bo'lmasligi mumkin).

**Telefon UNIQUE emas.** Sabab §4.6 da: qattiq `UNIQUE` + qo'lda bo'shatish
registratsiyani abadiy to'sadigan hujum vektori. O'rniga egalik o'tkazish modeli.

**Kompozit FK — asosiy invariant:**

```
memberships:   kind text NOT NULL DEFAULT 'staff' CHECK (kind = 'staff'),
               FOREIGN KEY (user_id, kind) REFERENCES users(id, kind)
super_admins:  shu naqsh
```

`REVOKE UPDATE (kind) ON users FROM playbron_app` — `kind` ilova roli uchun
o'zgarmas. Mijoz qatoriga membership yozib bo'lmaydi; hech qanday kod xatosi buni
chetlab o'tolmaydi.

### 3.2 `staff_telegram` — xodimning yetkazish kanali (identity EMAS)

| Ustun | Izoh |
|---|---|
| `user_id` | PK, FK `users(id) ON DELETE CASCADE` |
| `telegram_id` | `bigint NOT NULL UNIQUE` |
| `chat_id` | `bigint NOT NULL` |
| `verified_phone` | bog'lash paytida `requestContact` bilan tasdiqlangan raqam |
| `linked_at`, `linked_by_invite_id` | audit |
| `blocked_at` | bot bloklangani (`my_chat_member` dan) |

RLS: `ENABLE` + `FORCE`, policy `USING (user_id = app_user_id())`. Yozish
faqat `SECURITY DEFINER` funksiya orqali (bog'lash webhook kontekstida sodir
bo'ladi, u yerda `app.user_id` yo'q).

### 3.3 `staff_credentials` — parol xeshi

| Ustun | Izoh |
|---|---|
| `user_id` | PK/FK |
| `password_hash` | Argon2id PHC satri |
| `password_set_at`, `must_change` | |
| `last_login_at`, `failed_count`, `last_failed_at` | telemetriya (qulf uchun **emas**) |

- `ENABLE` + `FORCE ROW LEVEL SECURITY` va **birorta ham policy yozilmaydi** →
  ilova roli uchun butunlay yopiq (fail-closed).
- Ikkinchi qatlam: `REVOKE ALL ON staff_credentials FROM playbron_app`.
- Yagona kirish yo'li — §3.6 dagi `SECURITY DEFINER` funksiyalari.

### 3.4 Yangi jadvallar — qisqacha

| Jadval | Vazifa | RLS |
|---|---|---|
| `staff_invites` | `user_id`, `token_hash UNIQUE`, `expected_phone`, `target_role`, `created_by`, `expires_at`, `consumed_at`, `revoked_at`, `opened_by_telegram_id` | yozish/o'qish faqat o'sha klub OWNER/ADMIN, **va faqat pastroq rolli maqsad uchun** (§9.2) |
| `staff_devices` | `id`, `user_id`, `device_hash`, `label`, `first_seen_at`, `last_seen_at`, `revoked_at` | `USING (user_id = app_user_id())` |
| `staff_recovery_codes` | `user_id`, `code_hash`, `used_at` | policy yo'q + `REVOKE ALL` (parol bilan bir xil rejim) |
| `auth_events` | `at`, `event`, `user_id NULL`, `login_hash`, `ip`, `user_agent`, `request_id`, `club_id NULL`, `detail jsonb` | `INSERT WITH CHECK (true)`, o'qish §3.5, `REVOKE UPDATE, DELETE` |

**Nega `auth_events` alohida, `audit_log` emas.** `0003_rls_hardening.py:148-149`:

```
CREATE POLICY audit_log_insert ON audit_log
    FOR INSERT WITH CHECK (actor_user_id = app_user_id());
```

Muvaffaqiyatsiz kirishda va webhook kontekstida **aktor yo'q** (`app.user_id = 0`),
ya'ni `audit_log` ga yozish RLS bilan rad etiladi va aynan eng kerakli xavfsizlik
signali jimgina yo'qoladi. `auth_events` append-only, aktorsiz yozuvni qabul qiladi.

Saqlash muddati **180 kun** — bir mavsumlik tergov oynasi; undan uzog'i PII yukini
oshiradi. Tozalash — egasi roli (`DIRECT_URL`) bilan yuradigan kunlik job.

### 3.5 RLS policy o'zgarishlari

**`users_self` qayta yoziladi:**

```
USING (id = app_user_id()
       OR (app_telegram_id() <> 0
           AND kind = 'customer'
           AND telegram_id = app_telegram_id()))
WITH CHECK (shu shart)
```

**`memberships_write` ikkiga bo'linadi** (rol shifti DB darajasida):

```
memberships_write_owner:
    USING/WITH CHECK (club_id = app_club_id()
                      AND app_club_role(app_club_id()) = 'OWNER')

memberships_write_admin:
    USING/WITH CHECK (club_id = app_club_id()
                      AND app_club_role(app_club_id()) = 'ADMIN'
                      AND role = 'STAFF')
```

Hozirgi `memberships_write` (`0003:135-140`) faqat **aktorning** roliga qaraydi,
yoziladigan `role` qiymatini umuman tekshirmaydi. Ya'ni ADMIN o'z qatorini
`role='OWNER'` ga ko'tara oladi va `club_payment_credentials_owner` policy'si
orqali Click/Payme merchant kalitlarini oladi. Yangi ikkita policy buni yopadi.

**`audit_log_read` qayta yoziladi.** Hozir `USING (org_id = app_org_id() OR ...)` —
ko'p klubli tashkilotda A klubning oddiy STAFF xodimi B va C klublarning barcha
izlarini o'qiydi. `audit_log` ga `club_id` ustuni qo'shiladi:

```
USING (actor_user_id = app_user_id()
       OR (club_id = app_club_id()
           AND app_club_role(app_club_id()) IN ('OWNER','ADMIN'))
       OR (club_id IS NULL AND org_id = app_org_id()
           AND EXISTS (SELECT 1 FROM organizations o
                       WHERE o.id = org_id AND o.owner_user_id = app_user_id())))
```

`auth_events` o'qishi ham shu naqsh bo'yicha: o'zining hodisalari + klub
OWNER/ADMIN o'z klubi xodimlarining hodisalari.

### 3.6 `SECURITY DEFINER` funksiyalari — egasi BYPASSRLS roli

**Bu bo'lim majburiy va oson unutiladigan.** `SECURITY DEFINER` faqat
`current_user` ni funksiya egasiga almashtiradi — u RLS'ni **o'chirmaydi**.
`docs/04-deploy-render.md` da yozilganidek, docker'dagi `playbron` superuser
(RLS'ni butunlay chetlab o'tadi), Render'da esa oddiy **ega**, va
`FORCE ROW LEVEL SECURITY` egaga ham tatbiq etiladi. Aynan shu sabab
`0002_seed.py:171` seed vaqtiga `NO FORCE` qilishga majbur bo'lgan.

Oqibat: agar `auth_lookup_staff()` migratsiya egasiga tegishli bo'lsa, u
`staff_credentials` (policy yo'q + FORCE) dan **0 qator** qaytaradi va prod'da
har bir xodim kirishi 401 bilan tugaydi. Deploy tunidagi «tez tuzatish»
(`NO FORCE` yoki `USING (true)`) parol xeshlarini ilova roliga ochib qo'yadi —
dizaynning butun himoya g'oyasi yo'qoladi.

**Qoida:** barcha yangi `SECURITY DEFINER` funksiyalari `playbron_platform`
(BYPASSRLS) roliga tegishli bo'ladi:

```
ALTER FUNCTION <fn> OWNER TO playbron_platform;
REVOKE ALL ON FUNCTION <fn> FROM PUBLIC;
GRANT EXECUTE ON FUNCTION <fn> TO playbron_app;
SET search_path = pg_catalog, pg_temp;   -- 'public' emas
```

**Mavjud `app_club_role()` ham shu tuzoqda** (`memberships` FORCE RLS ostida, va
`memberships_read` policy'si o'z ichida yana `app_club_role()` ni chaqiradi →
Render'da rekursiya yoki bo'sh natija). U ham 0005 da `playbron_platform` ga
o'tkaziladi. CI testi §13.4 da.

**Funksiyalar ro'yxati:**

| Funksiya | Qaytaradi / qiladi | Ichki avtorizatsiya |
|---|---|---|
| `auth_lookup_staff(p_login text)` | `(user_id, password_hash, status, top_role)` — tor tuple | chaqiruvni `auth_events` ga yozadi |
| `auth_change_password(p_new_hash text)` | joriy foydalanuvchi paroli | `app_user_id()` dan oladi, **`user_id` parametri yo'q** |
| `auth_consume_reset(p_ticket_hash text, p_new_hash text)` | tiketni atomik iste'mol qiladi va parolni yozadi | foydalanuvchini **tiketdan** topadi |
| `auth_consume_invite(p_token_hash text, p_telegram_id bigint, p_chat_id bigint, p_phone text)` | invaytni bog'laydi | telefon mosligini va maqsad rolini **ichida** tekshiradi |
| `auth_touch_login(p_user_id bigint, p_ok bool)` | telemetriya | faqat `auth_lookup_staff` bergan `user_id` ga, bir tranzaksiyada |

**Nega `auth_set_password(bigint, text)` YO'Q.** Ichki avtorizatsiyasiz, `user_id`
ni parametr sifatida oladigan yozuvchi `SECURITY DEFINER` — bu tayyor imtiyoz
oshirish primitivi: kelajakdagi istalgan hisobot/filtr marshrutidagi SQL
injeksiya `SELECT auth_set_password(<super_admin_id>, '<o'z xeshim>')` ga
aylanadi. **Qoida:** hech bir yozuvchi funksiya `user_id` ni parametr sifatida
qabul qilmaydi.

### 3.7 `refresh_tokens` — yangi ustunlar

| Ustun | Sabab |
|---|---|
| `kind text NOT NULL DEFAULT 'customer'` | mijoz refresh'i xodim access'iga aylanmasin; `rotate_refresh` dunyoni **saqlangan qatordan** oladi, `users` dan qayta hisoblamaydi |
| `chain_started_at timestamptz NOT NULL` | mutlaq sessiya chegarasi; rotatsiya bu vaqtni **ko'chirmaydi** |
| `device_hash char(64) NULL` | qurilma bog'lanishi (§6.5) |

### 3.8 Ism maydonlari — validatsiya yozish nuqtasida

`service.upsert_user` (`service.py:66-76`) har Mini App kirishida `first_name`,
`last_name`, `username` ni `initData` dan olib **ustiga yozadi** — hech qanday
validatsiyasiz. Bu maydonlarni foydalanuvchi to'liq nazorat qiladi (Telegram
profilining o'zi). Botdagi ism validatsiyasi shuning uchun ma'nosiz: hujumchi
`first_name` ni `Bekor qilindi — 90 111 22 33 ga qo'ng'iroq qiling` ga
o'zgartirib Mini App'ni ochadi va bu satr xodim konsolidagi bron ro'yxatida
chiqadi.

**Qaror:** normallashtirish `upsert_user` ning o'zida, ya'ni ikkala oqim uchun
ham: NFKC → boshqaruv va bidi belgilarini (`U+200E`, `U+200F`, `U+202A`–`U+202E`)
olib tashlash → uzunlik cheklovi. Konsolda ko'rsatiladigan ism — botda
tasdiqlangan `display_name`; Telegram profilidan kelgan `first_name` texnik
maydon bo'lib qoladi.

---

## 4. Mijoz oqimi

### 4.1 Bot suhbati

`@playbronbot`, webhook `POST /api/v1/telegram/webhook/main`.

1. **`/start`** → salom + «Ismingiz **{from.first_name}**mi?» ·
   `[✅ Ha] [✍️ Boshqa ism]`. Telegram ismni allaqachon beradi — «bot ismni
   so'raydi» talabi bir bosishda bajariladi, 90% holatda harf yozilmaydi.
   «Boshqa ism» → erkin matn (2..64 belgi; 2 dan qisqasi ma'nosiz, 64 —
   `users.first_name` ustuni kengligining yarmi va Telegram profilining amaliy
   chegarasi).
2. **Telefon** → `ReplyKeyboardMarkup` + `KeyboardButton(request_contact=True)`,
   `one_time_keyboard=true`, `resize_keyboard=true`.
   `[TEKSHIRISH]` maydon nomlari va `KeyboardButton` ning aniq imzosi.
   **Qo'lda yozilgan raqam umuman qabul qilinmaydi** — tasdiqning butun ma'nosi shunda.
3. **Kontakt kelgach** → `ReplyKeyboardRemove` + yakuniy xabar + inline
   `web_app` tugmasi «Ilovani ochish»; ustiga `setChatMenuButton` bilan chat
   pastidagi menyu tugmasi ham Mini App'ga sozlanadi (`[TEKSHIRISH]` metod nomi).

### 4.2 Kontakt egaligini tekshirish — olti shart, hammasi majburiy

Bu dizayndagi **eng muhim mijoz-tomon tekshiruvi**. Bittasi tushib qolsa mijoz
o'zini begona telefon bilan ro'yxatdan o'tkazadi.

| # | Shart | Nega |
|---|---|---|
| 1 | `message.contact.user_id` **mavjud** (`is None` aniq tekshiriladi) | Telegram foydalanuvchisi bo'lmagan kontaktda bu maydon **umuman kelmaydi**. `contact.user_id != from.id` deb yozilsa `None != 12345` → `True` bo'lib tekshiruv jimgina ochilib ketadi |
| 2 | `int(contact.user_id) == int(message.from.id)` | address book'dan ulashilgan begona kontakt rad etiladi |
| 3 | `message.chat.type == 'private'` va `chat.id == from.id` | guruhda bot telefon yig'uvchi vositaga aylanmasin va javob matni begonalarga ko'rinmasin |
| 4 | `message.forward_origin` yo'q | uzatilgan xabar |
| 5 | `message.via_bot` yo'q | boshqa bot orqali kelgan |
| 6 | Redis'da shu `telegram_id` uchun `awaiting_contact` holati bor va u **atomik iste'mol qilinadi** | kutilmagan kontakt qabul qilinmaydi; soxta webhook uchun qadam soni oshadi |

`[TEKSHIRISH]` `contact.user_id`, `forward_origin`, `via_bot` maydonlarining
aniq nomlari va mavjudlik shartlari.

Rad etilganda: «Bu boshqa odamning raqami. Pastdagi tugma orqali **o'z**
raqamingizni yuboring» + tugma qayta. Urinish `auth_events: contact_rejected`
(sababi bilan, **telefon raqamsiz**). 3 urinishdan keyin 10 daqiqa jim.

Raqam E.164 ga normallashtiriladi (Telegram `+` siz ham berishi mumkin) va
`^\+998\d{9}$` ga mos kelishi shart — `apps/miniapp/src/screens/register.tsx`
dagi validatsiya bilan bir xil. Normallashtirilgan uzunlik `users.phone`
(`String(20)`) ga sig'ishi **oldindan** tekshiriladi, DB xatosi bilan emas.

### 4.3 Bot mijozga birinchi yozolmaydi — bu yerda muammo emas

Mijoz oqimi butunlay `/start` dan boshlanadi, ya'ni birinchi kontaktni
foydalanuvchining o'zi ochadi. Cheklov faqat xodim dunyosida muammo tug'diradi
(§5.1).

### 4.4 Bot holati va update dedupe

Holat — Redis: `bot:fsm:cust:{telegram_id}` → `{step, draft_name, attempts}`,
TTL **24 soat** (bir kunlik oyna: odam botni ochib, telefonini keyinroq
ulashishi normal; undan uzog'i esa yarim tashlangan oqimlarni to'playdi).

**FSM faqat kesh.** Haqiqiy manba — Postgres: qator yo'q → ism so'raladi;
`phone_verified_at IS NULL` → telefon so'raladi; aks holda darhol Mini App
tugmasi. Redis o'chsa oqim buzilmaydi (mijoz oqimida bu fail-open **maqbul**:
hech qanday huquq berilmaydi; parol va OTP yo'llarida esa fail-closed — §10.4).

**Update dedupe (hozir umuman yo'q):** har update boshida
`SET tg:upd:{bot}:{update_id} 1 NX EX 3600` — takroriy bo'lsa jimgina 200.
TTL 1 soat: Telegram'ning qayta yuborish oynasidan sezilarli uzoq, lekin Redis
xotirasini yemaydi. Ushbu himoyasiz sekin javobda kelgan takroriy `contact`
xabari telefon o'zgarishini ikki marta qayta ishlaydi.

**Webhook hech qachon 4xx/5xx qaytarmaydi.** Handler eng tashqi darajada
`try/except Exception` bilan o'raladi va **har doim 200**; xato ichkarida log va
`auth_events` ga yoziladi. Aks holda bitta noto'g'ri update Telegram navbatini
to'xtatadi va **butun** mijoz ro'yxatdan o'tish oqimi o'ladi.

### 4.5 Mini App bilan bog'lanish

`POST /auth/customer/miniapp` `initData` imzosini tekshiradi va sessiya beradi —
**kirish ekrani ko'rsatilmaydi** (hozirgi `useTelegramAuth` xatti-harakati
saqlanadi). Lekin Mini App'ni botsiz ham ochish mumkin (menyu tugmasi,
to'g'ridan-to'g'ri havola), shuning uchun sessiya **profil darvozasi** bilan
keladi:

- `phone_verified_at IS NULL` → Mini App klublarni ko'rsatadi, lekin bron
  yaratishda API `403 PHONE_REQUIRED` beradi va ekranda botga deep-link chiqadi.
- Bu **kirish** darvozasi emas, **bron** darvozasi —
  `docs/01-architecture.md` §2 dagi «birinchi bron → telefon majburiy» jadvali
  bilan aynan mos.

**`initData` replay — ikki tomonlama tuzatish.** Hozir
`apps/miniapp/src/lib/auth.ts` har mount'da `initData` ni qayta POST qiladi,
`service.guard_replay` esa ikkinchisiga `401 AUTH_REPLAY` beradi. Kirish ekrani
yo'q dunyoda bu mijozni tiqilgan holatga tushiradi.

1. **Mijoz tomon:** amal qiluvchi sessiya bo'lsa `initData` umuman yuborilmaydi
   (mount'dagi shartsiz POST olib tashlanadi).
2. **Server tomon:** `source='initdata'` uchun replay **idempotent** — kalit
   `(telegram_id, hash)` bo'yicha; birinchi iste'moldan keyingi so'rov
   **mavjud sessiyani** qaytaradi, yangi refresh zanjiri ochmaydi. Qat'iy guard
   Login Widget uchun kerak edi, u esa o'chirilmoqda.

**Replay guard TTL imzo oynasining oxiriga bog'lanadi.** Hozir kalit
`ex=initdata_ttl_sec` (300 s) bilan **birinchi ishlatish** paytidan sanaladi,
`_check_age` esa `auth_date-60` dan `auth_date+300` gacha, ya'ni **360 soniya**
qabul qiladi. Server soati 60 soniya orqada bo'lsa (Render'da NTP siljishi
odatiy) oxirgi 60 soniyada kalit o'lgan, imzo esa hali tirik — bitta `initData`
ikki marta ishlaydi. Yangi formula:

```
ttl = max(1, auth_date + initdata_ttl_sec + SKEW - now())
```

`SKEW` va `initdata_ttl_sec` **bitta konstantadan** olinadi, ikki joyda
yozilmaydi.

### 4.6 Telefon: egalik o'tkazish, «qulflash» emas

Muammo ikki tomonlama:

- **Qattiq `UNIQUE(phone)` + qo'lda super-admin bo'shatish** → hujumchi arzon
  SIM'lar bilan raqam bloklarini oldindan band qiladi va kelajakdagi mijozlarni
  registratsiyadan to'sadi; qurbon uchun bu «ilova ishlamayapti» ko'rinishida.
- **UNIQUE umuman yo'q** → bitta raqam cheksiz `telegram_id` ga bog'lanadi,
  no-show qora ro'yxati va depozit talabi yangi akkaunt bilan nolga qaytadi.

**Qaror — o'tkazish modeli.** `phone` UNIQUE **emas**, lekin «faol tasdiqlangan
egalik» yagona: yangi `telegram_id` shu raqamni Telegram tasdig'i bilan ulashsa,
bitta `SECURITY DEFINER` tranzaksiyada:

1. eski qatorda `phone` va `phone_verified_at` NULL qilinadi;
2. yangi qator raqamni oladi;
3. `auth_events: phone_transferred` yoziladi;
4. eski `telegram_id` ga bot orqali xabar ketadi.

O'tkazish tezligi: bitta raqam uchun **30 kunda bir marta** (operator raqamni
qayta sotishi haqiqiy hodisa, lekin oyiga bir martadan tez emas; bu chegara
o'g'irlangan Telegram akkaunti bilan tarixni aylantirishni ham sekinlashtiradi).
Depozit, qarz va qora ro'yxat holati **ko'chirilmaydi** — u eski qatorda qoladi.

### 4.7 `phone_verified_at` abadiy emas

`upsert_user` izohida yozilganidek telefon bir marta yoziladi va **hech qachon
qayta ko'rib chiqilmaydi**. Foydalanuvchi Telegram akkauntining raqamini
almashtirsa (`user_id` o'zgarmaydi), PlayBron buni bilmaydi: hisob endi
foydalanuvchi egalik qilmaydigan raqamga «tasdiqlangan» holda bog'langan.

**Qaror:** `phone_verified_at` ga amal qilish muddati — **180 kun**. Muddat
o'tgach quyidagi amallardan **oldin** qayta `requestContact` so'raladi: birinchi
bron, depozit, refund, qora ro'yxatga qo'shish. Bot allaqachon tanish, ya'ni
«bot birinchi yozolmaydi» cheklovi bu yerda to'sqinlik qilmaydi. `users` ga
`phone_reverified_at` qo'shiladi.

---

## 5. Xodim ro'yxatdan o'tishi va OTP

### 5.1 «Bot birinchi yozolmaydi» — qanday hal qilinadi

Yechim: **taklif havolasining o'zi `/start` bo'ladi.**

```
Admin konsolda xodim yaratadi
   → server inv_<token> yasaydi (DB'da faqat sha256 xeshi)
   → admin havolani xodimga beradi:
        https://t.me/playbronadminbot?start=inv_<token>
   → XODIM O'ZI Start bosadi        ← birinchi kontakt foydalanuvchidan
   → bot requestContact so'raydi
   → telefon admin kiritgan raqam bilan solishtiriladi
   → shundan keyingina OTP yuborish mumkin
```

`secrets.token_urlsafe(32)` → 43 belgi, `inv_` prefiksi bilan 47.
`[TEKSHIRISH]` deep-link `start` parametrining uzunlik va belgilar to'plami
cheklovi (`A-Za-z0-9_-`, 64 belgi) rasmiy hujjatdan tasdiqlansin.

### 5.2 Invayt — bearer sir emas, ikki omil

Havola tarqaladi: admin uni klub guruhiga tashlaydi, SMS qiladi, qulflanmagan
telefonda ochiq qoladi. Shuning uchun **`/start` ning o'zi hech qachon
bog'lanishni yakunlamaydi**. Bog'lanish uchun `auth_consume_invite()` ichida,
bitta tranzaksiyada:

1. `token_hash` topildi, `consumed_at IS NULL`, `revoked_at IS NULL`,
   `expires_at > now()`;
2. §4.2 dagi **oltala** kontakt egaligi sharti bajarildi;
3. `normalize(contact.phone_number) == invite.expected_phone`;
4. maqsad rolining shifti tekshirildi (§9.2).

Ya'ni hisobni egallash uchun **token + admin kiritgan raqamga egalik**
ikkalasi kerak.

- **TTL 12 soat** — bitta smena. Uzun TTL bearer sirning yashash oynasini
  cho'zadi; qayta yuborish adminda bir bosish.
- Muvaffaqiyatsiz urinish invaytni **iste'mol qilmaydi**, lekin
  `opened_by_telegram_id` yoziladi va admin panelida «havolani kim ochdi»
  ko'rinadi — u bekor qilib yangisini yasay oladi.
- Bog'lanish sodir bo'lganda klub egasiga bildirishnoma.

### 5.3 Prefiks marshrutga qattiq bog'lanadi

Telegram update'ida qaysi bot yetkazgani haqida maydon **yo'q** — yagona
bog'lanish marshrut + sekret. Agar `/start` payload'i umumiy dispatcher orqali
ajratilsa, hujumchi xodim invaytini **mijoz** botiga qaratadi
(`t.me/playbronbot?start=inv_<token>`) va u yerda telefon solishtiruvi umuman
yo'q — mijoz dunyosidan xodim dunyosiga to'g'ridan-to'g'ri eskalatsiya.

**Qoida:** `inv_`, `sg_`, `rst_` prefikslari **faqat** admin marshrutida qabul
qilinadi; mijoz marshrutida bunday payload jimgina tashlanadi va
`auth_events: wrong_bot_payload` yoziladi. Handler ro'yxati marshrutga xos,
umumiy dispatcher yo'q.

### 5.4 Webhook sekretiga tayanmaslik

Hozir bitta `TG_WEBHOOK_SECRET` bor va `webhook_secret_token()` uning sha256
hex'ini qaytaradi. Bu qiymat **har bir update'da ochiq sarlavhada** keladi va
teskari proksi/APM/access-log, Render env dump yoki xato hisoboti orqali chiqib
ketishi mumkin. Uni bilgan hujumchi to'g'ridan-to'g'ri soxta update yozadi:
`contact.user_id` ni ham, `from.id` ni ham **o'zi** yozgani uchun §4.2 dagi
egalik shartlari «bajariladi».

Uch qatlamli javob:

1. **Ikki mustaqil sekret** — `MAIN_BOT_WEBHOOK_SECRET`, `ADMIN_BOT_WEBHOOK_SECRET`,
   ikkalasi ham `render.yaml` da alohida `generateValue: true`. Bir ildizdan
   hosil qilish (`sha256(root + ":" + bot)`) **yetarli emas**: ildiz sizsa ikkala
   dunyo bir vaqtda quladi. Start'da `main != admin` ekani tekshiriladi, aks holda
   ilova ishga tushmaydi. Mavjud sha256-hex hiylasi saqlanadi (Telegram
   `secret_token` belgilar to'plami cheklovi — `[TEKSHIRISH]`).
2. **Telegram chiquvchi IP diapazoni bo'yicha allowlist** — `[TEKSHIRISH]`
   diapazonlar rasmiy hujjatdan olinadi va env'da saqlanadi (kod ichida
   qotirilmaydi, chunki ular o'zgarishi mumkin). Mos kelmasa 403.
3. **Bog'lanish faqat webhook payload'i bilan yakunlanmaydi** — u konsolda
   yaratilgan, DB'da yashaydigan tiketga (`staff_invites` qatori) va telefon
   mosligiga tayanadi. Sekret o'zi hech qanday hisobni bermaydi.

Sarlavha hech qachon log/trace/xato hisobotiga tushmasin — middleware'da qora
ro'yxat.

### 5.5 Klub egasi (OWNER) o'zi ro'yxatdan o'tadi

1. Landing formasi: klub nomi, ism, telefon, tanlangan login →
   `POST /auth/owner/signup` **har doim 202** qaytaradi + `sg_<token>` deep-link.
   Login bandligi bu bosqichda **aytilmaydi** — aks holda ochiq endpoint hisob
   sanash orakuliga aylanadi.
2. Egasi `/start` qiladi → `requestContact` (formadagi telefon bilan
   solishtiriladi) → OTP.
3. Konsolda login + OTP + parol. **«Login band» javobi faqat shu yerda** beriladi —
   ya'ni Telegram bilan tasdiqlangan tirik odamga, anonim forma yuboruvchiga emas.
4. Tashkilot `pending` + `plan_code IS NULL` holida yaratiladi —
   `0003` dagi `organizations_insert` policy'si buni allaqachon majburlaydi.

### 5.6 SUPER_ADMIN

Onlayn ro'yxatdan o'tish yo'li **yo'q**. Login `0005` migratsiyasining o'zida
yaratiladi (`0002_seed` ga **tegilmaydi** — §12.5), parol
`scripts/set_staff_password.py` orqali `DIRECT_URL` bilan, **stdin'dan** so'ralib
qo'yiladi (argv yoki env emas — shell tarixiga va `ps` chiqishiga tushmasin).
Skript deep-link chop etadi; super admin admin botni `/start` qiladi, shundan
keyin OTP ishlaydi. Super adminda OTP **har kirishda** majburiy (§6.3).

> **Chetlanish (2026-08-15, loyiha egasining aniq so'rovi bilan).** Yuqoridagi
> "stdin'dan, hech qayerda saqlanmaydi" qoidasiga qo'shimcha, ixtiyoriy yo'l
> qo'shildi: `SUPER_ADMIN_PASSWORD` muhit o'zgaruvchisi berilsa, ilova
> `SUPER_ADMIN_LOGINS`dagi har bir login uchun parolni HAR START'da
> tekshiradi va FARQ bo'lsagina yangilaydi (`core/super_admin_bootstrap.py`).
> Sabab: Render bepul rejasida Shell yo'q, bazaga tashqi ulanish esa har
> safar IP allowlist bilan qo'lda ishlashni talab qiladi — loyiha egasi bu
> ishqalanishni parolni Dashboard'da saqlash xavfiga almashtirishni ANIQ
> tanladi. Standart yo'l (stdin, skript) o'zgarmadi va TAVSIYA etiladi;
> bu — uni istagan payt qo'llash mumkin bo'lgan qo'shimcha variant.

### 5.7 OTP dizayni

| Element | Qiymat | Sabab |
|---|---|---|
| Uzunlik | 6 xona, `secrets.randbelow(1_000_000)` → `f"{n:06d}"` | nusxa olinadigan kod; 4 xonaning ergonomik foydasi yo'q, entropiya esa kam. `random` emas — kriptografik generator |
| TTL — faollashtirish/tiklash | **300 s (5 daq)** | bu yo'l hisobni to'liq egallashga olib boradi → oyna tor |
| TTL — kirish step-up | **600 s (10 daq)** | smena boshida telefon qo'lida bo'lmasligi mumkin; kirish o'zi hisob egallash emas (parol allaqachon to'g'ri) |
| Urinish — kod bo'yicha | **3** | 3×10⁻⁶; 3 dan ko'pi qo'lda xato uchun ortiqcha |
| Urinish — (foydalanuvchi, maqsad) bo'yicha | **soatiga 9** | 3 kod × 3 urinish; ko'p kod so'rash byudjetni oshirmaydi |
| Qayta yuborish oralig'i | **≥60 s** | SMS-emas, lekin baribir bezovtalik; 60 s odam qayta bosishga ulguradigan eng qisqa oyna |
| Qayta yuborish | **3/soat, 10/kun** | umumiy hujum byudjeti 9 taxmin/soat |

**Ochiq saqlanmaydi.** Redis'da:

```
kalit:  otp:{purpose}:{otp_id}
qiymat: HMAC-SHA256(key=OTP_PEPPER, msg=f"{purpose}:{otp_id}:{code}") + attempts + user_id
```

`otp_id` — `secrets.token_urlsafe(24)` (≈32 belgi, taxmin qilib bo'lmaydi).

**Nega Argon2 emas, nega pepper.** 6 xonali kod atigi 10⁶ variant — sof xesh
(hatto sekin bo'lsa ham) dump ochilganda brute-force qilinadi. Entropiya
**pepper**dan keladi: `OTP_PEPPER` serverda, Redis'da yo'q.

**`OTP_PEPPER` alohida env** (`SecretStr`, prod'da majburiy, ≥32 bayt,
`render.yaml` da `generateValue: true`). `JWT_SECRET` qayta ishlatilmaydi:
(a) JWT siri rotatsiya qilinsa uchayotgan barcha OTP jimgina o'lardi va sabab
hech kimga tushunarli bo'lmasdi; (b) bitta sir yo'qolganda ikkala himoya bir
vaqtda quladi. Kalit ajratish — qat'iy talab.

**Tekshirish atomik.** Solishtirish + `attempts` oshirish + muvaffaqiyatda
o'chirish **bitta Lua skriptida**. `GET` + `DEL` ketma-ketligi poyga beradi:
1000 parallel so'rov `attempts=0` ni o'qib, bitta koddan 1000 taxmin chiqaradi —
6 xonali kod bir necha kunda ochiladi. Qo'shimcha: `otp_id` bo'yicha
konkurrentlik qulfi (`SET lock:{otp_id} NX PX 2000`), aks holda 409.
Solishtirish `hmac.compare_digest` (mavjud `constant_time_equal`).

**Yangi kod eskisini bekor QILMAYDI.** Ayni paytda ko'pi bilan 3 ta faol kod
bo'lishi mumkin. Sabab: «yangi kod eskisini o'ldiradi» qoidasi uchinchi shaxsga
qurbonning qo'lidagi kodni cheksiz bekor qilish imkonini beradi (u `forgot` ni
takrorlaydi → xodim «kod noto'g'ri» oladi). Urinishlar shifti (foydalanuvchi,
maqsad) darajasida umumiy bo'lgani uchun bu hujum byudjetini oshirmaydi.

**Yetkazish.** Faqat `@playbronadminbot`, faqat allaqachon bog'langan
`telegram_id` ga. Bog'lanmagan yoki `blocked_at` to'lgan bo'lsa javob **baribir
bir xil 202**, ichkarida `auth_events: otp_undeliverable` va konsolda
«Telegram ulanmagan ⚠» ogohlantirishi. `sendMessage` 403 qaytarsa
`staff_telegram.blocked_at = now()` va `users.tg_blocked_at` (ustun
`models.py:60` da **allaqachon bor**).

**Xabar matni.**

- Kod va **login bitta xabarda bo'lmaydi**. Umumiy kompyuterdagi Telegram
  Desktop toast'i yoki telefon qulf ekranidagi preview bitta qarashda
  «login + kod» juftligini bermasin.
- Birinchi qator: «PlayBron xodimlari bu kodni **hech qachon** so'ramaydi».
  Sabab: §8.4 dagi telefon orqali ijtimoiy muhandislik.
- Kod muvaffaqiyatli tekshirilgandan **keyin darhol** `deleteMessage`
  (`[TEKSHIRISH]` metod nomi va 48 soatlik cheklov); TTL tugashini kutish
  hujum oynasiga umuman ta'sir qilmaydi.
- Kod hech qachon log'ga, `auth_events.detail` ga yoki `sendMessage` javob
  korpusi bilan birga yozilmaydi. `main.py:26` dagi `httpx` INFO ni o'chirish
  (Bot API URL'ida token bor) shu qoidaning davomi.

### 5.8 Zaxira tiklash kodlari

Hisob **yagona** Telegram akkauntiga bog'lanib qolmasin. Faollashtirish oxirida
xodimga **8 ta** bir martalik zaxira kod ko'rsatiladi (har biri 10 belgi,
chalkashadigan belgilarsiz base32 — ≈50 bit, ya'ni brute-force qilib bo'lmaydi).
Ekranda **bir marta**, keyin faqat xeshi (`HMAC(OTP_PEPPER, code)`,
`staff_recovery_codes`, parol bilan bir xil yopiq rejim).

8 ta: bir yillik amaliy ehtiyoj (yiliga bir-ikki marta telefon almashadi),
qog'ozga yozib qo'yish uchun esa qisqa ro'yxat. Ishlatilgani `used_at` bilan
o'chadi; 2 tadan kam qolganda konsolda banner.

---

## 6. Xodim kirishi

`POST /auth/staff/login {login, password, otp_id?, otp?}` → `SessionOut`.

### 6.1 Qadamlar tartibi — xavfsizlik uchun muhim

1. **Login normallashtiriladi:** NFKC → casefold → trim →
   `^[a-z0-9._-]{3,32}$`. Mos kelmasa darhol §6.2 dagi **bir xil** 401,
   hech qanday bucket ochilmaydi, DB'ga tegilmaydi.
2. **Rate limit** — kalit `sha256(normallashgan_login)`, keyin IP, keyin
   `IP + login`. **DB va Argon2 gacha.**
3. `auth_lookup_staff(login)` — `SECURITY DEFINER`, tor tuple. `app.*` GUC
   o'rnatilmaydi, `users_self` kengaytirilmaydi.
4. **Hisob topilmasa** — parol baribir `DUMMY_HASH` ga qarshi tekshiriladi.
5. Argon2id tekshiruvi **chegaralangan hovuzda** (§6.4).
6. `status != 'active'` (invited/disabled) — **aynan o'sha** 401.
7. Step-up qarori (§6.3).
8. `check_needs_rehash()` → parametrlar ko'tarilgan bo'lsa xesh jimgina
   qayta yoziladi (PHC satri o'zini tavsiflaydi).
9. RLS konteksti shu yerda ochiladi: `set_current_user()`, keyin
   `load_memberships`, `is_super_admin`, `_finish_session()`.
   **`app.telegram_id` xodim oqimida hech qachon o'rnatilmaydi.**

### 6.2 Normallashtirish limiterdan OLDIN — nega bu kritik

Agar limiter **xom** satrni xeshlasa, qidiruv esa normallashganini, per-hisob
chegara amalda cheksiz aylanadi:

- `kassa01` → 8 urinish, bucket to'ldi;
- `KASSA01` → sha256 boshqa, bucket yangi, hisob **aynan o'sha**;
- `Kassa01`, `KaSsA01`… (2⁷ variant), NFKC bilan bir xil satrga tushadigan
  fullwidth `ｋassa01`, Kelvin belgisi `K`assa01 va h.k. — amalda minglab kalit,
  har biri to'liq yangi byudjet.

Login **sir emas** (konsolda ustun sifatida ko'rinadi), shuning uchun bu
to'g'ridan-to'g'ri ishlatiladigan yo'l. Testda `kassa01`, `KASSA01`, fullwidth va
Kelvin varianti **bitta** bucketga tushishi qulflanadi.

### 6.3 Step-up: qurilmaga bog'lanadi, muvaffaqiyatsizlik hisoblagichiga emas

**Noto'g'ri model** (rad etildi): «8 muvaffaqiyatsizlikdan keyin step-up».
Uch sabab:

1. Hujumchi 15 daqiqada 7 urinish yuborib chegarani **hech qachon** ishga
   tushirmaydi va online taxmin cheksiz davom etadi (~670 taxmin/kun/hisob).
2. Login sir bo'lmagani uchun uchinchi shaxs istalgan xodimni step-up holatiga
   tiqib qo'yadi — bu «hisob qulflanmaydi» va'dasining buzilishi.
3. `OTP_REQUIRED` faqat to'g'ri paroldan keyin chiqsa, u **«parol topildi»**
   orakuliga aylanadi: hujumchi kodni ko'rmasa ham tasdiq oladi va uni boshqa
   xizmatlarda sinaydi yoki SIM-swap'ni kutadi.

**To'g'ri model:**

| Rol | Step-up |
|---|---|
| SUPER_ADMIN | **har doim** (majburiy 2FA) |
| OWNER | **tanilmagan qurilmada har doim** |
| ADMIN / STAFF | **tanilmagan qurilmada** |
| hamma | tanilgan qurilmada — yo'q |

Ya'ni step-up sukut bo'yicha **yoqiq**, faqat tanilgan qurilmada o'chadi. Past
tezlikdagi hujum ham ikkinchi omilga uriladi. Smena davomida umumiy klub
kompyuteridan o'nlab marta kiradigan kassachi esa OTP ko'rmaydi — qurilma
tanilgan.

**Orakul yopiladi:** noto'g'ri parolda ham javob **aynan bir xil shakl** —
`otp_id` qaytariladi (soxta, hech qachon tasdiqlanmaydigan) va kechikish teng.
`OTP_REQUIRED` javobi hisobning mavjudligini ham, parolning to'g'riligini ham
oshkor qilmaydi.

**Eksponensial kechikish** (qulf emas, vaqt bilan o'zi so'nadi): hisob bo'yicha
0 → 1 s → 4 s → 16 s (yuqori chegara 16 s). Bu 670 taxmin/kun ni ~50 ga
tushiradi va halol foydalanuvchini deyarli bezovta qilmaydi.

**Hech qanday hisob qulflanmaydi.** `locked_until` **umuman kiritilmaydi**:
login sir emas, ya'ni qulf istalgan odam qo'lidagi maqsadli DoS quroli bo'lardi
(19:00 da har bir loginga 5 ta axlat parol — butun klub ishlamaydi).

### 6.4 Argon2 — chegaralangan hovuz (autentifikatsiyasiz OOM)

`asyncio.to_thread` sukut executor'i `min(32, cpu+4)` ta ishchi ochadi.
`memory_cost = 19 MiB` × 32 ≈ **608 MiB** → Render'ning 512 MB instansiyasi
darhol OOM-kill. IP chegaralari **so'rov sonini** cheklaydi, **ayni paytdagi**
sonini emas, shuning uchun ular bu hujumni to'smaydi.

```
anyio.to_thread.run_sync(ph.verify, ..., limiter=CapacityLimiter(4))
```

4 × 19 MiB = 76 MiB. Formula: `N = (mavjud RAM − ilova ishg'oli) / memory_cost`,
Render 512 MB uchun N=4; DB pool (10+5) bilan mos.

**Halol trafik uchun rezerv.** Yagona global hovuz bo'lsa hujumchi 200 IP dan
10 tadan so'rov yuborib (per-IP chegaradan o'tadi) semaforni doimiy to'la ushlab
turadi va smena boshidagi halol xodim 429 oladi. Shuning uchun **tanilgan
qurilma cookie'si bilan kelgan so'rovlar** uchun alohida, kichik lekin
kafolatlangan kvota ajratiladi. Navbat kutishiga 2 soniyalik timeout;
oshsa `429 RATE_LIMITED` + `Retry-After`.

**Reliz darvozasi:** 50 parallel `staff/login` da RSS cho'qqisi o'lchanadi va
CI'da qulflanadi.

### 6.5 Sessiya saqlash va qurilma bog'lanishi

Bugun konsol sessiyasi `apps/admin/src/lib/api.ts:19` da `localStorage` da, va
`POST /auth/refresh` (`router.py:151`) access token **talab qilmaydi** —
korpusda faqat `{refresh_token}`. Refresh TTL xodim uchun `refresh_ttl_sec` =
**30 kun**, `refresh_tokens.ip`/`user_agent` yoziladi lekin **hech qachon
solishtirilmaydi**, mutlaq chegara yo'q (har rotatsiya yangi 30 kun beradi).
Ya'ni o'g'irlangan refresh — cheksiz yashaydigan to'liq xodim kredensiali, va
o'g'irlikni aniqlash faqat qurbon eski tokenni qayta ishlatganda ishlaydi.

**Qaror (shu fazada, kechiktirilmaydi):**

| Element | Qiymat | Sabab |
|---|---|---|
| Access token (xodim) | **300 s** | parol almashgach yoki xodim bo'shatilgach qoladigan oyna; hozirgi 900 s konsol uchun uzun |
| Access token (mijoz) | 900 s (o'zgarmaydi) | |
| Refresh (xodim, sliding) | **12 soat** | bitta smena + zaxira |
| Refresh **mutlaq zanjiri** | **24 soat** (`chain_started_at`, rotatsiya ko'chirmaydi) | kuniga bir marta parol; `01-architecture.md` §2 dagi «konsol sessiyasi 24 soat» va'dasi bilan mos |
| Refresh (SUPER_ADMIN) | 8 soat (mavjud `sa_refresh_ttl_sec`) | |
| Refresh (mijoz, sliding) | **24 soat**, mutlaq 30 kun | uzaytirish faqat yangi, imzosi tekshirilgan `initData` bilan — Telegram har ochilishda yangisini beradi |
| Konsol idle timeout | **30 daqiqa** | umumiy kompyuterda unutilgan sessiya |
| Qurilma cookie | **60 kun** | step-up chastotasi va xavf muvozanati |

**Cookie mexanikasi:**

- Refresh token — `__Host-pb_refresh`, `httpOnly; Secure; SameSite=Strict;
  Path=/api/v1/auth/refresh`. `__Host-` prefiksi majburiy: `Domain` yozilmaydi,
  ya'ni qardosh subdomen (landing `playbron.uz` ↔ konsol `app.playbron.uz`) uni
  **yozolmaydi**. Prefikssiz cookie'da landingdagi XSS `Domain=.playbron.uz`
  bilan qurbonga o'z sessiyasini o'rnata oladi (sessiya fiksatsiyasi) va qurbon
  hujumchining tenantida ishlaydi.
- Qurilma cookie — `__Host-pb_device`, qiymati **imzolangan va foydalanuvchiga
  bog'langan**: `HMAC(pepper, user_id | device_id | issued_at)`. Boshqa
  foydalanuvchida taqdim etilsa e'tiborsiz qoldiriladi va `auth_events` ga
  yoziladi. Aks holda hujumchi o'z hisobida OTP bajarib olgan cookie'ni
  ko'chirib, qurbonning step-up'ini o'chirib qo'yardi. DB'da `staff_devices`
  qatori — egasi konsoldan bekor qila oladi.
- Muvaffaqiyatli kirishda mavjud sessiya cookie'si **almashtiriladi**
  (fiksatsiyaga qarshi klassik qoida).
- CSRF: `SameSite=Strict` + sessiyaga bog'langan token (statik sarlavha
  **yetarli emas** — u fiksatsiyaga umuman ta'sir qilmaydi). CORS allaqachon
  aniq origin ro'yxati + `allow_credentials=True`.
- Rotatsiyada `device_hash` mos kelmasa → `revoke_all_tokens` + Telegram
  ogohlantirishi. Yangi IP yoki yangi UA dan kelgan refresh — sukut ruxsat emas,
  step-up.

### 6.6 `aud` klaymi va `_finish_session()`

Access tokenga `aud` (`'customer' | 'staff'`) qo'shiladi va u
`jwt.decode(..., audience=...)` bilan tekshiriladi — klaym yo'q bo'lsa pyjwt
o'zi `MissingRequiredClaimError` beradi (fail-closed). Qo'lda `if knd == 'staff'`
yozilmaydi: teskari yozilgan shart (`if knd == 'customer': deny`) da'vosi yo'q
tokenni **xodim** deb qabul qilardi.

`require_staff_token` — `aud != 'staff'` → 403; u `require_role(...)` va
`require_super_admin` **ichiga** solinadi. `X-Club-Id` sarlavhasi mijoz tokenda
403.

**Mijoz yo'lida `memberships=[]` va `is_super_admin=False` majburlanadi**
(`load_memberships`/`is_super_admin` umuman chaqirilmaydi — bitta so'rov ham
tejaladi). `deps.py:79` dagi `if ctx.is_super_admin: return` erta qaytishi
tufayli bitta unutilgan tekshiruv butun platformani ochadi.

**`_finish_session()` ajratib olinadi** — `sign_in`, `staff_login` va
`rotate_refresh` bitta quyruqdan foydalanadi: JWT berish, rotatsiya, o'g'irlik
aniqlash, RLS konteksti, `kind` to'ldirish **bir joyda** yoziladi.
`rotate_refresh` dunyoni **saqlangan qatordan** oladi (§3.7), aks holda rotatsiya
paytida token dunyo almashtirishi mumkin.

### 6.7 Klub tanlash — `X-Club-Id` yo'l parametri bilan solishtiriladi

`deps.current_claims` (`deps.py:37-44`) faol klubni faqat `X-Club-Id` dan oladi;
yo'ldagi `{club_id}` bu zanjirda **umuman qatnashmaydi**. A klubda OWNER, B
klubda STAFF bo'lgan odam `POST /clubs/<B>/staff` ni `X-Club-Id: <A>` bilan
yuborsa `require_role(OWNER, ADMIN)` **o'tadi**.

**Qaror:** yagona `require_club_scope(club_id: int = Path(...))` dependency —
`ctx.club_id` bo'sh bo'lsa yo'ldan to'ldiradi, tokendagi a'zolikni tekshiradi,
mos kelmasa `403 CLUB_MISMATCH`. `len(roles) == 1` bo'lgandagi avtomatik
tanlash **olib tashlanadi**: klub har doim aniq belgilanadi.

### 6.8 Umumiy klub kompyuteri — konsol ergonomikasi

Bu mahsulotning kundalik yuzasi; xavfsizlik qarorlari uni ishlatib bo'lmaydigan
qilib qo'ymasligi kerak.

- **Qurilma chiplari:** shu qurilmada muvaffaqiyatli kirgan loginlar
  `localStorage` da (`{login, displayName}` — **hech qanday token yoki parol**).
  Kirish ekranida bosiladigan chip: xodim ismini bosadi, faqat parolni yozadi.
  Login klub ichida sir emas.
- **Yuqori panelda joriy xodim ismi doim ko'rinadi** — boshqa odam nomidan ish
  qilib qo'yish xavfi shunday kamayadi.
- **«Almashtirish» tugmasi** — `signOut()` + kirish ekrani, chiplar joyida.
  Xodim almashishi ~4 soniya.
- **Xavfli amallar uchun step-up parol:** OWNER darajasidagi amallar (to'lov
  kalitlari, xodim o'chirish, tarif) — oxirgi 5 daqiqada parol tasdiqlanmagan
  bo'lsa modal parol so'raydi. OTP emas: Telegramga chiqish shart emas.

---

## 7. Parol siyosati

### 7.1 Algoritm

**Argon2id, `argon2-cffi>=23.1`** (`api/pyproject.toml` ga qo'shiladigan yagona
yangi bog'liqlik; `anyio` FastAPI bilan allaqachon keladi).

- `passlib` emas — 2020 dan beri faol rivojlanmayapti va bcrypt 4.x bilan
  mos kelmaslik muammosi bor.
- `bcrypt` emas — parolni 72 baytda kesadi va GPU'ga ko'proq beriladi.

```
PasswordHasher(type=Type.ID, memory_cost=19456, time_cost=2,
               parallelism=1, hash_len=32, salt_len=16)
```

`m=19 MiB, t=2, p=1` — OWASP ning ikkinchi tavsiya etilgan konfiguratsiyasi.
Kutubxonaning sukuti (64 MiB, p=4) Render'ning 512 MB instansiyasida bir necha
parallel kirishda OOM beradi. `p=1` + `CapacityLimiter(4)` = eng ko'pi 76 MiB.
Xesh PHC satri sifatida saqlanadi va o'zini tavsiflaydi, ya'ni kelajakda
parametrlarni ko'tarib `check_needs_rehash()` bilan jimgina qayta xeshlash
mumkin. Salt kutubxona tomonidan har xeshda yangi.

**Pepper qo'shilmaydi.** Argon2 ning ixtiyoriy `secret` kirishi `PasswordHasher`
API'sida ochilmagan; ustidan HMAC qurish kalit rotatsiyasini murakkablashtiradi,
xesh jadvali esa allaqachon ilova roliga umuman ko'rinmaydigan joyda
(`staff_credentials`, policy'siz + `REVOKE ALL` + BYPASSRLS egasiga tegishli
funksiya). OTP da pepper bor — u yerda entropiya kodning o'zida yo'q, bu yerda
esa parolda.

### 7.2 Minimal talablar (NIST SP 800-63B ruhida)

| Rol | Minimal uzunlik | Sabab |
|---|---|---|
| STAFF / ADMIN | **12** | konsolda pul va mijoz PII si turadi; 8 belgi bu yuza uchun past |
| OWNER | **14** | to'lov kalitlari va tarif |
| SUPER_ADMIN | **16** | platforma miqyosidagi kirish |

- Maksimal **128 belgi** — kirish DoS'ining oldini olish. Argon2 da bcrypt'ning
  72-baytlik kesish muammosi **yo'q**.
- **Tarkib qoidalari yo'q** («kamida bitta bosh harf/raqam/belgi») — ular
  parolni bashoratli qiladi (`Parol1!`).
- NFKC normallashtirish; Unicode ruxsat etiladi; faqat boshi/oxiri trim
  qilinadi (ichkaridagi bo'shliq parolning qismi).
- **Qora ro'yxat:** login, telefon, klub nomi, tashkilot nomi bilan bir xil
  bo'lmasin; ~10 000 ta eng ko'p uchraydigan/sizib chiqqan parol + o'zbekcha
  xoslari (`parol123`, `playbron`, ketma-ketliklar). Rad etilganda **nima
  uchun** ekani aytiladi.

### 7.3 Almashtirish

- **Muddatli majburiy almashtirish yo'q** — u foydalanuvchini
  `Parol1!` → `Parol2!` ga majburlaydi.
- `must_change` faqat uch holatda: admin reset qilganda (tiket orqali),
  tasdiqlangan kompromissdan keyin, super adminning favqulodda aralashuvi.
  **`must_change=true` holatida sessiya faqat parol almashtirish ekranini
  ochadi** — o'qish marshrutlari ham yopiq (aks holda vaqtinchalik holatdagi
  hisob mijoz PII sini va hisobotlarni o'qiy olardi).
- Autentifikatsiya bilan almashtirish: **joriy parol majburiy** + yangi parol.
  Muvaffaqiyatda joriy sessiyadan tashqari barcha refresh tokenlar bekor
  qilinadi (mavjud `revoke_all_tokens()` qayta ishlatiladi),
  `password_updated_at` yangilanadi, `auth_events: password_change`, Telegramga
  bildirishnoma.
- `password_updated_at > refresh.issued_at` → `REFRESH_STALE` +
  `revoke_all_tokens`.
- Access token ≤300 s yashagani uchun parol almashgach qoladigan oyna cheklangan
  va qabul qilinadi (har so'rovda DB tekshiruvi qo'shilmaydi).
- `apps/admin/src/screens/admin/settings.tsx` dagi «Parolni almashtirish» paneli
  **qaytadi** — DCR-003 bekor qilinadi.

### 7.4 Server hech qachon parol yaratmaydi va uzatmaydi

Vaqtinchalik parolni server yasab, API javobida qaytarib, admin ekranida
ko'rsatish — keng tarqalgan, lekin bu dizaynda **taqiqlanadi**:

1. Admin xodim nomidan kira oladi → `audit_log` ning non-repudiation ma'nosi
   birinchi almashtirishgacha yo'qoladi;
2. parol amalda Telegram/WhatsApp orqali uzatiladi va chat tarixida, brauzer
   HAR faylida, admin ekranining DOM'ida qoladi.

Parolni **faqat egasi** qo'yadi: invayt → `/start` → `requestContact` → OTP →
konsolda parol. Klub admini xodimning parolini hech qachon bilmaydi.

---

## 8. Parolni tiklash

### 8.1 1-pog'ona — o'zi tiklaydi (Telegram bog'langan)

```
POST /auth/staff/password/forgot {login}
    → HAR DOIM 202 + otp_id (noma'lum loginda ham soxta otp_id va teng kechikish)
    → ichkarida: login mavjud va staff_telegram bor va blocked_at NULL bo'lsa
      OTP yuboriladi (purpose='reset', TTL 300 s, 3 urinish)

POST /auth/staff/password/reset {otp_id, otp, new_password}
    → OTP atomik iste'mol qilinadi
    → parol siyosati tekshiriladi
    → auth_consume_reset(ticket_hash, new_hash)   ← SECURITY DEFINER, user_id tiketdan
    → revoke_all_tokens()
    → auth_events: password_reset
    → Telegramga «parolingiz almashtirildi» xabari
```

Bu yerda bot allaqachon tanish (bog'lashda `/start` bosilgan), ya'ni «bot
birinchi yozolmaydi» cheklovi to'sqinlik qilmaydi.

### 8.2 Tiklash kanali parol kanalidan mustaqil

Aynan shu sabab hech qanday parol chegarasi doimiy xizmatdan mahrum qilishga
aylanmaydi: hujumchi login'ni step-up holatiga tiqib qo'ysa ham, haqiqiy egasi
Telegram orqali (yoki zaxira kod bilan) kirib oladi.

**Byudjetlar ajratiladi.** `login` (step-up) va `reset` (forgot) — **alohida**
bucketlar. Bitta bucket bo'lsa hujumchi soatiga 3 marta autentifikatsiyasiz
`forgot` yuborib xodimning step-up OTP byudjetini tugatadi: hisob «qulflanmagan»,
lekin kirib bo'lmaydi — ya'ni lockout-DoS boshqa endpoint orqali qaytadi.
Step-up OTP byudjeti **tasdiqlangan parol hodisasiga** bog'lanadi: parol to'g'ri
kelgan so'rov OTP olishga har doim haqli (bu yo'lni faqat parolni biladigan odam
ochadi).

### 8.3 `otp_id` so'rovchiga bog'lanadi

`otp_id` qaysi IP/qurilma cookie'si bilan yaratilgan bo'lsa, `reset` ham o'sha
manbadan kelishi shart; boshqa manbadan kelgan verify rad etiladi. Aks holda
so'rovni **hujumchi** boshlaydi (`otp_id` uning qo'lida), kod esa qurbonga
ketadi.

### 8.4 Telefon orqali ijtimoiy muhandislikka qarshi

Stsenariy real: hujumchi `forgot` yuboradi, keyin klub telefoniga qo'ng'iroq
qiladi — «PlayBron texnik xizmati, hozir Telegramga kod keldi, aytib yuboring».
Smena vaqtida kassa telefonni doim ko'taradi.

Choralar:

1. Kod matni «PlayBron xodimlari bu kodni hech qachon so'ramaydi» bilan
   boshlanadi; **login xabarga qo'shilmaydi** (qo'ng'iroq qiluvchini ishonchli
   qiladigan detal).
2. **OWNER va SUPER_ADMIN darajasida kod emas, botdagi inline tasdiq tugmasi**
   (`callback_query`, `[TEKSHIRISH]`): tugma matnida so'rovchining IP/shahri va
   qurilmasi ko'rsatiladi. Inline tugmani telefonda aytib bo'lmaydi.
3. `otp_id` ↔ so'rovchi bog'lanishi (§8.3).
4. Har bir xodim paroli tiklanganda klub egasiga darhol bildirishnoma.

### 8.5 Umumiy kompyuterda OTP ikkinchi omil emas

Kassadagi bitta kompyuterda konsol ham, Telegram Web ham ochiq bo'lishi mumkin —
u holda «ikkinchi omil» bitta jismoniy mashinada. Choralar: OWNER darajasida
kod emas inline tasdiq (§8.4.2); OWNER hisobiga «kirish faqat ro'yxatdagi
qurilmalardan» opsiyasi; konsolga idle timeout; hujjatda ochiq qoida —
**OWNER Telegrami klub kompyuterida ochilmaydi**.

### 8.6 Telegram yo'qolgan bo'lsa — zinapoyali break-glass

| Kim | Yo'l |
|---|---|
| STAFF / ADMIN | (a) zaxira tiklash kodi (§5.8); (b) klub OWNER/ADMIN konsoldan yangi invayt yasaydi — eski `staff_telegram` bog'lanishi uziladi, yangi `requestContact` tekshiruvi qaytadan o'tadi |
| OWNER | **faqat super admin panelidan** (§9.2). Klub ADMIN'i OWNER'ni qayta bog'lay **olmaydi** |
| SUPER_ADMIN | `scripts/set_staff_password.py`, `DIRECT_URL`, stdin. Onlayn yo'l yo'q |

Har bir «Telegram bog'lanishini almashtirish» amali: `auth_events` + klub egasiga
va tashkilotdagi boshqa adminlarga bildirishnoma + **24 soat davomida
`password/forgot` bloklanadi** (relink → forgot zanjirini uzadi).

### 8.7 Bot bloklangani ko'rinib turadi

`register_webhook()` hozir `allowed_updates: ["message"]` yozadi. Unga
`my_chat_member` qo'shiladi (`[TEKSHIRISH]` update turi nomi) — xodim botni
bloklaganda `staff_telegram.blocked_at` va `users.tg_blocked_at` to'ladi.
Konsolda xodim kartasida `Bog'lanmagan ⚠` holati **ochiq ko'rsatiladi**, aks
holda bu faqat parol unutilgan kuni — eng yomon paytda — ma'lum bo'ladi.

Qo'shimcha: yuborish shifti **so'rovchi** tomonidan hisoblanadi, qurbon
tomonidan emas — bir kishi boshqasining kanalini spam bilan o'chira olmasin.

---

## 9. Xodim qo'shish

### 9.1 Oqim

1. `POST /clubs/{id}/staff` — ism, telefon (E.164 `+998…`), rol, **login**.
   Login maydonini forma taklif qiladi (`{ism}.{klub_qisqartmasi}`), admin
   o'zgartira oladi. **Jonli bandlik tekshiruvi endpointi yo'q**
   (`GET /auth/login-available` **yaratilmaydi**): global login makonida u
   istalgan klub adminiga boshqa klublarning loginlarini sanab chiqish imkonini
   beradi. Bandlik faqat saqlashda, xato sifatida aytiladi.
2. Server tranzaksiyada yaratadi:
   `users(kind='staff', status='invited', login, telegram_id=NULL, phone=<kutilayotgan>)`
   + `memberships(user_id, club_id, role, kind='staff')`.
   `staff_credentials` yozuvi **hali yo'q** → parolsiz hisobga kirib bo'lmaydi
   (`auth_lookup_staff` NULL qaytaradi, dummy xesh yo'li ishlaydi, javob oddiy 401).
3. Invayt: `secrets.token_urlsafe(32)`, DB'da `sha256` xeshi, TTL 12 soat, bir
   martalik. Havola admin ekranida **bir marta** ko'rsatiladi (server uni qayta
   ko'rsatolmaydi). Qayta yuborish = yangi token, eskisi bekor.
4. Xodim: `/start` → `requestContact` → OTP → konsolda parolni **o'zi** qo'yadi
   → `status='active'`.
5. Faollashtirish oxirida zaxira tiklash kodlari bir marta ko'rsatiladi (§5.8).

### 9.2 Rol shifti — DB darajasida

**Hujum:** klub ADMIN'i OWNER uchun «Telegram bog'lanishini almashtirish» yoki
yangi invayt yasaydi, `expected_phone` ga **o'z** raqamini kiritadi, havolani
o'zi ochadi, o'z kontaktini ulashadi — hamma shart halol o'tadi. Endi OWNER
hisobining OTP kanali unga qaragan; `password/forgot` → parol → to'lov
kalitlari.

**Choralar (barchasi kerak):**

| Qatlam | Chora |
|---|---|
| RLS | `memberships_write` ikkiga bo'linadi (§3.5): ADMIN faqat `role='STAFF'` qatorlarga tegadi va o'z qatorini ko'tara olmaydi |
| RLS | `staff_invites` policy'siga maqsad roli sharti: `EXISTS (SELECT 1 FROM memberships t WHERE t.user_id = target AND t.club_id = club_id AND t.role = 'STAFF')` ADMIN uchun |
| Funksiya | `auth_consume_invite()` invayt qatoridagi rolga **ko'r-ko'rona ishonmaydi** — yaratuvchining o'sha paytdagi roliga qarab qayta tekshiradi (`SECURITY DEFINER` RLS'ni chetlab o'tgani uchun tekshiruv **funksiya ichida** bo'lishi shart) |
| API | ADMIN → faqat STAFF yaratadi/reset qiladi; OWNER → ADMIN va STAFF; OWNER'ning o'zi ustidagi har qanday reset/relink — **faqat super admin** |
| Bildirishnoma | har bir relink/reset OWNER'ga va tashkilotdagi boshqa adminlarga |

### 9.3 Xodim kartasi (`staff.tsx`) — DCR-004 qayta yoziladi

- **«Login» ustuni qoladi** — u endi haqiqiy identifikator.
- Yangi **«Telegram» ustuni**: `Kutilmoqda` (invayt yuborilgan) / `@username`
  (bog'langan) / `Bog'lanmagan ⚠` (OTP yetkazib bo'lmaydi).
- Amallar: «Taklif yuborish», «Parolni tiklash» (ochiq parol emas — tiket
  yaratadi, `must_change=true`, barcha tokenlar bekor), «Telegram bog'lanishini
  almashtirish» (rol shifti bilan cheklangan).
- Jadval ustunlari soni o'zgarmaydi.

### 9.4 Ishdan bo'shatish

`memberships.status='inactive'` + `users.status='disabled'` +
`revoke_all_tokens(user_id)` + faol invaytlar bekor + `staff_devices` bekor.
`0003` dagi `memberships_read`/`clubs_read` policy'lari allaqachon
`status='active'` ni talab qiladi, ya'ni bo'shatilgan xodim ma'lumot ko'rmaydi.
Qolgan oyna — access token muddati (300 s).

Tarif chegarasi: xodim soni `plans.limits.staff_per_club` dan oshsa
`403 LIMIT_REACHED` (mavjud `core/errors.py::LimitReached`).

---

## 10. Chegaralar jadvali

Barchasi Redis'da (sliding window / token bucket), **har doim eng qimmat ishdan
(Argon2, DB) OLDIN**. Loginlar kalitda hech qachon ochiq emas:
`sha256(normallashgan_login)` (§6.2).

### 10.1 Jadval

| Endpoint | Kalit | Chegara | Sabab |
|---|---|---|---|
| `POST /auth/staff/login` | IP | 10 / 15 daq (burst 5) | qo'pol skanerlash |
| `POST /auth/staff/login` | `sha256(login)` | 8 / 15 daq → eksponensial kechikish (**qulf yo'q**) | maqsadli brute-force |
| `POST /auth/staff/login` | IP + `sha256(login)` | 5 / 5 daq | aniqroq; NAT ostidagi klubni jazolamaydi |
| `POST /auth/staff/login` | Argon2 hovuzi | `CapacityLimiter(4)` + tanilgan qurilma rezervi; navbat 2 s | OOM va halol trafik |
| `POST /auth/staff/otp/request` (step-up) | tasdiqlangan parol hodisasi | 3 / soat, ≥60 s oralig'i | `forgot` byudjeti bilan **aralashmaydi** |
| `POST /auth/staff/password/forgot` | `sha256(login)` | 3 / soat, 10 / kun, ≥60 s | tiklash spam'i |
| `POST /auth/staff/password/forgot` | IP | 10 / soat | |
| `POST /auth/staff/otp/verify`, `.../password/reset` | `otp_id` | 3 urinish (keyin kod o'chadi) + `(user, purpose)` bo'yicha 9/soat | ko'p kod so'rash byudjetni oshirmasin |
| `POST /auth/staff/activate` | invayt token xeshi | 5 / soat | |
| `POST /auth/owner/signup` | IP | 3 / soat, 10 / kun | soxta tashkilot |
| `POST /auth/refresh` | IP | 60 / daq | qonuniy issiq yo'l |
| `POST /auth/refresh` | `sha256(token)` | 5 / daq | rotatsiya poygasi |
| `POST /auth/customer/miniapp` | `telegram_id` | 30 / daq | |
| `POST /auth/customer/miniapp` | IP | 60 / daq | Telegram WebView'lari NAT ostida |
| Bot webhook (ikkalasi) | `message.from.id` | 20 / daq, oshig'i jimgina tashlanadi | Telegram'ga baribir 200 |
| Kontakt nomuvofiqligi | `telegram_id` | 3 → 10 daq jim | |

### 10.2 Nega bu lockout-DoS emas

1. **Hech qanday hisob qulflanmaydi** — chegaradan oshgan login kechikish oladi,
   qurilma tanilmagan bo'lsa step-up so'raladi. Haqiqiy egasi doim o'tadi.
2. Barcha chegaralar vaqt bilan so'nadi, qo'lda ochish talab qilmaydi.
3. Tiklash kanali (Telegram OTP / zaxira kod) parol kanalidan mustaqil va
   uchinchi shaxs tomonidan chegaralanmaydi (§8.2).
4. Step-up **qurilma** dalilidan kelib chiqadi, uchinchi shaxsning
   muvaffaqiyatsizlik hisoblagichidan emas (§6.3).

### 10.3 Global tripwire — faqat kuzatuv

«Daqiqasiga >200 muvaffaqiyatsizlik → hamma uchun step-up» qoidasi
**rad etiladi**. 250–300 IP dan bittadan so'rov per-IP va per-login
chegaralarining birortasini ham ishga tushirmaydi, lekin global hisoblagichni
oshiradi va butun platformani majburiy OTP holatiga tiqadi — bu bitta
hujumchining qo'lidagi «SaaS ni ish vaqtida o'chirish» tugmasi.

O'rniga:

- global hisoblagich — **signal**: super adminga ogohlantirish, `auth_events`,
  dashboard ko'rsatkichi;
- avtomatik javob faqat **tor segmentga** (ASN/subnet, yangi IP, yangi UA,
  mos kelmayotgan geo);
- tanilgan qurilma cookie'si bo'lgan sessiyalar bu rejimdan ozod;
- `Bog'lanmagan ⚠` xodimlar uchun zaxira yo'l (zaxira kod, OWNER tasdig'i)
  ochiq qoladi.

### 10.4 Redis tushib qolsa

| Yo'l | Xatti-harakat | Sabab |
|---|---|---|
| Parol kirishi, OTP, initData replay guard | **fail-CLOSED (503)** | fail-open brute-force'ni ochadi va `forgot` ni cheklovsiz Telegram-yuborish kuchaytirgichiga aylantiradi; OTP baribir ishlamaydi, ya'ni fail-open hech narsa yutmaydi |
| Mijoz bot FSM | fail-open (oqim boshidan) | hech qanday huquq berilmaydi |
| `POST /auth/refresh` | ishlayveradi | faqat Postgres'ga tayanadi |

Ya'ni Redis uzilishi = **«yangi kirish yo'q, ishlayotgan smena to'xtamaydi»**.
Bu ochiq-oydin yangi bog'liqlik: Redis SLA'si endi auth SLA'si.

### 10.5 `client_ip()` tuzatiladi

`core/http.py:16-19` ikki nuqsonli:

1. `request.headers.get()` bir nechta bir xil nomli sarlavha **qatoridan faqat
   birinchisini** qaytaradi;
2. `"1.2.3.4,"` → `rsplit(",", 1)[-1].strip() or None` → **`None`**
   (`test_client_ip.py::test_empty_header_falls_back_to_none` buni tasdiqlaydi).

Hujum: `X-Forwarded-For: x,` yuborib barcha IP-scoped chegaralarni chetlab o'tish
(agar `None` da tekshiruv o'tkazib yuborilsa) yoki `"none"` bucketini ataylab
to'ldirib halol trafikni 429 ga tiqish.

**Qaror:**

- sarlavha qatorlari birlashtirib o'qiladi (`getlist`/raw scope), eng o'ng
  element **o'sha birlashgan** ro'yxatdan olinadi;
- natija `ipaddress.ip_address()` bilan tekshiriladi — noto'g'ri qiymat `None`
  emas, **aniq xato**;
- rate limiter uchun `None` = **eng qat'iy chelak** (yoki peer IP);
  «chegarasiz» varianti taqiqlanadi;
- `deps.py:114` dagi `/platform/*` allowlist allaqachon fail-closed — o'zgarmaydi;
- `test_client_ip.py` ga ikki test: takrorlangan sarlavha qatorlari va `"a,"`.

---

## 11. Ilova yuzalari

| Yuza | Kim | Kirish | Joylashuv |
|---|---|---|---|
| `apps/miniapp` | CUSTOMER | `initData`, **jimgina, ekransiz** | faqat `@playbronbot` ichidagi Mini App |
| `apps/admin` | STAFF / ADMIN / OWNER | login + parol | **brauzer** (desktop va mobil web) |
| `apps/admin` `/platform/*` | SUPER_ADMIN | login + parol + majburiy OTP + IP allowlist | brauzer |
| `apps/landing` | ochiq | — | «Konsolga kirish» va «Klub ochish» havolalari |

### 11.1 Xodim Mini App'i yaratilmaydi

Bu xavfsizlik qarori, qulaylik emas:

1. Xodim Mini App'i muqarrar ravishda **ikkinchi `initData` yuzasini** keltiradi.
   U `ADMIN_BOT_TOKEN` bilan tekshirilishi kerak bo'lardi va o'sha zahoti
   «xodim Telegram bilan kiradi» yo'li qayta tug'ilardi.
2. Ikkita `initData` endpointi bo'lsa, ular orasidagi **token chalkashuvi**
   (bir endpoint ikkinchisining imzosini qabul qilishi) klassik xatoga aylanadi.
   Bitta endpoint = chalkashish imkoniyati nol.
3. Telegram WebView'da to'lov redirect'i (Click/Payme) og'riqli —
   `01-architecture.md` §4 shu sababdan brauzer kabinetini tanlagan.

`docs/designs/PlayBron Xodim Mobil.dc.html` — **mobil web layout**, Mini App emas.

**`login-hint` kabi endpoint yaratilmaydi** (`initData` → login satri). U
cross-tenant «kim xodim va uning logini nima» orakuli bo'lardi va biznes qarori
taqiqlagan bog'lanishni API darajasida qaytadan tiklardi. Loginni oldindan
to'ldirish faqat mijoz tomonda, qurilma chiplaridan (§6.8).

### 11.2 Landing

Telegram Login Widget **butunlay olib tashlanadi** (`verify_widget` bilan birga).

### 11.3 Mijoz brauzerda

`initData` yo'q → kirish yo'li yo'q. Ekran: «PlayBron Telegram ichida ishlaydi» +
`t.me/playbronbot` havolasi. Hozirgi mock rejim (`apps/miniapp/src/lib/auth.ts`)
faqat `import.meta.env.DEV` da qoldiriladi.

### 11.4 Mijoz profilida faol sessiyalar

Mini App profil ekraniga «Faol qurilmalar / chiqish» bo'limi qo'shiladi. Hozir
o'g'irlangan mijoz sessiyasini aniqlash yoki bekor qilish imkoniyati **nol**.

---

## 12. Migratsiya rejasi

Repo ildizi: `C:\Users\Xurshid Istamov\Documents\Claude\Projects\Playbron`

### 12.1 Migratsiya fayli

`api\migrations\versions\0005_two_worlds_auth.py`
(`down_revision = "0004_role_passwords"`, `downgrade()` → `NotImplementedError`).

Mazmuni:

1. `users`: `kind`, `login`, `status`, `display_name`, `phone_reverified_at`;
   `telegram_id` `DROP NOT NULL`; uchta CHECK; `users_telegram_id_uk` DROP +
   to'rtta yangi indeks (§3.1).
2. `memberships`, `super_admins`: `kind` + kompozit FK — **`NOT VALID` bilan
   qo'shiladi**, backfill'dan keyin `VALIDATE CONSTRAINT`.
3. Backfill (§12.5).
4. Yangi jadvallar: `staff_telegram`, `staff_credentials`, `staff_invites`,
   `staff_devices`, `staff_recovery_codes`, `auth_events` — har biri **o'sha
   migratsiyada** `ENABLE` + `FORCE ROW LEVEL SECURITY`, policy va **aniq
   `GRANT`** bilan (CLAUDE.md qoidasi; `0003` `ALTER DEFAULT PRIVILEGES` ni
   revoke qilgan, yozilmasa jadvallar ilovaga umuman ko'rinmaydi).
5. `refresh_tokens`: `kind`, `chain_started_at`, `device_hash`.
6. `audit_log`: `club_id`; `audit_log_read` qayta yoziladi (§3.5).
7. `users_self` DROP/CREATE — `AND kind='customer'` bilan.
8. `memberships_write` → `memberships_write_owner` + `memberships_write_admin`.
9. `SECURITY DEFINER` funksiyalari (§3.6) + **mavjud `app_club_role()` ning
   egasini `playbron_platform` ga o'tkazish**.
10. `REVOKE UPDATE (kind) ON users`, `REVOKE ALL ON staff_credentials`,
    `REVOKE ALL ON staff_recovery_codes`.
11. Yakuniy **assert** (§12.5).

### 12.2 O'chadi

| Fayl / element | Izoh |
|---|---|
| `api\...\auth\telegram.py`: `verify_widget()`, `_widget_token()` | Login Widget yo'li |
| `api\...\auth\router.py`: `POST /auth/telegram/widget`, `WidgetIn` | |
| `api\...\auth\router.py`: `POST /auth/dev/login`, `DevLoginIn` | saqlash sababi yo'qoldi (u faqat «Widget localhost'da ishlamaydi» uchun edi); env bilan qo'riqlanadigan zaxira eshikni olib tashlash sof yutuq |
| `api\...\auth\router.py`: kirish beruvchi `POST /auth/telegram/start`, `/start/{nonce}` | bog'lash vazifasi `botlink.py` ga (§12.3) |
| `apps\admin\src\store\session.ts`: `beginTelegramLogin`, `pollTelegramLogin`, `signInDev`, `TELEGRAM_LOGIN_BOT`, `DEV_TELEGRAM_ID` | |
| `packages\api-client\src\endpoints.ts`: `signInWithWidget` | |
| `apps\miniapp\src\screens\register.tsx` | ro'yxatdan o'tish 100% botda; ekran «Botni oching» darvozasiga aylanadi |
| `render.yaml`: `VITE_TELEGRAM_LOGIN_BOT`, `WIDGET_TTL_SEC` | |
| `core/config.py`: `widget_ttl_sec` | |

### 12.3 `botlogin.py` **butunlay o'chirilmaydi**

`main.py:14` uni import qiladi va `main.py:40` `botlogin.register_webhook()` ni
chaqiradi; webhook marshruti `webhook_secret_token()` ga tayanadi. Fayl o'chsa
API umuman ishga tushmaydi.

Qaror: `botlogin.py` → `api\src\playbron\modules\telegram\` paketiga ko'chadi va
**bog'lash** vazifasiga o'tadi:

- `register_webhook()` — ikkala bot uchun umumiylashtiriladi
  (`allowed_updates: ["message", "my_chat_member"]`);
- `webhook_secret_token()` — saqlanadi, endi bot nomiga qarab tegishli
  sekretdan hisoblanadi;
- `start_login/approve_login/poll_login` → `start_link/approve_link/poll_link`:
  **sessiya bermaydi**, `{status, telegram:{id, first_name, username}}` qaytaradi;
- `extract_start` — prefiks bo'yicha, lekin **marshrutga qattiq bog'langan** (§5.3);
- `notify` — saqlanadi, lekin OTP kanalida «xato oqimni to'xtatmaydi»
  yondashuvi **qo'llanmaydi**: `sendMessage` 403 → `blocked_at` + konsolda
  ko'rsatiladi.

`apps\admin\src\screens\login.tsx` dagi `saveAttempt`/`loadAttempt`/`watch`/
`POLL_INTERVAL_MS`/`POLL_TIMEOUT_MS`/`FALLBACK_DELAY_MS`/`ATTEMPT_KEY` mantiqi
o'chirilmaydi — u **faollashtirish/bog'lash** ekraniga (`/join`, `/activate`)
ko'chadi. Panel, brend ustuni, `Backdrop`, barcha `CSSProperties` konstantalari
va layout **tegilmaydi**; panel ichi ikkita `TextField` + tugmaga almashadi.

### 12.4 O'zgaradi

| Fayl | O'zgarish |
|---|---|
| `core\config.py` | `+OTP_PEPPER`, `+MAIN_BOT_WEBHOOK_SECRET`, `+ADMIN_BOT_WEBHOOK_SECRET`, `+TELEGRAM_IP_RANGES`, `+STAFF_ACCESS_TTL_SEC`, `+STAFF_REFRESH_TTL_SEC`, `+STAFF_SESSION_MAX_SEC`, `+OTP_TTL_*`, `+ARGON2_*`, `+SUPER_ADMIN_LOGINS`, `+MINIAPP_URL`, `+CONSOLE_URL`; `−widget_ttl_sec`; prod tekshiruvlari ro'yxatiga qo'shiladi (mavjud `RuntimeError` naqshi); start'da `main_secret != admin_secret` |
| `core\security.py` | `+hash_password`, `+verify_password`, `+needs_rehash`, `+DUMMY_HASH` (start'da bir marta, **aynan shu parametrlar** bilan), `+new_otp`, `+otp_digest`, `+hmac_hex`; `encode_access(..., audience)`, `decode_access(token, *, audience)` |
| `core\http.py` | `client_ip()` §10.5 bo'yicha |
| `core\db.py` | `set_telegram_scope()` docstring'i «faqat mijoz» deb aniqlashtiriladi |
| `models.py` | `User.kind/login/status/display_name/phone_reverified_at`, `telegram_id: int \| None`; `StaffTelegram`, `StaffCredential`, `StaffInvite`, `StaffDevice`, `StaffRecoveryCode`, `AuthEvent`; `RefreshToken.kind/chain_started_at/device_hash`; `Membership.kind`; `AuditLog.club_id`; `User` docstring'idagi «Parol yo'q» tuzatiladi |
| `deps.py` | `+require_staff_token` (`require_role`/`require_super_admin` ichida), `+require_club_scope`, `+require_password_current`; `len(roles)==1` avtotanlash olib tashlanadi |
| `modules\auth\service.py` | `+_finish_session()`; `upsert_user` ga `kind='customer'` va **`index_where=`** (qisman indeks bilan `ON CONFLICT` aks holda `InvalidColumnReference` beradi va **har bir mijoz kirishi yiqiladi**); ism normallashtirish (§3.8); `sign_in` → `aud='customer'`, `mbr=[]`, `sa=False`; `guard_replay` idempotent + TTL formulasi (§4.5); `rotate_refresh` `kind` va `chain_started_at` bilan |
| Yangi API modullari | `core\ratelimit.py`, `modules\auth\otp.py`, `modules\auth\password.py`, `modules\auth\staff.py`, `modules\telegram\{webhook,customer_bot,admin_bot,fsm}.py` |
| `main.py` | ikkita webhook ro'yxati; webhook sarlavhasi log qora ro'yxati |
| `core\errors.py` | `+RateLimited(status_code=429, code='RATE_LIMITED')` |
| `pyproject.toml` | `+argon2-cffi>=23.1` |
| `packages\api-client` | `−signInWithWidget`; `+signInWithPassword`, `+forgotPassword`, `+resetPassword`, `+changePassword`, `+activateStaff`, `+startStaffLink`, `+pollStaffLink`; refresh cookie rejimiga o'tish; `types.ts`: `UserOut.telegram_id: number \| null`, `+login`, `+kind`, `AuthSession.+audience` |
| `apps\admin\src\i18n.ts` | `telegramButton`, `confirmInTelegram`, `openViaTme`, `startExpired`, `devHint`, `devButton`, `authMethodLabel` o'chadi; login/parol/OTP/faollashtirish/tiklash/zaxira kod kalitlari qo'shiladi; `Lang = 'uz' \| 'ru'` (DCR-007) |
| `docs\01-architecture.md` §2 | to'liq qayta yoziladi — bu hujjatga havola |
| `docs\design-change-requests.md` | Ilova B |

### 12.5 Super adminlar — platformani o'zi-o'zi qulflashdan saqlash

`0002_seed.py:174-198` super adminlarni **faqat `telegram_id`** bilan yaratadi:
`memberships` yozuvi yo'q, `organizations.owner_user_id` ham yo'q.

**Xavf:** agar backfill faqat «membership egalarini `kind='staff'` ga o'tkazish»
bo'lsa, super adminlar `kind='customer'` bo'lib qoladi va `super_admins` ga
qo'shilayotgan kompozit FK mavjud qatorlarda **validatsiyadan o'tmaydi** —
`SUPER_ADMIN_TELEGRAM_IDS` bir marta ishlatilgan har qanday bazada migratsiya
to'xtaydi. Deploy tunidagi «tez tuzatish» esa ularni `login` siz va
`staff_credentials` siz `kind='staff'` ga o'tkazadi → `/platform/*` ga kirish
yo'li **butunlay yopiladi**.

**Qaror:**

1. Backfill imtiyoz manbalarining **hammasi** bo'yicha:
   `super_admins` ∪ `memberships` ∪ `organizations.owner_user_id`.
2. Ularning `telegram_id` si `users` dan `staff_telegram` ga **ko'chiriladi**
   (§2.1 invarianti: xodimda `users.telegram_id` NULL).
3. Loginlar **0005 ning o'zida** yaratiladi (`SUPER_ADMIN_LOGINS` env'idan).
   **`0002_seed` ga tegilmaydi**: bo'sh bazada u 0005 dan oldin yuradi va
   `kind`/`login` ustunlari hali mavjud emas → butun zanjir yiqiladi; prod'da
   esa u allaqachon stamp qilingan va hech qachon qayta yurmaydi.
4. FK `NOT VALID` bilan qo'shiladi, backfill'dan keyin `VALIDATE CONSTRAINT`.
5. Migratsiya oxirida **assert**:
   `SELECT count(*) FROM super_admins sa JOIN users u ON u.id = sa.user_id
    WHERE u.kind <> 'staff' OR u.login IS NULL` noldan farq qilsa
   `RAISE EXCEPTION`. Platformani qulflagandan ko'ra deploy'ning yiqilgani yaxshi.

### 12.6 Chiqarish tartibi (runbook)

```
1. 0005 migratsiyasi                         (DIRECT_URL)
2. scripts/set_staff_password.py             super admin parollari, stdin
3. Super admin @playbronadminbot ni /start   OTP kanali ochiladi
4. Yangi API deploy                          eski marshrutlar 410 GONE
5. Mavjud membership egalariga invayt        (deploy kuni, hammasiga)
6. Konsol build
7. Bir haftadan keyin 410 marshrutlar o'chadi
```

- **Aks tartibda platforma o'zini o'zi qulflaydi.**
- Eski `/auth/telegram/start*`, `/auth/telegram/widget`, `/auth/dev/login`
  darrov o'chirilmaydi — **bir hafta `410 GONE`** bilan javob beradi. Aks holda
  smena o'rtasidagi deploy barcha konsol foydalanuvchilarini bir zumda tushirib
  yuboradi.
- `aud` klaymi yo'q eski access tokenlar 401 beradi; migratsiyada
  `UPDATE refresh_tokens SET revoked_at = now()` — Widget bilan olingan
  sessiyalar qolib ketmasin.
- **Faza 1 da real ma'lumot yo'q** — barcha xodimlarni qayta provizioning
  qilish hozir arzon, keyinroq qimmat.

---

## 13. Testlar

### 13.1 O'chadigan / o'zgaradigan mavjud testlar

| Test | Nima bo'ladi |
|---|---|
| `api\tests\test_bot_login.py` (5 test, 188 qator) | `test_staff_link.py` ga qayta yoziladi: poll `linked` + telegram profil qaytaradi, **sessiya yo'q**; nonce bir martalik; `test_webhook_requires_secret` shu yerga ko'chadi |
| `test_telegram_auth.py::test_widget_valid`, `::test_widget_tampered_rejected`, `::test_widget_uses_admin_bot_not_main_bot`, `::test_widget_and_initdata_use_different_keys` | o'chadi (`verify_widget` yo'q) |
| `test_telegram_auth.py` — 7 ta `initData` testi | **o'zgarishsiz qoladi** |
| `test_telegram_auth.py::test_real_initdata_sample` | **skip'dan chiqariladi** — reliz darvozasi (§2.4) |
| `test_auth_flow.py::test_replay_is_rejected` | `test_repeated_initdata_is_idempotent` ga aylanadi: ikkinchi so'rov ham 200, **mavjud sessiya** qaytadi |
| `test_auth_flow.py::test_owner_sees_club_and_plan` | **ikkiga bo'linadi** — (a) OWNER `initData` bilan kirsa `memberships == []` va `is_super_admin is False`; (b) parol bilan kirsa klub va tarif ko'rinadi |
| `test_auth_flow.py::test_foreign_club_header_is_rejected` | parol bilan kirgan sessiyaga o'tkaziladi |
| `test_auth_flow.py` qolgani | o'zgarishsiz o'tadi |
| `test_rls_hardening.py::test_every_table_has_rls` | oltita yangi jadval RLS'siz qo'shilsa **yiqiladi** — bu uning vazifasi |
| `test_rls.py` | fixture'lariga `kind` qo'shiladi |
| `test_client_ip.py` | ikki yangi test (§10.5) |

### 13.2 Yangi testlar — majburiy (har biri aniq bir hujumni qulflaydi)

**Ikki dunyo chegarasi**

1. Mijoz `initData`si xodim qatorini **ocholmasligi** (`users_self` regressiyasi).
2. Mijozga membership yozib bo'lmasligi (kompozit FK → `DBAPIError`).
3. `kind` ni ilova roli **UPDATE qila olmasligi**.
4. Mijoz refresh tokeni rotatsiyadan keyin ham hech qachon `aud='staff'`
   bermasligi.
5. Parol bilan olingan sessiya rotatsiyadan keyin ham `aud='staff'` saqlashi.
6. Super adminning Mini App sessiyasida `mbr == []` va `sa is False`.

**Kirish**

7. Noma'lum login va noto'g'ri parol — javob **shakli va vaqti teng** (dummy xesh).
8. `KASSA01`, `kassa01`, fullwidth `ｋassa01`, Kelvin `K`assa01 — **bitta**
   rate-limit bucketiga tushishi.
9. `status='invited'`/`'disabled'` — aynan o'sha 401.
10. Rate limiter Argon2 **dan oldin** ishlashi (Argon2 chaqirilmagani).
11. `CapacityLimiter` chegarasi: N+1-so'rov navbatda kutadi, RSS cho'qqisi
    belgilangan chegaradan oshmaydi.
12. Redis yo'qligida parol kirishi va OTP — **503** (fail-closed).

**OTP**

13. OTP Redis'da **ochiq emas** (dump'da kod topilmaydi).
14. 200 parallel noto'g'ri taxmin → aynan 3 tasi hisoblanadi, kod o'chadi
    (atomiklik).
15. `forgot` byudjetini tugatish step-up OTP ni **bloklamaydi**.
16. Uchinchi shaxs `forgot` yuborsa qurbonning qo'lidagi kod **amal qilaveradi**.
17. Boshqa IP/qurilmadan kelgan `reset` rad etiladi.

**Bot va webhook**

18. `contact.user_id` **yo'q** → rad etiladi (`None != from.id` tuzog'i).
19. `contact.user_id != from.id` → rad etiladi.
20. Guruh chatidan kelgan kontakt → rad etiladi.
21. `forward_origin` / `via_bot` bor kontakt → rad etiladi.
22. `awaiting_contact` holati yo'q → rad etiladi.
23. Bir xil `update_id` ikki marta → telefon **bir marta** yoziladi.
24. Handler ichida istisno → javob baribir **200**.
25. `inv_<token>` **mijoz** marshrutiga yuborilsa jimgina tashlanadi.
26. Main va admin webhook sekretlari **teng bo'lsa** ilova ishga tushmaydi.

**Provizioning va rol shifti**

27. ADMIN kontekstida `INSERT INTO memberships (..., role) VALUES (..., 'OWNER')`
    → `DBAPIError`.
28. ADMIN o'z qatorini `UPDATE ... SET role='OWNER'` → `DBAPIError`.
29. ADMIN OWNER uchun invayt/relink yarata olmasligi.
30. Invaytning bir martaligi; telefon mos kelmasa **iste'mol qilinmasligi**.
31. OWNER(A) + STAFF(B) foydalanuvchi `X-Club-Id: A` bilan `/clubs/B/staff` ga
    **403**.

**Parol va tiklash**

32. Parol siyosati: uzunlik rol bo'yicha, login/telefonni o'z ichiga olishi,
    qora ro'yxat.
33. `must_change=true` holatida **o'qish marshrutlari ham** yopiq.
34. Parol almashgach barcha refresh tokenlar bekor; `password_updated_at`
    eskirgan refresh → `REFRESH_STALE`.
35. Zaxira tiklash kodi bir marta ishlashi.

**Sessiya**

36. Mutlaq zanjir chegarasi: 24 soatdan keyin rotatsiya rad etiladi.
37. Boshqa `device_hash` bilan refresh → `revoke_all_tokens`.
38. Qurilma cookie'si **boshqa foydalanuvchida** taqdim etilsa e'tiborsiz
    qolishi (step-up baribir so'raladi).

### 13.3 Mijoz oqimi testlari

39. To'liq ro'yxatdan o'tish telefonni yozadi va `phone_verified_at` ni to'ldiradi.
40. `initData` qayta yuborilishi 401 bermasligi (idempotentlik).
41. Replay kaliti TTL'i imzo oynasidan **qisqa emasligi** (soat siljishi testi).
42. Telefon egaligini o'tkazish: eski qatorda `phone` NULL bo'lishi, `auth_events`
    yozuvi, 30 kunlik chegara.
43. `first_name` da bidi/boshqaruv belgilari `upsert_user` da tozalanishi.

### 13.4 Infratuzilma testi — non-superuser ega

**Majburiy, chunki hozirgi test to'plami buni yashiradi.** `docker-compose` ga
alohida **superuser bo'lmagan** `playbron_owner` roli qo'shiladi; CI'da
migratsiya va funksiyalar o'sha rol ostida yuritiladi va tekshiriladi:

- `auth_lookup_staff()` haqiqiy qator qaytaradi (FORCE RLS ostida bo'sh emas);
- `app_club_role()` haqiqiy rol qaytaradi va rekursiya bermaydi;
- `auth_consume_invite()` yozadi.

Bu testsiz §3.6 dagi nuqson faqat prod'da, deploy tunida ma'lum bo'ladi.

---

## 14. Hal qilinmagan savollar

Quyidagilar **ochiq** — dizayn ularga javob bermaydi, qaror kerak.

1. **`initData` ichidagi `signature` maydoni.** `data_check_string` ga
   kiradimi? Reliz darvozasi (§2.4), lekin haqiqiy namuna hali yo'q. Namuna
   qayerdan olinadi va kim tasdiqlaydi?
2. **Login makoni global unikalmi?** Hozirgi qaror — ha (`{ism}.{klub}` naqshi
   bilan). Klub soni o'sganda mashhur loginlar tugaydi. Muqobil: klub ichida
   unikal + kirish formasida «klub kodi» maydoni (bitta maydon ko'p, smena
   boshida sekinroq).
3. **Bitta odam ham mijoz, ham xodim** (ikki qator, ikki sessiya) biznes uchun
   maqbulmi? Xodim o'z klubida mijoz sifatida bron qilsa bu ikki profil sifatida
   ko'rinadi. Chegirma siyosati bunga qanday qaraydi?
4. **Umumiy «kassa» hisobi.** Klub bitta login so'rasa — smenada kim bo'lsa
   o'sha ishlatadi — ruxsat beriladimi? Bu `audit_log` ning atributsiya ma'nosini
   yo'qotadi. Tavsiya: qat'iy taqiqlash va shartnomada yozib qo'yish.
5. **`auth_events` ni kim o'qiydi?** Klub egasi o'z xodimlarining kirish
   urinishlarini ko'rsinmi (foydali, lekin xodim uchun kuzatuv)? 180 kun
   kifoyami?
6. **Telefon egaligini o'tkazish avtomatikmi?** §4.6 avtomatik o'tkazishni
   tanlaydi (30 kunda bir marta). Muqobil: klub xodimi qo'lda tasdiqlasin —
   qo'llab-quvvatlash yuki oshadi, lekin bron tarixi uzilmaydi.
7. **OWNER uchun «tanilgan qurilma» chegarasi.** 60 kunlik cookie yetarlimi yoki
   OWNER uchun har kirishda OTP majburiy bo'lsinmi? Ikkinchisi umumiy
   kompyuterda baribir kuchsiz (§8.5).
8. **Bot va konsol i18n qamrovi.** CLAUDE.md `uz/ru/en` deydi, DCR-007 va
   `docs/00-audit.md` esa `uz/ru`. Bu hujjat `uz/ru` ni tanlaydi (DCR-007
   bajariladi) — CLAUDE.md yangilanishi kerak.
9. **Telegram chiquvchi IP diapazonlari.** Ular o'zgarsa webhook to'xtaydi.
   Env'da saqlash yetarlimi yoki monitoring kerakmi?
10. **`must_change` holatidagi hisob qancha yashaydi?** Admin reset qilgan, lekin
    xodim hech qachon kirmagan hisob — 30 kundan keyin `disabled` bo'lsinmi?

---

## Ilova A — Hujum topilmalarini yopish matritsasi

Har bir **critical** va **high** topilma uchun: qaysi bo'lim, qaysi chora.
Yopilmaganlari §14 da.

### A.1 Critical

| # | Hujum | Chora | Bo'lim |
|---|---|---|---|
| C-1 | Rate-limit kaliti normallashtirilmagan login ustidan → per-hisob chegara cheksiz aylanadi | NFKC→casefold→trim→regex **limiterdan oldin**; kalit **aynan qidiruvdagi** satrdan; homoglif testi | §6.1, §6.2, §13.2/8 |
| C-2 | Argon2 konkurrentlik limitersiz → autentifikatsiyasiz OOM va API sikli | `CapacityLimiter(4)` (76 MiB), tanilgan qurilma rezervi, navbat timeout'i, CI RSS darvozasi | §6.4, §13.2/11 |
| C-3 | Soxta webhook = xodim hisobini to'liq egallash (egalik tekshiruvining ikkala tomonini hujumchi yozadi) | ikki mustaqil sekret + start'da tenglik tekshiruvi; Telegram IP allowlist; bog'lash DB'dagi tiketga va telefon mosligiga tayanadi, webhook payload'ining o'ziga emas; sarlavha log qora ro'yxatida | §5.4, §5.2 |
| C-4 | ADMIN → OWNER imtiyoz oshirish (invayt/relink maqsad rolini tekshirmaydi, iste'mol RLS'ni chetlab o'tadi) | `memberships_write` ikkiga bo'linadi; `staff_invites` policy'sida maqsad roli; tekshiruv `auth_consume_invite()` **ichida**; OWNER relink faqat super admin | §3.5, §9.2, §13.2/27-29 |
| C-5 | `memberships_write` da rol shifti yo'q → ADMIN o'ziga OWNER yozadi va to'lov kalitlarini oladi | shu yerda | §3.5, §9.2 |
| C-6 | O'g'irlangan `initData` → 30 kunlik mijoz sessiyasi, qurbonda abadiy 401 | mijoz refresh sliding 24 soat + mutlaq 30 kun, uzaytirish faqat yangi imzo bilan; qurilma bog'lanishi; replay idempotent va mavjud sessiyani qaytaradi; mount'dagi shartsiz POST olib tashlanadi; profilda «faol qurilmalar» | §4.5, §6.5, §11.4 |
| C-7 | Webhook sekreti telefon tasdiqlash uchun yagona bearer → istalgan raqamni istalgan hisobga «tasdiqlangan» qilib yozish | C-3 choralari + `awaiting_contact` holatining atomik iste'moli + har telefon o'zgarishi `auth_events` va foydalanuvchiga xabar | §4.2/6, §4.6, §5.4 |
| C-8 | `/start` payload prefiksi botga bog'lanmagan → xodim invaytini mijoz boti orqali iste'mol qilish | prefiks marshrutga qattiq bog'lanadi; umumiy dispatcher yo'q; `wrong_bot_payload` hodisasi | §5.3, §13.2/25 |

### A.2 High

| # | Hujum | Chora | Bo'lim |
|---|---|---|---|
| H-1 | Step-up faqat chegaradan oshganda → chegara ostida cheksiz taxmin; `OTP_REQUIRED` = «parol to'g'ri» orakuli | step-up **qurilmaga** bog'lanadi (sukut yoqiq); noto'g'ri parolda ham bir xil javob shakli va soxta `otp_id`; eksponensial kechikish | §6.3 |
| H-2 | OTP byudjeti loginga bog'langan va autentifikatsiyasiz iste'mol qilinadi → «qulflanmaydi» va'dasi buziladi | `login` va `reset` byudjetlari **ajratiladi**; step-up byudjeti tasdiqlangan parol hodisasiga bog'lanadi; yangi kod eskisini **bekor qilmaydi** | §5.7, §8.2, §10.1 |
| H-3 | Global >200 fail/min tripwire = platformani o'chirish tugmasi | global hisoblagich faqat **signal**; avtomatik javob tor segmentga; tanilgan qurilma ozod; zaxira yo'l ochiq | §10.3 |
| H-4 | Refresh token yakka to'liq kredensial: qurilmasiz, mutlaq chegarasiz, `localStorage` da, rotatsiya haqida xabar yo'q | `__Host-` httpOnly cookie; `device_hash`; `chain_started_at` (24 soat); xodim access 300 s / refresh 12 soat; yangi qurilmadan rotatsiyada Telegram ogohlantirishi | §6.5, §3.7 |
| H-5 | `SECURITY DEFINER` uchligi — tekshiruvsiz imtiyoz primitivlari; «xesh ko'rinmaydi» da'vosi noto'g'ri | `auth_set_password(bigint,text)` **yo'q**; yozuvchi funksiyalar `user_id` qabul qilmaydi; tiket ichida iste'mol; har chaqiruv `auth_events` ga; `search_path = pg_catalog, pg_temp` | §3.6 |
| H-6 | `locked_until` hisob qulfi — sir bo'lmagan login ustidan smena vaqtidagi DoS | qulf **umuman kiritilmaydi**; eksponensial kechikish + qurilmaga bog'langan step-up | §6.3, §10.2 |
| H-7 | Server yaratgan ochiq vaqtinchalik parol → admin xodim nomidan kiradi, audit atributsiyasi buziladi | server parol yaratmaydi va uzatmaydi; reset = **tiket**; `must_change` da o'qish ham yopiq | §7.4, §7.3, §9.3 |
| H-8 | OTP tekshiruvi atomik emas → parallel taxminlar urinish shiftini bo'lishadi | bitta Lua skript; `otp_id` konkurrentlik qulfi; 200 parallel taxmin testi | §5.7, §13.2/14 |
| H-9 | Redis fail-open → OTP kuchaytirgichi va platforma miqyosidagi bot bloki | auth yo'lida **fail-closed (503)**; yuborish shifti so'rovchi bo'yicha; chiquvchi xabarlar yagona navbatda | §10.4, §8.7 |
| H-10 | Tiklash kodi telefon orqali «to'g'ri odamdan» olinadi | ogohlantirish matni; login kod bilan bitta xabarda emas; `otp_id` so'rovchiga bog'langan; OWNER darajasida inline tasdiq tugmasi; egaga bildirishnoma | §8.3, §8.4, §5.7 |
| H-11 | Umumiy klub kompyuterida OTP ikkinchi omil emas (konsol va Telegram bitta mashinada) | OWNER uchun inline tasdiq; qurilma ro'yxati; idle timeout; xavfli amallarda step-up **parol**; hujjatlashtirilgan qoida | §8.5, §6.8 |
| H-12 | «Bot birinchi yozolmaydi» + blok = tiklanmaydigan holat, uni hujumchi ataylab keltirib chiqaradi | `my_chat_member` → `blocked_at` konsolda ochiq; **zaxira tiklash kodlari**; yuborish shifti so'rovchi bo'yicha | §8.7, §5.8 |
| H-13 | Telefon skvottingi (`UNIQUE(phone)` + qo'lda bo'shatish) / teskarisi — cheksiz hisob | egalik **o'tkazish** modeli, 30 kunlik chegara, audit, eski egaga xabar; depozit/qora ro'yxat ko'chirilmaydi | §4.6 |
| H-14 | `phone_verified_at` hech qachon qayta tekshirilmaydi → tasdiq yolg'onga aylanadi | 180 kunlik amal muddati; pul/nizoli amallardan oldin qayta `requestContact`; `phone_reverified_at` | §4.7 |
| H-15 | `SECURITY DEFINER` `FORCE RLS` ni chetlab o'tmaydi → prod'da kirish umuman ishlamaydi, «tez tuzatish» xeshni ochadi | barcha funksiyalar egasi `playbron_platform` (BYPASSRLS); mavjud `app_club_role()` ham tuzatiladi; **non-superuser ega ostida CI testi** | §3.6, §13.4 |
| H-16 | `auth_set_password(bigint, text)` — ichki avtorizatsiyasiz yozuvchi | H-5 bilan bir xil chora | §3.6 |
| H-17 | 0005 super adminlarni `kind='customer'` qoldiradi → FK yiqiladi, «tez tuzatish» platformani abadiy qulflaydi | uch manbadan backfill; `telegram_id` ni `staff_telegram` ga ko'chirish; `NOT VALID` + `VALIDATE`; **`0002_seed` ga tegilmaydi**; yakuniy `RAISE EXCEPTION` assert; runbook | §12.5, §12.6 |
| H-18 | Bitta `users` qatori ikki dunyoni bo'lishishi → mijoz sessiyasi RLS darajasida xodim huquqini oladi | tanlangan model bunga yo'l qo'ymaydi: `kind` diskriminatori + xodimda `telegram_id IS NULL` + `users_self` da `AND kind='customer'` + kompozit FK | §2.1, §3.1, §3.5 |
| H-19 | Ikkala webhook sekreti bitta ildizdan → bitta sizish ikkala dunyoni ochadi | ikki mustaqil env, alohida rotatsiya, start'da tenglik tekshiruvi | §5.4 |
| H-20 | Invayt havolasi bearer sir — birinchi ochgan odam hisobni oladi | token + `expected_phone` ga egalik = ikki omil; TTL 12 soat; muvaffaqiyatsiz urinish iste'mol qilmaydi; «kim ochdi» ko'rinadi; egaga bildirishnoma | §5.2, §9.1 |
| H-21 | «Hech qanday hisob qulflanmaydi» va'dasi step-up orqali buziladi | H-1 va H-2 choralari birgalikda; §10.2 dagi to'rt sabab | §6.3, §8.2, §10.2 |

### A.3 Medium va low — qisqa

| Hujum | Chora | Bo'lim |
|---|---|---|
| Qurilma cookie'si foydalanuvchiga bog'lanmagan; `__Host-` yo'q → 2FA olib tashlanadi, sessiya fiksatsiyasi | imzolangan va `user_id` ga bog'langan cookie; `__Host-` prefiksi; kirishda cookie almashtiriladi; sessiyaga bog'langan CSRF tokeni | §6.5 |
| `client_ip()` `None` qaytaradi / faqat birinchi XFF qatorini o'qiydi | birlashgan o'qish, `ip_address()` validatsiyasi, `None` = eng qat'iy chelak | §10.5 |
| Dunyo belgisi refresh tokenda saqlanmaydi → rotatsiyadan keyin konsol qulflanadi yoki teshik ochiladi | `refresh_tokens.kind`; `rotate_refresh` saqlangan qatordan oladi; `aud` pyjwt bilan | §3.7, §6.6 |
| `login-hint` orakuli | endpoint **yaratilmaydi** | §11.1 |
| Ikkala bot uchun bitta webhook sekreti | ikki mustaqil env | §5.4 |
| OTP pepper = `JWT_SECRET` | alohida `OTP_PEPPER` | §5.7 |
| Replay guard TTL imzo oynasidan qisqa | TTL imzo oxiriga bog'lanadi, bitta konstanta | §4.5 |
| Bot ismini validatsiya ma'nosiz (`first_name` `initData` bilan ustiga yoziladi) | normallashtirish `upsert_user` da; `display_name` alohida | §3.8 |
| Webhook'da istisno → Telegram cheksiz qayta yuborish; dedupe yo'q | har doim 200; `update_id` dedupe; qat'iy sxema | §4.4 |
| Kontakt xususiy chat va kutilayotgan holatga bog'lanmagan | oltala shart | §4.2 |
| `X-Club-Id` va yo'ldagi `club_id` solishtirilmaydi | `require_club_scope`, avtotanlash olib tashlanadi | §6.7 |
| `audit_log` org bo'yicha o'qiladi → STAFF qo'shni klublarni ko'radi | `club_id` ustuni + policy qayta yoziladi; `auth_events` ham | §3.5 |
| Kod chat tarixida va bildirishnoma preview'ida, login bilan bitta xabarda | login ajratiladi; muvaffaqiyatli tekshiruvdan keyin darhol `deleteMessage`; kod log'ga tushmaydi | §5.7 |

---

## Ilova B — Bekor qilinadigan qarorlar

### B.1 DCR'lar

| DCR | Yangi holat |
|---|---|
| **DCR-001** — «Konsolga kirish: login/parol → Telegram» | **BEKOR QILINADI.** Konsolga kirish login + parol. `login.tsx` dagi ikkita `TextField` qaytadi (mavjud panel, brend ustuni, `Backdrop` va barcha `CSSProperties` tegilmaydi). «Demo hisoblar» bloki qaytmaydi |
| **DCR-002** — «Mijoz ro'yxatdan o'tishi: initData + requestContact» | **QAYTA YOZILADI.** Ro'yxatdan o'tish **100% botda**; `register.tsx` forma emas, «Botni oching» darvozasi. «Kirish / Boshqa raqam bilan» tarmog'i o'chadi — Telegram ichida almashtiriladigan identity yo'q |
| **DCR-003** — «Sozlamalardagi Parolni almashtirish bloki o'chsin» | **BEKOR QILINADI.** Panel qaytadi; joriy parol majburiy, muvaffaqiyatda barcha tokenlar bekor |
| **DCR-004** — «Xodim kartasidagi Login maydoni Telegram ustuniga almashsin» | **QAYTA YOZILADI.** «Login» ustuni **qoladi** (haqiqiy identifikator), ustiga «Telegram» ustuni qo'shiladi: `Kutilmoqda` / `@username` / `Bog'lanmagan ⚠` |
| **DCR-005** | o'zgarishsiz (yopilgan) |
| **DCR-006** | o'zgarishsiz; `apps/admin/src/routes.ts` ga `/join`, `/activate`, `/reset` marshrutlari qo'shiladi |
| **DCR-007** — «English olib tashlansin» | **BAJARILADI.** `apps/admin/src/i18n.ts`: `Lang = 'uz' \| 'ru'`; CLAUDE.md dagi «uz/ru/en» → «uz/ru» |

### B.2 Mavjud Telegram auth bilan nima bo'ladi

| Element | Qaror |
|---|---|
| **Login Widget** (`verify_widget`, `_widget_token`, `POST /auth/telegram/widget`, `WidgetIn`, `signInWithWidget`, `VITE_TELEGRAM_LOGIN_BOT`, `widget_ttl_sec`) | **Butunlay o'chadi.** Landing'da o'rniga oddiy havolalar. `test_widget_*` testlari o'chadi |
| **Bot deep-link + nonce + poll** (`botlogin.py`) | **Kirish beruvchi sifatida bekor qilinadi**, lekin fayl o'chirilmaydi: `register_webhook()` va `webhook_secret_token()` `main.py:14,40` da ishlatiladi. Modul `modules/telegram/` ga ko'chadi va **bog'lash** (invayt, faollashtirish, relink) vazifasini oladi — nonce/poll mashinasi allaqachon test bilan qoplangan va aynan «bot birinchi yozolmaydi» cheklovining yechimi |
| **`POST /auth/telegram/start`, `/start/{nonce}`** | Sessiya bermaydi. `POST /auth/staff/link/start` va `.../poll` ga aylanadi: javob `{status, telegram:{...}}` |
| **`POST /auth/dev/login`** | **O'chadi.** Saqlash sababi (Widget localhost'da ishlamaydi) yo'qoldi; prod'da `env` bilan qo'riqlanadigan zaxira eshikni olib tashlash sof yutuq |
| **`POST /auth/telegram/initdata`** | `POST /auth/customer/miniapp` ga qayta nomlanadi; **mantiq saqlanadi**, ustiga: `kind='customer'`, `mbr=[]`, `sa=False`, idempotent replay, TTL formulasi, ism normallashtirish |
| **`login.tsx` dagi nonce/poll UI mantiqi** | O'chirilmaydi — `/join`, `/activate` ekranlariga ko'chadi |
| **`test_bot_login.py`** | `test_staff_link.py` ga qayta yoziladi; `test_webhook_requires_secret` saqlanadi |
| **`TG_WEBHOOK_SECRET`** | Ikkiga bo'linadi: `MAIN_BOT_WEBHOOK_SECRET`, `ADMIN_BOT_WEBHOOK_SECRET` |
| **`docs/01-architecture.md` §2** | To'liq qayta yoziladi. «Parol yo'q, email yo'q» qoidasi **faqat mijozga** tegishli deb aniqlashtiriladi; «ikki kirish nuqtasi» diagrammasi ikki dunyo bilan almashadi |

---

## Ilova C — Biznes qarorlari (2026-08-14)

Quyidagilar loyiha egasi tomonidan aytilgan va §7.4 hamda §9.1 dagi dastlabki
qarorlarni **qisman bekor qiladi**. Ustuvorlik shu bo'limda.

### C.1 Hisob kim tomonidan yaratiladi

| Rol | Hisobni kim yaratadi | Parolni kim qo'yadi |
|---|---|---|
| SUPER_ADMIN | migratsiya + skript (§5.6) | o'zi, stdin orqali |
| Klub egasi / admini | **o'zi** — landing formasidan ro'yxatdan o'tadi | **o'zi** |
| Klub egasi / admini (muqobil yo'l) | **super admin** klub qo'shganda | super admin **bir martalik** parol beradi |
| Xodim | **klub egasi** | **klub egasi** boshlang'ich parol beradi |

Klub egasi — platformaning to'lovchi mijozi. Uning ro'yxatdan o'tishida super
admin qatnashmaydi. Super adminning klub qo'shishi — qo'shimcha yo'l, majburiy
emas.

### C.2 Boshlang'ich parol — birinchi kirishda majburan almashtiriladi

Har qanday **birov tomonidan berilgan** parol bir martalik hisoblanadi:
`staff_credentials.must_change = true`. Birinchi muvaffaqiyatli kirishdan keyin
foydalanuvchi yangi parol qo'ymaguncha boshqa hech qanday endpoint ochilmaydi.

Sabab: §7.4 da yozilgani kuchda qoladi — parolni bilgan odam hisob egasi
nomidan kira oladi va `audit_log` ning isbot kuchi yo'qoladi. Majburiy
almashtirish bu xavfni «berish ↔ birinchi kirish» oralig'i bilan cheklaydi.
Almashtirish hodisasi `auth_events` ga yoziladi.

Bu §7.4 dagi «server hech qachon parol yaratmaydi» qoidasini **buzmaydi**:
parolni server emas, odam qo'yadi. O'zgargani — uni egasi emas, boshqa odam
qo'yishi mumkinligi.

### C.3 Telegram bog'lash endi kirish sharti emas

Xodim login va parolni to'g'ridan-to'g'ri oladi, ya'ni invayt → `/start` → OTP
zanjiri kirish uchun **shart emas**. Lekin Telegram baribir kerak: usiz parolni
tiklash kanali va bildirishnoma yo'q.

Shuning uchun bog'lash birinchi kirishdan **keyingi** qadamga ko'chadi:
parol almashtirilgach, konsol Telegram bog'lashni taklif qiladi. Bog'lanmagan
hisob ishlayveradi, lekin parolni unutsa faqat klub egasi qayta tayinlay oladi.

### C.4 Ochiq qolgan savollarga tanlangan qiymatlar

- Login **global unikal**, `{ism}.{klub}` naqshi bilan (§14/2).
- Umumiy «kassa» hisobi **taqiqlanadi** (§14/4).
- Telefon egaligi **avtomatik** o'tadi, 30 kunda bir marta (§14/6).
