# PlayBron — Super admin qatlami: platforma paneli, Glass rejimi va Landing CMS

> **Holat:** yakuniy dizayn, amalga oshirishga tayyor.
> **Faza:** 7 (`docs/02-roadmap.md`). **Bog'liq:** Faza 5 (obuna va to'lov), `docs/05-auth-redesign.md`.
> **Migratsiyalar:** `0006_platform_glass`, `0007_landing_cms` (`0005_two_worlds_auth` dan keyin).
> Hujjat kod yozmaydi — SQL va TypeScript parchalar faqat **shartnoma** sifatida keltirilgan.

---

## 0. Qisqacha: uchta asosiy qaror

**1. Glass rejimi BYPASSRLS'ga UMUMAN tegmaydi.** Glass `playbron_app` roli ostida,
RLS to'liq kuchda ishlaydi. Super admin nishon tashkilotga "kirganda" tenant
izolyatsiyasi o'chmaydi — faqat **yo'nalishi** o'zgaradi. Bu eng muhim xususiyat:
super admin xato qilsa yoki modulda `WHERE` unutilsa ham, u bitta tashkilot
doirasida qoladi.

**2. Cross-tenant huquq SHAXSDAN emas, KOD YO'LIDAN keladi.** Policy'lar
"kim super admin" degan savolga emas, "so'rov qaysi qamrovdan ochildi" degan
savolga javob beradi: `app.platform` GUC'i **faqat** `core/db.py:platform_scope()`
ichida qo'yiladi, `_apply_context()` uni hech qachon qo'ymaydi. Shu bitta qoida
tufayli glass ichidan ham, super adminning oddiy klub sessiyasidan ham platforma
policy'larini yoqib bo'lmaydi. `super_admins` jadvaliga tayanadigan policy
umuman yozilmaydi.

**3. Landing CMS — (b) variant:** kontent bazada, "Nashr qilish" Render deploy
hook'ini chaqiradi, sayt qayta yig'iladi. Statiklik va nol bayt JS saqlanadi.
Asoslar va rad etilgan variantlar — §7.1.

**Birinchi versiyada glass FAQAT O'QISH.** Yozish rejimi sxemada (`mode` ustuni,
policy'lar, ikkinchi omil) tayyor turadi, lekin `platform_settings.glass.write_enabled`
sukut bo'yicha `false` va deploysiz yoqiladi. Sabab: `docs/01-architecture.md` §9
allaqachon "klub ma'lumotiga super admin yozmaydi" deb yozgan; yozish rejimi
xavf yuzasining eng katta qismini beradi, foydasi esa hali isbotlanmagan.

---

## 0.1 BOSQICH 0 — glass'dan OLDIN yopilishi shart bo'lgan poydevor

Quyidagi to'rt nuqta hozirgi kodda mavjud va **glass shulardan biri ochiq
turgan holda yoqilmaydi**. Ular Faza 7 emas, `0005_two_worlds_auth` va infra ishi.

| # | Muammo | Nima uchun bloklovchi |
|---|---|---|
| P0-1 | `render.yaml` da `DATABASE_URL`, `DIRECT_URL`, `PLATFORM_DATABASE_URL` — uchalasi bitta `playbron-db.connectionString` (baza egasi). `0001_core._create_roles()` `CREATEROLE` yo'qligini va `BYPASSRLS` berilmasligini **jimgina** yutadi | Ilova baza egasi roli bilan ishlaydi. `FORCE ROW LEVEL SECURITY` DML ni egaga ham qo'llaydi, lekin `TRUNCATE`, `DROP POLICY`, `ALTER TABLE … DISABLE ROW LEVEL SECURITY` va `GRANT` ni ushlamaydi. Ega o'zidan REVOKE qilingan huquqni istalgan payt tiklaydi — ya'ni `audit_log` ning append-only kafolati bugun **haqiqiy emas** |
| P0-2 | `deps.py:79-80` — `require_role()` ichidagi `if ctx.is_super_admin: return` | Auditsiz, muddatsiz, sababsiz impersonation yo'li. Glass yoqilsa bu nazorat mexanizmining yonidan aylanib o'tadigan parallel kanal bo'lib qoladi. **O'chiriladi** |
| P0-3 | `platform_ip_allowlist` prod'da bo'sh (`render.yaml` da env umuman yo'q) va `SUPER_ADMIN_TELEGRAM_IDS` ochiq repoda | `/platform/*` uchun yagona tarmoq to'sig'i yo'q, nishon esa nomlangan |
| P0-4 | `app_club_role()` (`0003:37-56`) `SECURITY DEFINER`, lekin `OWNER` ko'rsatilmagan | `SECURITY DEFINER` RLS'ni **o'chirmaydi**, faqat `current_user` ni almashtiradi; `FORCE RLS` egaga ham tegishli. `docs/05-auth-redesign.md` §3.6 buni "majburiy va oson unutiladigan" deb yozgan va 0005 da `ALTER FUNCTION … OWNER TO playbron_platform` ni talab qiladi |

**Qabul mezoni:** `/readyz` javobida `db_role`, `rolbypassrls`, `rolsuper` va
`audit_log_owner` ko'rinadi; prod'da ilova ega roli bilan ulangan bo'lsa
`core/config.py` dagi prod-tekshiruvlar ishga tushishga yo'l bermaydi.

---

## 1. Rol va vakolat chegarasi

### 1.1 Super admin kim

Platformaning egasi va yagona operatori (hozircha bitta odam). U **mahsulotni**
boshqaradi: tashkilotlar, obunalar, tariflar, landing matni, platforma sog'ligi.
U **mijozning biznesini** boshqarmaydi.

### 1.2 Uch qamrov, uch token

Bitta odam, lekin uchta ajratilgan qamrov. Har biri alohida token va alohida
DB yo'li bilan ishlaydi.

| Qamrov | `scp` klaymi | `sa` | DB yo'li | Nima uchun ajratilgan |
|---|---|---|---|---|
| Klub konsoli (o'z klubi bo'lsa) | `app` | `false` | `session_scope()` | Oddiy foydalanuvchi |
| Platforma paneli | `platform` | `true` | `platform_scope()` | Cross-tenant o'qish, obuna va CMS yozuvi |
| Glass | `glass` | **`false`** | `session_scope()` | Bitta tenant ichida, RLS ostida |

`docs/05-auth-redesign.md` §6.6 `aud` klaymini `'customer' | 'staff'` uchun band
qilgan va uni `jwt.decode(audience=…)` bilan tekshiradi. Shuning uchun bu yerda
`aud` **qayta ishlatilmaydi**: uchala konsol tokeni ham `aud='staff'`, qamrov esa
alohida `scp` klaymida. Bu ikki dizaynni to'qnashtirmaydi va `decode_access` ga
qo'shimcha `audience=` parametri kiritishni talab qilmaydi (u 0005 da baribir
kiritiladi).

### 1.3 Fail-safe konstruksiya

Glass tokeni ataylab **oddiy a'zolik tokeniga o'xshaydi**: `sa=false`,
`mbr=[{club_id, role, org_id}]` bitta yozuv bilan. Agar biror marshrut `scp` ni
tekshirishni unutsa, u glass'ni super admin emas, oddiy STAFF/ADMIN deb ko'radi —
xato **yopiq tomonga** qulaydi.

`RequestContext` ga qat'iy invariant kiritiladi:

> `ctx.glass is not None` → `ctx.is_super_admin` **majburan `False`**.

Bu bitta invariant butun xatolar oilasini yopadi: `platform_scope()`
(`db.py:126`) `is_super_admin` ni tekshiradi, demak glass ichida u printsipial
ochilmaydi.

### 1.4 Vakolat chegarasi — qisqa jadval

| Amal | Platforma paneli | Glass | Sabab |
|---|---|---|---|
| Tashkilotlar ro'yxati, statistika | ✅ (o'qish) | ❌ | Cross-tenant — faqat `platform_scope()` |
| Obuna, tarif, to'xtatish, refund | ✅ (TOTP + sabab) | ❌ | Biznes amali, glass'niki emas |
| Landing CMS, platforma sozlamalari | ✅ (TOTP) | ❌ | Glass tokeni `/platform/*` ga yetmaydi |
| Klub ekranlarini mijoz ko'zi bilan ko'rish | ❌ | ✅ | Glass'ning yagona maqsadi |
| Klub ma'lumotini o'zgartirish | ❌ | ⚠️ (v2, kill switch ortida) | §6.4 |
| Merchant/to'lov kalitlari | ❌ | ❌ | §6.5 — ikki qulf |
| A'zolik yaratish/o'zgartirish | ❌ | ❌ | §6.5 — eng muhim taqiq |

---

## 2. Ma'lumotlar modeli

Ikki oldinga migratsiya. Har bir yangi jadval **o'sha migratsiyada**
`ENABLE`+`FORCE ROW LEVEL SECURITY` oladi (aks holda
`tests/test_rls_hardening.py::test_every_table_has_rls` yiqiladi), va `0003`
`ALTER DEFAULT PRIVILEGES` ni bekor qilgani uchun **har bir GRANT aniq yoziladi**.

### 2.1 Yangi GUC funksiyalari (`0001` dagi `app_user_id()` uslubida)

```
app_platform()      -> boolean   -- current_setting('app.platform', true) = 'true'
app_glass_id()      -> bigint    -- 0 = glass emas
app_glass_club_id() -> bigint
app_glass_mode()    -> text      -- '' | 'read' | 'write'
app_actor_user_id() -> bigint    -- platforma yo'lidagi trigger uchun
```

**`app.platform` qo'yiladigan yagona joy — `platform_scope()`.**
`_apply_context()` uni hech qachon qo'ymaydi. Shu bilan birga `_apply_context()`
dan `app.is_super_admin` GUC'i **olib tashlanadi**: u hozir hech qaysi policy'da
ishlatilmaydi, lekin kelajakda kimdir unga policy bog'lasa oddiy app pooli super
admin uchun cheklovsiz bo'lib qolardi.

### 2.2 `app_club_role()` — yagona choke point

`0003:37-56` dagi funksiya qayta yoziladi (`CREATE OR REPLACE`, `SECURITY DEFINER`
saqlanadi, **`ALTER FUNCTION … OWNER TO playbron_platform`** majburiy — P0-4):

```sql
SELECT COALESCE(
  (SELECT m.role FROM memberships m
     WHERE m.club_id = target_club_id AND m.user_id = app_user_id()
       AND m.status = 'active' LIMIT 1),
  (SELECT CASE WHEN g.mode = 'write' THEN 'ADMIN' ELSE 'STAFF' END
     FROM glass_sessions g
    WHERE g.id            = app_glass_id()
      AND g.actor_user_id = app_user_id()     -- GUC'ga ishonilmaydi
      AND g.club_id       = target_club_id
      AND g.status        = 'active'
      AND g.ended_at IS NULL
      AND g.expires_at    > now()
    LIMIT 1)
);
```

Uch qaror shu yerda:

1. **`'OWNER'` hech qachon qaytmaydi.** `club_payment_credentials_owner` policy'si
   (`0003:155-171`) aynan `'OWNER'` ga bog'langan — demak merchant kalitlari
   glass'dan **o'z-o'zidan** yopiq.
2. **Tiriklik DB ichida qayta tekshiriladi.** GUC faqat ko'rsatkich; funksiya
   `actor_user_id`, `club_id`, `status`, `ended_at`, `expires_at` ni o'zi
   tasdiqlaydi. Sabab: `app.refresh_hash` GUC'iga ishonish mumkin edi, chunki u
   48 baytli **sir**; glass sessiya id si sir emas.
3. **O'qish rejimida ham rol beriladi** (`'STAFF'`). Aks holda `memberships_read`
   (`0003:128-133`) glass'da 0 qator qaytarardi va "klub ko'zi bilan ko'rish"
   degan asosiy maqsad ishlamasdi.

### 2.3 `glass_sessions`

Glass sessiyasining **yagona haqiqat manbai** — token emas, shu qator.

| Ustun | Tip | Izoh |
|---|---|---|
| `id` | `bigint PK` | |
| `actor_user_id` | `bigint FK users NOT NULL` | **HAR DOIM** super admin |
| `org_id` | `bigint FK organizations NOT NULL` | |
| `club_id` | `bigint FK clubs NOT NULL` | Aynan bitta klub — §6.5 |
| `role` | `text CHECK IN ('STAFF','ADMIN')` | `OWNER` yo'q |
| `mode` | `text CHECK IN ('read','write')` | |
| `status` | `text CHECK IN ('pending_2fa','active','ended','revoked','denied')` | |
| `reason_code` | `text NOT NULL` | `support_request` \| `incident` \| `bug` \| `data_fix` \| `billing` \| `owner_request` |
| `reason_text` | `text NOT NULL CHECK (length(reason_text) >= 20)` | DB CHECK — ilova validatsiyasi chetlab o'tilmasin |
| `ticket_ref` | `text NULL` | |
| `requested_at`, `started_at`, `expires_at`, `ended_at` | `timestamptz` | |
| `end_reason` | `text NULL` | `manual` \| `expired` \| `revoked` \| `kill_switch` \| `budget` \| `binding` |
| `renew_count` | `int DEFAULT 0` | |
| `request_count`, `write_count`, `rows_read` | hisoblagichlar | |
| `flagged_at` | `timestamptz NULL` | Ega e'tiroz bildirgan |
| `ip` | `inet` | Tenantga **ko'rsatilmaydi** — §6.6 |
| `ua_hash` | `char(64)` | Xom UA saqlanmaydi |

Indekslar: `(org_id, requested_at DESC)`, `(actor_user_id, requested_at DESC)`,
`(status) WHERE status = 'active'`, va

```sql
CREATE UNIQUE INDEX glass_sessions_one_active
  ON glass_sessions (actor_user_id) WHERE status = 'active';
```

Bitta super admin bir vaqtda faqat bitta tashkilotda — parallel sessiyalarda
chalkashish imkoni DB darajasida yopiladi.

**RLS:**

```sql
ALTER TABLE glass_sessions ENABLE  ROW LEVEL SECURITY;
ALTER TABLE glass_sessions FORCE   ROW LEVEL SECURITY;

-- Tashkilot o'z ustidagi kirishlarni o'zi ko'radi. Shaffoflik — mahsulot xususiyati.
CREATE POLICY glass_sessions_tenant_read ON glass_sessions
  FOR SELECT USING (org_id = app_org_id() AND app_glass_id() = 0);

CREATE POLICY glass_sessions_platform ON glass_sessions
  FOR ALL USING (app_platform()) WITH CHECK (app_platform());
```

**Grantlar:**

```sql
REVOKE ALL ON glass_sessions FROM playbron_app;
GRANT SELECT ON glass_sessions TO playbron_app;        -- faqat o'qish
GRANT SELECT, INSERT, UPDATE ON glass_sessions TO playbron_platform;
-- DELETE hech kimga: glass tarixi o'chirilmaydi (audit_log bilan bir xil kelishuv)
```

App roli **yoza olmaydi**. Bu ataylab: aks holda glass ichidagi so'rov o'z
`expires_at` ini uzaytirib, `app_club_role()` ning tiriklik tekshiruvini va
`end`/`kill` amallarini bekor qilardi. Qo'shimcha qatlam — `BEFORE UPDATE`
trigger: `org_id`, `club_id`, `role`, `mode`, `reason_code`, `reason_text`,
`started_at`, `requested_at` **o'zgarmas**; `ended_at IS NOT NULL` bo'lgan qator
qayta ochilmaydi; `expires_at` faqat `/renew` yo'lida va faqat o'sishi mumkin.

`glass_sessions_tenant_read` dagi `app_glass_id() = 0` sharti: glass ichidan
boshqa glass sessiyalarining ro'yxatini ko'rish yo'li yopiladi.

### 2.4 `audit_log` kengaytmasi

Yangi jadval emas — mavjud jadvalga ustun qo'shiladi:

| Ustun | Tip | Izoh |
|---|---|---|
| `actor_kind` | `text NOT NULL DEFAULT 'user' CHECK IN ('user','platform','glass','system')` | Trigger to'ldiradi |
| `glass_session_id` | `bigint NULL FK glass_sessions(id)` | |
| `club_id` | `bigint NULL` | Filtrlash va toraytirilgan o'qish uchun |
| `prev_hmac` | `char(64) NULL` | |
| `row_hmac` | `char(64) NOT NULL` | |
| `chain_seq` | `bigint NOT NULL` | Uzluksiz, bo'shliq — signal |
| `key_id` | `smallint NOT NULL` | Kalit rotatsiyasi uchun |

Indekslar: `(glass_session_id)`, `(actor_user_id, at DESC)`, `(action, at DESC)`,
`UNIQUE (chain_seq)`.

**Yozish policy'si toraytiriladi.** Hozirgi `audit_log_insert`
(`0003:148-149`) faqat aktorni bog'laydi — qolgan har bir ustun erkin:

```sql
DROP POLICY audit_log_insert ON audit_log;

CREATE POLICY audit_log_insert ON audit_log
  FOR INSERT WITH CHECK (
    actor_user_id = app_user_id()
    AND (org_id IS NULL OR org_id = app_org_id())
    AND action NOT LIKE 'glass.%'
    AND action NOT LIKE 'platform.%'
    AND action NOT LIKE 'system.%'
  );

CREATE POLICY audit_log_platform_insert ON audit_log
  FOR INSERT WITH CHECK (app_platform());
```

**O'qish policy'si klub darajasiga toraytiriladi** — hozir org bo'ylab ochiq,
ya'ni bitta klubdagi STAFF butun tashkilotning `before`/`after` diff'larini
o'qiy oladi:

```sql
DROP POLICY audit_log_read ON audit_log;

CREATE POLICY audit_log_read ON audit_log
  FOR SELECT USING (
    (actor_user_id = app_user_id() AND app_glass_id() = 0)
    OR (org_id = app_org_id()
        AND (club_id IS NULL OR club_id = app_club_id()
             OR app_club_role(app_club_id()) IN ('OWNER','ADMIN')))
  );
```

`actor_user_id = app_user_id()` shoxiga qo'shilgan `app_glass_id() = 0`
hal qiluvchi: usiz glass ichidagi `SELECT * FROM audit_log` nishon tashkilotning
yozuvlariga **qo'shimcha ravishda** super adminning boshqa tashkilotlardagi
butun tarixini (`before`/`after` tanalari bilan) qaytarardi. Xuddi shu sabab
bilan `organizations_read` ham qayta yoziladi:

```sql
CREATE POLICY organizations_read ON organizations
  FOR SELECT USING (
    (owner_user_id = app_user_id() AND app_glass_id() = 0)
    OR id = app_org_id()
    OR app_platform()
  );
```

**Grant tuzatishi:**

```sql
REVOKE UPDATE ON audit_log FROM playbron_platform;   -- 0001:354 bergan
REVOKE SELECT (ip, user_agent) ON audit_log FROM playbron_app;
```

`0001:354` dagi `GRANT INSERT, UPDATE ON organizations, audit_log TO
playbron_platform` — `audit_log` ga UPDATE huquqi append-only kafolatini buzadi
va BYPASSRLS pool policy'lar bilan cheklanmagani uchun o'z izini tahrirlay
olardi.

**Trigger'lar** (`SECURITY DEFINER`, egasi `playbron_platform`):

- `audit_log_seal` — `BEFORE INSERT`. `actor_kind`, `glass_session_id`, `at` ni
  **GUC'lardan o'zi hisoblaydi** (ilova bergan qiymatga ishonmaydi), `chain_seq`
  ni oladi, `prev_hmac` ni oxirgi qatordan o'qiydi va
  `row_hmac = HMAC(key, prev_hmac || chain_seq || actor_user_id || actor_kind ||
  org_id || club_id || action || target || before || after || at)` yozadi.
  **Muhim:** trigger BYPASSRLS ostida ham ishlaydi, policy esa yo'q — shuning
  uchun yaxlitlik policy'ga emas trigger'ga qurilgan.
- `audit_log_no_truncate` — `BEFORE TRUNCATE`. TRUNCATE'ga RLS **umuman**
  qo'llanmaydi.

### 2.5 `audit_seal_key`

`key_id smallint PK`, `secret bytea`, `created_at`, `retired_at NULL`.
ENABLE+FORCE RLS, policy yo'q, hech qaysi ilova roliga GRANT berilmaydi —
kalitga faqat muhr trigger'i (SECURITY DEFINER) yetadi. Eski kalit **hech qachon
o'chirilmaydi**, `key_id` qatorda saqlanadi.

> **Ogohlantirish:** bu himoya ilova baza egasi roli bilan ulanmagan bo'lsa
> ishlaydi (P0-1). Ega uchun jadval grantlari to'siq emas.

### 2.6 `audit_anchors` va tashqi lang'ar

`id`, `chain_seq_from`, `chain_seq_to`, `count`, `rolling_hash`, `at`,
`external_ref text`. HMAC modifikatsiyani ushlaydi, **o'chirishni emas** —
buning uchun zanjir boshi tashqariga chiqariladi.

Chastota: **har 5 daqiqada + har bir glass sessiyasi yopilganda va
boshlanganda majburiy**. Sabab: kunlik lang'ar 24 soatlik "o'chirish oynasi"
qoldiradi — ertalab qilingan amal kechqurun digest hisoblanishidan oldin
o'chirilsa, digest allaqachon tozalangan holatdan olinadi va nomuvofiqlik hech
qachon paydo bo'lmaydi.

Lang'arni ilovaning o'zi emas, bazaga faqat `SELECT` huquqi bilan ulanadigan
mustaqil ishchi chiqaradi. Tekshiruv `GET /platform/audit/integrity` javobiga
emas, tashqi arxivga solishtiriladi.

### 2.7 `platform_settings`

`key text PK`, `value jsonb`, `updated_by`, `updated_at`.
ENABLE+FORCE RLS; `USING (key LIKE 'public.%' OR app_platform())`,
yozish `WITH CHECK (app_platform())`.

Kalitlar: `glass.enabled`, `glass.write_enabled` (kill switch),
`glass.read_max_min`, `glass.write_max_min`, `glass.daily_cap`,
`glass.row_budget`, `public.contacts`, `cms.published_version_id`,
`ops.subscription_warn_days`.

**Deploy hook URL, tokenlar va sirlar bu yerda EMAS — `render.yaml` env'ida**
(`sync: false`). Bazadagi hook URL "CMS jadvaliga yozish huquqi" ni "ixtiyoriy
deploy chaqirish huquqi" ga aylantirardi.

### 2.8 `platform_daily_stats`, `platform_alert_state`

- `platform_daily_stats(day date, metric text, dims jsonb, value bigint,
  PK (day, metric, dims))` — kechalik rollup. Sabab: cross-tenant `COUNT`/`SUM`
  har panel ochilishida tenantlarning ish tezligini yeydi; statistika mijozning
  bron ekranini sekinlashtirmasligi kerak.
- `platform_alert_state(alert_key text, org_id bigint, acked_by, acked_at,
  PK (alert_key, org_id))` — "ko'rdim" holati. Hodisa qayta yuz bersa yana
  chiqadi.

Ikkalasi ham ENABLE+FORCE RLS, faqat `app_platform()` o'qiydi, app roliga
grant yo'q.

### 2.9 `plans` qulflanadi

Hozirgi holat: `plans` da RLS **yo'q** (`test_rls_hardening.py:280` da
`exempt = {"alembic_version", "plans"}`), `playbron_app` esa `0001:349` dagi
`GRANT … ON ALL TABLES` orqali unga to'liq INSERT/UPDATE/DELETE huquqiga ega —
`0003` faqat `organizations`/`clubs`/`audit_log` uchun qaytarib olgan. CMS
aynan `plans.price_month` ni tahrirlaydi, ya'ni latent teshik jonli nishonga
aylanadi: tenant kontekstidagi buzilgan sessiya `limits` jsonb'ini qayta yozib
entitlement tekshiruvini butunlay chetlab o'tardi.

```sql
REVOKE INSERT, UPDATE, DELETE ON plans FROM playbron_app;
ALTER TABLE plans ENABLE ROW LEVEL SECURITY;
ALTER TABLE plans FORCE  ROW LEVEL SECURITY;
CREATE POLICY plans_public_read ON plans FOR SELECT USING (true);
CREATE POLICY plans_platform_write ON plans FOR ALL
  USING (app_platform()) WITH CHECK (app_platform());
GRANT UPDATE ON plans TO playbron_platform;
```

`test_rls_hardening.py` dagi `exempt` to'plamidan `plans` chiqariladi.

### 2.10 Mavjud policy'larga glass taqiqlari

```sql
-- Merchant kalitlari: ikkinchi qulf (birinchisi — 'OWNER' qaytmasligi)
ALTER POLICY club_payment_credentials_owner ... USING (... AND app_glass_id() = 0)
                                          WITH CHECK (... AND app_glass_id() = 0);

-- A'zolik: glass HECH QACHON a'zolik yarata/o'zgartira olmaydi
DROP POLICY memberships_write ON memberships;
CREATE POLICY memberships_write ON memberships
  FOR ALL
  USING (club_id = app_club_id()
         AND app_club_role(app_club_id()) IN ('OWNER','ADMIN')
         AND app_glass_id() = 0)
  WITH CHECK (club_id = app_club_id()
              AND app_club_role(app_club_id()) IN ('OWNER','ADMIN')
              AND app_glass_id() = 0
              AND role <> 'OWNER'                 -- OWNER faqat tashkilot egaligi orqali
              AND user_id <> app_user_id());      -- aktor o'ziga a'zolik yozmaydi

-- Tashkilot egaligi platforma ishi
REVOKE UPDATE (owner_user_id) ON organizations FROM playbron_app;

CREATE POLICY organizations_platform ON organizations
  FOR ALL USING (app_platform()) WITH CHECK (app_platform());
```

`memberships_write` dagi qo'shimcha — dizayndagi **eng muhim bitta qator**.
Hozirgi policy `USING`/`WITH CHECK` da faqat **aktorning** rolini tekshiradi;
yozilayotgan qatordagi `role` va `user_id` ustunlariga hech qanday cheklov yo'q.
Ya'ni glass ADMIN sifatida `INSERT INTO memberships (user_id=<o'zi>, club_id=…,
role='OWNER')` bajarardi, sessiya tugagach a'zolik qolardi, keyingi oddiy
kirishda `load_memberships` uni olardi va `app_club_role()` haqiqiy `'OWNER'`
qaytarardi → merchant kalitlari ochilardi. Muddat, sabab, audit va egaga
xabar — hammasi bir INSERT bilan chetlab o'tilardi.

### 2.11 `platform_read` policy'lari

Cross-tenant o'qish uchun har bir tenant jadvaliga qo'shiladi:

```sql
CREATE POLICY <t>_platform_read ON <t> FOR SELECT USING (app_platform());
```

Jadvallar: `organizations`, `clubs`, `memberships`, `glass_sessions`,
`platform_daily_stats`, keyinchalik `subscriptions`, `platform_payments`,
`bookings`, `bills`.

**`club_payment_credentials` ga yozilmaydi** va qo'shimcha ravishda
`REVOKE SELECT ON club_payment_credentials FROM playbron_platform` (`0003:200`
uni bergan — `0003` ning butun maqsadi merchant kalitlarini yashirish edi, ammo
BYPASSRLS pool ularni o'qiy olardi).

`users` uchun ustun darajasida:
`REVOKE SELECT (phone, first_name, last_name, telegram_id, login) ON users FROM
playbron_platform` va platforma qidiruvi maskalangan VIEW orqali (§5.4).

---

## 3. Boshqaruv paneli

`/platform` — kirish ekrani. Maqsad: super admin ertalab 30 soniyada "bugun
nima muhim" ni bilishi.

### 3.1 Kunlik holat (yuqori qator)

`StatTile` qatori: bugungi platforma tushumi va oy boshidan jami · faol
tashkilotlar (va o'zgarish) · faol klublar · bugungi bronlar (agregat) ·
tizim sog'ligi (5xx darajasi, `notifications_outbox` navbati, oxirgi rollup).

Har bir kartada **"oxirgi yangilanish"** vaqti. `platform_daily_stats` 26
soatdan eski bo'lsa `StatusLine tone="warn"` — sabab: rollup job jimgina
o'lsa, nazorat mexanizmi ishlamay qolganini aynan o'sha nazorat mexanizmi
yashirardi.

### 3.2 Diqqat talab qiladigan hodisalar

Panelning yuragi. Ro'yxat, grafik emas. Har qator: nima, kimda, qachon va
**bitta aniq amal tugmasi**.

| Ustuvorlik | Hodisa | Manba | Amal |
|---|---|---|---|
| 0 | **Faol glass sessiyasi** | `glass_sessions WHERE status='active'` | Ko'rish / darhol tugatish |
| 0 | Bayroq qo'yilgan glass (ega e'tiroz bildirgan) | `flagged_at IS NOT NULL` | Tekshirish |
| 0 | Audit zanjiri nomuvofiqligi | `audit_anchors` vs tashqi arxiv | Tekshiruv hisoboti |
| 0 | `/platform/*` ga rad etilgan urinishlar (IP, TOTP) | `audit_log` | Allowlist'ni ko'rish |
| 1 | To'lov o'tmadi (24 soat) | `platform_payments.state='failed'` | To'lov tarixiga o'tish |
| 1 | Obuna tugadi, `grace` ichida | `subscriptions.grace_until` | Bog'lanish |
| 2 | Obuna 3 kunda tugaydi | `ops.subscription_warn_days` | Eslatma yuborish |
| 2 | Limitdan oshgan tashkilot | `plans.limits` vs `platform_daily_stats` | Tarif taklifi |
| 3 | 24 soatdan beri `pending` tashkilot | `organizations.status` | Ko'rib chiqish |
| 3 | Bildirishnomalar to'planib qoldi | `notifications_outbox` | Navbatni ko'rish |
| 3 | Nashr mos kelmadi (§7.6) | `cms.published_version_id` vs saytdagi meta | CMS ga o'tish |

Glass hodisalari **har doim tepada va boshqa tonda** — super admin o'zining
yoki boshqa qurilmada ochiq qolgan sessiyasini birinchi ekrandayoq ko'radi.
Har bir hodisa `platform_alert_state` orqali "ko'rdim" qilinadi, aks holda
ro'yxat kundan kunga o'sib ketadi.

### 3.3 Oxirgi amallar

`audit_log` dan so'nggi 20 ta platforma amali. Bu jurnal emas, nazorat: agar
super admin hisobi o'g'irlangan bo'lsa, haqiqiy egasi panelga kirgan zahoti
begona amallarni ko'radi.

**Yangilanish:** poll 30 s, WebSocket emas — panel kam ochiladi, doimiy
ulanish ortiqcha yuk va ortiqcha hujum yuzasi.
**Bo'sh holat:** "Hammasi joyida" — soxta grafiklar bilan to'ldirilmaydi.

---

## 4. Tashkilotlar

### 4.1 Ro'yxat — `/platform/orgs`

Ustunlar: nomi · ega (barqaror handle) · holat (`pending`/`active`/`suspended`) ·
tarif · klublar soni · obuna tugash sanasi · oxirgi to'lov · MRR hissasi ·
limitdan oshish bayrog'i.

Filtrlar: holat, tarif, "7 kunda tugaydi", `past_due`, `grace`, "limitdan
oshgan". Sahifalash — **kursor** (offset emas: cross-tenant jadval o'sib boradi).
O'qish `platform_scope()` orqali, `SET TRANSACTION READ ONLY` va
`SET LOCAL statement_timeout = '3s'` bilan.

**Qidiruv — PII bo'yicha xom qiymat bilan emas.** `GET /platform/search?q=`
telefon yoki username uchun **HMAC xeshi** bo'yicha qidiradi (kalit ilovada) va
javobda faqat `org_id`/`club_id`/nom qaytadi — raqam va shaxsiy ism qaytmaydi.
Audit'ga so'rov matni emas, xeshi yoziladi. Sabab: xom qidiruv "bu raqam
PlayBron mijozimi va qayerda" degan oracle bo'lardi — raqamlar fazosi kichik,
`+99890` prefiksi bilan enumeratsiya amaliy, va butun jarayon glass'dan
tashqarida, sababsiz, egaga xabarsiz kechardi. Qidiruv chastotasi va natija
soni cheklanadi.

### 4.2 Tafsilot — `/platform/orgs/{id}`

`Tabs` bilan olti bo'lim:

1. **Umumiy** — nomi, ega, ro'yxatdan o'tgan sana, holat, ichki izoh (tenant
   ko'rmaydi).
2. **Obuna** — joriy tarif, davr boshi/oxiri, `grace_until`, keyingi to'lov.
   Amallar: qo'lda tarif berish, muddatni uzaytirish (kompensatsiya), bekor
   qilish. Har biri **TOTP + sabab**.
3. **Klublar** — holat, xona soni, xodim soni, oxirgi faollik. Har birida
   "Glass" tugmasi.
4. **To'lov tarixi** — `platform_payments`: sana, provayder (Click/Payme),
   summa (`bigint` so'm, JSON'da satr), holat, `provider_txn_id`.
   **Xom `raw` jsonb ko'rsatilmaydi** — unda provayder yuborgan ortiqcha
   ma'lumot bo'lishi mumkin.
5. **Limitlar** — `plans.limits` va joriy iste'mol yonma-yon (`ProgressMeter`),
   oshganlari `danger` tonida. Manba — `platform_daily_stats` dagi kunlik surat.
6. **Xavfsizlik** — glass sessiyalari tarixi va shu tashkilot bo'yicha audit.

### 4.3 Amallar

| Amal | Tekshiruv | Ta'siri |
|---|---|---|
| `Suspend` | TOTP + sabab | `organizations.status='suspended'`. Klublar bron qabul qilmaydi, xodimlar kira olmaydi, ma'lumot saqlanadi, mavjud bronlar bekor qilinmaydi. Egaga xabar |
| `Resume` | TOTP + sabab | Teskarisi |
| Qo'lda tarif | TOTP + sabab | `plan_code` + davr. **Joriy obunalar narxi o'zgarmaydi** — narx `subscriptions` ga snapshot qilinadi |
| `Grace` uzaytirish | TOTP | Kunlar soni, shift bilan |
| Egani almashtirish | TOTP + ikkinchi SA (bo'lsa) | Eng xavfli amal |

Yozish faqat `platform_scope()` orqali: `organizations.status`/`plan_code`
`0003:186` da app roldan REVOKE qilingan, `owner_user_id` esa bu dizaynda
qo'shimcha REVOKE oladi (§2.10). ORM'ning to'liq obyektini saqlash yo'q —
aniq `UPDATE … SET` yoziladi.

**Tashkilotni o'chirish UI'da umuman yo'q.** To'xtatish — o'chirish emas.

---

## 5. Statistika — cross-tenant o'qish qanday

### 5.1 Ikki tushum aralashmaydi

`docs/01-architecture.md` §9 dagi qat'iy talab. Panelda ular alohida
bo'limlarda, alohida rang tokenida, alohida endpointda va hech qachon bitta
yig'indida ko'rsatilmaydi.

**(a) Platforma tushumi** — bizning pulimiz. `platform_payments` +
`subscriptions`: MRR/ARR, yangi obunalar, uzaytirishlar, churn, o'rtacha chek,
provayder kesimi, muvaffaqiyatsiz to'lovlar ulushi, qaytarishlar.

**(b) Klublar aylanmasi** — mijozlarimizning puli. `booking_payments` + `bills`:
jami bron tushumi, o'rtacha bandlik, seanslar soni. Panel sarlavhasida aniq:
"Klublar aylanmasi — platforma tushumi emas".

### 5.2 Cross-tenant o'qish mexanizmi

`platform_scope()` `PlatformSession` ochadi va **endi kontekstni ham qo'yadi**:

```
SET LOCAL app.platform        = 'true'
SET LOCAL app.actor_user_id   = <SA id>
SET LOCAL app.actor_kind      = 'platform'
SET TRANSACTION READ ONLY               -- o'qish marshrutlarida
SET LOCAL statement_timeout   = '3s'
```

Ikki foyda:

1. **BYPASSRLS bor-yo'qligidan qat'i nazar ishlaydi.** Rol haqiqatan BYPASSRLS
   bo'lsa GUC'lar zararsiz; bo'lmasa (bugungi Render holati — P0-1) `platform_read`
   policy'lari o'qishga ruxsat beradi. Bugun `platform_scope()` cross-tenant
   **xato bermaydi, bo'sh natija qaytaradi** — ya'ni statistika prod'da "hammasi
   nol" bo'lib ko'rinadi va buni hech qanday test ushlamaydi.
2. **Audit yozuvi ishlaydi.** Kontekstsiz `audit_log_insert` policy'si
   (`actor_user_id = app_user_id()`) `app_user_id()=0` da FALSE beradi: platforma
   amali bajariladi, audit yozuvi esa 42501 bilan yiqiladi va odatiy
   `try/except` ichida jimgina yo'qoladi. Trigger `actor_user_id` ni
   `COALESCE(app_user_id(), app_actor_user_id())` dan oladi.

**Audit yozuvi hech qachon yutilmaydi** — audit yozilmasa amal ham bajarilmaydi
(bitta tranzaksiya).

### 5.3 Materializatsiya

- **Kechalik rollup** (02:30 UTC) `platform_daily_stats` ga yozadi,
  `INSERT … ON CONFLICT DO UPDATE` (qayta yugurtirilsa dublikat bo'lmaydi).
  Job **HTTP so'rovi emas**, shuning uchun uning uchun alohida `system_scope()`
  bor: u `app.platform='true'`, `app.actor_kind='system'` qo'yadi va
  `context.current().is_super_admin` ga **tayanmaydi** (aks holda job
  `PermissionError` bilan yiqilardi va panel eskirgan ma'lumotni jimgina
  ko'rsatardi). Har bir yugurish `system.stats.rollup` sifatida audit'ga tushadi.
- **"Bugun"** — tor, indeksli `COUNT`/`SUM`, `statement_timeout` bilan. Timeout
  oshsa panel "hozircha kechagi ma'lumot" holatini ko'rsatadi, xato emas.

### 5.4 Deanonimizatsiyaga qarshi chegara

"Klublar aylanmasi faqat agregat, alohida klub uchun glass kerak" degan chegara
o'z-o'zidan hech narsani ushlamaydi: `?plan=infinite` + tor sana oynasi bitta
tashkilotni ajratadi, ikki so'rov ayirmasi (`plan=gold` va
`plan=gold&status=active`) esa bitta tashkilotning hissasini beradi.

Chora:

- **Minimal hujayra qoidasi** — agregat kamida **5** ta tashkilotni qamrasa
  qaytariladi, aks holda `{"suppressed": true}`. 5 — differencing hujumini
  amaliy bo'lmagan qilish uchun eng kichik qiymat; undan pastda ikki so'rov
  ayirmasi individual qiymatga aylanadi.
- Filtrlar kombinatsiyasi cheklanadi: `plan` + `status` + `over_limit` + 7 kundan
  tor oyna bir vaqtda taqiqlanadi.
- **Nomlangan `top-10` ro'yxati** agregat statistikadan ajratiladi va alohida
  sabab + audit talab qiladi.
- Har bir `/platform/stats/*` so'rovi **to'liq filtrlari bilan**
  `platform.stats.query` sifatida audit'ga tushadi va chastotasi cheklanadi —
  differencing ketma-ket so'rovlar naqshi bo'yicha aniqlanadi.

### 5.5 Pul va vaqt

Pul — hamma joyda `bigint`, so'm, kasrsiz; Python `int`, JSON'da **satr**
(`"49000000"`); frontendda `BigInt`, `Number` ga o'girish yo'q. O'sish foizi
backendda bazis punktlarda (`int`) yoki xom qiymatlar bilan — float hech qayerda
paydo bo'lmaydi.

Vaqt — DB'da UTC `timestamptz`, panelda `Asia/Tashkent`. Kunlik agregat chegarasi
**platforma mintaqasi** (Toshkent) bo'yicha, klub mintaqasi bo'yicha emas —
barcha klublar hozircha bitta mintaqada; bu faraz `platform_daily_stats` jadval
izohida yozib qo'yiladi.

**Eksport** — CSV mavjud, lekin: PII ustunlari maskalangan, hajm cheklangan,
`platform.export` sifatida audit'ga tushadi.

---

## 6. GLASS REJIMI

Tizimdagi eng xavfli funksiya. Shuning uchun eng batafsil bo'lim.

### 6.1 Nima uchun bor va nima qilmaydi

Glass — impersonation: super admin muammoni **foydalanuvchi ko'zi bilan**
ko'radi. U hisobot vositasi ham, ma'lumot chiqarish vositasi ham, boshqaruv
vositasi ham emas — bular platforma panelining ishi.

### 6.2 Sessiya qanday almashadi

**Haqiqat manbai — `glass_sessions` qatori + Redis keshi. Token faqat ko'rsatkich.**

Uchala muqobilning bahosi:

| Variant | Baho |
|---|---|
| Mavjud JWT ichidagi da'voni almashtirish | **Rad.** `decode_access` faqat imzoni tekshiradi; bekor qilish mexanizmi yo'q — glass'ni to'xtatib bo'lmaydi |
| Faqat server yozuvi (token o'zgarmaydi) | **Rad.** Bir brauzerda ikki tab (platforma va glass) ajratilmaydi; "qaysi so'rov glass ichida?" degan savolga javob yo'q |
| **Yangi qisqa umrli token + DB yozuvi** | **Tanlanadi** |

**Token tarkibi:**

```jsonc
{
  "sub": "<SUPER ADMINNING O'Z user_id si>",   // hech qachon klub egasiniki emas
  "aud": "staff",                               // 05-auth-redesign §6.6 bilan mos
  "scp": "glass",
  "sa":  false,                                 // /platform/* yopiq
  "mbr": [{ "club_id": 12, "org_id": 7, "role": "STAFF" }],   // AYNAN BITTA klub
  "gl":  { "sid": 42, "mode": "read", "exp": 1771000000 },
  "ent": { /* nishon tashkilotning entitlement'lari */ },
  "exp": "<90 soniya>",
  "jti": "…"
}
```

`sub` — super adminning o'zi. Bu audit uchun hal qiluvchi: `audit_log_insert`
policy'si `actor_user_id = app_user_id()` talab qiladi, demak **klub egasi
nomidan audit yozish texnik jihatdan imkonsiz**.

`ent` — nishon tashkilotning entitlement'lari; aks holda glass'da tarif
funksiyalari noto'g'ri yashirinardi va SA mijoz ko'rmaydigan narsani ko'rardi.

**Oqim:**

1. `POST /platform/glass` — **oddiy platforma tokeni bilan**
   (`{org_id, club_id, mode, reason_code, reason_text}`).
2. Qator `status='pending_2fa'` bilan yoziladi va `audit_log` ga `glass.request`
   tushadi — **sessiya boshlanmasa ham iz qoladi**.
3. `POST /platform/glass/{sid}/confirm {totp}` → `status='active'`, `started_at`,
   Redis `glass:{sid}` (TTL = `expires_at` gacha). Javobda glass tokeni.
4. Har so'rovda middleware Redis'dan sessiyani o'qiydi (bitta `GET`, ~0.2 ms).
   Yo'q bo'lsa — `401 GLASS_ENDED`. **Bekor qilish bir zumda ishlaydi:**
   `DEL glass:{sid}`.
5. Token yangilash — `POST /platform/glass/{sid}/renew`, **faqat platforma
   tokeni bilan**. Glass tokenining o'zi bilan emas.

**Glass'da refresh token YO'Q.** `refresh_tokens` jadvaliga glass hech narsa
yozmaydi va glass tokeni `/auth/refresh` ga hech qachon yuborilmaydi.

### 6.3 Glass va RLS: `app.org_id` yetarlimi?

**Javob: `app.org_id` ni almashtirish YETARLI EMAS, lekin BYPASSRLS ham TO'G'RI
JAVOB EMAS.**

**Nega faqat `app.org_id` yetarli emas.** `0003` dan keyin policy'larning
aksariyati `app_club_role()` ga tayanadi, u esa `memberships` ni o'qiydi. Super
adminda nishon klubda a'zolik qatori yo'q. Faqat `app.org_id` qo'yilsa:

| Policy | Natija |
|---|---|
| `organizations_read`, `clubs_read` (`org_id = app_org_id()`) | ✅ ochiladi |
| `memberships_read` | ❌ xodimlar ro'yxati bo'sh |
| `clubs_update` | ❌ |
| kelajakdagi domen jadvallari (`bookings`, `bills`, `shifts`) | ❌ |

Ya'ni glass "yarim ko'r" bo'lardi va muammoni hal qila olmasdi.

**Nega BYPASSRLS roliga o'tish XAVFLI — olti sabab:**

1. **U so'rovning emas, ROLNING atributi.** Pool'dan ulanish olingan zahoti
   o'sha tranzaksiyadagi har bir operator har bir jadvaldagi har bir policy'ni
   e'tiborsiz qoldiradi. Bitta klub uchun ham, ming klub uchun ham bir xil —
   toraytirish mexanizmi yo'q.
2. **U ilova xatosidan omon qoladigan yagona qatlamni olib tashlaydi.** RLS
   ostida unutilgan `WHERE club_id` — nol oqim; BYPASSRLS ostida o'sha xato —
   butun bazaning oqimi. `CLAUDE.md` dagi "qo'lda `where: { club_id }` yozib
   chetlab o'tilmaydi" qoidasi glass uchun ham amal qilishi kerak.
3. **SQL injection blast radiusi** bir klubdan butun platformaga kengayadi.
4. **`0003` ning butun ishi bekor bo'ladi** — `tenant_isolation`, `clubs_read`
   status tekshiruvi, `club_payment_credentials_owner` — hech biri qo'llanmaydi.
   Bugungi holatda BYPASSRLS pool merchant kalitlarini ham o'qiy oladi
   (`0003:200`).
5. **Atribusiya buziladi.** `platform_scope()` kontekst qo'ymaganida
   `audit_log_insert WITH CHECK (actor_user_id = app_user_id())` tekshirilmaydi —
   soxta aktor bilan audit yozish mumkin bo'ladi.
6. **Yozish granti kerak bo'lardi.** `playbron_platform` da faqat
   `organizations` va `audit_log` ga yozish bor; glass yozuvini u yerdan qilish
   uchun butun sxemaga yozish granti berish, ya'ni platforma poolini ikkinchi
   superuser'ga aylantirish kerak bo'lardi.

**Tanlangan yechim.** Glass `session_scope()` (`playbron_app`, RLS YOQILGAN)
ichida ishlaydi. `_apply_context()` qo'shimcha qo'yadi:

```
app.user_id       = <SUPER ADMIN id>       -- O'ZGARMAYDI (atribusiya uchun)
app.org_id        = <glass org>
app.club_id       = <glass club>
app.glass_id      = <sid>
app.glass_club_id = <glass club>
app.glass_mode    = 'read' | 'write'
-- app.platform    QO'YILMAYDI
-- app.is_super_admin  UMUMAN OLIB TASHLANGAN
```

`app_club_role()` esa GUC'ni faqat ko'rsatkich sifatida olib, `glass_sessions`
dagi **tirik** qatorni DB ichida qayta tasdiqlaydi (§2.2).

**Nega "SA ni egaga aylantirish" (`app.user_id = owner_id`) rad etiladi.**
Texnik jihatdan ishlaydi, lekin atribusiyani o'ldiradi: `audit_log` egani aktor
deb muhrlaydi, kelajakdagi `created_by`/`updated_by` ustunlari ham ega bo'lib
chiqadi. Egani soxta ayblash — kechirib bo'lmaydigan dizayn xatosi.

**`app.user_id` SA bo'lib qolishining narxi va uni to'lash.** Mavjud
policy'lardagi `OR actor_user_id = app_user_id()` va `OR owner_user_id =
app_user_id()` shoxlari glass ichida SA ning **boshqa** tashkilotlaridagi
qatorlarni ochib yuborardi. Shuning uchun har bir o'z-o'ziga havola qiluvchi
shoxga `AND app_glass_id() = 0` qo'shiladi (§2.4). Qoida: **glass GUC'i faqat
toraytiradi, hech qachon kengaytirmaydi.**

**Glass qamrovi serverdan keladi, mijozdan emas.** `deps.current_claims()`
`club_id` ni mijozning `X-Club-Id` sarlavhasidan oladi. Glass'da qo'shimcha
tekshiruv: `X-Club-Id != glass_sessions.club_id` → `403 GLASS_SCOPE`. Glass
tokeni `mbr` da bittadan ortiq klub olib yurmaydi. Aks holda sessiya qatoridagi
qamrov (audit va egaga ketadigan xabar shundan olinadi) DB'dagi haqiqiy qamrovga
mos kelmasdi: ega "A klubga kirildi" xabarini olar, amalda B klub o'zgarardi.

**Tranzaksiya tartibi — qat'iy.** `SET TRANSACTION READ ONLY` `BEGIN` dan
keyingi **birinchi** operator bo'lishi shart (`_apply_context()` dan oldin),
aks holda Postgres `25001 active_sql_transaction` beradi
("SET TRANSACTION must be called before any query"). `SET SESSION CHARACTERISTICS
AS TRANSACTION READ ONLY` va `LOCAL` siz `default_transaction_read_only`
**taqiqlanadi**: ular sessiya darajasida qoladi va pool orqali keyingi tenant
so'roviga sizib o'tadi — mijozning bron yaratishi tasodifiy `25006` bilan
yiqilardi.

Barcha kontekst GUC'lari ham `BEGIN` dan keyingi birinchi blokda qo'yiladi,
har qanday `SAVEPOINT` dan oldin. Sabab: `ROLLBACK TO SAVEPOINT` o'zidan keyin
qo'yilgan `set_config(..., true)` qiymatlarini bekor qiladi, `CLAUDE.md` esa
bron to'qnashuvi uchun (`23P01 → 409 SLOT_TAKEN`) savepoint bilan qayta urinish
naqshini talab qiladi. GUC yo'qolsa `app.org_id=0` bo'lib qoladi va
`clubs_read` ning `status='active'` shoxi glass ekranini jimgina **platforma
bo'ylab barcha faol klublar** ro'yxatiga aylantirardi.

### 6.4 O'qish va yozish rejimlari

**Ha, ajratiladi. Bu dizayndagi asosiy chegara.**

| | `read` (sukut) | `write` (v2, kill switch ortida) |
|---|---|---|
| Ikkinchi omil | TOTP | TOTP + ikkinchi SA (bo'lsa) |
| Sukut muddat | **30 daq** | **15 daq** |
| Maksimum (uzaytirish bilan) | **60 daq** | **30 daq** |
| Uzaytirish soni | 1 | 1 |
| DB qulfi | `SET TRANSACTION READ ONLY` | policy'lar + `'ADMIN'` shifti |
| Egaga xabar | Boshlanishida | Boshlanishida + yakunda o'zgarishlar ro'yxati |
| Yoqilganmi | Ha | `platform_settings.glass.write_enabled` (sukut `false`) |

**Raqamlar va sabablari:**

| Qiymat | Sabab |
|---|---|
| Token TTL **90 s** | Token brauzer log'ida, HAR eksportida, proksi log'ida yoki xato hisobotida qolishi mumkin. Uzaytirish fon so'rovi bilan bo'lgani uchun foydalanuvchi sezmaydi, o'g'irlangan token esa deyarli darhol o'ladi |
| O'qish **30 daq** | Bitta qo'llab-quvvatlash suhbatining amaliy uzunligi. Uzunroq qilinsa sessiya ochiq qolib ketadi, qisqaroq qilinsa ish o'rtasida uziladi |
| Yozish **15 daq** | Yozish amali aniq va tor bo'lishi kerak. Uzoq yozish sessiyasi — "tuzatish" emas, "boshqarish" |
| Maksimum **60/30 daq** | Uzaytirish `renew_count` bilan cheklangan; chegara oshsa **yangi sabab bilan yangi sessiya** kerak. "Bir marta kirdim, kun bo'yi turdim" holati yozuvda yashirinmaydi |
| `reason_text` **≥ 20 belgi** | DB CHECK. Qisqaroq matn ("test", "ok") sabab emas, formallik. 20 — bitta ma'noli jumlaning eng kichik uzunligi |
| Bir vaqtda **1** faol sessiya | Unikal indeks. Parallel sessiyalarda "qaysi tashkilotda ekanini" chalkashtirib yuborish xavfi |
| Kunlik **`glass.daily_cap`** (sukut 10) | Normal qo'llab-quvvatlash kunida 10 dan ortiq kirish — naqsh o'zgarishi, tekshirilishi kerak |
| Qatorlar byudjeti **`glass.row_budget`** (sukut 5 000) | "Glass orqali sekin-asta butun bazani ko'chirish" stsenariysini o'ldiradi. 5 000 — eng katta ekranni (bir oylik bron ro'yxati) bir necha marta ochish uchun yetarli, ommaviy eksport uchun yetarli emas |
| Anchor **5 daqiqada** | Glass sessiyasining eng qisqa muddatidan kichik — o'chirish oynasi sessiya uzunligidan qisqa bo'lishi kerak |

**Ikkinchi omil Telegramdan MUSTAQIL bo'lishi shart.**
`docs/05-auth-redesign.md` §6.3 super adminga har kirishda OTP ni majburiy
qilgan, lekin OTP kanali — Telegram. Telegram akkaunti egallangan bo'lsa
(SIM-swap, qurilma) kod ham hujumchiga boradi. Shuning uchun glass uchun
**TOTP** (`super_admin_secrets` jadvali, `verify_totp(bigint, text)`
`SECURITY DEFINER` — sir DB'dan chiqmaydi, `last_used_step` replay'ni
bloklaydi), keyinchalik WebAuthn.

**Faqat-o'qish DB darajasida ushlanadi.** `SET TRANSACTION READ ONLY` — bu
bitta operator: unutilgan guard, ORM xatosi, yangi marshrut — hech biri yoza
olmaydi, Postgres `25006` qaytaradi (`core/errors.py` ga
`25006 → 403 GLASS_READ_ONLY` mapping qo'shiladi). Ilova qatlamida qo'shimcha:
`read` rejimida `POST/PUT/PATCH/DELETE` marshrutga umuman yetmaydi.

### 6.5 Super admin glass'da nima qila OLMAYDI

Bu ro'yxatning har bir qatori **server tomonida**, ko'pchiligi **DB
darajasida** yopilgan. UI'da tugmani yashirish hech qachon yagona chora emas.

| Qila olmaydi | Mexanizm | Qatlam |
|---|---|---|
| **Merchant/to'lov kalitlarini ko'rish** | `club_payment_credentials_owner` `'OWNER'` talab qiladi, `app_club_role()` glass'ga hech qachon `'OWNER'` bermaydi; ustiga policy'ga `AND app_glass_id() = 0` | DB, ikki qulf |
| **A'zolik yaratish yoki o'zgartirish** | `memberships_write` ga `AND app_glass_id() = 0`; qo'shimcha `role <> 'OWNER'` va `user_id <> app_user_id()` | DB |
| **O'ziga doimiy huquq qoldirish** | Yuqoridagi bilan bir xil — bu **eng muhim taqiq**. Usiz butun muddat/audit/xabar apparati bitta INSERT bilan chetlab o'tilardi | DB |
| **Tashkilot egaligini o'ziga ko'chirish** | `REVOKE UPDATE (owner_user_id) ON organizations FROM playbron_app` | DB |
| **Tarif, obuna, tashkilot holatini o'zgartirish** | `REVOKE UPDATE (status, plan_code)` (`0003:186`) + `organizations_update` egaga bog'langan | DB |
| **Boshqa tashkilotni ko'rish** | `app.platform` qo'yilmaydi; o'z-o'ziga havola shoxlarida `AND app_glass_id() = 0` | DB |
| **Platforma paneliga kirish** (`/platform/*`) | Token `sa=false`, `scp='glass'`; `require_super_admin` `gl` klaymi bor tokenni **404** bilan rad etadi | Ilova |
| **Glass ichidan glass ochish** | `glass_sessions_platform` policy'si `app_platform()` talab qiladi; app roliga yozish granti yo'q | DB |
| **O'z sessiyasini uzaytirish yoki tahrirlash** | App roliga `glass_sessions` ga yozish granti yo'q + `BEFORE UPDATE` trigger o'zgarmas ustunlarni qulflaydi | DB |
| **Boshqa foydalanuvchining sessiyasini ko'rish/bekor qilish** | `refresh_tokens_scope` — `user_id = app_user_id()` | DB |
| **Mijozlarning to'liq telefoni va ismini ko'rish** | `users_self` glass'da faqat SA ning o'z qatorini beradi. Domen jadvallaridagi mijoz maydonlari **markazlashgan serializer**da niqoblanadi (`+998 90 ***-**-67`, `Jasur A.`) | DB + ilova |
| Niqobni ochish | Mumkin, lekin `glass.reveal_pii` sifatida audit'ga tushadi va egaga ketadigan yakuniy xulosada sanaladi | Ilova + audit |
| **Ma'lumot eksporti (CSV, bulk)** | Glass ichida marshrut yo'q; egress byudjeti | Ilova |
| **Mijozga klub nomidan xabar yuborish** | Bot marshrutlari glass'da bloklanadi | Ilova |
| **O'chirish** | `REVOKE DELETE` (`0003:182`); glass qo'shimcha huquq bermaydi. Soft-delete majburiy | DB |
| **Auditni o'chirish yoki tahrirlash** | Append-only + HMAC zanjiri + tashqi lang'ar + `BEFORE TRUNCATE` | DB |

**Tashkilotning ixtiyori.** `organizations.glass_write_allowed boolean DEFAULT
true` — ega yozish rejimini o'zi o'chira oladi; o'chirilgan bo'lsa
qo'llab-quvvatlash undan aniq ruxsat so'rashi kerak. O'qish rejimi shartnoma
darajasida qoladi (§14).

### 6.6 Audit: kim nomidan, nima, kim ko'radi

**Kim nomidan — HAR DOIM super admin nomidan.** Bu tanlov emas, DB
majburiyati: `audit_log_insert WITH CHECK (actor_user_id = app_user_id())`,
glass'da esa `app.user_id` — SA. "Klub egasi qildi" deb ko'rinadigan yozuvni
**yasab bo'lmaydi**.

```jsonc
{
  "actor_user_id":    1,                    // super admin
  "actor_kind":       "glass",              // trigger GUC'dan hisoblaydi
  "glass_session_id": 42,
  "org_id":           7,                    // MAJBURIY — §Ilova B
  "club_id":          12,
  "action":           "glass.booking.cancel",
  "target":           "bookings:1042",
  "before":           { … }, "after": { … },
  "chain_seq":        918_233,
  "prev_hmac":        "…", "row_hmac": "…", "key_id": 1
}
```

Domen jadvallarida `created_by`/`updated_by` bo'lsa ular ham SA ni ko'rsatadi —
klub xodimi "bu o'zgarishni men qilmadim" deganda jurnal shuni tasdiqlaydi.

**Nima yoziladi:**

| Hodisa | Batafsillik |
|---|---|
| `glass.request` / `glass.approve` / `glass.deny` | Sabab, rejim, qamrov — sessiya boshlanmasa ham |
| `glass.start` / `glass.renew` / `glass.end` | `end_reason`, `request_count`, `write_count`, `rows_read` |
| Har bir **yozish** amali | `before`/`after` glass'da **majburiy** |
| `glass.reveal_pii` | Qaysi yozuv, qaysi maydon |
| **O'qishlar** | Har bir GET emas — **ekran darajasida**: `glass.view`, `target='screen:bookings'`, qatorlar soni. Sabab: har so'rovni yozish audit'ni shovqinga va PII omboriga aylantiradi |
| `/platform/*` amallari | Har biri alohida, o'qishlar ham (§5.4) |
| Rad etilgan urinishlar | IP allowlist, TOTP xatosi, `scp` nomuvofiqligi |

> **Arxitektura hujjatiga tuzatish kerak:** `docs/01-architecture.md` §9
> "har bir platforma so'rovi audit_log'ga yoziladi (o'qish ham)" deydi. Bu
> `/platform/*` uchun kuchda qoladi, glass ichidagi o'qishlar uchun esa
> sessiya + ekran darajasiga tushiriladi.

**Faqat-o'qish rejimidagi tuzoq va yechimi.** `SET TRANSACTION READ ONLY`
o'sha tranzaksiyadagi `INSERT INTO audit_log` ni ham bloklaydi (`25006`).
Odatiy "audit best-effort" naqshi bilan bu jimgina yutilardi va **eng ko'p
ishlatiladigan rejim butunlay auditsiz qolardi**. Shuning uchun:

- audit **alohida sessiyada** yoziladi (`modules/auth/service.py:168-183` dagi
  `revoke_all_tokens()` naqshi);
- o'sha sessiyada `_apply_context()` **majburiy** chaqiriladi (faqat
  `set_current_user()` yetarli emas: `app.org_id` 0 bo'lib qolsa yozuv
  yoziladi, lekin `audit_log_read` `org_id = app_org_id()` shoxi mos kelmagani
  uchun **tashkilot egasi uni hech qachon ko'rmaydi** — nazorat mexanizmi aynan
  o'zi himoya qilishi kerak bo'lgan tomon uchun ishlamay qolardi);
- audit INSERT xatosi hech qachon yutilmaydi;
- DB darajasida ushlash: `CHECK (actor_kind <> 'glass' OR org_id IS NOT NULL)`.

**Kim ko'radi:**

1. **Super admin** — `/platform/audit`, sessiya bo'yicha guruhlangan.
2. **Tashkilot egasi** — klub kabinetida yangi "Platforma kirishlari" bo'limi:
   sana, davomiylik, rejim, sabab kodi, barqaror operator handle'i, nechta
   o'zgartirish. `audit_log_read` va `glass_sessions_tenant_read` policy'lari
   buni allaqachon ochadi.
   **Xom qator ko'rsatilmaydi** — `ip` va `ua_hash` tenantga chiqmaydi:
   `platform_ip_allowlist` aynan o'sha IP'lardan iborat, ya'ni xom qator
   platformaning yagona tarmoq to'sig'i qanday qiymatlardan iboratligini har
   bir mijozga oshkor qilardi. Ko'rsatish `SECURITY DEFINER` funksiya orqali,
   tanlangan maydonlar bilan.
3. **STAFF/ADMIN** — faqat o'z klubi doirasida (§2.4 dagi toraytirilgan
   `audit_log_read`).

**Egaga xabar — majburiy va sozlanmaydigan.** Admin bot orqali sessiya
**boshlanishida** (tugaganda emas) barcha `OWNER` rolidagilarga: kim, nima
uchun (sabab kodi va matni), qaysi qamrov, qancha vaqt, o'qish yoki yozish.

- Xabarda **"Bu men so'ramaganman"** tugmasi. Bosilsa sessiya avtomatik
  **bekor qilinmaydi** (aks holda ega qo'llab-quvvatlashni DoS qila olardi),
  lekin `flagged_at` qo'yiladi, yozish rejimi darhol faqat-o'qishga tushadi va
  barcha SA'larga signal ketadi.
- Bir soat ichidagi takroriy kirishlar **bitta xabarga birlashtiriladi** —
  aks holda faol qo'llab-quvvatlash kunlarida ega xabarlarni e'tiborsiz
  qoldirishni o'rganadi va shaffoflik chorasi o'z ma'nosini yo'qotadi.
- "Jim rejim" checkbox'i **yo'q** (§14 da ochiq savol sifatida qoldi).

**PII audit ichiga tushmaydi.** `before`/`after` dagi telefon, telegram_id,
to'liq ism — **markazlashgan serializer**da maskalanadi (har marshrutda alohida
emas). Aks holda audit jadvali eng katta PII to'plamiga aylanadi. Testda
ushlanadi: `audit_log` da `\+998\d{9}` naqshi topilmasin.

### 6.7 UI — glass rejimini unutib qo'yib bo'lmaydi

Uch qatlam belgi, hammasi DS tokenlari bilan (`packages/ui/src/tokens/**` —
tegilmaydigan zona; ogohlantirish/danger tonlari mavjud nomlardan olinadi).

1. **Yopishqoq yuqori panel** — `apps/admin/src/app.tsx` dagi eng tashqi `div`
   ichida, `header` dan **oldin**, `position: sticky; top: 0`, yopilmaydi:

   ```
   ◆ GLASS · Neon Arena MCHJ · «Neon Arena» klubi · FAQAT O'QISH · 24:13 · [Uzaytirish] [CHIQISH]
     Sabab: mijoz shikoyati bo'yicha bronni tekshirish
   ```

   Taymer — mavjud `Countdown` (`packages/ui/src/components/time.tsx`), rangi
   `toneForRemaining()` orqali; 5 daqiqa qolganda `danger` toniga o'tadi va
   "Uzaytirish" (yangi sabab + TOTP) taklif qilinadi.
2. **Butun ilova ramkasi** — `box-shadow: inset 0 0 0 2px var(--tone-warn-line)`
   (o'qish) / `var(--tone-danger-line)` (yozish). Kontent maydonidan joy olmaydi,
   lekin periferik ko'rish bilan sezilib turadi va **skrinshotda ham qoladi**.
3. **Brauzer tab'i** — `document.title` oldiga `[GLASS]`, favicon almashadi.
   Ko'p tabli ishda (platforma paneli + glass) bu yagona ko'rinadigan belgi.

Qo'shimchalar:

- `UserMenu` da ism o'rniga "Super admin (glass)", rol o'rniga tashkilot nomi;
  oddiy "Chiqish" olib tashlanadi, o'rnida "Glass'dan chiqish" — noto'g'ri
  tugmani bosib butunlay chiqib ketilmasin.
- Yozish rejimida destruktiv amal dialogi **klub nomini qo'lda yozishni** talab
  qiladi — mushak xotirasi bilan "OK" bosishning oldini oladi.
- Faqat-o'qishda yozuvchi tugmalar `disabled` + tooltip.
- Maskalangan maydon yonida `visibility` ikonkasi, tooltip: "Ko'rish audit'ga
  yoziladi".
- Muddat tugaganda ekran bloklanmaydi va kiritilayotgan forma holati
  yo'qolmaydi: ustiga "Glass sessiyasi tugadi" overlay'i va ikki tugma.
- **Chiqish — bitta bosish, tasdiqsiz.** Chiqish har doim arzon bo'lishi kerak.

**Navigatsiya.** Glass ichida platforma menyusi umuman ko'rinmaydi (token ham
unga yetmaydi). SA nishon tashkilot ko'radigan **aynan o'sha** menyuni ko'radi
(`NAV_STAFF` / `NAV_ADMIN`) va **mavjud klub ekranlarini** ishlatadi —
`LiveBoardScreen`, `TimelineScreen`, `DashboardScreen` o'zgarishsiz. Glass uchun
parallel API yoki ekranlarning ikkinchi nusxasi yozilsa, u asosiy mahsulotdan
drift qiladi va SA "mijoz ko'radigan narsani" ko'rmay qoladi.

**Matn** — literal yo'q, `apps/admin/src/i18n.ts` dagi `STRINGS` ga uz/ru/en
kalitlari (`glassBanner*`, `glassExit`, `glassReadOnly`, `glassExpiresIn`…).

### 6.8 Chiqish

| Yo'l | Natija |
|---|---|
| "CHIQISH" tugmasi | `POST /platform/glass/{sid}/end`, `end_reason='manual'`, Redis kaliti o'chadi |
| Muddat tugashi | `401 GLASS_EXPIRED`; `expires_at` so'rov yo'lida tekshiriladi (kunlik job'ga tayanmaydi) |
| Tab yopilishi | `pagehide`/`visibilitychange` da `navigator.sendBeacon` bilan `end`; ustiga token 90 s da o'ladi |
| Masofadan bekor qilish | `POST /platform/glass/{sid}/kill` — boshqa qurilmadan yoki panel ro'yxatidan |
| Kill switch | `platform_settings.glass.enabled = false` → barcha faol sessiyalar tugaydi, yangisi ochilmaydi (deploy kutmasdan) |
| Byudjet / kunlik chegara | `end_reason='budget'` |
| IP yoki UA nomuvofiqligi | `end_reason='binding'` |
| Ega bayrog'i | Sessiya tugamaydi, `flagged_at` + yozish → o'qish |

Chiqishda `sessionStorage` dagi glass kaliti o'chadi va **platforma sessiyasi
tegilmaydi** — qayta kirish talab qilinmaydi. `end` da sessiyaga berilgan barcha
`jti` lar qora ro'yxatga tushadi.

**Glass klienti hech qachon `/auth/refresh` ni chaqirmaydi.** Bu alohida
ta'kidlanadi, chunki mavjud `packages/api-client/src/client.ts:51-64` istalgan
401 javobda avtomatik `refresh()` chaqiradi, `service.rotate_refresh()` esa
DB'dan `is_super_admin` ni qayta o'qib **`sa: true` bo'lgan to'liq platforma
tokenini** qaytaradi va klient uni o'sha store'ga yozib so'rovni qayta yuboradi.
Natija: bekor qilingan glass sessiyasidan keyin so'rov bajarilardi, ustiga
glass'ning cheklangan roli o'rniga to'liq super admin huquqi bilan. Shuning
uchun glass klientida `refresh` yo'li **o'chiriladi** va 401 faqat
`onGlassEnded()` chaqiradi; server tomonda esa glass tokeni `/auth/refresh` ga
kelsa 400 bilan rad etiladi.

Bu bilan bog'liq mavjud tuzoq: `packages/api-client/src/session.ts:38`
`if (!parsed.accessToken || !parsed.refreshToken) return null` — refresh
tokensiz sessiyani umuman saqlay olmaydi. `Session` tipida `refreshToken`
**ixtiyoriy** qilinadi, aks holda implementator platforma refresh tokenini
glass store'ga qo'yishga majbur bo'ladi.

---

## 7. Landing CMS

### 7.1 Tanlangan variant: (b) — kontent bazada, nashr deploy hook'i orqali

**Asos:**

1. **Statiklik — mahsulot qarori, texnik tasodif emas.**
   `apps/landing/astro.config.mjs` "to'liq statik, mijoz tomonida JS yo'q"
   deb yozilgan; `render.yaml:167-170` da landing `runtime: static` va SPA
   rewrite **ataylab yo'q** ("mavjud bo'lmagan manzil haqiqiy 404 qaytarishi
   kerak"). Landing — mijoz jalb qilish yuzasi: eng tez, eng arzon va eng
   ishonchli narsa bo'lishi kerak.
2. **Nol-JS eng arzon xavfsizlik qatlami.** Saytda o'z JS'i bo'lmagani uchun
   `script-src 'none'` CSP hech narsani buzmaydi (§7.7).

**(a) SSR — rad etiladi.**

- Statiklik va nol-JS yo'qoladi; Render'da `runtime: static` → `web` ga o'tadi,
  bepul rejada sovuq start (birinchi tashrifchi o'nlab soniya kutadi) — bu
  **Core Web Vitals orqali to'g'ridan-to'g'ri SEO zarari**.
- **Anonim internetdan tenant bazasiga yangi yo'l ochiladi.** Bugun landing va
  baza o'rtasida umuman aloqa yo'q. SSR bilan har bir tashrif DB'ga tegadi —
  yangi RLS, DDoS va ulanish pooli yuzasi.
- API yiqilsa yoki uxlab qolsa **marketing sayti ham yiqiladi**: ichki nosozlik
  tashqi yuzani o'ldiradi va obuna sotib olish oqimining kirish nuqtasi
  yo'qoladi.
- SEO foydasi **nol** — statik sahifa allaqachon eng yaxshi holat.
- Yagona ustunligi — nashr bir zumda. Kontent oyiga bir necha marta
  o'zgaradigan sahifa uchun bu arzimaydigan yutuq.

**(c) CMS repodagi fayllarni tahrirlaydi (git commit) — rad etiladi.**

- **Kredensial radiusi — hal qiluvchi sabab.** API'da repo'ga **yozish**
  huquqli GitHub tokeni turishi kerak. O'sha token repo'ga **kod** ham push
  qiladi, kod esa avtomatik deploy bo'ladi. Ya'ni "landing matnini tahrirlash"
  huquqi de-fakto "prodga ixtiyoriy kod chiqarish" huquqiga aylanadi: buzilgan
  SA hisobi yoki admin paneldagi XSS CI orqali RCE beradi va `render.yaml` dagi
  barcha `generateValue`/`sync: false` sirlarni bir kalit bilan almashtiradi.
  Biz bir tomondan glass'ni qattiq nazorat qilib, ikkinchi tomondan CMS orqali
  RCE qoldira olmaymiz. **Kontentni tahrirlash hech qachon kodga yozish
  bo'lmasligi kerak.**
- Ishlab chiquvchi o'sha `uz.ts`/`ru.ts` ni tahrirlayotganda konflikt chiqadi
  va uni CMS UI'dan hal qilib bo'lmaydi.
- Qoralama holati, versiyalash va rollback git tarixida yashaydi — mahsulot
  ichida emas; audit `audit_log` bilan bog'lanmaydi.
- Yakuniy natija baribir deploy — ya'ni (b) ning sekinligi saqlanadi, xavf esa
  qo'shiladi.

**(b) ning narxi va uni qanday to'laymiz.** Nashr darhol emas — Astro build +
Render statik deploy ≈ 2–4 daqiqa. UI'da "Nashr qilinmoqda" holati, Render
deploy id'si va status polling'i; nashr tugagach bildirishnoma va
**haqiqiy tekshiruv** (§7.6).

### 7.2 Ma'lumot modeli

**`landing_versions`** — `id`, `version int UNIQUE`, `status text CHECK IN
('draft','preview','published','archived')`, `doc jsonb NOT NULL`,
`plans_snapshot jsonb NOT NULL`, `schema_version int NOT NULL`, `note text`,
`author_user_id`, `created_at`, `published_at`, `render_deploy_id text`.

`doc` — **bitta hujjat, ichida ikkala til**: `{"uz": {...}, "ru": {...}}`.

Sabab: "uz yangilandi, ru eskiligicha qoldi" holati **tuzilish darajasida**
imkonsiz. Til bo'yicha alohida qator (`PK (version_id, lang)`) qilinsa, ikkala
til mavjudligini DB kafolatlamaydi va faqat `uz` qatori bo'lgan versiyaga
rollback qilinganda `ru/index.html` bo'sh kontent bilan yig'ilib indekslanardi.

```sql
CREATE UNIQUE INDEX landing_one_published
  ON landing_versions ((status)) WHERE status = 'published';
```

`published` qatorni UPDATE qilish trigger bilan taqiqlanadi — immutable.

RLS: `ENABLE`+`FORCE`; `landing_public_read FOR SELECT USING (status =
'published')` (nashr etilgan matn — saytning o'zi, ochiq ma'lumot),
`landing_write FOR ALL USING (app_platform()) WITH CHECK (app_platform())`.
App roliga yozish granti yo'q.

**Nima CMS'ga TUSHMAYDI.** `apps/landing/src/content/uz.ts` dagi top-level
skalyarlar — `lang`, `htmlLang`, `localeTag`, `dir` — hujjatdan **chiqariladi**
va kodda `LOCALE_ROUTES: Record<Lang, {dir, htmlLang, localeTag}>` konstantasida
qoladi. Sabab: `Base.astro:25` da `const canonical = new URL(c.dir, base).href`
va `Header.astro` da `href={c.dir}`. Ru hujjatida `dir` ni `'/'` qilib qo'yish
(hatto oddiy xatodan ham) `/ru/` sahifasini `/` ga canonical qilib, rus
tilidagi butun organik trafikni o'chirardi; `dir = '//evil.example/'` esa
`new URL()` orqali canonical'ni begona domenga olib ketardi va "faqat `/` bilan
boshlanishi kerak" degan sodda tekshiruvdan o'tib ketardi. Bu **til marshruti**,
kontent emas.

### 7.3 Tip xavfsizligi

Bugungi kafolat: `ru.ts` `uz.ts` tipiga bo'ysunadi va `package.json` dagi
`astro check && astro build` tarjima tushib qolsa build'ni yiqitadi. Bu
kafolat serverga ko'chiriladi: `uz.ts` ning `Content` tipidan
`packages/types` da `ContentSchema` (zod) hosil qilinadi va API (1) saqlashda,
(2) nashrdan oldin, (3) build paytida tekshiradi.

- Build'da `ContentSchema.parse()` va `.strict()` — `safeParse` emas.
  Yetishmayotgan yoki ortiqcha maydon build'ni **yiqitsin**. Aks holda Astro
  `undefined` ni "hech narsa" qilib chiqaradi va sahifada jimgina bo'sh bo'lim
  paydo bo'ladi.
- **Komponent ↔ hujjat drifti.** `schema_version` oshganda `cms_migrations/`
  da har bir eski `doc` ni yangi sxemaga ko'taradigan sof funksiya yoziladi,
  yangi maydon uchun sukut qiymat majburiy. Deploy tartibi:
  komponent → sxema → kontent migratsiyasi → kod deploy'i. Nashrda
  `schema_version` mos kelmasa `422`.
- CI qo'riqchisi:
  `expectTypeOf<z.infer<typeof ContentSchema>>().toEqualTypeOf<Content>()`.

### 7.4 Build vaqtida o'qish

`apps/landing/src/content/remote.ts` — build paytida ishlaydi, chiqishga bir
bayt ham JS qo'shmaydi:

```
GET {API}/api/v1/public/landing-content?version={LANDING_CONTENT_VERSION}
  → 3 urinish, eksponensial, jami ~60 s (uxlagan konteynerni uyg'otish uchun)
  → ContentSchema.parse()
  → xato bo'lsa: process.exit(1)   ← build QIZIL, joriy sayt tegilmaydi
```

**Repodagi `uz.ts`/`ru.ts` ga jimgina fallback YO'Q.** Sabab: fallback build'ni
yashil qoldirsa, SA narxni 490 000 → 590 000 qilib "Nashr qilish" bosadi, API
uxlab qolgan bo'lsa build eski matn bilan chiqadi va panelda yashil belgi
turadi. Rollback holatida bu yanada yomon: "v4 da xato bor, v3 ga qaytaramiz"
→ fallback → sayt na v4, na v3, balki oylar oldingi baseline'ni ko'rsatadi.
Xato haqida xabar beruvchi kanal aynan yiqilgan kanalning o'zi bo'lgani uchun
"fallback bo'lsa release'ni failed deb belgilaymiz" chorasi ham ishlamaydi.

Render oxirgi muvaffaqiyatli deploy'ni saqlaydi — ya'ni qizil build joriy
saytga zarar bermaydi. Repodagi fayllar `import.meta.env.DEV` da fallback
sifatida **qoladi** (o'chirilmaydi) va lokal ishlab chiqish uzilmaydi.

**Nashrdan oldin API uyg'otiladi:** `publish` avval `/healthz` javobini kutadi,
keyin hook'ni chaqiradi.

**Versiya ID bo'yicha olinadi, "joriy nashr" ko'rsatkichi bo'yicha emas.**
Aks holda poyga: v5 nashri (hook A) → 30 soniyadan keyin v4 ga rollback
(hook B) → build A hali kontentni olmagan bo'lsa v4 ni yig'adi va
`landing_versions[v5].render_deploy_id` yolg'on gapiradi.

### 7.5 Narxlar va aloqa ma'lumotlari

- Narx manbai — `plans` jadvali. CMS `plans.price_month/price_year` ni
  tahrirlaydi, landing build paytida shu yerdan oladi (`formatSum` saqlanadi).
  Shu bilan bugungi uch joydagi dublikat (`docs/03-entitlements.md`,
  `0002_seed.py`, `apps/landing/src/content/plans.ts`) bitta manbaga keladi.
- **Narx o'zgarishi — billing amali:** TOTP majburiy, va u **mavjud obunalarga
  ta'sir qilmaydi** — narx sotib olish paytida `subscriptions` ga snapshot
  qilinadi. Bu ustun Faza 5 da bo'lmasa, CMS'dagi narx tahriri Faza 5 dan
  **keyin** yoqiladi (§14). Narx o'zgarganda Redis `org:*:ent` keshi bekor
  qilinadi.
- Aloqa (`apps/landing/src/config.ts` dagi `email`, `phone`, `phoneHref` —
  hozir "TODO" o'rinbosarlar) → `platform_settings['public.contacts']`.
  Bot va ilova URL'lari kodda qoladi — ular deploy topologiyasi, kontent emas.

### 7.6 Preview, nashr, rollback

**Preview.** `render.yaml` da landing `runtime: static` — statik saytda cookie
tekshiradigan yoki basic auth so'raydigan **server tomonidagi kod yo'q**, ya'ni
"preview'ni parol bilan yopamiz" texnik jihatdan amalga oshmaydi. Shuning uchun
ikki bosqich:

- **v1 — maydon-diff.** CMS ekranida joriy nashr ↔ draft solishtiruvi,
  o'zgargan qatorlar ajratilgan. Imlo va matn tuzatishlari uchun yetarli, hech
  qanday yangi hujum yuzasi yo'q, hech qanday build sarflanmaydi.
- **v2 — to'liq preview**, ikkita shartdan biri bilan:
  (a) build artefakti obyekt saqlagichga chiqariladi va API imzolangan qisqa
  muddatli URL beradi — tekshiruv server bor joyda bo'ladi; yoki
  (b) alohida Render statik xizmati **taxmin qilinmaydigan nom bilan**
  (`playbron-lp-<random>.onrender.com`), va bu "noaniqlik orqali himoya" ekani
  hujjatda ochiq yoziladi.

  Preview'da **ikki qatlam** noindex majburiy — bittasi unutilsa yetarli emas:
  `apps/landing/src/pages/robots.txt.ts` `Disallow: /` qaytaradi va
  `Sitemap:` qatorini **chiqarmaydi**; `Base.astro` `<meta name="robots"
  content="noindex, nofollow">` qo'shadi. `@astrojs/sitemap` preview build'da
  o'chiriladi.

  **Canonical prod'ga QO'YILMAYDI.** `noindex` + boshqa URL'ga canonical
  kombinatsiyasi Google preview'ni prod bilan bitta canonical guruhga qo'shsa,
  `noindex` guruhning vakiliga — ya'ni prod sahifaga — qo'llanishi mumkin.
  Preview self-canonical bo'ladi yoki canonical umuman chiqarilmaydi.

  Preview build **prod build'ning aynan o'zi** — "preview'da boshqacha ko'rindi"
  holati bo'lmaydi.

**Nashr.** `POST /platform/landing/publish` → validatsiya → yangi
`landing_versions` qatori `published` → `platform_settings['cms.published_version_id']`
→ prod deploy hook (`LANDING_CONTENT_VERSION` bilan). TOTP + majburiy izoh.

**Nashr tekshiruvi.** Har bir sahifa `<head>` iga
`<meta name="pb-content-version" content={version} />` yoziladi.
`GET /platform/landing/verify` prod URL'ni o'qib uni
`cms.published_version_id` bilan solishtiradi; nomuvofiqlik boshqaruv panelida
`danger` tonli hodisa bo'ladi. Tekshiruv build'dan emas API'dan yuritiladi —
ya'ni yiqilgan kanalga bog'liq emas.

**Rollback.** `POST /platform/landing/rollback/{version}` — eski versiyaning
`doc` i **joriy zod sxemasi bilan qayta validatsiya qilinadi** va **yangi
versiya sifatida** yoziladi. Tarix faqat oldinga o'sadi ("Migratsiyalar faqat
oldinga" falsafasi bilan bir xil), hech narsa o'chirilmaydi. Validatsiya
yiqilsa rollback bloklanadi va yetishmayotgan kalitlar ro'yxati ko'rsatiladi —
aks holda avariya paytidagi rollback bo'sh bo'limli sahifa berib, tuzatish
o'rniga ikkinchi avariyaga aylanardi.

Oxirgi **50** versiya saqlanadi (sabab: bir yillik tahrir tarixi uchun yetarli,
jsonb hajmi esa boshqariladigan qoladi).

**Deploy hook — chastota va sir.**

- Hook faqat **alohida tugma** bilan chaqiriladi; "Saqlash" faqat DB yozuvi.
  Sabab: har saqlashda hook chaqirilsa autosave yoki `Ctrl+S` odati Render
  build daqiqalarini tugatadi — va kvota **akkaunt bo'ylab umumiy**, ya'ni
  `playbron-api` ning shoshilinch hotfix deploy'i ham chiqmay qoladi. Marketing
  matnini tahrirlash huquqi butun platformaning deploy qobiliyatini o'chirish
  huquqiga aylanardi.
- Redis qulfi: preview **120 s**, nashr **300 s** debounce; kunlik hisoblagich
  preview ≤ 20, nashr ≤ 10. Chegara oshsa `429` va UI'da qolgan vaqt.
- Bir vaqtda bitta `building`: yangi so'rov `409 DEPLOY_IN_PROGRESS`.
- **Hook URL hech qachon log/DB/audit/xato matniga tushmaydi.** `httpx`
  chaqiruvi `except httpx.HTTPError:` ichida faqat `status_code` va oldindan
  belgilangan xato kodini saqlaydi — istisno matni URL'ni o'z ichiga oladi.
  Hook'ni aylantirish tartibi hujjatlashtiriladi.

### 7.7 XSS va kontent injeksiyasi

**1. Kontent hech qachon HTML emas.** Maydon tiplari cheklangan:
`plain` (Astro `{expr}` avtomatik escape qiladi), `inline` (juda tor ruxsat
ro'yxati — qalin, kursiv, havola — serverda strukturaviy AST'ga parse qilinadi
va Astro komponenti chizadi, hech qayerda HTML **satri** bo'lmaydi),
`url`, `icon` (DS ikonkalar enum'i), `number`.

**2. `set:html` ga CMS kiritmasi HECH QACHON berilmaydi.** Landing'da ikkita
`set:html` bor va ikkalasi ham JSON-LD:

- `apps/landing/src/layouts/Base.astro:100` — `jsonLdScript(jsonLd)`, ichida
  `description: c.meta.description`;
- `apps/landing/src/components/sections/Faq.astro:47` — `jsonLdScript(faqLd)`,
  ichida FAQ savol va javoblari (CMS'dagi eng katta erkin matn).

> **Bu teshik repoda ALLAQACHON YOPILGAN.**
> `apps/landing/src/lib/jsonld.ts` `<`, `>`, `&` ni `<` ko'rinishiga
> almashtiradi va fayl izohida "landing CMS ulangach u foydalanuvchi kiritmasiga
> aylanadi, ya'ni teshik o'sha kuni ochiladi" deb yozilgan. CMS bu qatlamni
> **buzmasligi** kerak.

Qo'riqchi test (CI): `grep -rn 'set:html={JSON.stringify' apps/landing/src`
natija bersa build yiqiladi — kelajakdagi uchinchi JSON-LD bloki
`jsonLdScript()` dan chetlab o'tmasin.

**3. Zod sxemasida qattiq cheklovlar:** har maydon uchun `max()` uzunlik
(`meta.title` ≤ 60, `meta.description` ≤ 160 — SEO uchun ham foydali va
admin'da hisoblagich ko'rsatiladi), `<` va `>` ni rad etuvchi regex. Bu
**ikkinchi** qatlam; birinchisi — chiqishda kodlash.

**4. `url` maydonlari:** faqat `https:`, `tel:`, `mailto:`; host allowlist
(`playbron.uz`, `t.me`). Aks holda CMS'ni qo'lga kiritgan kishi CTA tugmasini
fishing saytiga yo'naltiradi — bu XSS'dan ham xavfliroq. Tashqi rasm/asset
qabul qilinmaydi (aks holda tashqi manba landing'ga trekker qo'shadi va
"nol JS" va'dasi buziladi).

**5. Admin konsolida CMS matni FAQAT matn tuguni sifatida chiziladi.**
Diff bo'yash `dangerouslySetInnerHTML` bilan emas, `<ins>{chunk.value}</ins>`
segment massivi orqali. `apps/admin` uchun `eslint` qoidasi
`react/no-danger: error`, istisnosiz. Sabab: nashr qilinmagan **draft** ham
yetarli — ikkinchi SA `/platform/cms` ni ochgan zahoti diff render bo'ladi, va
platforma tokeni `localStorage` da turgani uchun bitta matn maydoni butun
glass nazorat apparatini o'zi boshqaradigan holatga aylanardi. Bu aynan (c)
variantidan qochgan natijaning o'zi, faqat boshqa yo'l bilan.
Qo'shimcha: `apps/admin` ga `script-src 'self'` CSP.

**6. CSP — `render.yaml` da landing va preview xizmatlariga.** Hozir faqat
`X-Frame-Options` va `X-Content-Type-Options` bor:

```yaml
- path: /*
  name: Content-Security-Policy
  value: "default-src 'self'; script-src 'none'; style-src 'self' 'unsafe-inline';
          img-src 'self' data:; font-src 'self' https://fonts.gstatic.com;
          connect-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'"
- path: /*
  name: Referrer-Policy
  value: strict-origin-when-cross-origin
```

`script-src 'none'` saytda o'z JS'i yo'qligi uchun hech narsani buzmaydi;
`<script type="application/ld+json">` bloklari **bajarilmaydi** (ular ma'lumot),
qidiruv tizimlari ularni HTML parseridan o'qiydi. `connect-src 'none'`
ekfiltratsiyani yopadi. Natija: shablon xatosi bo'lsa ham saqlangan XSS'ni
ekspluatatsiya qilib bo'lmaydi. Qo'riqchi test: chiqarilgan HTML'da faqat
`type="application/ld+json"` skriptlari borligi.

**7. CMS glass'dan tashqarida.** U `/platform/*` da yashaydi; glass tokeni u
yerga yetmaydi va `landing_write` policy'si `app_platform()` talab qiladi.

### 7.8 SEO ta'siri

URL to'plami o'zgarmaydi (har til uchun bitta sahifa, slug tahrirlanmaydi) —
demak redirect boshqaruvi kerak emas va nashr indeksga zarar bermaydi.
Canonical / `hreflang` / sitemap / JSON-LD bugungidek `Astro.site` dan yasaladi
va **`dir` CMS'dan olinmaydi** (§7.2). `sitemap.lastmod = published_at`.
Build vaqtidagi tekshiruvlar: `meta.title`/`description` uzunligi, ikkala til
mavjudligi, bo'sh maydon yo'qligi, va post-build skript har bir HTML'dagi
`<link rel=canonical>` hostini `Astro.site` hosti bilan solishtiradi (mos
kelmasa build yiqiladi). To'liq qayta yig'ish tufayli qisman eskirgan CDN
fragmentlari bo'lmaydi.

---

## 8. Platforma sozlamalari

`/platform/settings`. Barcha yozuvlar **TOTP** talab qiladi va `audit_log` ga
`platform.settings.update` sifatida before/after bilan tushadi.

| Guruh | Kalitlar |
|---|---|
| Glass siyosati | `glass.enabled` (kill switch), `glass.write_enabled`, `glass.read_max_min`, `glass.write_max_min`, `glass.daily_cap`, `glass.row_budget` |
| Xavfsizlik | IP allowlist (prod'da bo'sh bo'lishi taqiqlanadi), TOTP boshqaruvi, faol sessiyalar |
| Obuna | `ops.subscription_warn_days`, `ops.grace_days` |
| Aloqa (landing uchun) | `public.contacts.email`, `public.contacts.phone`, `public.contacts.phone_href` |
| CMS | `cms.published_version_id` (o'qish uchun), nashr chegaralari |
| Audit | Zanjir holati, oxirgi lang'ar, kalit rotatsiyasi |

**Sirlar bu yerda emas.** Deploy hook URL, bot tokenlari, JWT siri, HMAC
kaliti — `render.yaml` env va `audit_seal_key` jadvalida.

---

## 9. API endpointlari va himoyasi

Barcha `/api/v1/platform/*`: `Depends(require_super_admin)` (mavjud, **404**
qaytaradi — panel borligi bilinmasin) + IP allowlist (prod'da majburiy) +
`scp='platform'` + amal audit'i. `require_super_admin` yangilanadi: `gl` klaymi
bor token uchun ham **404**.

**Glass**

```
POST   /platform/glass                 {org_id, club_id, mode, reason_code, reason_text}
                                       → sessiya (pending_2fa) + glass.request audit
POST   /platform/glass/{sid}/confirm   {totp}         → glass tokeni
POST   /platform/glass/{sid}/renew                    → yangi glass tokeni (platforma tokeni bilan)
POST   /platform/glass/{sid}/extend    {reason_text, totp}
POST   /platform/glass/{sid}/end
POST   /platform/glass/{sid}/kill                     — boshqa qurilmadan
GET    /platform/glass?active=1&org_id=&cursor=
POST   /platform/glass/{sid}/reveal    {entity, id, field}  → + glass.reveal_pii
```

**Tashkilotlar**

```
GET    /platform/orgs?status=&plan=&q=&over_limit=&cursor=&limit=
GET    /platform/orgs/{id}
GET    /platform/orgs/{id}/{clubs|staff|payments|limits|audit}
PATCH  /platform/orgs/{id}/status      {status, reason, totp}
POST   /platform/orgs/{id}/plan        {plan_code, period, reason, totp}
POST   /platform/orgs/{id}/grace       {days, reason, totp}
POST   /platform/orgs/{id}/owner       {user_id, reason, totp}   — ikkinchi SA
POST   /platform/payments/{id}/refund  {reason, totp}
GET    /platform/search?q=                                        — PII xesh bo'yicha
```

**Panel va statistika** (o'qish, `platform_scope()`, READ ONLY)

```
GET    /platform/overview
GET    /platform/stats/revenue?from&to&granularity      — (a) platforma
GET    /platform/stats/clubs?from&to                    — (b) klublar, ALOHIDA endpoint
GET    /platform/stats/orgs · /platform/stats/health
POST   /platform/alerts/{key}/ack      {org_id}
GET    /platform/audit?actor&org&club&action&kind&glass_session_id&from&to&cursor
GET    /platform/audit/integrity
```

**CMS va sozlamalar**

```
GET    /platform/landing/draft · PUT /platform/landing/draft   {doc, note}
GET    /platform/landing/versions?cursor= · GET /platform/landing/diff/{a}/{b}
POST   /platform/landing/preview
POST   /platform/landing/publish       {note, totp}
POST   /platform/landing/rollback/{version}  {totp}
GET    /platform/landing/deploy/{id} · GET /platform/landing/verify
GET|PUT /platform/plans/{code}         {price_month, price_year, limits, totp}
GET|PUT /platform/settings             {totp}
```

**Tenant tomonida (RLS ostida, glass emas)**

```
GET /api/v1/me/security/glass-sessions   — ega o'z tashkiloti ustidagi kirishlarni ko'radi
GET /api/v1/me/security/audit            — mavjud audit_log_read policy'si beradi
```

**Ochiq (autentifikatsiyasiz, build uchun)**

```
GET /api/v1/public/landing-content?version={id}
```

Faqat `status='published'` yoki `Authorization: Bearer $LANDING_PREVIEW_TOKEN`
bilan draft. **Token URL query'siga hech qachon qo'yilmaydi** — u Render build
log'ida, proksi log'ida va API access log'ida ochiq qolardi. `ETag` +
`Cache-Control` (versiya id — immutable resurs), rate limit.

**Glass ichida yangi endpoint YO'Q** — mavjud tenant marshrutlari ishlatiladi,
cheklovlar token, GUC va RLS orqali qo'yiladi.

### 9.1 Himoya matritsasi

| Endpoint guruhi | Himoya |
|---|---|
| `/platform/*` | `require_super_admin` (404) + IP allowlist + `scp='platform'` + glass tokeni rad etiladi + audit |
| Glass yaratish (`write`) | + TOTP + ikkinchi SA (bo'lsa) + `glass.write_enabled` |
| Glass yaratish (`read`) | + TOTP |
| Qaytarib bo'lmaydigan amallar (suspend, plan, refund, owner) | + TOTP + majburiy sabab |
| CMS publish/rollback | + TOTP + izoh + debounce |
| Glass tokeni bilan tenant marshrutlari | `read` → `SET TRANSACTION READ ONLY`; qamrov `X-Club-Id` vs `glass_sessions.club_id`; Redis tiriklik; RLS |
| `/public/landing-content` | Ochiq; faqat published yoki Bearer preview tokeni; rate limit |
| `/me/security/*` | RLS (`glass_sessions_tenant_read`, `audit_log_read`) |

Yozish amallari `Idempotency-Key` qabul qiladi.

---

## 10. Frontend ekranlari

Hammasi `apps/admin` ichida — yangi app yaratilmaydi (`docs/01-architecture.md`
§4: DS, shell, jadval komponentlari tayyor). Lekin **alohida shell**:
`PlatformApp`.

### 10.1 Marshrutlar

`apps/admin/src/routes.ts` dagi `SCREEN_PATH` ga qo'shiladi:

```
pOverview  /platform            pOrgs   /platform/orgs      pOrg   /platform/orgs/:id
pStats     /platform/stats      pAudit  /platform/audit
pCms       /platform/cms        pSettings /platform/settings
```

`screenOf()` hozir **aniq moslik** bilan ishlaydi (`PATH_SCREEN` — Map).
`/platform/orgs/:id` va `/platform/glass/:orgId` uchun prefiks moslashtirish
qo'shiladi (~5 qator).

`ScreenId`, `NavItem`, `NAV_*`, `TITLES` hozir `apps/admin/src/mock/data.ts`
da, u esa "prototip mock ma'lumoti" deb belgilangan. Ular yangi
`apps/admin/src/nav.ts` ga ko'chadi, `mock/data.ts` re-export qiladi (mavjud
importlar sinmaydi).

### 10.2 Rol bo'yicha ajratish

`app.tsx:64-65` dagi mavjud seam (`// Super admin hozircha klub admini
menyusini ko'radi; platforma paneli — Faza 7`) aynan shu bilan yopiladi:

```
glass faol            → clubNavFor(glass.role)   + GlassBanner
session.isSuperAdmin  → NAV_PLATFORM
role !== 'STAFF'      → NAV_ADMIN
aks holda             → NAV_STAFF
```

Mavjud route guard (`items.some(...)` va URL to'g'rilash) o'zgarishsiz ishlaydi:
oddiy klub admini `/platform/orgs` ga kirsa `/dashboard` ga qaytariladi va
"ruxsat yo'q" ekrani ko'rsatilmaydi — panel borligi bilinmasin (API baribir
404 beradi).

### 10.3 Sessiya qatlami

`store/session.ts` ga `mode: 'club' | 'platform' | 'glass'` va
`glass: {sid, orgName, clubName, role, mode, expiresAt} | null`.

Ikki saqlash kaliti:

| Kalit | Joy | Sabab |
|---|---|---|
| `playbron.session` | `localStorage` | Platforma/klub sessiyasi — tegilmaydi |
| `playbron.glass` | `sessionStorage` | Yangi tab hech qachon glass'da ochilmaydi; tab yopilsa glass o'zi tugaydi |

Glass mijozi `refresh` yo'lisiz (§6.8). `packages/api-client` ga bitta additiv
o'zgarish: ixtiyoriy `refresh?: (() => Promise<Session|null>) | null` va
`Session.refreshToken` ni ixtiyoriy qilish.

**Glass'ga kirish va chiqishda `queryClient.clear()`.** TanStack Query keshidagi
platforma ma'lumoti tenant ekranida (yoki aksincha) ko'rinib qolishi — RLS
umuman ushlamaydigan, sof mijoz tomonidagi cross-tenant oqish.

### 10.4 Ekranlar

`apps/admin/src/screens/platform/`:
`overview.tsx`, `orgs.tsx`, `org-detail.tsx`, `stats.tsx`, `audit.tsx`,
`glass.tsx` (so'rov modali + tarix), `cms.tsx` (ikki tilli muharrir, diff,
preview/publish, nashr holati), `settings.tsx`.
Shell komponenti: `apps/admin/src/components/glass-bar.tsx`.
Klub tomonida: `screens/admin/settings.tsx` ga "Platforma kirishlari" bo'limi.

**Yangi vizual element kiritilmaydi:** `EntityTable`, `StatTile`, `Panel`,
`Tabs`, `StatusLine`, `Tag`, `ProgressMeter`, `ActivityBars`, `Countdown`,
`EmptyState`, `FieldLadder` — hammasi mavjud. Yangi DS komponentlari faqat
`GlassBanner`, `ReasonDialog` (sabab + TOTP), `TotpField`, `DiffView`.
Rang/spacing faqat tokenlar orqali; `packages/ui/src/tokens/**` tegilmaydi.

**i18n:** barcha yangi kalitlar `apps/admin/src/i18n.ts` da uz/ru/en bilan.
Matn literali yo'q, `any` yo'q; API javoblari uchun `packages/types` da zod
sxemalari.

---

## 11. Migratsiya rejasi

`0005_two_worlds_auth` slotini `docs/05-auth-redesign.md` egallagan. Shuning
uchun:

### `0006_platform_glass` (revises `0005_two_worlds_auth`)

1. **Oldindan tekshiruv (fail-fast):** `playbron_platform` mavjudmi va
   `rolbypassrls` bormi; `app_club_role()` egasi to'g'rimi. Yo'q bo'lsa
   migratsiya `RAISE EXCEPTION` bilan to'xtaydi — P0-1/P0-4 hal qilinmagan
   holda glass yoqilmaydi.
2. GUC funksiyalari: `app_platform()`, `app_glass_id()`, `app_glass_club_id()`,
   `app_glass_mode()`, `app_actor_user_id()`.
3. `glass_sessions` + RLS + policy + grant + unikal indeks + `BEFORE UPDATE`
   trigger.
4. `super_admin_secrets` (TOTP) + `verify_totp()` (`SECURITY DEFINER`, egasi
   `playbron_platform`, grant yo'q) + `super_admins` ga `display_handle`,
   `disabled_at`.
5. `audit_log`: `actor_kind`, `glass_session_id`, `club_id`, `prev_hmac`,
   `row_hmac`, `chain_seq`, `key_id` + indekslar.
   `audit_seal_key`, `audit_anchors`. `audit_log_seal` va
   `audit_log_no_truncate` trigger'lari.
6. Policy qayta yozilishi: `app_club_role()`, `audit_log_insert`,
   `audit_log_read`, `organizations_read`, `memberships_write`,
   `club_payment_credentials_owner`, `organizations_platform`.
7. `platform_read` policy'lari.
8. `platform_settings`, `platform_daily_stats`, `platform_alert_state`.
9. `plans` qulflanishi (+ `test_rls_hardening` dagi `exempt` tozalanishi).
10. **Grant tuzatishlari:** `REVOKE UPDATE ON audit_log FROM playbron_platform`,
    `REVOKE SELECT ON club_payment_credentials FROM playbron_platform`,
    `REVOKE UPDATE (owner_user_id) ON organizations FROM playbron_app`,
    `REVOKE SELECT (ip, user_agent) ON audit_log FROM playbron_app`,
    `users` PII ustunlari platforma roldan.
11. `organizations.glass_write_allowed boolean DEFAULT true`.
12. Har bir yangi jadval uchun **aniq** GRANT va sequence granti.

### `0007_landing_cms` (revises `0006_platform_glass`)

`landing_versions` + RLS + policy + grant + `landing_one_published` indeksi +
`published` immutability trigger'i. Boshlang'ich versiya `0`: repodagi
`uz.ts`/`ru.ts` ning joriy mazmuni `published` sifatida yoziladi — nashr
tarixi bo'sh boshlanmaydi va birinchi rollback nishoni bo'ladi.

`downgrade()` — ikkalasida ham `NotImplementedError`. Migratsiyalar faqat
oldinga.

---

## 12. Testlar

### 12.1 Poydevor (bosqich 0)

| Test | Nima tasdiqlaydi |
|---|---|
| `test_db_role_is_not_owner` | Prod konfiguratsiyasida ilova ega roli bilan ulanmaydi (P0-1) |
| `test_platform_read_crosses_tenants` | Ikki tashkilot, platforma sessiyasida ikkalasi ham ko'rinadi. Hozir `platform_scope()` xato bermaydi, **bo'sh natija** qaytaradi va buni hech narsa ushlamaydi |
| `test_platform_cannot_write_club_data` | Platforma sessiyasidan `clubs`/`bookings` ga yozish rad etiladi |
| `test_super_admin_token_has_no_role_bypass` | `sa=true` token bilan `require_admin` ostidagi marshrutga a'zoliksiz so'rov 403 (P0-2) |
| `test_security_definer_functions_owned_by_platform` | `pg_proc` bo'yicha barcha `SECURITY DEFINER` funksiyalarining egasi (P0-4) |

### 12.2 Glass — xavfsizlik

| Test | Nima tasdiqlaydi |
|---|---|
| `test_glass_cannot_write_membership` | Glass write sessiyasidan `role='OWNER'` va `role='ADMIN'` a'zolik INSERT'i **ikkalasi ham** rad etiladi; sessiyadan keyin `load_memberships` da yangi qator yo'q |
| `test_glass_cannot_read_payment_credentials` | Ikkala rejimda ham 0 qator |
| `test_glass_cannot_open_platform_routes` | Har bir `/platform/*` marshruti glass tokeni bilan 404 |
| `test_glass_cannot_touch_own_session` | `UPDATE glass_sessions` — `insufficient_privilege` yoki 0 qator |
| `test_glass_sees_only_target_org` | SA B-tashkilot egasi bo'lsin, A da glass ochsin: `organizations` = 1 qator, `audit_log WHERE org_id <> A` = 0 |
| `test_glass_scope_bound_to_server` | `X-Club-Id` ni boshqa klubga almashtirish → `403 GLASS_SCOPE` |
| `test_glass_read_only_blocks_write` | `25006` → `403 GLASS_READ_ONLY` |
| `test_glass_read_is_audited` | Read rejimida ekran ochilgach `audit_log` da `glass.view` bor va uning `actor_user_id` — SA, `org_id` — nishon |
| `test_glass_revoked_immediately` | `DEL glass:{sid}` dan keyingi so'rov 401; klient store'ida `sa:true` token **paydo bo'lmaydi** |
| `test_glass_token_not_accepted_by_refresh` | Glass tokeni `/auth/refresh` ga → 400 |
| `test_glass_guc_survives_savepoint` | `begin_nested()` ochib qaytargandan keyin `app_org_id()`, `app_glass_id()` saqlanadi |
| `test_read_only_does_not_leak_to_pool` | Read glass'dan keyin o'sha ulanish oddiy sessiyada yoza oladi |
| `test_glass_one_active_session` | Ikkinchi sessiya ochilmaydi |

### 12.3 Audit

| Test | Nima tasdiqlaydi |
|---|---|
| `test_audit_append_only_for_platform_role` | `UPDATE`/`DELETE`/`TRUNCATE` audit_log — rad etiladi |
| `test_audit_actor_cannot_be_forged` | App roldan `action='glass.*'` yoki begona `org_id` bilan INSERT rad etiladi; `at` trigger tomonidan qayta yoziladi |
| `test_audit_chain_detects_edit_and_delete` | Qatorni tahrirlash → HMAC nomuvofiqligi; qatorni o'chirish → `chain_seq` bo'shlig'i va lang'ar nomuvofiqligi |
| `test_owner_sees_glass_audit` | Tashkilot egasi sessiyasida `glass.*` qatorlari ko'rinadi (`org_id` to'ldirilgan) |
| `test_staff_cannot_read_other_club_audit` | Toraytirilgan `audit_log_read` |
| `test_audit_has_no_raw_pii` | `before`/`after` da `\+998\d{9}` naqshi yo'q |
| `test_platform_action_writes_audit` | `suspend` chaqirilgach aynan bitta `platform.org.suspend` qatori |

### 12.4 CMS va landing

| Test | Nima tasdiqlaydi |
|---|---|
| `test_cms_rejects_html` | `<`/`>` bo'lgan matn 422 |
| `test_cms_url_scheme_allowlist` | `javascript:`, `data:`, begona host — 422 |
| `test_no_raw_jsonstringify_in_set_html` | `grep` qo'riqchisi (CI) |
| `test_jsonld_escaping` | `</script>` bo'lgan matn chiqishda `<` bo'lib chiqadi |
| `test_publish_requires_both_languages` | Yetishmagan kalit → 422 + ro'yxat |
| `test_rollback_revalidates` | Eski sxemadagi versiyaga rollback bloklanadi |
| `test_build_fails_without_api` | API yo'q bo'lsa build qizil, jimgina fallback yo'q |
| `test_landing_no_scripts` | Chiqarilgan HTML'da faqat `ld+json` skriptlari |
| `test_preview_noindex_two_layers` | `robots.txt` va meta robots ikkalasi ham |
| `test_canonical_host_matches_site` | Post-build tekshiruv |
| `test_cms_admin_no_dangerous_html` | `react/no-danger` lint |

### 12.5 Statistika

`test_stats_min_cell_rule` (5 dan kam tashkilot → `suppressed`),
`test_stats_query_is_audited`, `test_search_returns_no_pii`,
`test_rollup_job_runs_without_request_context`,
`test_stats_degrade_when_tables_missing` (`to_regclass(...) IS NULL` →
`{"available": false}`, chunki `bookings`/`bills`/`platform_payments` Faza 3–5
jadvallari).

### 12.6 Mavjud testlarga o'zgartirish

`api/tests/test_rls_hardening.py:280` — `exempt = {"alembic_version"}`
(`plans` chiqadi). `test_every_table_has_rls` yangi jadvallarni avtomatik
qamrab oladi.

---

## 13. Bosqichma-bosqich joriy qilish tartibi

| Bosqich | Mazmun | Tugash mezoni |
|---|---|---|
| **0. Poydevor** | P0-1…P0-4 (§0.1). `render.yaml` da uchta alohida DSN, ilova roli DDL huquqisiz, `deps.py:79-80` o'chirilgan, IP allowlist prod'da majburiy, `app_club_role()` egasi to'g'ri | §12.1 dagi besh test yashil; `/readyz` da rol ma'lumoti |
| **1. Platforma o'qish** | `0006` ning o'qish qismi: `app_platform()`, `platform_read` policy'lari, `platform_scope()` kontekst qo'yishi, `platform_daily_stats`, rollup job. Ekranlar: `/platform`, `/platform/orgs`, `/platform/stats` | Cross-tenant testlar yashil; panel prod'da haqiqiy raqam ko'rsatadi (bo'sh emas) |
| **2. Audit qattiqlashuvi** | HMAC zanjiri, trigger'lar, lang'ar, toraytirilgan policy'lar, grant tuzatishlari, `plans` qulfi, `/platform/audit` | §12.3 yashil; tashqi lang'ar chiqmoqda |
| **3. Boshqaruv va tashkilotlar** | Hodisalar ro'yxati, `platform_alert_state`, tashkilot amallari, TOTP infratuzilmasi | Suspend/resume/plan amallari TOTP + audit bilan ishlaydi |
| **4. Glass — FAQAT O'QISH** | `glass_sessions`, token, GUC, `SET TRANSACTION READ ONLY`, banner, egaga xabar, tenant tomonidagi "Platforma kirishlari" | §12.2 yashil; egaga xabar keladi va u kabinetda ko'radi |
| **5. Landing CMS** | `0007`, muharrir, diff, nashr, rollback, verify, CSP | §12.4 yashil; birinchi nashr va rollback bajarilgan |
| **6. Glass — YOZISH (ixtiyoriy)** | `glass.write_enabled` yoqilishi, ikkinchi SA, egaga yakuniy xulosa, `glass_write_allowed` | Alohida qaror bilan (§14). Sxema tayyor turadi |

Bosqich 4 dan **oldin** bosqich 2 tugagan bo'lishi shart: audit yozuvi
ishonchli bo'lmasa glass'ning butun hisobdorlik modeli qog'ozda qoladi.

**Faza 5 ga bog'liqlik.** `subscriptions`, `platform_payments`,
`booking_payments`, `bills` hali yo'q. Bosqich 1 va 3 `organizations.plan_code`
bilan ishlaydi, statistika bloklari `to_regclass(...) IS NULL` bo'lsa
`{"available": false}` qaytaradi va UI `EmptyState` ko'rsatadi — panel bugun
yoziladi, jadvallar kelganda o'zi to'ladi.

---

## Ilova A — topilmalarning yopilish jadvali

`critical` va `high` topilmalarning har biri. "Qaysi chora qaysi hujumni
yopadi" — chapdan o'ngga o'qiladi.

### Critical

| # | Hujum | Yopuvchi chora | Bo'lim | Qatlam |
|---|---|---|---|---|
| C1 | Glass write sessiyasidan `memberships` ga o'ziga `role='OWNER'`/`'ADMIN'` yozib, sessiyadan omon qoladigan backdoor; keyingi kirishda `app_club_role()` haqiqiy OWNER beradi va merchant kalitlari ochiladi | `memberships_write` ga `AND app_glass_id() = 0`, ustiga `WITH CHECK role <> 'OWNER' AND user_id <> app_user_id()` | §2.10, §6.5 | DB |
| C2 | `app_is_super_admin()` shaxsga bog'langani uchun platforma policy'lari glass ichida va SA ning oddiy tenant sessiyasida ham TRUE — cross-tenant o'qish/yozish, `owner_user_id` ni o'ziga ko'chirish, kill switch'ni o'chirish | Huquq qamrovga bog'lanadi: `app_platform()` faqat `platform_scope()` da; `super_admins` ga tayanadigan policy yozilmaydi; `app.is_super_admin` GUC'i olib tashlanadi; `REVOKE UPDATE (owner_user_id)` | §0(2), §2.1, §2.10 | DB |
| C3 | Glass o'z `glass_sessions` qatorini UPDATE qilib muddatni cheksiz uzaytiradi, `mode`/`reason`/`org_id` ni retroaktiv qayta yozadi (ega ko'radigan shaffoflik yozuvi soxtalashadi), `ended_at` ni NULL ga qaytaradi | App roliga `glass_sessions` ga yozish granti **umuman yo'q**; `BEFORE UPDATE` trigger o'zgarmas ustunlarni qulflaydi; `ended_at IS NOT NULL` qayta ochilmaydi | §2.3, §6.5 | DB |
| C4 | Ilova baza egasi roli bilan ulanadi → `TRUNCATE audit_log`, `DROP POLICY`, `DISABLE RLS`, o'ziga qayta GRANT, `audit_seal_key` ni o'qish. Audit append-only emas | Bosqich 0 (P0-1): rollar ajratmasi haqiqiy bo'lsin, ilova DDL huquqisiz; `0006` fail-fast tekshiruvi; `BEFORE TRUNCATE` trigger; `/readyz` da rol ma'lumoti; tashqi lang'ar | §0.1, §2.4, §2.6, §11 | Infra + DB |
| C5 | `Faq.astro` va `Base.astro` dagi `set:html={JSON.stringify(...)}` orqali CMS matnidan `</script>` bilan chiqib saqlangan XSS | **Repoda allaqachon yopilgan** — `apps/landing/src/lib/jsonld.ts`. CMS uni buzmasligi uchun CI grep qo'riqchisi + CSP `script-src 'none'` | §7.7 | Chiqishda kodlash + CSP |

### High

| # | Hujum | Yopuvchi chora | Bo'lim |
|---|---|---|---|
| H1 | Glass klienti 401 da avtomatik `/auth/refresh` chaqirib o'ziga `sa=true` to'liq platforma tokenini yozadi va bekor qilingan sessiyadan keyin so'rovni qayta yuboradi | Glass klientida `refresh` yo'li o'chiriladi; `Session.refreshToken` ixtiyoriy; server glass tokenini `/auth/refresh` da 400 bilan rad etadi | §6.8, §10.3 |
| H2 | Telegram akkaunti egallansa (SIM-swap) glass'ga to'siqsiz kirish; prod'da IP allowlist bo'sh; SA telegram id repoda ochiq | Telegramdan **mustaqil** TOTP; prod'da bo'sh allowlist bilan ishga tushmaslik; `SUPER_ADMIN_TELEGRAM_IDS` → `sync: false` | §0.1 (P0-3), §6.4 |
| H3 | `SET TRANSACTION READ ONLY` noto'g'ri joyda → `25001`; "tuzatish" uchun `SET SESSION CHARACTERISTICS` qo'yilsa read-only holat pool orqali begona tenant so'roviga sizadi | Tartib qat'iy: `BEGIN` dan keyingi birinchi operator, `_apply_context()` dan oldin; sessiya darajasidagi variantlar taqiqlanadi; regression test | §6.3, §12.2 |
| H4 | GUC'ga to'liq ishonish: eskirgan `RequestContext` bilan yangi tranzaksiya ochadigan har qanday yo'l (job, WebSocket, ichki chaqiruv) o'lgan glass huquqini qayta beradi | `app_club_role()` `glass_sessions` dagi tirik qatorni DB ichida qayta tasdiqlaydi; barcha DB kirishi faqat `session_scope()`/`platform_scope()`/`system_scope()` orqali | §2.2, §6.3 |
| H5 | `SECURITY DEFINER` FORCE RLS ni chetlab o'tmaydi → glass rol funksiyasi va muhr trigger'i prod'da jimgina 0 qator ko'radi | Har bir `SECURITY DEFINER` funksiyaga `ALTER FUNCTION … OWNER TO playbron_platform`; `0006` fail-fast tekshiruvi; superuser bo'lmagan rol bilan integratsiya testi | §0.1 (P0-4), §11, §12.1 |
| H6 | `app.user_id` glass'da SA bo'lib qolgani uchun OR-shaklidagi policy'lar (`audit_log_read`, `organizations_read`) SA ning boshqa tashkilotlaridagi qatorlarni ochadi | Har bir o'z-o'ziga havola shoxiga `AND app_glass_id() = 0`. Qoida: glass GUC'i faqat toraytiradi | §2.4, §6.3 |
| H7 | `platform_scope()` ning yagona qulfi — tekshirilmaydigan `sa` klaymi; `encode_access` da TTL tanlash `sa` bayrog'iga bog'langani uchun glass tokeniga `sa=true` qo'yish tabiiy xato | `ctx.glass is not None` → `is_super_admin=False` invarianti; `platform_scope()` glass kontekstida `PermissionError`; TTL `ttl_sec` bilan aniq beriladi; `scp` klaymi qat'iy tekshiriladi | §1.3, §6.2 |
| H8 | `audit_log_insert` faqat aktorni bog'laydi — begona `org_id`, `action='glass.*'`, orqaga surilgan `at` bilan soxta yozuv kiritiladi va HMAC uni "yaxlit" deb muhrlaydi | Policy `org_id = app_org_id()` va `glass.*`/`platform.*`/`system.*` prefikslarini rad etadi; trigger `actor_kind`, `glass_session_id`, `at` ni GUC'dan **o'zi** hisoblaydi | §2.4 |
| H9 | Kunlik lang'ar 24 soatlik o'chirish oynasi qoldiradi; per-qator HMAC zanjir emas, o'chirishni ushlamaydi | `prev_hmac` bilan haqiqiy hash-chain; uzluksiz `chain_seq`; lang'ar har 5 daqiqada + har glass sessiya boshi/oxirida; mustaqil ishchi | §2.4, §2.6 |
| H10 | `platform_scope()` kontekst qo'ymagani uchun platforma amallarining audit yozuvi RLS'ga urilib rad etiladi — amal bajariladi, iz qolmaydi | `platform_scope()` `app.actor_user_id`/`app.actor_kind` qo'yadi; `audit_log_platform_insert` policy'si; audit xatosi yutilmaydi | §5.2 |
| H11 | Faqat-o'qish glass'da audit INSERT `25006` bilan yiqilib jimgina yo'qoladi | Audit alohida sessiyada, `_apply_context()` majburiy; `CHECK (actor_kind <> 'glass' OR org_id IS NOT NULL)`; `test_glass_read_is_audited` | §6.6 |
| H12 | Filtrlangan agregatlar va differencing orqali bitta tashkilotni aniqlash — glass'siz, sababsiz, xabarsiz | Minimal hujayra qoidasi (5), filtr kombinatsiyalari cheklovi, nomlangan `top-N` ajratilishi, har bir stats so'rovining auditi va chastota cheklovi | §5.4 |
| H13 | Telefon/telegram bo'yicha cross-tenant qidiruv — "bu raqam mijozmi va qayerda" oracle'i; audit'ning o'zi qidirilgan raqamlar omboriga aylanadi | Qidiruv HMAC xeshi bo'yicha, javobda PII yo'q; audit'ga xesh yoziladi; `users` PII ustunlari platforma roldan REVOKE; chastota cheklovi | §4.1, §2.11 |
| H14 | CMS'dagi `dir` maydoni orqali canonical va brend havolasi begona domenga (yoki `/ru/` → `/`) — deindeksatsiya va trafik o'g'irlash | `dir`/`htmlLang`/`localeTag` CMS hujjatidan chiqariladi, kodda `LOCALE_ROUTES` da qoladi; post-build canonical host tekshiruvi | §7.2, §7.8 |
| H15 | CMS matni admin konsolida `dangerouslySetInnerHTML` bilan chizilsa saqlangan XSS platforma tokenini `localStorage` dan o'g'irlaydi va glass ochadi | Faqat matn tugunlari; `react/no-danger: error`; `apps/admin` ga `script-src 'self'` CSP; nashr shart emasligi hisobga olinadi (draft ham render bo'ladi) | §7.7 |
| H16 | Har saqlashda preview deploy hook → Render build kvotasi (akkaunt bo'ylab umumiy) tugaydi va API hotfix deploy'i ham chiqmaydi; hook URL xato matni orqali bazaga tushadi | Hook faqat alohida tugmada; Redis debounce 120/300 s + kunlik cap; bir vaqtda bitta `building`; hook URL faqat env'da va hech qachon log/DB/xato matnida emas | §7.6 |
| H17 | Build repoga jimgina fallback qilib nashrni va rollback'ni bekor qiladi; xato haqida xabar beruvchi kanal yiqilgan kanalning o'zi | Fallback yo'q — retry (~60 s) va `process.exit(1)`; nashrdan oldin `/healthz` bilan API uyg'otiladi; `pb-content-version` meta va API tomonidan yuritiladigan `verify` | §7.4, §7.6 |
| H18 | Rollback validatsiyasiz va build "joriy nashr" ko'rsatkichini oladi → poyga va bo'sh bo'limli sahifa | Build versiya **id** bo'yicha oladi (`LANDING_CONTENT_VERSION`); rollback = qayta validatsiya + yangi versiya; `ContentSchema.parse().strict()` | §7.4, §7.6, §7.3 |
| H19 | `plans` da RLS yo'q va app roli to'liq DML — CMS narx tahriri latent teshikni jonli nishonga aylantiradi; `limits` qayta yozilsa entitlement bekor bo'ladi | `plans` qulflanadi (RLS + policy + REVOKE), `exempt` dan chiqariladi | §2.9 |
| H20 | Landing'da CSP yo'q — har qanday shablon xatosi to'siqsiz ekspluatatsiya qilinadi | `render.yaml` da `script-src 'none'`, `connect-src 'none'`, `frame-ancestors 'none'` | §7.7 |
| H21 | `deps.py:79` — `sa=true` token har qanday rol tekshiruvidan o'tadi: auditsiz, muddatsiz, sababsiz "yashirin glass" | Ikki qator o'chiriladi (P0-2); glass'da rollar `mbr`/`gl` dan sintez qilinadi va `require_role` normal ishlaydi | §0.1, §12.1 |

### Medium — qisqacha

| Hujum | Chora | Bo'lim |
|---|---|---|
| Tab yopilgach eski glass tokeni `exp` gacha ishlaydi | Token TTL 90 s; `sendBeacon` bilan `end`; `jti` qora ro'yxati; `expires_at` so'rov yo'lida | §6.4, §6.8 |
| Glass audit'i `org_id=0` bilan yozilsa ega hech narsa ko'rmaydi | Audit sessiyasida `_apply_context()` majburiy + DB CHECK | §6.6 |
| `SAVEPOINT` qaytarilishida GUC'lar yo'qoladi → `clubs_read` ommaviy shoxi | GUC'lar BEGIN dan keyingi birinchi blokda; regression test | §6.3, §12.2 |
| Glass qamrovini mijozning `X-Club-Id` si hal qiladi | Server tomonidagi `glass_sessions.club_id` bilan solishtirish → `403 GLASS_SCOPE`; token bitta klub | §6.3 |
| `glass_sessions.ip`/`ua` tenantga ochiq → IP allowlist qiymati oshkor | Tenantga `SECURITY DEFINER` funksiya orqali tanlangan maydonlar | §6.6 |
| `audit_log_read` org bo'ylab → boshqa klublarning diff'lari | Klub darajasiga toraytirilgan policy | §2.4 |
| Rollup job kontekstsiz yiqiladi, panel eskirgan ma'lumotni jimgina ko'rsatadi | `system_scope()`; "oxirgi yangilanish" belgisi; 26 soatdan eski bo'lsa `warn` | §3.1, §5.3 |
| Preview statik sayt — auth texnik jihatdan imkonsiz; noindex + prod canonical ziddiyati | v1 diff, v2 imzolangan URL yoki taxmin qilinmaydigan nom; ikki qatlam noindex; self-canonical | §7.6 |
| Komponent ↔ sxema drifti → jimgina bo'sh bo'lim | `strict().parse()`, `schema_version` migratsiyasi, CI tip tekshiruvi | §7.3 |
| TanStack Query keshi orqali cross-tenant oqish | `queryClient.clear()` | §10.3 |

---

## 14. Hal qilinmagan savollar

1. **Glass yozish rejimi umuman kerakmi?** Dizayn birinchi versiyada uni
   yubormaydi. Sxema tayyor. Haqiqiy talab paydo bo'lganda yoqiladimi yoki
   butunlay tashlab yuboriladimi — biznes qarori.
2. **Ikkinchi super admin bormi?** "To'rt ko'z" qoidasi (yozish uchun ikkinchi
   SA tasdig'i) faqat SA soni ≥ 2 bo'lsa ishlaydi. Yagona SA holatida
   muqobillar: (a) egadan aniq ruxsat, (b) 10 daqiqalik kechikish + xabar,
   (c) yozish rejimini umuman o'chirish. Qaysi biri?
3. **`super_admins` ga rol darajasi kerakmi?** Kelajakda qo'llab-quvvatlash
   xodimi paydo bo'lsa: `full` / `support` — support faqat glass'ga kira olsin,
   to'lov va tarifga tegmasin.
4. **"Jim rejim" (egaga xabarsiz kirish) kerakmi?** Firibgarlik tekshiruvi
   (masalan klub soxta bron bilan tarifni aldayotgani) uchun kerak bo'lishi
   mumkin. Bu checkbox emas, alohida va huquqiy ko'rib chiqilgan imkoniyat
   bo'lishi kerak.
5. **Tashkilot glass'ni butunlay rad eta oladimi** (nafaqat yozishni)?
   Faqat-o'qish glass'siz qo'llab-quvvatlash amalda ishlamaydi; lekin ba'zi
   mijozlar buni shart qilishi mumkin. Narx/shartnoma savoli.
6. **Foydalanish shartlarida impersonation bandi bormi?** Texnik nazorat
   huquqiy himoya bermaydi. O'zbekiston shaxsiy ma'lumotlar qonuni (ZRU-547)
   bo'yicha tekshirilishi kerak. Landing'ga "Maxfiylik" va "Shartlar"
   sahifalari qo'shiladimi (hozir ular yo'q)?
7. **Mijoz PII si glass'da qanchalik ko'rinadi?** Dizayn maskalashni tanlaydi.
   Lekin "mijoz Jasur bilan bog'liq muammo" ni hal qilish uchun to'liq raqam
   kerak bo'lishi mumkin. Taklif: `reason_code='owner_request'` bo'lsa to'liq,
   aks holda maskalangan — bu qo'shimcha murakkablik, biznes qaroriga muhtoj.
8. **TOTP tiklash tartibi.** SA telefoni yo'qolsa nima bo'ladi? Zaxira kodlari
   (bir martalik, xeshlangan) kerakmi va ular qayerda beriladi?
9. **Audit va glass tarixini saqlash muddati.** Hozir cheksiz (`DELETE` yo'q).
   Partitsiya qachon kerak? Qonun bo'yicha saqlash muddati cheklovi bormi?
   Kelajakda tenant domen hodisalari (bron, kassa) ham `audit_log` ga tushadimi
   yoki platforma audit'i alohida jadval bo'ladimi — bu HMAC zanjiri va hajm
   rejasiga bevosita ta'sir qiladi.
10. **Klublar aylanmasi qanchalik batafsil?** Dizayn agregat + minimal hujayra
    qoidasini taklif qiladi; alohida klubning kunlik tushumi uchun glass va
    sabab kerak. Biznes shu chegara bilan roziligi tasdiqlanishi kerak.
11. **Narx tahriri Faza 5 ga bog'liq.** `subscriptions` da narx snapshot'i
    bo'lmasa, narx ko'tarilishi barcha mavjud mijozning keyingi hisobini
    jimgina oshiradi. Faza 5 loyihasida bu ustun bormi?
12. **Landing CMS'da media kerakmi?** Hozirgi dizayn faqat matn, narx va aloqa.
    Media qo'shilsa — obyekt saqlagich, fayl tipi validatsiyasi, CDN va
    "nol JS" va'dasi bilan mos kelish masalasi ochiladi.
13. **Preview uchun ikkinchi Render sloti bepul rejada joizmi?** Xizmatlar soni
    va build daqiqalari cheklovi. Aks holda v1 diff bilan cheklanadi.
14. **Glass sessiyasi davomida real vaqt kanali (Socket.IO, Faza 4).**
    WebSocket ulanishi ham glass kontekstini olishi va sessiya tugaganda
    **majburan uzilishi** kerak — alohida dizayn talab qiladi.
15. **Bekor qilingan yoki bayroq qo'yilgan sessiya bo'yicha eskalatsiya
    tartibi.** Texnik chora bor, tashkiliy jarayon yo'q.
16. **`platform_daily_stats` scheduler'i.** Render bepul rejada cron xizmati
    yo'q — API ichidagi background job (APScheduler/ARQ) yoki tashqi
    qo'zg'atuvchi. Qaysi biri?
17. **`docs/01-architecture.md` §9 ga tuzatish.** "Har bir platforma so'rovi
    audit'ga (o'qish ham)" bandi glass o'qishlari uchun sessiya + ekran
    darajasiga tushirilmoqda. Hujjatga rasmiy tuzatish kiritiladimi?
