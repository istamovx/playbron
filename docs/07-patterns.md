# Naqshlar — yangi jadval va yangi endpoint

> `CLAUDE.md` dagi "Naqshlar" bo'limining to'liq shakli. CLAUDE.md da
> tekshiruv ro'yxati, bu yerda shablon.

---

## 1. Yangi tenant-scoped jadval

Bitta migratsiyada bajariladigan olti qadam. Bittasi yetishmasa jadval
ishlamaydi yoki izolyatsiyasiz qoladi.

### 1.1 Jadval

```python
op.create_table(
    "example",
    sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
    sa.Column(
        "club_id", sa.BigInteger, sa.ForeignKey("clubs.id", ondelete="CASCADE"),
        nullable=False,
    ),
    sa.Column("amount", sa.BigInteger, nullable=False),
    sa.Column("created_by", sa.BigInteger, sa.ForeignKey("users.id"), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    sa.CheckConstraint("amount >= 0", name="example_amount_nonneg_ck"),
)
op.create_index("example_club_ix", "example", ["club_id"])
```

`club_id` bolalar jadvalida ham TAKRORLANADI (`order_items`,
`shift_cash_movements` naqshi) — RLS'ni ota-jadvalga JOIN qilmasdan
qo'llash uchun.

### 1.2 RLS

```sql
ALTER TABLE example ENABLE ROW LEVEL SECURITY;
ALTER TABLE example FORCE  ROW LEVEL SECURITY;

CREATE POLICY example_staff_all ON example FOR ALL
    USING (club_id = app_club_id()
           AND app_club_role(app_club_id()) IN ('OWNER', 'ADMIN', 'STAFF'))
    WITH CHECK (club_id = app_club_id()
                AND app_club_role(app_club_id()) IN ('OWNER', 'ADMIN', 'STAFF'));
```

- `FORCE` — jadval EGASIGA ham tegishli. `ENABLE` yolg'iz yetarli emas.
- Faqat OWNER/ADMIN uchun bo'lsa rollar ro'yxati qisqartiriladi.
- Mijoz o'qishi kerak bo'lsa alohida `FOR SELECT` policy'si yoziladi —
  `FOR ALL` ga mijozni qo'shib yuborilmaydi.

### 1.3 GRANT

```sql
GRANT SELECT, INSERT, UPDATE ON example TO playbron_app;
GRANT USAGE, SELECT ON SEQUENCE example_id_seq TO playbron_app;
GRANT SELECT ON example TO playbron_platform;
```

GRANT va RLS — ikki alohida qatlam:
GRANT bor + policy yo'q → bo'sh ro'yxat (xato emas, jimgina noto'g'ri).
GRANT yo'q → `permission denied`.

### 1.4 Platforma o'qishi

Superadmin ko'radigan jadval bo'lsa `playbron_platform` uchun policy ham
kerak (`0029_platform_read_gaps.py` naqshi) — BYPASSRLS Render'da yo'q
deb hisoblanadi.

### 1.5 Self-test

Migratsiya o'zi yozgan invariantni sinaydi (`0009`, `0010` naqshi):

```python
def _self_test() -> None:
    conn = op.get_bind()
    exempt = conn.execute(
        sa.text("SELECT rolsuper OR rolbypassrls FROM pg_roles WHERE rolname = current_user")
    ).scalar()
    if exempt:
        return          # lokal superuser — test ma'nosiz
    ...                 # invariantni buzishga urinish
    raise RuntimeError("...")   # buzilmasa migratsiya yiqiladi
```

Fixture yozish uchun FORCE vaqtincha olinsa — `try/finally` da qaytariladi.

### 1.6 Tekshiruv

```bash
python api/scripts/check_render_shape.py
```

Toza bazada NOSUPERUSER/NOBYPASSRLS ega bilan hamma migratsiyani yuritadi —
self-testlar faqat shunda haqiqatan sinaladi.

---

## 2. Cross-tenant o'qish kerak bo'lsa

Yangi BYPASSRLS roli qo'shilmaydi. Naqsh — `SECURITY DEFINER` funksiya +
nomlangan GUC "claim" (`0009_bookings.py::_notify_support()`):

```sql
CREATE OR REPLACE FUNCTION app_example_claim() RETURNS bigint
    LANGUAGE sql STABLE PARALLEL SAFE AS
$$ SELECT NULLIF(current_setting('app.example_claim', true), '')::bigint $$;

CREATE OR REPLACE FUNCTION example_targets(p_club_id bigint)
RETURNS TABLE (...) LANGUAGE plpgsql SECURITY DEFINER AS $$
BEGIN
    PERFORM set_config('app.example_claim', p_club_id::text, true);  -- LOCAL
    RETURN QUERY SELECT ... ;
END $$;

CREATE POLICY example_claim_read ON example FOR SELECT
    USING (club_id = app_example_claim());
```

Qoidalar:
- Claim funksiyaning O'ZI ichida `set_config(..., true)` bilan o'rnatiladi —
  chaqiruvchi kod uni o'rnata olmaydi.
- Ochiladigan qatorlar to'plami aniq bir ish uchun eng tor holda yoziladi.
- Funksiya nomi va nima uchun ochilgani migratsiya docstring'ida yoziladi.

Mavjud claim'lar: `app_booking_notify_claim`, `app_bot_lookup_claim`,
`app_signup_claim`, `app_club_publish_claim`, `app_login_claim`,
`app_org_check_claim`, `app_org_revoke_claim`, `app_telegram_link_claim`,
`app_club_role_claim`, `app_shift_guard_claim` (0034 — trigger ichida,
yopiq smena qo'riqchisi).

---

## 3. Yangi endpoint

### 3.1 Joylashuv

```
api/src/playbron/modules/<modul>/router.py    # validatsiya, marshrutlash, HTTP
api/src/playbron/modules/<modul>/service.py   # biznes mantiq, SQL
packages/api-client/src/endpoints.ts          # tipli klient + DTO
```

Router'da SQL yozilmaydi. Service'da HTTP tushunchasi bo'lmaydi
(`Request`, `Response`, status kodi — `AppError` orqali).

### 3.2 Router shabloni

```python
from playbron.deps import db, require_admin   # require_owner / require_staff

@router.post(
    "/{club_id}/examples",
    response_model=ExampleOut,
    dependencies=[Depends(require_admin)],
)
async def create_example(
    club_id: Annotated[int, Path(ge=1)],
    body: ExampleCreateIn,
    session: Annotated[AsyncSession, Depends(db)],
) -> ExampleOut:
    _assert_path_matches_header(club_id)
    row = await service.create_example(
        session,
        club_id=club_id,
        created_by=int(context.current().user_id or 0),
        **body.model_dump(),
    )
    return ExampleOut(**row)
```

- Rol tekshiruvi `deps.py` guard'i orqali: `require_owner` (OWNER),
  `require_admin` (OWNER+ADMIN), `require_staff` (OWNER+ADMIN+STAFF).
  Router tanasida `if role ==` yozilmaydi.
- Guard — RLS'ning ustiga qo'shimcha qatlam, o'rniga emas.
- `_assert_path_matches_header()` — yo'ldagi `club_id` faol klub sarlavhasiga
  mos kelishini tekshiradi (`pos/router.py`, `finance/router.py` naqshi).
- Kirish validatsiyasi Pydantic'da (`Field(gt=0)`, `max_length`,
  `pattern=`), service'da takrorlanmaydi.

### 3.3 Service shabloni

```python
async def create_example(
    session: AsyncSession, *, club_id: int, created_by: int, amount: int
) -> dict[str, Any]:
    if amount <= 0:
        raise AppError("Summa musbat bo'lsin", code="AMOUNT_INVALID")

    row_id = await session.scalar(
        text(
            "INSERT INTO example (club_id, amount, created_by)"
            " VALUES (:club_id, :amount, :by) RETURNING id"
        ),
        {"club_id": club_id, "amount": amount, "by": created_by},
    )

    await log_action(action="example_created", target=str(row_id), club_id=club_id,
                     after={"amount": amount})
    return {"id": row_id, "amount": amount}
```

- Pul qiymati `int(...)` bilan qaytariladi.
- Pulga yoki sozlamaga tegadigan har amal `log_action()` yozadi.
- Xato — `AppError(matn, code=...)`, kod barqaror va frontend unga tayanadi.

### 3.4 api-client

```ts
export interface ExampleDto { id: number; amount: number }

export const createExample = async (
  api: ApiClient, clubId: number, body: { amount: number },
): Promise<ExampleDto> => {
  const row = await api.post<{ id: number; amount: number }>(
    `/clubs/${clubId}/examples`, { amount: body.amount },
  );
  return { id: row.id, amount: row.amount };
};
```

- `snake_case` → `camelCase` xaritalash shu yerda, ekranda emas.
- `any` yo'q.

### 3.5 Test

```python
async def test_example_is_created_and_isolated(...):
    # 1. amal ishlaydi
    # 2. boshqa klub xodimi uni KO'RMAYDI (RLS)
    # 3. yetarli roli yo'q xodim uchun 403
```

Pul tegadigan endpoint uchun qo'shimcha: summa hisobining o'zi sof funksiya
sifatida DB'siz test bilan qoplanadi.

---

## 4. Xato → HTTP xaritasi

`api/src/playbron/core/errors.py`:

| sqlstate | Nima | HTTP |
|---|---|---|
| `23P01` | EXCLUDE (bron kesishuvi) | `409 SLOT_TAKEN` |
| `23505` | UNIQUE | `409` + domen kodi |
| `23514` | CHECK | `422` + domen kodi |
| `23503` | FK | `409` + domen kodi |

Ishlanmagan sqlstate foydalanuvchiga 500 chiqaradi — yangi konstreynt
qo'shilganda xarita ham to'ldiriladi.
