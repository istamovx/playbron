# D-bosqich — seans hayotiy sikli

<context>
Hozir `bookings` bitta qatorda uch rolni bajaradi: bron (reja), seans
(fakt) va chek. Natijada `stations` ning jonli holati rejadan hisoblanadi —
mijoz kelmagan bo'lsa ham stansiya "band" ko'rinadi.

`CHECKED_IN`, `NO_SHOW`, `COMPLETED` — kodda nol uchrash.
</context>

<task>
## D1. `bookings` holat mashinasi

Mavjud: `PENDING`, `CONFIRMED`, `CANCELLED`.
Qo'shiladi: `CHECKED_IN`, `IN_PROGRESS`, `COMPLETED`, `NO_SHOW`.

- O'tishlar servis qatlamida bitta joyda tekshiriladi; noto'g'ri o'tish
  `409 INVALID_TRANSITION`.
- `bookings_no_overlap` EXCLUDE konstreyni qaysi statuslarni qamrashi
  qayta ko'riladi: `CHECKED_IN` va `IN_PROGRESS` ham band hisoblanadi,
  `NO_SHOW` va `COMPLETED` — yo'q.
- Migratsiya self-testi: `NO_SHOW` bo'lgan slotga yangi bron kirishi
  mumkinligini tekshiradi.

## D2. `bookings.code` — check-in

- `code`: qisqa unikal kod (klub ichida), QR sifatida miniapp'da
  ko'rsatiladi.
- `POST /clubs/{id}/bookings/{id}/check-in` — kod yoki ro'yxatdan.
  `CONFIRMED` → `CHECKED_IN`, `checked_in_at` yoziladi.
- Xodim yo'li: konsolda kod kiritish yoki ro'yxatdan tanlash.

## D3. `duration_minutes`

- `bookings.hours` (butun son) → `duration_minutes`. Ma'lumot ko'chiriladi
  (`hours * 60`), eski ustun o'chiriladi.
- `club_settings.slot_minutes` va `min_booking_minutes` bilan tekshiruv
  serverda.
- `extend` ham minutlarda; `max_booking_minutes` CHECK'i yangilanadi.
- C-bosqichdagi narx funksiyasi allaqachon minutlarda ishlaydi — faqat
  chaqiruv joyi o'zgaradi.

## D4. Haqiqiy vaqt va stansiya holati

- `started_at`, `ended_at` — reja (`period`) dan alohida.
- `stations.status`: `FREE` / `OCCUPIED` / `RESERVED` / `CLEANING` /
  `MAINTENANCE`. Holat hodisadan hisoblanadi, qo'lda ham o'zgartiriladi.
- `live-board.tsx` bandlikni `period` dan emas, `stations.status` va
  `started_at` dan oladi.

## D5. Overtime

- Reja tugagach `club_settings.overtime_grace_min` ichida seans davom
  etsa — avtomatik uzayadi va qo'shimcha vaqt narxi C-bosqich funksiyasi
  bilan hisoblanadi.
- Uzayish `price_breakdown` ga alohida bo'lak sifatida qo'shiladi.
- Keyingi bron bo'lsa uzaytirilmaydi — xodimga ogohlantirish.

## D6. B-bosqichdagi bloklangan vazifalarni ochish

- `mark_no_show` — endi ishlaydi (`CHECKED_IN` bor).
- `low_stock_alert` — C4 dagi `min_stock` bilan ishlaydi.
</task>

<constraints>
Pauza, transfer va hisobni bo'lish (split) bu bosqichga KIRMAYDI —
alohida bosqich.
`payments` sxemasiga tegilmaydi. Seans holati to'lovga ta'sir qilmaydi:
chek yopish mantig'i o'zgarmagan holda qoladi.
</constraints>

<output>
Migratsiyalar `0036+`. Holat mashinasi diagrammasi `docs/HOLAT.md` ga.
`stations.status` qaysi hodisadan qaysi holatga o'tishi jadval sifatida.
</output>
