# C-bosqich — tarif, xona, klub sozlamalari

<context>
Narx hozir `stations.rate` — bitta flat son. Klub siyosati (`MAX_ADVANCE_DAYS
= 14`, `PREPAY_HOURS = 1`) kodda konstanta. Ya'ni platforma faqat bir xil
qolipdagi klublarga yaraydi — bu SaaS sifatida asosiy cheklov.

`apps/admin/src/mock/club.ts` dagi `TARIFFS_INIT` va `ROOMS_INIT` — aynan
shu bajarilmagan ishning frontend'dagi soyasi. Bu bosqich tugagach ular
o'chadi.
</context>

<task>
## C1. `club_settings`

Bitta klubga bitta qator (`club_id` PK). Kodda konstanta bo'lgan hamma
narsa shu yerga:

`max_advance_days` · `min_booking_minutes` · `slot_minutes` ·
`max_booking_minutes` · `extend_max_minutes` · `payment_window_min` ·
`cancel_free_before_min` · `no_show_after_min` · `overtime_grace_min` ·
`variance_limit` · `deposit_percent`

- Migratsiya `0035`: jadval + RLS + policy + GRANT + self-test.
- Klub yaratilganda standart qator avtomatik yoziladi (trigger yoki
  servis).
- `bookings/service.py` dagi konstantalar shu jadvaldan o'qishga o'tadi.
- Konsolda sozlamalar ekrani (`screens/admin/settings.tsx` mavjud).

## C2. `rooms`

- `rooms`: `club_id`, `name`, `kind` (`STANDARD`/`VIP`/`VR`/`PC`),
  `price_multiplier`, `capacity`, `sort_order`.
- `stations.room_id` FK qo'shiladi; `stations.room_label` dan ma'lumot
  ko'chiriladi va ustun o'chiriladi.
- Xona bo'yicha filtr va hisobot uchun indeks.

## C3. `tariffs` + `tariff_rules`

Bu bosqichning eng nozik qismi.

**Sxema:**
- `tariffs`: `club_id`, `name`, `kind` (`HOURLY`/`PACKAGE`), `is_active`,
  `priority`
- `tariff_rules`: `tariff_id`, `days_of_week` (int[]), `time_from`,
  `time_to`, `room_id?`, `console_type?`, `controllers_count?`,
  `price_per_hour`, `min_minutes`

**Hisoblash algoritmi — sof funksiya sifatida yoziladi:**

```
narx(boshlanish, tugash, station, club_settings, qoidalar) -> bo'laklar[]
```

- Sessiya bir necha qoidani kesib o'tsa vaqt bo'yicha proporsional
  bo'linadi. Misol: 16:00–19:00 → 1 soat kunduzgi + 2 soat kechki.
- Bir vaqtga bir necha qoida mos kelsa `priority` hal qiladi; teng bo'lsa
  eng aniq (ko'proq shart to'ldirilgan) qoida.
- Yarim tunni kesib o'tuvchi oraliq (`time_from > time_to`) qo'llab-
  quvvatlanadi.
- Hech qanday qoida mos kelmasa — `stations.rate` fallback.

**Testlar DB'siz** (`test_tariff_pure.py`), kamida: bitta qoida ichida,
ikki qoida chegarasida, yarim tun kesishuvi, priority to'qnashuvi, fallback,
nol davomiylik, qoida yo'q holat.

- `bookings.rate_snapshot` o'rniga `bookings.price_breakdown` jsonb —
  qaysi bo'lak qaysi narxda hisoblangani saqlanadi. Snapshot qoidasi
  saqlanadi (CLAUDE.md §Pul): yopilgan hujjat narxi qayta hisoblanmaydi.

## C4. Qo'shimcha ustunlar

- `products.cost_price` (marja hisoboti uchun), `products.min_stock`
  (B3 dagi `low_stock_alert` shunga bog'liq)
- `menu_categories` jadvali; `products.category` matni ko'chiriladi

## C5. Frontend

- `apps/admin/src/mock/club.ts` o'chiriladi. `TARIFFS_INIT`, `ROOMS_INIT`,
  `DEVICES_INIT`, `PRODUCTS_INIT`, `STAFF_INIT` ni ishlatuvchi ekranlar
  real API'ga ulanadi.
- `apps/miniapp/src/lib/bill.ts` narxni server bergan `price_breakdown`
  dan ko'rsatadi, o'zi hisoblamaydi (CLAUDE.md §Pul).
- Tarif tahrirlash ekrani: qoidalar ro'yxati, vaqt oralig'i, priority.
</task>

<constraints>
`bookings.hours` → `duration_minutes` ko'chirishi bu bosqichda QILINMAYDI —
u D-bosqich ishi va bron holat mashinasi bilan bitta migratsiyada ketadi.
C3 dagi hisob funksiyasi minutlarda ishlaydi, chaqiruvchi hozircha
`hours * 60` uzatadi.

Narx hisobi faqat serverda. Frontend'da narx formulasi yozilsa merge
qilinmaydi.
</constraints>

<output>
Migratsiyalar `0035+`. `test_tariff_pure.py` DB'siz o'tishi ko'rsatiladi.
`mock/club.ts` o'chirilgani va uni ishlatgan ekranlar ro'yxati.
</output>
