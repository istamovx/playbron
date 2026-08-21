---
name: rls-money-security-review
description: PlayBron backend (api/migrations/versions/**, api/src/playbron/modules/*/service.py, router.py) o'zgargan yoki yangi fayllarni CLAUDE.md §Pul, §RLS va migratsiya, §Xatolar invariantlariga qarshi tekshiradi — RLS policy to'liqligi, pul ustuni turi/CHECK, audit log, SECURITY DEFINER+GUC naqshi, sqlstate xaritasi, migratsiya downgrade qoidasi. Yangi migratsiya yoki service.py o'zgarishi review qilinganda ishlatiladi.
---

# RLS + pul xavfsizlik review

PlayBron backendining eng qimmatga tushadigan xato sinfi — RLS chetlab
o'tilishi (jimgina 0 qator) va pul mantig'idagi nomuvofiqlik. Bu skill
CLAUDE.md dagi tegishli invariantlarga qarshi tekshiradi. Faqat review —
kod o'zgartirmaydi, topilmalarni tasdiqlangan/shubhali deb belgilab
ro'yxatlaydi.

## Qamrov

O'zgargan yoki yangi: `api/migrations/versions/**`,
`api/src/playbron/modules/*/service.py`, `api/src/playbron/modules/*/router.py`,
`api/src/playbron/core/errors.py`, `api/src/playbron/core/audit.py`.

## Tekshirish ro'yxati — RLS va migratsiya

1. **Yangi tenant-scoped jadval** bitta migratsiyada oltita narsaga ega
   bo'lishi kerak: `club_id` ustuni + CHECK/indeks, `ENABLE ROW LEVEL
   SECURITY`, `FORCE ROW LEVEL SECURITY`, policy (rol bo'yicha; mijoz
   o'qishi kerak bo'lsa alohida `FOR SELECT`), `GRANT` (`playbron_app`,
   kerak bo'lsa `playbron_platform`), self-test. Uchtasidan biri yetishmasa
   — bloklovchi topilma.
2. **Yangi so'rov mavjud jadvalni o'qiydimi** — o'sha jadvalning policy'si
   chaqiruvchi rolni (`playbron_app` yoki `playbron_platform`) qamrab
   olishini tekshirish. Qamramasa — SELECT xato bermay jimgina 0 qator
   qaytaradi, bu eng xavfli sinf.
3. **`UPDATE` policy bor-u `SELECT` policy yo'qmi** — Postgres qatorni
   topish bosqichida SELECT policy'sini qo'llaydi, shuning uchun ikkalasi
   ham kerak.
4. **Policy ichida JOIN/subquery** — u jadval ham tegishli GUC'ni bilishi
   (RLS policy'siga ega bo'lishi) kerak.
5. **`app_club_role()` `memberships` policy ichida chaqirilganmi** —
   rekursiya xatosi. `app.club_role` GUC to'g'ridan-to'g'ri ishlatilishi
   kerak.
6. **Cross-tenant o'qish** faqat `SECURITY DEFINER` funksiya + nomlangan
   GUC claim orqali. Yangi `BYPASSRLS` roli — bloklovchi topilma.
7. **Invariant yozilgan migratsiyada uni buzishga urinuvchi self-test bormi.**
8. **`downgrade()`** — `NotImplementedError` dan boshqa narsa yozilgan bo'lsa,
   yoki mavjud (eski) migratsiya tahrirlangan bo'lsa — bloklovchi topilma.
9. **`check_render_shape.py`** migratsiya qo'shilgach yuritilganmi va
   natijasi keltirilganmi.

## Tekshirish ro'yxati — pul

1. Pul ustuni turi `bigint` (so'm, kasrsiz) — `numeric`/`float`/
   `double precision` bo'lsa bloklovchi topilma.
2. Pul ustunida `>= 0` yoki `> 0` CHECK bormi.
3. JSON javobda pul butun son sifatida qaytadimi (kasr/satr emas).
4. Yopilgan hujjat narxi joriy jadvaldan JOIN bilan qayta hisoblanmayaptimi
   — snapshot ustunidan (`rate_snapshot`, `price_snapshot`,
   `product_name`) o'qilishi kerak.
5. Narx/hisob formulasi bitta manbada (`modules/*/service.py`,
   `modules/bookings/pricing.py`) — takrorlangan formulani izlash.
6. `bookings.play_amount` o'rniga `rate_snapshot * hours` bilan yangi
   hisoblovchi kod bormi — bloklovchi topilma (tarif vaqt bo'yicha
   o'zgarsa mos kelmaydi).
7. Naqd pul yozuvi `shift_id` bilan bog'langanmi.
8. Yopilgan smena hisobiga ta'sir qiluvchi yozuv keyin o'zgartirilmayaptimi.
9. Hisoblangan `total` bilan olingan summa farqi sababi bilan yozilganmi
   (`DISCOUNT`/`DEBT` kam bo'lsa, `TIP` ko'p bo'lsa).
10. Bekor qilish `DELETE` emas, teskari `REFUND` yozuvi bilanmi.
11. Hisobot maydonida `planned_*`/`received_*` ajratilganmi.
12. Pul yoki sozlamaga tegadigan amal `core/audit.py::log_action()`
    chaqirayaptimi.

## Tekshirish ro'yxati — xatolar

1. Router'da to'g'ridan-to'g'ri `HTTPException` yozilmaganmi — biznes xatosi
   `core/errors.py::AppError(matn, code=...)` orqali chiqishi kerak.
2. Yangi CHECK/UNIQUE/FK konstreynt qo'shilgan bo'lsa, `core/errors.py`
   dagi sqlstate xaritasida mos yozuv bormi (`23P01`→409, `23505`→409,
   `23514`→422, `23503`→409). Yo'q bo'lsa — foydalanuvchiga 500 chiqadi.
3. Bron to'qnashuvi ilova qatlamida emas, `bookings_no_overlap` EXCLUDE
   konstreyni bilan to'xtatilganmi.

## Tekshirish ro'yxati — testlar

1. Pul mantig'i o'zgargan bo'lsa test ham o'zgarganmi.
2. Sof hisob funksiyasi DB'siz testlanganmi.
3. Yangi endpoint uchta test bilan qoplanganmi: amal ishlaydi, boshqa klub
   ko'rmaydi, yetarli roli yo'q xodim `403` oladi.
4. `RUN_DB_TESTS=1` siz olingan natija tasdiq sifatida keltirilmaganmi.

## Chiqish formati

Har topilma: fayl:qator, buzilgan invariant bandi, CONFIRMED/PLAUSIBLE,
bitta gaplik tuzatish taklifi. Eng og'ir (RLS chetlab o'tilishi, pul
turi/CHECK yo'qligi) birinchi. Toza bo'lsa aniq "Topilma yo'q" deyiladi.
