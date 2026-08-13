# Dizayn o'zgartirish so'rovlari (DCR)

> Dizayn muzlatilgan. Bu yerda — biznes modeli bilan **to'g'ridan-to'g'ri ziddiyatda**
> bo'lgani uchun o'zgarishi shart bo'lgan joylar. Hech biri bajarilmagan; har biri
> alohida tasdiqlanadi.

---

## DCR-001 — Konsolga kirish: login/parol → Telegram

| | |
|---|---|
| **Ekran** | `apps/admin/src/screens/login.tsx` |
| **Nima uchun** | Spetsifikatsiya: «AUTH: faqat Telegram. Google, email/parol, OAuth — yo'q». Hozirgi ekranda login + parol maydonlari va demo hisoblar bloki bor |
| **Minimal o'zgarish** | Ikkita `TextField` va «Demo hisoblar» bloki olib tashlanadi; ularning o'rniga bitta Telegram Login Widget konteyneri qo'yiladi (`<div id="tg-login">`). Panel, brend ustuni, fon, tugma uslubi, layout — **o'zgarmaydi**. Widget yuklanmasa `StatusLine tone="danger"` bilan zaxira matn |
| **Ta'sir** | `store/session.ts` dagi `ACCOUNTS`, `signIn(login, password)`, `changePassword()` o'chadi |

---

## DCR-002 — Mijoz ro'yxatdan o'tishi: qo'lda kiritish → initData + requestContact

| | |
|---|---|
| **Ekran** | `apps/miniapp/src/screens/register.tsx` |
| **Nima uchun** | Mini App'da ism `initData` dan keladi, telefon esa `requestContact` orqali botdan olinadi. Hozir ikkalasi ham qo'lda kiritiladi |
| **Minimal o'zgarish** | «Ism» maydoni olib tashlanadi (`initData` dan to'ladi). «Telefon» maydoni o'rniga bitta `Button` — «Telefonni tasdiqlash», u botga deep-link ochadi; qaytgach shu joyda `StatusLine tone="ok"` ko'rinadi. Sahifa tuzilishi, PLAYBRON sarlavhasi, matn ohangi — o'zgarmaydi |
| **Ta'sir** | `useProfile.register()` imzosi o'zgaradi; «Kirish / Boshqa raqam bilan» ekrani saqlanadi (Telegram akkaunt almashsa kerak bo'ladi) |

---

## DCR-003 — Sozlamalardagi «Parolni almashtirish» bloki

| | |
|---|---|
| **Ekran** | `apps/admin/src/screens/admin/settings.tsx` |
| **Nima uchun** | Telegram-only auth'da parol yo'q — blok ma'nosiz |
| **Minimal o'zgarish** | Butun `Panel title="Parolni almashtirish"` olib tashlanadi. O'rniga hech narsa qo'yilmaydi (ustundagi qolgan panellar joyni egallaydi). Ixtiyoriy: o'sha joyga «Faol sessiyalar» paneli — keyingi faza |
| **Ta'sir** | `useSession.changePassword()` o'chadi |

---

## DCR-004 — Xodim kartasidagi «Login» maydoni

| | |
|---|---|
| **Ekran** | `apps/admin/src/screens/admin/staff.tsx` |
| **Nima uchun** | Xodim login/parol bilan emas, Telegram bilan kiradi. Egasi login **yaratmaydi**, taklif yuboradi |
| **Minimal o'zgarish** | Formadagi «Login» `TextField` o'rniga «Telegram" ustuni: taklif yuborilmagan bo'lsa `Button` «Taklif yuborish», yuborilgan bo'lsa `Tag` «Kutilmoqda», ulangan bo'lsa `@username`. Jadval ustunlari soni o'zgarmaydi, faqat mazmuni |
| **Ta'sir** | `StaffMember.login` → `telegram_id` + `invite_status` |

---

## DCR-005 — ~~Mijoz to'lov usullari~~ · YOPILDI

| | |
|---|---|
| **Ekran** | `apps/miniapp/src/screens/bill.tsx`, bron tasdiqlash oqimi |
| **Qaror** | Bron to'lovi ham **Click/Payme** orqali amalga oshadi |
| **Natija** | **O'zgarish kerak emas.** Mavjud UI to'g'ri. Backend tomonda ikki to'lov yuzasi ajratiladi: obuna → platforma merchant hisobi, bron → klub merchant hisobi (`01-architecture.md` §6.0) |

---

## DCR-007 — Til ro'yxatidan English olib tashlash

| | |
|---|---|
| **Ekran** | `apps/miniapp/src/screens/profile.tsx` → «Interfeys sozlamalari» |
| **Nima uchun** | Loyiha **o'zbek va rus** tilida ishlaydi. Uchinchi tugma («English») ishlamaydigan tanlovni va'da qiladi |
| **Minimal o'zgarish** | `mock/data.ts` dagi `LANGS` massividan `{ id: 'en' }` o'chiriladi. Layout, tugma uslubi, panel — o'zgarmaydi; uchta tugma o'rniga ikkitasi qoladi |
| **Ta'sir** | `CLAUDE.md` dagi «uz/ru/en» qoidasi «uz/ru» ga yangilanadi |

---

## DCR-006 — Konsolga router kiritish

| | |
|---|---|
| **Ekran** | `apps/admin/src/app.tsx` (barcha ekranlar bilvosita) |
| **Nima uchun** | To'lovdan qaytish (`return_url`), deep-link, brauzer «orqaga» tugmasi va route guard uchun URL kerak. Hozir navigatsiya faqat store'da |
| **Minimal o'zgarish** | `react-router` qo'shiladi, `useBoard.screen` URL bilan sinxronlanadi. **Bitta ham JSX markup yoki style o'zgarmaydi** — faqat `setScreen` o'rniga `navigate` |
| **Ta'sir** | Vizual o'zgarish nol; shuning uchun bu DCR emas, ogohlantirish sifatida yozildi |
