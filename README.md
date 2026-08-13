# PlayBron

PlayStation klublari uchun multi-tenant bron SaaS. To'liq spetsifikatsiya —
[docs/BUILD-BRIEF.md](docs/BUILD-BRIEF.md), dizayn manbai — [docs/DESIGN-HANDOFF.md](docs/DESIGN-HANDOFF.md).

## Talablar

Node ≥ 22.12, pnpm 10, Docker Desktop.

## Ishga tushirish

```bash
cp .env.example .env
docker compose up -d
pnpm install
pnpm build
pnpm db:deploy
pnpm db:seed
pnpm --filter api dev
```

API — `http://localhost:3000/api/v1`, Swagger — `http://localhost:3000/docs`,
health — `http://localhost:3000/health`.

## Buyruqlar

| Buyruq | Nima qiladi |
| --- | --- |
| `pnpm dev` | barcha app'lar watch rejimida |
| `pnpm build` / `pnpm test` / `pnpm lint` / `pnpm typecheck` | turbo pipeline |
| `pnpm db:migrate` | `prisma migrate dev` (yangi migratsiya) |
| `pnpm db:deploy` | mavjud migratsiyalarni qo'llash |
| `pnpm db:seed` | demo ma'lumot |
| `pnpm db:reset` | bazani tozalab qayta qurish + seed |

## Demo hisoblar (seed)

| Telefon | Rol | Parol |
| --- | --- | --- |
| `+998901110000` | SUPERADMIN | `playbron123` |
| `+998901110001` | CLUB_ADMIN | `playbron123` |
| `+998901110002/03` | STAFF | `playbron123` |

Mijoz kirishi — `POST /api/v1/auth/otp/request` + `otp/verify`. Eskiz kalitlari `.env` da
bo'sh bo'lsa kod SMS o'rniga konsolga chiqadi.

## Tuzilma

```
apps/api            NestJS 11 + Fastify + Prisma 6 + Socket.IO + BullMQ
apps/admin          React 19 + Vite — xodim va admin konsoli (port 5173)
apps/miniapp        React 19 + Vite — Telegram Mini App, mijoz (port 5174)
apps/landing        Next.js 15 — marketing sayt va klublar katalogi (port 3001)
packages/ui         SystemX tokenlari + umumiy React komponentlar
packages/types      zod sxemalar + sof hisob funksiyalari (narx, deposit, refund, hisob)
packages/config     tsconfig, eslint flat config
docs/designs        dizayn prototiplari (.dc.html) va SystemX dizayn tizimi
docker/postgres     initdb skriptlari (ilova roli)
```

Frontendlar `/api` ni `localhost:3000` ga proksilaydi, shuning uchun API'ni birinchi ishga tushiring.

## Ikki DB roli

RLS faqat superuser bo'lmagan rolga qo'llanadi, shuning uchun ulanish ikkiga bo'lingan:

- `DIRECT_URL` → `playbron` (egasi): migratsiya, seed, Prisma Studio.
- `DATABASE_URL` → `playbron_app`: ilova runtime'i. Har bir so'rov `app.club_id` GUC'i orqali
  o'z tenantini ko'radi, boshqa klub qatorlari umuman qaytmaydi.

`playbron_app` roli `docker/postgres/init/01-app-role.sh` da yaratiladi — u faqat
volume birinchi marta yaratilganda ishlaydi. Bazani noldan ko'tarish:
`docker compose down -v && docker compose up -d`.

## Migratsiya qoidasi

Prisma EXCLUDE konstreyni va RLS policy'larini bilmaydi — ular
`prisma/migrations/*_tenancy_guards/migration.sql` da qo'lda boshqariladi.
**Yangi tenant-scoped jadval qo'shsang**, o'sha migratsiyada unga `ENABLE`/`FORCE ROW LEVEL SECURITY`
va `tenant_isolation` policy'sini ham yozish shart — aks holda jadval izolyatsiyasiz qoladi.
