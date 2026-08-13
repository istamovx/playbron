# Handoff: PlayBron — xodim konsoli, xodim Mini App, mijoz Mini App

## Overview

PlayBron — PlayStation o'yin klublari uchun multi-tenant bron SaaS (O'zbekiston bozori).
Bu paket **UI dizayn manbai**: uch yuza to'liq mock-data bilan ishlaydigan prototip sifatida qurilgan.

| Fayl | Yuza | Rol |
| --- | --- | --- |
| `designs/PlayBron Xodim.dc.html` | Desktop konsol (1440+) | STAFF — Live board, Timeline, Buyurtmalar, Kassa, Smena, Qora ro'yxat |
| `designs/PlayBron Xodim Mobil.dc.html` | Telegram Mini App (420×880) | STAFF — o'sha rolning telefon varianti |
| `designs/PlayBron Mijoz.dc.html` | Telegram Mini App (420×880) | CUSTOMER — klub tanlash → bron → deposit → QR → aktiv seans → bronlarim → balans |

Hali qurilmagan: **admin (klub egasi) paneli**, **landing sayt**, **superadmin**.

## About the design files

Paketdagi HTML fayllar — **dizayn referensi**, production kod emas. Ular kutilgan ko'rinish va
xatti-harakatni ko'rsatuvchi prototiplar: React class komponenti + inline stillar + mock massivlar.
Vazifa — bu ekranlarni `BUILD-BRIEF.md` da belgilangan real stackda (React 19 + Vite + Tailwind v4 +
TanStack Query) qayta qurish, HTML'ni ko'chirib olmaslik.

Ochish: `designs/` papkasini brauzerda oching (`_ds/` yonida turishi shart — dizayn tizimi
stylesheet'lari va bundle shu yerdan yuklanadi). Barcha holat almashinuvi bosish orqali ishlaydi.

## Fidelity

**High-fidelity.** Rang, tipografiya, spacing, holatlar va oraliq holatlar (overtime, no-show,
chek tasdiqlash, kamomad) yakuniy. Piksel darajasida takrorlash kutiladi — lekin qiymatlar
hardcode qilinmaydi, hammasi dizayn tizimi tokenlari orqali (pastda).

## Design system

Dizayn **SystemX** (`SentinelSOCDesignSystem_d3364b`) ustiga qurilgan — qorong'i, "instrument-grade"
operatsion konsol tili. Manba `designs/_ds/systemx-.../` ichida:

- `tokens/*.css` — colors, typography, spacing, effects, breakpoints, base, light theme
- `styles.css` — barcha tokenlarni `@import` qiladigan yagona fayl
- `_ds_bundle.js` — React komponentlar, `window.SentinelSOCDesignSystem_d3364b` global
- `guidelines/`, `components/*/*.prompt.md` + `.d.ts` — har komponentning props kontrakti va qo'llanmasi

Ishlatilgan komponentlar: `Panel`, `Button`, `Chip`, `Tag`, `Icon`, `SegmentedControl`, `StatusLine`,
`SidebarNav`, `PageHeader`, `ServerClock`, `Metric`/`MetricCell`, `FieldRow`, `EntityTable`,
`ActionItemCard`, `ListCard`, `ProgressMeter`, `CapacityBar`, `AreaTrend`, `RankedBars`, `HeatMatrix`,
`Grid`, `ConsoleLayout`, `useBreakpoint`.

**Muhim:** brief "Blue design system" deydi — bu eskirgan. Yakuniy vizual til SystemX.
`packages/ui` ga ko'chiriladigan tokenlar shu papkadan olinadi.

### Tokenlar (to'liq ro'yxat `tokens/` ichida)

Ranglar: `--void-0 #07070A` (fon), `--void-2` (chassis), `--surface-panel`, `--surface-card`,
`--surface-field`, `--surface-inset`, `--surface-hover`, `--surface-selected` (violet 18% tint),
`--line-1` (8% white), `--line-2`, `--line-3`; interaktiv `--primary-100 #5700FF`;
matn `--text-title`, `--text-body`, `--text-muted`, `--text-label`, `--text-dim`, `--text-on-accent`;
ma'lumot ranglari `--red-100 #FF505D`, `--yellow-100 #EDB07E`, `--secondary-500 #32E197`,
`--violet-200 #B661DE`, `--purple-100`.

Tipografiya: `--font-display` Chakra Petch, `--font-mono` JetBrains Mono.
`--type-title`, `--type-section`, `--type-body`, `--type-body-sm`, `--type-control`,
`--type-label` (+ `--ls-label`), `--type-data`, `--type-data-xs`, `--type-metric` (38px/500).

Spacing (responsive, breakpoint bo'yicha qayta aniqlanadi): `--gutter`, `--gap-panel`, `--panel-pad`,
`--card-pad` → web 24px, ≤905px 16px; `--gap-block` 16px, `--gap-tight` 8px;
`--field-h` 28px (touch: 44px), `--control-h` 26px (touch: 40px).

Geometriya: radius 2px (`--r-1`), chassis 18px; `--clip-tr` — 14px 45° yuqori-o'ng chamfer;
soya deyarli yo'q (`--shadow-pop` faqat popover), chuqurlik hairline orqali.

**Qat'iy qoidalar:** rang faqat ma'lumotda (holat, risk, delta) — dekoratsiyada yo'q;
har sohada bitta primary violet amal; emoji yo'q; label hech qachon mono emas, qiymat hech qachon mono emas emas.

---

## 1. Xodim konsoli — `PlayBron Xodim.dc.html`

Shell: chapda `SidebarNav` (expand rejimi, 208px, collapse toggle), o'ngda ish maydoni.
≤905px da yon panel drawer'ga aylanadi, headerda hamburger paydo bo'ladi (DS'ning o'z bottom-bar
rejimi o'chirilgan — ikki navigatsiya bir vaqtda bo'lmaydi).
Header: `PageHeader` — sahifa nomi ALL CAPS display faceda, ostida meta qatori, o'ngda `ServerClock`
(`KLUB VAQTI` + `HH:MM:SS`) va `UserMenu` (xodim ismi, smena).

Navigatsiya: **Live board · Timeline · Buyurtmalar (badge) · Kassa · Smena · Qora ro'yxat (badge)**.

### 1.1 Live board
- Yuqorida 5 ta `MetricCell`: Band `5/10`, Bo'sh, Rezerv, Ta'mirda, Overtime (qizil).
- Markazda `Panel title="Xonalar"` — `Grid min={260}` ichida xona kartalari.
  Karta: kod + holat yorlig'i (o'ng yuqorida, holat rangida), konsol qatori (`PS5 · 55" · 2 pad`),
  mijoz ismi, `19:30 → 21:30`, o'ngda mono taymer, pastda 3px progress chizig'i.
  Holat ranglari: band `--primary-100`, bo'sh `--line-2`, rezerv `--violet-200`,
  ta'mirda `--yellow-100`, no-show/overtime `--red-100`. No-show kartasi fon `rgba(255,80,93,.06)`.
- O'ngda 352px detal paneli (`Panel brackets`): `FieldRow` ladder — Mijoz, Telefon, Kod (violet mono),
  Turi, Konsol, Vaqt, Tarif, O'yin summasi, Bar, Deposit. Ostida amal tugmalari:
  `Uzaytirish` (primary) · `Buyurtma` · `Hisobni yopish`.
- Tanlangan karta: 18% violet tint + `#5700FF` hairline + 2px violet chap rail.

### 1.2 Timeline
Kunlik gantt: chapda xona ustuni (kod + konsol), o'ngda 10:00–02:00 shkalasi, 1 soat = 1 katak.
Bandlar: band (violet), rezerv (violet outline), tugagan (kulrang), overtime (qizil),
`Kelmadi?` (qizil). Qizil vertikal chiziq — hozirgi vaqt. Legenda tepada, `Kecha / Bugun / Ertaga`
segmentlari bracket ticks bilan. Gorizontal scroll — `ScrollX`.

### 1.3 Buyurtmalar
4 ustunli kanban: **Yangi · Qabul qilindi · Tayyorlanmoqda · Yetkazildi**.
Karta: xona + buyurtma id, pozitsiyalar `× qty` bilan, jami (violet mono), qancha vaqt oldin,
va bitta primary tugma keyingi holatga suradi. Yangi ustun kartalari qizil chap rail bilan.

### 1.4 Kassa (POS)
- Chapda **Ochiq hisoblar** paneli — band xonalar kartalari: kod, mijoz, qolgan vaqt
  (overtime qizil), `TO'LANADI` yorlig'i + summa. Bosilganda o'ngdagi hisob almashadi.
- Katalog: `Ichimliklar / Snack / Ovqat` tabs, pozitsiya kartalari narx va **qoldiq** bilan
  (`48 dona`, `< 8` sariq, `Tugadi` bosilmaydi va xiralashadi). Tepada qulf izohi:
  *"Katalog, narx va kirim faqat admin tomonidan kiritiladi. Siz sotasiz."*
- O'ngda hisob: xona, mijoz, seans, o'ynagan soat, tarif → savat qatorlari `− qty +` stepper bilan →
  O'yin, Bar, Deposit hisobga olindi (yashil `−`), Bonus ball (yashil `−`) → `TO'LANADI` violet bloki.
- To'lov usuli: **Naqd** yoki **O'tkazma** (terminal yo'q). O'tkazmada mijoz Mini App'da klub
  kartasiga o'tkazadi va chek rasmini yuklaydi → kassada chek bloki: fayl nomi, mijoz, summa,
  `StatusLine` (kutilmoqda / tasdiqlandi `PAY-2041` / rad etildi) va `Tasdiqlash / Rad etish`.
  Tasdiqlanmaguncha `Hisobni yopish` disabled.
- Yopilgach: `Hisob yopildi · CS-2049` + yashil `StatusLine`, to'liq chek `FieldRow` ladderda
  (xona, mijoz, o'ynagan vaqt, o'yin, bar, to'landi, usul, yopdi + vaqt), ostida mijozga ketgan
  Telegram xabari matni. `Yangi hisob` keyingi mijozga o'tadi.
- **Yopish seansni tugatadi:** xona `FREE` bo'ladi, ochiq hisoblardan chiqadi, Live board
  hisoblagichlari kamayadi, Timeline'dagi bandi tugagan seans (kulrang) ga aylanadi.

### 1.5 Smena
Smena ma'lumoti (kechki, 16:00 dan, kassa boshi 200 000, 14 yopilgan hisob), 4 ta metrik plita —
Naqd 980 000, O'tkazma 640 000, Onlayn deposit 280 000, Farq −40 000;
**Tovar reestri** jadvali: mahsulot · smena boshi · sotildi · bo'lishi kerak · sanaldi (`− +` stepper) ·
farq (kam qizil, ortiq sariq), pastda **kamomad so'mda** avtomatik.
`Smenani yopish` primary tugma boshqa tugmalardan 16px bo'shliq bilan ajralgan.

### 1.6 Qora ro'yxat
Bloklanganlar jadvali (mijoz, no-show soni, sabab, sana, `Blokdan olish`), **Kuzatuvda** bo'limi
(1–2 no-show → keyingi bronda deposit 100%), 5 bandli qoida ro'yxati, oylik statistika
(9 no-show, 17.5 yo'qolgan soat, 214 000 ushlab qolingan deposit).
No-show oqimi: bron boshlanib 20 daqiqa o'tsa Live board kartasi `Kelmadi?` ga o'tadi →
o'ng panelda kechikish taymeri + `Oldingi no-show: 2 marta` → `Kelmadi deb belgilash` →
deposit klubda qoladi, xona bo'shaydi, 3-no-show da mijoz avtomatik bloklanadi va ro'yxatga tushadi.

---

## 2. Xodim Mini App — `PlayBron Xodim Mobil.dc.html`

420×880 telefon ramkasi. Telegram grammatikasi: yuqorida BackButton + sarlavha + soat +
QR skaner tugmasi; pastda **MainButton** (sahifaga qarab o'zgaradi); undan pastda 4 tab.
Jadval yo'q — hamma narsa karta va ladder. Barcha nishon ≥44px.

Tablar: **Xonalar · Buyurtma (badge) · Kassa · Smena**.

- **Xonalar** — 2×2 hisoblagich (Band `5/10`, Bo'sh, Rezerv, Overtime), filtr chiplari
  `Hammasi / Band / Bo'sh / Diqqat` (Diqqat = no-show, ta'mirda, 15 daqiqadan kam qolgan),
  so'ng xona kartalari: holat rail (3px chap chegara), mijoz + vaqt, mono taymer, progress.
  MainButton: `QR bilan check-in`.
- **Xona detali** (push) — `StatusLine` + `FieldRow` ladder; `Uzaytirish` paneli:
  xodimga eslatma *"Mijozdan so'rang: hali o'ynaysizmi yoki hisobni yopamizmi?"*,
  30 daq / 1 soat / 1,5 soat / 2 soat variantlari, joriy va yangi tugash vaqti, qo'shimcha summa;
  **keyingi bron bilan to'qnashuv tekshiriladi** — oshsa qizil ogohlantirish va tugma
  `Vaqt yetarli emas` holatiga o'tadi; `Yopamiz` to'g'ridan-to'g'ri hisobga olib boradi.
  Amal tugmalari 2×2: Uzaytirish · Buyurtma · Qo'ng'iroq · Buyurtmalar.
  No-show xonasida: qizil izoh paneli + `Yana 10 daqiqa` / `Qo'ng'iroq`, MainButton
  `Kelmadi deb belgilash`.
- **Check-in** (push) — 190px kamera oynasi violet ramka bilan, 6 katakli kod maydoni
  (aktiv katak violet chegara), 3×4 klaviatura (`C`, `⌫`), 6 raqam kiritilganda
  `Bron topildi` bloki va MainButton `Check-in qilish` yonadi.
- **Buyurtma** — kanban o'rniga `SegmentedControl` holat filtri; har karta bitta primary tugma bilan
  zanjir bo'ylab suradi (`Qabul qilish → Tayyorlash → Yetkazdim`), o'tgach filtr o'sha holatga ko'chadi.
- **Kassa** — ochiq hisoblar kartalari (`TO'LANADI` summa bilan) → hisob ekrani (ladder, savat
  stepperlari, `Bar qo'shish` push ekrani qoldiq bilan, jami, Naqd/O'tkazma, chek tasdiqlash) →
  MainButton `Hisobni yopish` (o'tkazma tasdiqlanmasa `Chek tasdiqlanmagan`, kulrang, inert) →
  chek ekrani + Telegram xabari, MainButton `Yangi hisob`.
- **Smena** — ladder (smena, xodim, kassa boshi, yopilgan hisob), 2×2 pul plitalari,
  tovar reestri (har mahsulot alohida blok, `− +` stepper, farq), kamomad, MainButton `Smenani yopish`.

---

## 3. Mijoz Mini App — `PlayBron Mijoz.dc.html`

420×880. Tablar: **Klublar · Bronlarim · Balans · Profil**. Push ekranlar:
klub sahifasi → slot tanlash → tasdiqlash → QR → aktiv seans → hisob → sharh.

- **Klublar** — sort chiplari (Yaqin / Reyting / Bo'sh joy / Arzon), klub kartalari:
  rasm placeholderi, bo'sh joy yorlig'i, nom, masofa, reyting, narx diapazoni.
- **Klub sahifasi** — rasm galereyasi placeholder, xonalar va narxlar, sharhlar.
- **Slot tanlash** — sana chiplari (14 kun), xona turi segmentlari (Standart / Turnir / VIP),
  davomiylik segmentlari bracket ticks bilan, 30 daqiqali slot gridi (band slot bosilmaydi),
  stansiya kartalari.
- **Tasdiqlash** — narx tafsiloti, deposit hisobi (30%, min 20 000, 1000 ga yaxlitlash),
  bekor qilish siyosati, **no-show ogohlantirishi** (uchinchisidan keyin blok),
  to'lov usuli (Payme / Click / O'tkazma). O'tkazmada klub karta raqami va
  **chek yuklash** oqimi, MainButton `Chekni yuklash`.
- **QR** — 6 xonali kod + QR placeholder, xodimga ko'rsatiladi.
- **Aktiv seans** — qolgan vaqt, bar menyusi (kategoriya chiplari, `+` bilan buyurtma),
  joriy hisob, `Uzaytirishni so'rash`.
- **Bronlarim** — tepada bot xabari (hisob yopildi: xona, o'ynagan vaqt, o'yin va bar summasi,
  to'langan, yig'ilgan bonus, `Sharh qoldirish`), so'ng bronlar tarixi.
- **Balans** — bar krediti (bekor qilingan depozitdan, 30 kun), bonus ballar va tier,
  tranzaksiya tarixi.

---

## Interactions & behavior

- **Motion:** faqat rang va chegara o'tishlari, 90/140/220/400ms, `cubic-bezier(.22,.61,.36,1)`.
  Layout animatsiya qilinmaydi. Bounce/scale yo'q. Press = `translateY(1px)`.
- **Hover:** fon ~4–6% oqartiriladi, chegara `--line-2 → --line-3`, matn `--text-muted → --text-title`.
- **Taymerlar** har sekundda yangilanadi; overtime manfiy vaqtni `+0:14:40` shaklida qizil ko'rsatadi;
  15 daqiqadan kam qolganda sariq.
- **Real-time (Socket.IO):** `station.status_changed`, `booking.created`, `session.started`,
  `session.ending_soon`, `session.overtime`, `order.created`, `order.status_changed`, `shift.closed` —
  Live board, Timeline va Buyurtmalar optimistik yangilanadi, event kelganda sinxronlanadi.
- **Disabled:** `--text-dim` on 2% white, chegara `--line-1`, `not-allowed`. Mini App'da MainButton
  disabled holatda `--surface-inset` foniga o'tadi va matni sababni aytadi.
- **Bo'sh holat:** dashed `--line-2` chegara + bir qatorli faktik matn (`Ochiq hisob yo'q`).

## State (prototipda mock, real appda server manbai)

`screen` + `stack` (Mini App navigatsiyasi), `sel` (tanlangan xona), `filter`, `orderTab`,
`states` (buyurtma holatlari), `carts` (xona → {menu_item_id: qty}), `pay`, `receipt`
(`PENDING|OK|NO`), `closed` (chek), `closedRooms`, `extended` (xona → qo'shilgan daqiqa),
`nsMarked`, `code` (6 xonali kirish), `counted` (reestr sanog'i), `tick` (soat).

Real implementatsiyada: TanStack Query (server holati), Zustand (faqat UI holati),
narx/deposit/refund hisoblari `packages/types` ichidagi sof funksiyalar.

## Copy qoidalari

Til: **uz-Latin** (default), keyin ru/en. Barcha matn i18n resurslarida — komponentda literal yo'q.
Ovoz: asbob, suhbat emas. Panel sarlavhalari Title Case; sahifa nomlari ALL CAPS;
maydon yorliqlari 10px ALL CAPS keng tracking; mashina hodisalari SCREAMING_SNAKE;
sanoq label ichida qavsda (`Buyurtmalar (5)`); tugmalar bir so'z; nuqta yo'q; emoji yo'q.
Pul: mono, 3 xonali guruh bo'sh joy bilan (`182 000`), valyuta caps yorlig'i alohida.
Vaqt: `HH:MM`, davomiylik `1:45:20`, timestamp `YYYY-MM-DD HH:MM:SS`.

## Assets

Rasm yo'q. Klub rasmlari, xona fotolari va street map — dashed placeholder, real material kerak.
Ikonkalar: Material Symbols Rounded FILL=1, faqat DS `Icon` orqali (`designs/_ds/.../components/primitives/Icon.jsx`).
Logotip yo'q — `PLAYBRON` wordmark display faceda.

## Files

```
designs/PlayBron Xodim.dc.html          desktop xodim konsoli
designs/PlayBron Xodim Mobil.dc.html    xodim Mini App
designs/PlayBron Mijoz.dc.html          mijoz Mini App
designs/_ds/systemx-.../                SystemX dizayn tizimi (tokenlar, bundle, komponent qo'llanmalari)
BUILD-BRIEF.md                          to'liq texnik spetsifikatsiya (domen modeli, biznes qoidalari, P0–P9)
PROJECT-RULES.md                        loyiha qat'iy qoidalari (CLAUDE.md sifatida ko'chiriladi)
```

Har bir `.dc.html` faylning tuzilishi: `<x-dc>` ichida template (inline stillar, `<sc-for>` /
`<sc-if>` takrorlash), so'ng `class Component` — barcha mock ma'lumot va holat mantiqi
`renderVals()` da. Real qiymatlarni (tariflar, xona tarkibi, menyu, smena raqamlari) shu
massivlardan oling: `ROOMS`, `MENU`, `STOCK`, `ORDERS`, `NEXT`, `BONUS`.

## Qolgan ish

Dizayn hali qilinmagan yuzalar: **admin (klub egasi) paneli** (KPI dashboard, bronlar, xonalar va
stansiyalar, tariflar va paketlar, menyu, xodimlar, mijozlar, promokodlar, hisobotlar, sozlamalar),
**landing sayt** (Next.js, klublar katalogi, web bron), **superadmin**.
Ular uchun mavjud uch fayldagi grammatikani davom ettiring.
