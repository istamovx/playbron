# PlayBron — Tarif entitlement matritsasi

> Manba: `plans.limits` va `plans.features` (jsonb, DB'da seed).
> Tekshiruv **backendda majburiy**, frontend faqat ko'rinish uchun.
> Narxlar taxminiy — biznes tomonidan tasdiqlanishi kerak.

---

## 1. Tariflar

> **Sinov davri yo'q.** Tashkilot birinchi to'lovgacha `pending` holatda — faqat checkout
> ko'rinadi. Muddat tugashiga **3 kun qolganda** egaga Telegram xabari va boshqaruv
> panelida alert chiqadi.

| Kod | Nomi | Oylik | Yillik (−2 oy) | Kimga |
|---|---|---|---|---|
| `gold` | Gold | 490 000 so'm | 4 900 000 so'm | **Bitta klub**, asosiy ish oqimi |
| `platinium` | Platinium | 990 000 so'm | 9 900 000 so'm | O'sayotgan klub, ko'p xodim, chuqur hisobot |
| `infinite` | Infinite | 1 890 000 so'm | 18 900 000 so'm | Tarmoq, ko'p klub, AI Agent |

---

## 2. Limitlar

| Limit kaliti | Gold | Platinium | Infinite | Limit tugaganda |
|---|---|---|---|---|
| `clubs` | 1 | 3 | **∞** | Yangi klub qo'shish bloklanadi |
| `rooms_per_club` | 10 | 30 | **∞** | Yangi xona qo'shish bloklanadi |
| `staff_per_club` | 5 | 20 | **∞** | Yangi xodim taklif qilish bloklanadi |
| `products` | 50 | 300 | **∞** | Yangi mahsulot qo'shish bloklanadi |
| `rate_plans_per_club` | 2 | 6 | **∞** | Yangi vaqt tarifi bloklanadi |
| `devices_per_club` | 30 | 150 | **∞** | Yangi qurilma bloklanadi |
| `bookings_per_month` | 1 500 | 8 000 | **∞** | Yangi bron bloklanadi, egaga ogohlantirish |
| `report_history_days` | 90 | 365 | **1 095** | Eski davr «tarifni ko'taring» holatida |
| `data_export_per_month` | 2 | 20 | **∞** | Eksport bloklanadi |
| `notification_recipients` | 1 (ega) | 5 | 20 | Yangi qabul qiluvchi qo'shilmaydi |

**Gold = 1 klub** (biznes qarori). Ko'p klubli tashkilot **Platinium** dan boshlanadi —
klub almashtirgich va `multi_club` funksiyasi shu tarifdan ochiladi.

---

## 3. Funksiyalar

`✓` bor · `—` yo'q · `◐` cheklangan

| Funksiya kaliti | Ekran / joy | Gold | Platinium | Infinite |
|---|---|---|---|---|
| `board_live` | Live board | ✓ | ✓ | ✓ |
| `timeline_day` | Timeline (bugun) | ✓ | ✓ | ✓ |
| `timeline_history` | Timeline (kecha/ertaga va tarix) | ◐ 7 kun | ✓ 90 kun | ✓ 365 kun |
| `pos` | Kassa | ✓ | ✓ | ✓ |
| `bar_orders` | Buyurtmalar kanbani | ✓ | ✓ | ✓ |
| `shift_close` | Smena yopish | ✓ | ✓ | ✓ |
| `blocklist` | Qora ro'yxat | ✓ | ✓ | ✓ |
| `inventory_basic` | Mahsulot katalogi va qoldiq | ✓ | ✓ | ✓ |
| `inventory_costing` | Tannarx va foyda hisobi | — | ✓ | ✓ |
| `expenses` | Xarajatlar | ◐ faqat kiritish | ✓ + taqsimot | ✓ + prognoz |
| `reports_daily` | Hisobot — kunlik | ✓ | ✓ | ✓ |
| `reports_weekly_monthly` | Hisobot — haftalik/oylik | — | ✓ | ✓ |
| `reports_yearly` | Hisobot — yillik | — | — | ✓ |
| `reports_compare` | Davrlarni taqqoslash | — | ✓ | ✓ |
| `multi_club` | Klub almashtirgich | — | ✓ | ✓ |
| `staff_roles` | ADMIN roli berish | — | ✓ | ✓ |
| `custom_rate_plans` | Vaqt tariflari (kunduzi/kechqurun) | ◐ 2 ta | ✓ | ✓ |
| `online_booking` | Mijoz Mini App'da klub ko'rinadi | ✓ | ✓ | ✓ |
| `reviews` | Sharhlar | ✓ | ✓ | ✓ |
| `notifications_custom` | Bildirishnoma sozlamalari | — | ✓ | ✓ |
| `data_export` | CSV/Excel eksport | ◐ 2/oy | ✓ | ✓ |
| `api_access` | Tashqi API kaliti | — | — | ✓ |
| `online_payment` | Mijoz bronni Click/Payme bilan to'laydi | ✓ | ✓ | ✓ |
| **`ai_agent`** | **AI Agent kunlik hisoboti** | — | — | **✓** |
| `ai_agent_custom` | Hisobot vaqti va tarkibini sozlash | — | — | ✓ |
| `priority_support` | Ustuvor qo'llab-quvvatlash | — | ◐ | ✓ |

---

## 4. Saqlash formati

```jsonc
// plans jadvalidagi qator
{
  "code": "platinium",
  "title": "Platinium",
  "price_month": "990000",
  "price_year": "9900000",
  "limits": {
    "clubs": 3,
    "rooms_per_club": 30,
    "staff_per_club": 20,
    "products": 300,
    "rate_plans_per_club": 6,
    "devices_per_club": 150,
    "bookings_per_month": 8000,
    "report_history_days": 365,
    "data_export_per_month": 20,
    "notification_recipients": 5
  },
  "features": [
    "board_live", "timeline_day", "timeline_history", "pos", "bar_orders",
    "shift_close", "blocklist", "inventory_basic", "inventory_costing",
    "expenses", "reports_daily", "reports_weekly_monthly", "reports_compare",
    "multi_club", "staff_roles", "custom_rate_plans", "online_booking",
    "reviews", "notifications_custom", "data_export", "priority_support"
  ]
}
```

`∞` limit — JSON'da `null`.

---

## 5. Tekshiruv nuqtalari

| Qatlam | Nima qiladi |
|---|---|
| **Backend — dekorator** | `@require_feature("multi_club")` → yo'q bo'lsa `403 FEATURE_NOT_IN_PLAN` |
| **Backend — limit** | `check_limit("rooms_per_club", club_id)` yozishdan oldin; oshsa `403 LIMIT_REACHED` + `{"limit": 10, "current": 10, "upgrade_to": "platinium"}` |
| **Backend — RLS'dan keyin** | Limit hisobi tenant kontekstida bajariladi |
| **Frontend** | `GET /api/v1/me/entitlements` → tugmani yashiradi yoki «tarifni ko'tarish» holatini ko'rsatadi |
| **Kesh** | Access token ichida (15 daqiqa) + Redis `org:{id}:ent`; tarif o'zgarganda bekor qilinadi |

### Xato javobi

```json
{
  "error": {
    "code": "LIMIT_REACHED",
    "message": "Xona limiti tugagan",
    "details": { "limit": 10, "current": 10, "feature": "rooms_per_club", "upgrade_to": "platinium" }
  }
}
```

Frontend shu `details` dan foydalanib mavjud dizayn tilida (`StatusLine tone="warn"` +
`Button` «Tarifni ko'tarish») holat ko'rsatadi — yangi vizual element kiritmasdan.

---

## 6. Downgrade va limitdan oshish

Downgrade joriy davr oxirida kuchga kiradi. Yangi limitdan oshgan resurslar:

| Resurs | Xatti-harakat |
|---|---|
| Xona, qurilma, mahsulot | **Muzlatiladi** — mavjudi ishlaydi, yangisi qo'shilmaydi |
| Xodim | Ortiqchasi `status = suspended` — egasi kimni qoldirishni tanlaydi |
| Klub | Ortiqchasi `read_only` — bron qabul qilmaydi, ma'lumot saqlanadi |
| Hisobot tarixi | Eski davr «tarifni ko'taring» holatida ko'rsatiladi, o'chirilmaydi |

Kabinetda «Tarif limitidan oshgan» ro'yxati va nima qilish kerakligi ko'rsatiladi.
