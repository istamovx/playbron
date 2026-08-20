---
name: fon-vazifasi
description: PlayBron'da yangi fon vazifasi (background job) yozish — arq worker, GUC konteksti, idempotentlik, klub vaqt zonasi, notifications jurnali. Yangi rejali vazifa, eslatma, avto-bekor, hisobot yuborish yoki qoldiq tekshiruvi qo'shilganda ishlatiladi.
---

# Fon vazifasi yozish

HTTP so'rovidan farqli o'laroq fon vazifasida **so'rov konteksti yo'q**.
Shu bitta farq bu yerdagi deyarli hamma xatoning sababi.

## 1. GUC kontekstini o'zing o'rnat

`core/db.py::session_scope()` odatda HTTP qatlamidan `app.club_id` va
`app.club_role` oladi. Fon vazifasida ular bo'sh keladi.

Natija: so'rov **xato bermaydi**, jimgina 0 qator qaytaradi. Vazifa
"hech narsa topilmadi" deb tugaydi va hech kim sezmaydi.

Shuning uchun klub bo'yicha aylanadigan vazifa har bir klub uchun
kontekstni alohida ochadi:

```python
for club_id in club_ids:
    async with session_scope(club_id=club_id, club_role="ADMIN") as s:
        ...
```

Klublar ro'yxatini olish uchun cross-tenant o'qish kerak — buni
`SECURITY DEFINER` funksiya + nomlangan GUC claim orqali qil
(`docs/07-patterns.md` §2). Yangi `BYPASSRLS` roli **qo'shilmaydi**.

## 2. Idempotentlik majburiy

Vazifa ikki marta yurishi mumkin: worker qayta ishga tushdi, tarmoq
uzildi, qo'lda qayta chaqirildi. Ikkinchi yurish birinchisidan farqli
natija bermasligi shart.

Ikki qatlam:
- Redis'da `job_id` bo'yicha qulf — parallel yurishni to'xtatadi
- DB darajasida unikal indeks — masalan bitta bron uchun "2 soat qoldi"
  eslatmasi bir marta yuboriladi

Faqat Redis qulfiga tayanma: Redis tozalansa himoya yo'qoladi.

## 3. Vaqt — klub zonasida

Rejali vazifa server zonasiga tayanmaydi. "Har kuni 09:00" — bu
**klubning** 09:00 i (`clubs.timezone`).

`datetime.now()` zonasiz, `date.today()` — ishlatilmaydi.
`datetime.now(UTC)` va `ZoneInfo(club.timezone)`.

Har bir klub uchun keyingi bajarilish vaqti alohida hisoblanadi.

## 4. Pulga tegsa

Fon vazifasi to'lov yozsa yoki summani o'zgartirsa — `CLAUDE.md` §Pul
to'liq qo'llanadi. Ayniqsa: naqd yozuv smenaga bog'lanadi, yopilgan
smenaga yozilmaydi.

Amalda fon vazifasining pul yozishi kam kerak bo'ladi. Kerak bo'lsa —
qaysi smenaga yozilishi aniq belgilanmagan bo'lsa, vazifani yozma,
avval qaror so'ra.

## 5. Xabar yuborish

To'g'ridan-to'g'ri `telegram_api` chaqirilmaydi. Yuborish
`notifications` jadvali orqali: yozuv yaratiladi, yuboriladi, natija
(`sent_at` yoki `error`) qaytib yoziladi.

Sabab: yuborilgan-yuborilmagani tekshirilishi va takroriy yuborish
bloklanishi kerak.

## 6. Xatolar

- Vazifa yiqilsa `jobs.last_error` ga yoziladi, `attempts` oshadi
- Uch urinishdan keyin platforma jurnaliga
- Bitta klubdagi xato boshqa klublarning bajarilishini to'xtatmaydi —
  sikl ichida `try/except`, umumiy `try` emas

## 7. Test

- Vazifa mantiqi sof funksiya sifatida ajratiladi va DB'siz test bilan
  qoplanadi: qaysi yozuv tanlanadi, qaysi vaqt hisoblanadi
- Integratsiya testi: vazifa ikki marta yurganda ikkinchi yurish hech
  narsa o'zgartirmasligini tekshiradi
- Kontekst testi: GUC o'rnatilmagan holda vazifa 0 qator emas, **xato**
  berishi kerak — jimgina bo'sh natija tuzoq

## Tekshiruv ro'yxati

- [ ] Har klub uchun GUC konteksti ochiladi
- [ ] Cross-tenant o'qish `SECURITY DEFINER` orqali, `BYPASSRLS` siz
- [ ] Redis qulfi + DB unikal indeksi
- [ ] Vaqt `clubs.timezone` da
- [ ] Xabar `notifications` orqali
- [ ] Bir klub xatosi siklni to'xtatmaydi
- [ ] Ikki marta yurish testi bor
