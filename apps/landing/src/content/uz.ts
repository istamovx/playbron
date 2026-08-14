/**
 * O'zbekcha matn resurslari — **manba til**.
 *
 * `ru.ts` shu obyektning tipiga bo'ysunadi, shuning uchun bu yerga qo'shilgan
 * har bir kalit rus tilida ham talab qilinadi: tarjimasi tushib qolsa
 * `astro check` xato beradi.
 *
 * Komponentlarda matn literali yo'q — hammasi shu yerdan keladi.
 */

import { STATS } from '../config';

/** Board mockup'idagi stansiya holati — CSS klassiga shu qiymat bo'yicha ulanadi. */
export type StationState = 'free' | 'busy' | 'soon' | 'booked';

export interface MockStation {
  name: string;
  room: string;
  state: StationState;
  time: string;
}

const stations: MockStation[] = [
  { name: 'PS5 · 01', room: 'VIP 1', state: 'busy', time: '1:24' },
  { name: 'PS5 · 02', room: 'VIP 1', state: 'busy', time: '0:47' },
  { name: 'PS5 · 03', room: 'Zal', state: 'soon', time: '0:12' },
  { name: 'PS5 · 04', room: 'Zal', state: 'free', time: '—' },
  { name: 'PS4 · 05', room: 'Zal', state: 'busy', time: '2:05' },
  { name: 'PS4 · 06', room: 'Zal', state: 'booked', time: '19:00' },
  { name: 'PS5 · 07', room: 'VIP 2', state: 'busy', time: '0:33' },
  { name: 'PS5 · 08', room: 'VIP 2', state: 'free', time: '—' },
];

export const uz = {
  lang: 'uz',
  htmlLang: 'uz',
  localeTag: 'uz-UZ',
  dir: '/',

  meta: {
    title: 'PlayBron — PlayStation klublari uchun bron va boshqaruv tizimi',
    description:
      'Mijozlaringiz Telegram’dan joy band qiladi, xodimingiz jonli board’da ko‘radi. Bron, kassa, mahsulot reestri, xarajat va hisobot — bitta tizimda.',
    ogAlt: 'PlayBron ilovasi — jonli board va bugungi ko‘rsatkichlar',
  },

  nav: {
    features: 'Imkoniyatlar',
    screens: 'Ekranlar',
    how: 'Qanday ishlaydi',
    pricing: 'Tariflar',
    faq: 'Savollar',
    login: 'Ilovaga kirish',
    skip: 'Asosiy mazmunga o‘tish',
    langLabel: 'Til',
  },

  hero: {
    eyebrow: 'PlayStation klublari uchun boshqaruv tizimi',
    title: 'Klubingizni bitta ekrandan',
    titleAccent: 'boshqaring',
    text: 'Mijoz Telegram’da bo‘sh vaqtni ko‘rib joyni band qiladi. Xodim jonli board’da real vaqtda kuzatadi. Siz kun oxirida taxmin emas, aniq raqamni olasiz.',
    ctaPrimary: 'Klubingizni ulash',
    ctaSecondary: 'Ekranlarni ko‘rish',
    stats: [
      { value: '24/7', label: 'Telegram’dan bron' },
      { value: STATS.customers, label: 'Mijozlar' },
      { value: STATS.clubs, label: 'Klublar' },
    ],
  },

  problem: {
    eyebrow: 'Tanish holat',
    title: 'Bron daftarda, hisob kalkulyatorda',
    text: 'Klub kichik ekan ishlaydi. Stansiya soni o‘sgani sari har biri pulga aylanadi.',
    items: [
      {
        icon: 'event_busy',
        title: 'Ikki mijoz — bitta xona',
        text: 'Telegram guruhda kelishilgan bron chalkashadi. Kim birinchi yozganini hech kim isbotlay olmaydi.',
      },
      {
        icon: 'person_off',
        title: '«Kelaman» dedi, kelmadi',
        text: 'Joy bo‘sh turdi, vaqt sotilmadi. Mijoz tomonida hech qanday javobgarlik yo‘q.',
      },
      {
        icon: 'receipt_long',
        title: 'O‘yin alohida, bufet alohida',
        text: 'Ikkita qog‘oz, ikkita hisob. Smena oxirida kassa mos kelmaydi.',
      },
      {
        icon: 'query_stats',
        title: 'Raqamlar yo‘q',
        text: 'Qaysi xona ko‘p daromad keltirgani, qaysi mahsulot turib qolgani taxmin bilan aytiladi.',
      },
    ],
  },

  features: {
    eyebrow: 'Nimalar bera olamiz',
    title: 'Klub ishining har bir bo‘g‘ini',
    text: 'Bron qabul qilishdan sof foyda hisobigacha — orada Excel yo‘q.',
    items: [
      {
        icon: 'smartphone',
        title: 'Telegram’da bron',
        text: 'Mijoz botni ochadi, bo‘sh sana va vaqtni ko‘radi, necha soatga olishini tanlaydi. Ilova o‘rnatish shart emas.',
      },
      {
        icon: 'grid_view',
        title: 'Jonli board',
        text: 'Barcha stansiyalar bitta ekranda: kim o‘ynayapti, qancha vaqt qoldi, qaysi joy bo‘sh. Taymer o‘zi yuradi.',
      },
      {
        icon: 'lock',
        title: 'Ikkilangan bron imkonsiz',
        text: 'To‘qnashuv ma’lumotlar bazasi darajasida bloklanadi — ikki kishi bir vaqtga bitta joyni ololmaydi.',
      },
      {
        icon: 'payments',
        title: '1 soatlik oldindan to‘lov',
        text: 'Depozit yo‘q. Mijoz bron uchun 1 soatlik summani to‘laydi: kelsa hisobiga qo‘shiladi, kelmasa klubda qoladi.',
      },
      {
        icon: 'point_of_sale',
        title: 'Kassa',
        text: 'O‘yin vaqti va bufet bitta hisobda. Hisob yopilganda mahsulot qoldig‘i o‘zi kamayadi.',
      },
      {
        icon: 'inventory_2',
        title: 'Mahsulot reestri',
        text: 'Kirim, sotuv, qoldiq bitta joyda. Tannarx va foyda hisobi Platinium’dan boshlab.',
      },
      {
        icon: 'analytics',
        title: 'Hisobot',
        text: 'Kunlik, haftalik, oylik va yillik daromad. Bandlik foizi, o‘rtacha chek, xona va smena kesimida.',
      },
      {
        icon: 'account_balance_wallet',
        title: 'Xarajatlar',
        text: 'Elektr, suv, ijara, ish haqi — kiritilgan xarajat daromaddan ayriladi. Sof foyda taxmin emas.',
      },
      {
        icon: 'groups',
        title: 'Xodimlar va smena',
        text: 'Kim qancha sotdi, smena qanday yopildi. Kirish Telegram orqali — parol yo‘q, unutiladigan narsa ham yo‘q.',
      },
      {
        icon: 'block',
        title: 'Qora ro‘yxat',
        text: 'Vaqt tugagach 10 daqiqa kutiladi. Kelmagan mijoz belgilanadi va keyingi bronida ko‘rinadi.',
      },
      {
        icon: 'apartment',
        title: 'Ko‘p klub',
        text: 'Filiallar bitta hisobda, orasida bir bosishda o‘tiladi. Klub almashtirgich Platinium tarifidan.',
      },
      {
        icon: 'shield',
        title: 'Ma’lumot ajratilgan',
        text: 'Har klubning ma’lumoti baza darajasida izolyatsiya qilingan. Qo‘shni klub sizning raqamlaringizni ko‘rmaydi.',
      },
    ],
  },

  screens: {
    eyebrow: 'Ekranlar',
    title: 'Mahsulot qanday ko‘rinadi',
    text: 'Bitta dizayn tizimi uch yuzada: klub egasi kabinetida, xodim ilovasida va Telegram Mini App’da.',

    board: {
      title: 'Jonli board',
      caption: 'Xodim ekrani — barcha stansiya bitta joyda, taymer bilan',
      brandRole: 'Xodim',
      nav: ['Board', 'Timeline', 'Buyurtmalar', 'Kassa', 'Hisobot'],
      pageTitle: 'JONLI BOARD',
      meta: ['Cyber Arena · Chilonzor', 'Smena: 12:00 — 24:00'],
      kpis: [
        { label: 'Bugungi tushum', value: '4 850 000', unit: 'so‘m' },
        { label: 'Bandlik', value: '72', unit: '%' },
        { label: 'Aktiv seans', value: '6/8', unit: '' },
        { label: 'O‘rtacha chek', value: '84 000', unit: 'so‘m' },
      ],
      statusFree: 'Bo‘sh',
      statusBusy: 'O‘yinda',
      statusSoon: 'Tugayapti',
      statusBooked: 'Bron',
      stations,
      chartTitle: 'Bugungi bandlik',
      chartHours: ['12', '14', '16', '18', '20', '22'],
    },

    pos: {
      title: 'Kassa',
      caption: 'O‘yin vaqti va bufet — bitta hisob',
      billTitle: 'Hisob № 218',
      billMeta: 'PS5 · 03 · Zal',
      lines: [
        { name: 'O‘yin vaqti · 2 soat 15 daq', qty: '', sum: '135 000' },
        { name: 'Coca-Cola 0.5', qty: '×2', sum: '24 000' },
        { name: 'Lays', qty: '×1', sum: '12 000' },
      ],
      subtotal: 'Jami',
      subtotalSum: '171 000',
      prepaid: 'Oldindan to‘langan',
      prepaidSum: '−45 000',
      due: 'To‘lanadi',
      dueSum: '126 000',
      action: 'Hisobni yopish',
    },

    mini: {
      title: 'Mijoz Mini App',
      caption: 'Telegram ichida — sana, vaqt va davomiylik',
      club: 'Cyber Arena',
      clubMeta: 'Chilonzor · PS5 · 30 000 so‘m/soat',
      dateLabel: 'Sana',
      dates: ['Bugun', 'Ertaga', '16 avg'],
      timeLabel: 'Bo‘sh vaqt',
      times: ['14:00', '15:00', '16:00', '17:00', '18:00', '19:00'],
      timeTaken: '16:00',
      durationLabel: 'Davomiylik',
      durations: ['1 soat', '2 soat', '3 soat'],
      summaryLabel: 'Oldindan to‘lov',
      summarySum: '30 000 so‘m',
      summaryNote: 'Kelganingizda hisobingizga qo‘shiladi',
      action: 'Bron qilish',
    },
  },

  how: {
    eyebrow: 'Qanday ishlaydi',
    title: 'Obunadan birinchi bronigacha',
    ownerTitle: 'Klub egasi',
    playerTitle: 'O‘yinchi',
    ownerSteps: [
      {
        title: 'Tarifni tanlaysiz',
        text: 'Click yoki Payme orqali to‘laysiz. Sinov davri yo‘q — to‘lovdan keyin kabinet ochiladi.',
      },
      {
        title: 'Klubni sozlaysiz',
        text: 'Xonalar, qurilmalar, soatlik tarif va ish vaqti kiritiladi. Bu — bir kunlik ish.',
      },
      {
        title: 'Xodimlarni qo‘shasiz',
        text: 'Har biri Telegram orqali ilovaga kiradi. Parol yo‘q, almashtiriladigan narsa ham yo‘q.',
      },
      {
        title: 'Klub Mini App’da ko‘rinadi',
        text: 'Shu lahzadan mijozlar sizni topadi va bron qila boshlaydi.',
      },
    ],
    playerSteps: [
      {
        title: 'Bo‘sh vaqtni tanlaydi',
        text: 'Mini App bo‘sh sana, vaqt va necha soat olish mumkinligini ko‘rsatadi.',
      },
      {
        title: '1 soatlik summani to‘laydi',
        text: 'Click yoki Payme. To‘lov o‘tgach bron tasdiqlanadi va joy band qilinadi.',
      },
      {
        title: 'Kelganda seans boshlanadi',
        text: 'Xodim board’dan belgilaydi yoki mijoz QR ko‘rsatadi — taymer o‘sha lahzadan yuradi.',
      },
      {
        title: 'Hisob yopiladi',
        text: 'O‘yin vaqti va buyurtmalar qo‘shiladi, oldindan to‘langan soat ayriladi. Qolgani kassada.',
      },
    ],
    noShowTitle: 'Kelmasa nima bo‘ladi?',
    noShowText:
      'Belgilangan vaqtdan keyin 10 daqiqa kutiladi. Kelmasa bron yopiladi, 1 soatlik summa klubda qoladi va mijoz qora ro‘yxatga tushadi. Bu — bo‘sh turgan joy uchun tovon.',
  },

  roles: {
    eyebrow: 'Uch rol, uch ekran',
    title: 'Har kim o‘ziga keragini ko‘radi',
    items: [
      {
        icon: 'admin_panel_settings',
        title: 'Klub egasi',
        text: 'Boshqaruv paneli, hisobot, xarajat, xodimlar, mahsulotlar va klub ma’lumoti.',
        points: ['Kunlik va oylik hisobot', 'Xarajat va sof foyda', 'Xodim va tarif boshqaruvi'],
      },
      {
        icon: 'badge',
        title: 'Xodim',
        text: 'Jonli board, timeline, buyurtmalar kanbani, kassa va smena yopish.',
        points: ['Bron va seans boshqaruvi', 'Tez sotuv (POS)', 'Smena hisoboti'],
      },
      {
        icon: 'sports_esports',
        title: 'Mijoz',
        text: 'Telegram Mini App: bron, aktiv seans, hisob, buyurtma va bronlar tarixi.',
        points: ['Bo‘sh vaqtni ko‘rish', 'Oldindan to‘lov', 'Seans eslatmalari'],
      },
    ],
  },

  players: {
    eyebrow: 'O‘yinchilarga',
    title: 'Navbat kutmang — joyni oldindan oling',
    text: 'PlayBron’ga ulangan klublar Telegram’da ko‘rinadi. Bo‘sh vaqtni ko‘rasiz, necha soatga olishingizni tanlaysiz va joy siznikiligicha qoladi.',
    points: [
      'Bo‘sh sana va vaqt real vaqtda',
      '1 soatlik to‘lov — kelganingizda hisobingizga qo‘shiladi',
      'Seans tugashiga 30 va 15 daqiqa qolganda eslatma',
      'Hisob va buyurtmalaringiz telefoningizda',
    ],
    cta: 'Telegram’da ochish',
  },

  pricing: {
    eyebrow: 'Tariflar',
    title: 'Klub o‘sgani sari',
    text: 'Sinov davri yo‘q — birinchi to‘lovdan keyin klub ishga tushadi. Muddat tugashiga 3 kun qolganda ogohlantiramiz.',
    perMonth: '/ oy',
    yearNote: 'Yillik to‘lovda ikki oy tekin',
    priceOnRequest: 'Bog‘laning',
    featured: 'Ko‘p tanlanadi',
    cta: 'Tanlash',
    limitsTitle: 'Limitlar',
    plans: [
      {
        code: 'gold',
        name: 'Gold',
        tagline: 'Bitta klub, asosiy ish oqimi',
        limits: ['1 klub', '10 xona', '5 xodim', '30 qurilma', 'oyiga 1 500 bron'],
        features: [
          'Jonli board va timeline',
          'Kassa va buyurtmalar',
          'Mahsulot katalogi va qoldiq',
          'Kunlik hisobot',
          'Qora ro‘yxat',
          'Mini App’da bron va onlayn to‘lov',
        ],
      },
      {
        code: 'platinium',
        name: 'Platinium',
        tagline: 'O‘sayotgan klub, ko‘p xodim va chuqur hisobot',
        limits: ['3 klub', '30 xona', '20 xodim', '150 qurilma', 'oyiga 8 000 bron'],
        features: [
          'Gold’dagi hammasi',
          'Haftalik va oylik hisobot',
          'Davrlarni taqqoslash',
          'Tannarx va foyda hisobi',
          'Klub almashtirgich',
          'Xodimga ADMIN roli',
          'Xarajat taqsimoti',
        ],
      },
      {
        code: 'infinite',
        name: 'Infinite',
        tagline: 'Tarmoq, cheksiz klub va AI Agent',
        limits: ['Cheksiz klub', 'Cheksiz xona', 'Cheksiz xodim', 'Cheksiz qurilma', 'Cheksiz bron'],
        features: [
          'Platinium’dagi hammasi',
          'Yillik hisobot',
          'AI Agent kunlik hisoboti',
          'Xarajat prognozi',
          'Tashqi API kaliti',
          'Ustuvor qo‘llab-quvvatlash',
        ],
      },
    ],
  },

  faq: {
    eyebrow: 'Savollar',
    title: 'Ko‘p so‘raladi',
    items: [
      {
        q: 'Mijoz alohida ilova o‘rnatishi kerakmi?',
        a: 'Yo‘q. Bron Telegram ichida ochiladi — bot va Mini App. Telefonda Telegram bo‘lsa yetarli.',
      },
      {
        q: 'Ikki kishi bir vaqtga bitta joyni bron qilsa-chi?',
        a: 'Bunday bo‘lmaydi. To‘qnashuv ma’lumotlar bazasi darajasida bloklanadi: ikkinchi so‘rov rad etiladi va mijozga boshqa vaqt taklif qilinadi.',
      },
      {
        q: 'Mijoz kelmasa pul kimda qoladi?',
        a: 'Klubda. Belgilangan vaqtdan keyin 10 daqiqa kutiladi, keyin bron yopiladi va 1 soatlik summa klubga tegishli bo‘ladi. Mijoz qora ro‘yxatga tushadi.',
      },
      {
        q: 'Ma’lumotlarim boshqa klubga ko‘rinadimi?',
        a: 'Yo‘q. Har tashkilotning ma’lumoti bazaning o‘zida ajratilgan (Row-Level Security). Bu sozlama emas — dastur uni chetlab o‘tolmaydi.',
      },
      {
        q: 'To‘lovlar qanday qabul qilinadi?',
        a: 'Click va Payme orqali. Obuna to‘lovi va mijozning bron to‘lovi — ikki alohida oqim: ular aralashmaydi va hisobotda ham alohida ko‘rinadi.',
      },
      {
        q: 'Xodim parolini unutsa nima qilamiz?',
        a: 'Parol yo‘q. Ilovaga kirish Telegram orqali: xodim botda tugmani bosadi va kiradi. Ishdan bo‘shasa — ro‘yxatdan olib tashlaysiz, kirish o‘sha zahoti yopiladi.',
      },
      {
        q: 'Tarifni keyin o‘zgartira olamanmi?',
        a: 'Ha. Yuqoriga ko‘tarish darhol kuchga kiradi, pastga tushirish esa joriy davr oxirida. Limitdan oshgan resurslar o‘chirilmaydi — muzlatiladi.',
      },
      {
        q: 'Interfeys qaysi tillarda?',
        a: 'O‘zbek va rus tilida. Xodim va mijoz o‘ziga qulayini tanlaydi.',
      },
    ],
  },

  cta: {
    eyebrow: 'Boshlaymiz',
    title: 'Klubingizni PlayBron’ga ulaymiz',
    text: 'Bir suhbat yetarli: xonalar, qurilmalar va tariflaringizni birga sozlaymiz. Sozlash — bir kunlik ish.',
    primary: 'Ro‘yxatdan o‘tish',
    secondary: 'Ilovaga kirish',
    tertiary: 'Telegram’da yozish',
    note: 'Ro‘yxatdan o‘tish bepul — to‘lov tarif tanlaganda.',
  },

  footer: {
    tagline: 'PlayStation klublari uchun bron va boshqaruv tizimi.',
    productTitle: 'Mahsulot',
    companyTitle: 'Aloqa',
    playersTitle: 'O‘yinchilarga',
    console: 'Ilova',
    miniapp: 'Mini App',
    telegram: 'Telegram',
    legalNote: 'Ommaviy oferta va maxfiylik siyosati tayyorlanmoqda.',
  },
};

/** Barcha til fayllari shu shaklga bo'ysunadi — kalit tushib qolsa build yiqiladi. */
export type Content = typeof uz;
