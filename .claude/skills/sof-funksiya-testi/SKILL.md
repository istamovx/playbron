---
name: sof-funksiya-testi
description: Hisob mantiqini servis qatlamidan sof funksiya sifatida ajratish va DB'siz test bilan qoplash. Narx, chek yakuni, kassa farqi, deposit, vaqt oralig'i hisobi yozilganda yoki o'zgartirilganda ishlatiladi.
---

# Sof funksiya va DB'siz test

`CLAUDE.md` §Testlar talab qiladi: "Sof hisob funksiyasi (narx, farq,
deposit) DB'siz test bilan qoplanadi."

Sabab amaliy: DB testlari `RUN_DB_TESTS=1` talab qiladi va usiz
**jimgina skip** bo'ladi. Lokal `pytest -q` yashil chiqadi, hisob esa
sinalmagan qoladi. Sof funksiya bu tuzoqdan tashqarida yuradi.

## 1. Nimani ajratish kerak

Ajratiladi:
- narx hisobi (tarif bo'laklari, uzaytirish, paket)
- chek yakuni (`total`, `discount`, `debt`, `tip` munosabati)
- kutilayotgan naqd va `variance`
- deposit summasi
- vaqt oralig'i hisoblari (slot tarmog'i, davomiylik, yarim tun)

Ajratilmaydi:
- SQL so'rovi
- RLS kontekstiga bog'liq mantiq
- tashqi API chaqiruvi

## 2. Imzo qanday bo'ladi

Sof funksiya `AsyncSession` qabul qilmaydi. U oddiy tiplar yoki
dataclass oladi va natija qaytaradi.

```python
# YO'Q — DB'ga bog'langan
async def hisobla(session: AsyncSession, booking_id: int) -> int: ...

# HA — sof
def hisobla(
    *,
    davomiylik_min: int,
    qoidalar: Sequence[TarifQoidasi],
    sozlamalar: KlubSozlamalari,
) -> list[NarxBolagi]: ...
```

Chaqiruvchi servis ma'lumotni o'qiydi, sof funksiyaga uzatadi, natijani
yozadi. Servisda hisob **qolmaydi** — faqat o'qish, chaqirish, yozish.

## 3. Test fayli

Nomi `test_<mavzu>_pure.py`. `skip_no_db` **ishlatilmaydi**. Test
`RUN_DB_TESTS` siz o'tishi ko'rsatiladi:

```
cd api && pytest tests/test_money_pure.py -q
```

## 4. Chekka holatlar — majburiy minimum

**Pul funksiyasi:**
nol summa · to'liq chegirma (`total` ga teng) · ortiqcha to'lov (tip) ·
qisman to'lov (debt) · qaytarimdan keyingi qoldiq · salbiy kiritish rad
etilishi

**Vaqt funksiyasi:**
yarim tun kesishuvi · klub zonasi UTC'dan farq qilishi · nol davomiylik ·
oraliq chegarasidagi aniq daqiqa · qoida topilmagan holat

**Tarif funksiyasi:**
bitta qoida ichida · ikki qoida chegarasida (proporsional bo'linish) ·
priority to'qnashuvi · fallback (`stations.rate`)

## 5. Assert haqiqiy bo'lsin

`assert natija is not None` — qoplama emas. Kutilgan son yozilishi kerak.

Chegara holatida sonni qo'lda hisoblab yoz, funksiyani chaqirib chiqqan
natijani ko'chirib qo'yma — aks holda test funksiyaning joriy xatosini
"to'g'ri" deb muzlatib qo'yadi.

## Tekshiruv ro'yxati

- [ ] Funksiya `AsyncSession` qabul qilmaydi
- [ ] Servisda hisob qolmagan
- [ ] Test fayli `_pure` bilan tugaydi va `skip_no_db` yo'q
- [ ] `RUN_DB_TESTS` siz o'tishi ko'rsatilgan
- [ ] Yuqoridagi chekka holatlar qoplangan
- [ ] Kutilgan sonlar qo'lda hisoblangan
