# PlayBron

PlayStation klublari uchun multi-tenant bron SaaS. Rollar: SUPERADMIN, CLUB_ADMIN, STAFF, CUSTOMER.
To'liq spetsifikatsiya: `docs/BUILD-BRIEF.md`.

## Stack

Turborepo + pnpm. `apps/api` (NestJS 11 + Fastify + Prisma 6 + PostgreSQL 16 + Redis + Socket.IO),
`apps/admin` va `apps/miniapp` (React 19 + Vite 6), `apps/landing` (Next.js 15),
`packages/ui` (SystemX design system — brief'dagi "Blue" eskirgan, manba `docs/designs/_ds/`),
`packages/types` (zod + sof hisob funksiyalari), `packages/config`.
Test — vitest (API'da `unplugin-swc`, chunki Nest DI `emitDecoratorMetadata` ga tayanadi).

## Buyruqlar

```bash
pnpm dev              # hamma app
pnpm --filter api dev
pnpm db:migrate       # prisma migrate dev
pnpm db:seed
pnpm test
pnpm build
docker compose up -d  # postgres, redis, minio
```

## Qat'iy qoidalar

- Pul — `bigint`, so'm, kasrsiz. Float yo'q. JSON javobda satr (`BigInt.prototype.toJSON`).
- Vaqt — DB'da UTC `timestamptz`, UI'da `Asia/Tashkent`, `date-fns-tz`.
- Tenant izolyatsiyasi — Postgres RLS + `nestjs-cls`. Qo'lda `where: { club_id }` yozib chetlab o'tilmaydi.
  Ilova `playbron_app` roli bilan ulanadi (`DATABASE_URL`), migratsiya va seed egasi roli bilan
  (`DIRECT_URL`) — superuser RLS'ni chetlab o'tadi, shuning uchun ular ajratilgan.
- Yangi tenant-scoped jadval → o'sha migratsiyada `ENABLE`/`FORCE ROW LEVEL SECURITY` va
  `tenant_isolation` policy'si ham yoziladi. RLS va EXCLUDE konstreynlarini Prisma ko'rmaydi.
- Bron to'qnashuvi — `bookings_no_overlap` EXCLUDE konstreyni. `23P01` → `409 SLOT_TAKEN`.
- Narx, deposit, refund hisoblari — `packages/types` ichidagi sof funksiyalar, API va frontend bitta manbadan foydalanadi.
- Rang/spacing/typography faqat design tokenlar orqali. Hardcode qiymat yo'q.
- `any` yo'q. Matn literal yo'q — i18n resurslari (uz/ru/en).
- Migratsiyalar faqat oldinga.

## Tegilmaydi

`prisma/migrations/**` (mavjudlari), `packages/ui/src/tokens/**`, `.env`

## Uslub

Birinchi tool chaqiruvidan oldin bir gapda nima qilayotganingni ayt. Ish davomida faqat muhim
topilma yoki yo'nalish o'zgarishida yoz. Oxirida natijadan boshla.
Subagent faqat haqiqatan mustaqil va parallellashadigan katta ish uchun.
Javoblar qisqa.
