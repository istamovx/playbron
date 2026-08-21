# A-bosqich — CLAUDE.md nomuvofiqliklari

<context>
`CLAUDE.md` to'rt joyda qoida yozgan, kod esa uni bajarmayapti. Yangi
funksiyadan oldin shular yopiladi: bajarilmaydigan qoida CLAUDE.md ni
dekorativ hujjatga aylantiradi, keyin uni tiklab bo'lmaydi.

Manba: `docs/audit-report.md`, HEAD `268aa23`.
</context>

<task>
To'rt mustaqil vazifa, har biri alohida commit.

## A1. Sof hisob funksiyalari va ularning DB'siz testlari

CLAUDE.md §Testlar: "Sof hisob funksiyasi (narx, farq, deposit) DB'siz test
bilan qoplanadi." Hozir `api/tests/test_money.py` (673 qator) butunlay
`skip_no_db` ostida — pul mantiqining birorta DB'siz testi yo'q.

- `modules/pos/service.py` va `modules/finance/shifts.py` dan hisob
  mantiqini sof funksiya sifatida ajrat. Kamida:
  - chek yakuni: `total`, `discount_amount`, `debt_amount`, `tip_amount`
    o'rtasidagi munosabat va qaysi holatda qaysi biri to'ldirilishi
  - kutilayotgan naqd: `opening_cash + payments(CASH) − expenses(CASH)
    ± movements`
  - `variance` hisobi
- Bu funksiyalar `AsyncSession` qabul qilmaydi, faqat oddiy tiplar.
  Chaqiruvchi kod ma'lumotni o'qiydi va sof funksiyaga uzatadi.
- `api/tests/test_money_pure.py` — DB'siz, `skip_no_db` siz. Chekka
  holatlar: nol summa, to'liq chegirma, ortiqcha to'lov (tip), qisman
  to'lov (debt), qaytarimdan keyingi qoldiq.
- Mavjud `test_money.py` o'zgarmaydi — u integratsiya darajasida qoladi.

## A2. `shifts_staff_one_open_uk` klub bo'yicha

`0021_shifts.py`:71 — `CREATE UNIQUE INDEX ... ON shifts (staff_id)`,
`club_id` siz va `WHERE status='open'` siz. `memberships` ko'p klubni
ataylab qo'llab-quvvatlaydi — ziddiyat.

- Migratsiya `0033`: indeksni `(club_id, staff_id) WHERE status = 'open'`
  ga almashtir.
- Self-test: bitta xodim ikki klubda smena ocha olsin, bitta klubda ikki
  marta ocholmasin.
- `CLAUDE.md` §"Ma'lum texnik qarz" dan mos bandni olib tashla.

## A3. Yopilgan smenaga to'lov yozishning oldini olish

CLAUDE.md §Pul: "Yopilgan smenaning hisobiga ta'sir qiladigan yozuv keyin
o'zgartirilmaydi." Hozir buni faqat matn ushlab turadi — `payments` ga
yopilgan smenaning `shift_id` si bilan qator kiritilsa, o'sha smenaning
`variance` i retroaktiv o'zgaradi.

- Migratsiya `0033` (A2 bilan bitta migratsiyada bo'lishi mumkin):
  `payments` va `expenses` uchun trigger yoki CHECK — `shift_id` ko'rsatgan
  smena `status='closed'` bo'lsa INSERT rad etilsin.
- Xato `AppError` ga aylanib `409 SHIFT_CLOSED` qaytsin.
- Self-test: yopilgan smenaga to'lov yozishga urinish rad etilishini
  tekshiradi.

Muqobil yechim (yopishda `expected_cash`/`variance` ni `shifts` ga muzlatib
yozish) TANLANMAYDI: u hisobni ikki joyda saqlaydi va CLAUDE.md ning
"hisob bitta manbadan" qoidasiga zid.

## A4. `mypy` ni CI'ga qo'shish

CLAUDE.md yozadi: "`mypy src/` 27 xato beradi. CI'da mypy qadami YO'Q.
Yangi kod bu sonni oshirmaydi." Bu tekshirilmaydigan qoida.

- `.github/workflows/ci.yml` `api` job'iga `mypy` qadami qo'shiladi.
- Mavjud 27 xato bloklamasligi uchun: baseline fayl yoki aniq modullarni
  `[[tool.mypy.overrides]]` bilan vaqtincha chiqarish. Yangi modul
  baseline'ga qo'shilmaydi.
- CLAUDE.md dagi bandni yangilangan holatga moslab yoz.
</task>

<constraints>
Yangi jadval yoki yangi funksiya qo'shilmaydi. Bu bosqich faqat mavjud
qoidalarni bajariladigan qiladi.
Migratsiyalar `0033+`. Mavjud migratsiyalar tahrirlanmaydi.
`packages/ui/src/tokens/**` va `docs/archive/**` ga tegilmaydi.
</constraints>

<output>
To'rt commit. Har biri uchun: nima o'zgardi, qaysi test qopladi.
CLAUDE.md §"Ma'lum texnik qarz" yopilgan bandlardan tozalanadi.
</output>
