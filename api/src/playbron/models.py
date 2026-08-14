"""Faza 1 modellari: identity, tenancy, sessiya, tarif.

Domen jadvallari (xona, bron, hisob…) keyingi fazalarda qo'shiladi —
`docs/01-architecture.md` dagi ER sxemasi bo'yicha.
"""

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from playbron.core.db import Base

# ── Rollar ────────────────────────────────────────────────────────────────
ROLE_OWNER = "OWNER"
ROLE_ADMIN = "ADMIN"
ROLE_STAFF = "STAFF"
CLUB_ROLES = (ROLE_OWNER, ROLE_ADMIN, ROLE_STAFF)

# ── Holatlar ──────────────────────────────────────────────────────────────
ORG_PENDING = "pending"
ORG_ACTIVE = "active"
ORG_SUSPENDED = "suspended"

CLUB_DRAFT = "draft"
CLUB_ACTIVE = "active"
CLUB_SUSPENDED = "suspended"


class User(Base):
    """Global identity — **ikki dunyo bitta jadvalda** (`docs/05-auth-redesign.md`).

    `kind` o'zgarmas diskriminator:
      • `customer` → `telegram_id` bilan tanaladi, `login` va parol yo'q
      • `staff`    → `login` bilan tanaladi, `telegram_id` NULL
                     (Telegram alohida `staff_telegram` jadvalida)

    Ajratish DB'da CHECK va kompozit FK bilan majburlanadi; `kind` ustuni ilova
    roli uchun `REVOKE UPDATE` qilingan, ya'ni kod xatosi bilan o'zgarmaydi.
    """

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    kind: Mapped[str] = mapped_column(Text, default="customer")
    # Qisman UNIQUE indeks: `WHERE kind = 'customer'`
    telegram_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    # Qisman UNIQUE indeks: `lower(login) WHERE kind = 'staff'`
    login: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, default="active")
    username: Mapped[str | None] = mapped_column(String(64))
    first_name: Mapped[str] = mapped_column(String(128), default="")
    # Botda tasdiqlangan ism. `first_name` Telegram profilidan keladi va uni
    # foydalanuvchi to'liq nazorat qiladi — ko'rsatish uchun shu maydon.
    display_name: Mapped[str | None] = mapped_column(String(128))
    last_name: Mapped[str | None] = mapped_column(String(128))
    language_code: Mapped[str | None] = mapped_column(String(8))
    photo_url: Mapped[str | None] = mapped_column(Text)

    # initData telefonni bermaydi — bot `requestContact` orqali to'ldiradi
    phone: Mapped[str | None] = mapped_column(String(20))
    phone_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Tasdiq abadiy emas — raqam boshqa odamga berilishi mumkin (§4.7)
    phone_reverified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    tg_blocked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # `Membership` da `users` ga ikkita FK bor (`user_id`, `invited_by`) —
    # qaysi biri bo'yicha bog'lanishini aniq ko'rsatish shart
    memberships: Mapped[list["Membership"]] = relationship(
        back_populates="user",
        foreign_keys="Membership.user_id",
    )


class SuperAdmin(Base):
    """Platforma egasi. **Faqat seed** — UI orqali qo'shilmaydi."""

    __tablename__ = "super_admins"

    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    note: Mapped[str | None] = mapped_column(Text)
    granted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Plan(Base):
    """Tarif. Limit va funksiyalar DB'da — kodda qotirilmaydi."""

    __tablename__ = "plans"

    code: Mapped[str] = mapped_column(String(32), primary_key=True)
    title: Mapped[str] = mapped_column(String(64))
    price_month: Mapped[int] = mapped_column(BigInteger)
    price_year: Mapped[int] = mapped_column(BigInteger)
    limits: Mapped[dict] = mapped_column(JSONB, default=dict)
    features: Mapped[list] = mapped_column(JSONB, default=list)
    sort: Mapped[int] = mapped_column(Integer, default=0)
    is_public: Mapped[bool] = mapped_column(Boolean, default=True)


class Organization(Base):
    """Tenant. Klub egasiga tegishli, bir yoki bir nechta klubni saqlaydi."""

    __tablename__ = "organizations"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    owner_user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), index=True)
    name: Mapped[str] = mapped_column(String(160))
    status: Mapped[str] = mapped_column(String(16), default=ORG_PENDING, index=True)

    # Faza 1 da tarif shu yerda. Faza 5 da `subscriptions` jadvali manba bo'ladi
    # va bu ustun undan hosil qilinadi.
    plan_code: Mapped[str | None] = mapped_column(String(32), ForeignKey("plans.code"))

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    clubs: Mapped[list["Club"]] = relationship(back_populates="org")


class Club(Base):
    """Klub — tenant ichidagi asosiy birlik. Barcha domen jadvallari `club_id` bilan."""

    __tablename__ = "clubs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    org_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(160))
    address: Mapped[str] = mapped_column(Text, default="")
    phone: Mapped[str | None] = mapped_column(String(20))
    cover_url: Mapped[str | None] = mapped_column(Text)
    about: Mapped[str] = mapped_column(Text, default="")

    # Ish vaqti yarim tundan daqiqada; 26*60 = ertalabki 02:00
    opens_at_min: Mapped[int] = mapped_column(Integer, default=600)
    closes_at_min: Mapped[int] = mapped_column(Integer, default=1560)
    timezone: Mapped[str] = mapped_column(String(64), default="Asia/Tashkent")

    lat: Mapped[float | None] = mapped_column(Numeric(9, 6))
    lng: Mapped[float | None] = mapped_column(Numeric(9, 6))
    status: Mapped[str] = mapped_column(String(16), default=CLUB_DRAFT, index=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    org: Mapped[Organization] = relationship(back_populates="clubs")


class ClubPaymentCredentials(Base):
    """Bron to'lovi klub hisobiga tushadi — merchant kalitlari shu yerda.

    Ataylab `clubs` dan ajratilgan: RLS ustun darajasida ishlamaydi, `clubs` esa
    `status='active'` bo'lganda anonim o'qiladi (mijoz klublar ro'yxati). Kalitlar
    o'sha jadvalda qolsa har qanday `SELECT *` ularni tashqariga chiqarardi.
    """

    __tablename__ = "club_payment_credentials"

    club_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("clubs.id", ondelete="CASCADE"), primary_key=True
    )
    provider: Mapped[str] = mapped_column(String(16))
    credentials: Mapped[dict] = mapped_column(JSONB)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class Membership(Base):
    """Foydalanuvchi × klub × rol.

    Mijoz bu yerda **bo'lmaydi** — u global. Membership faqat qo'shimcha rol beradi,
    shuning uchun bitta `telegram_id` A klubda STAFF, B klubda mijoz bo'la oladi.
    """

    __tablename__ = "memberships"
    __table_args__ = (
        UniqueConstraint("user_id", "club_id", name="memberships_user_club_uk"),
        Index("memberships_club_role_ix", "club_id", "role"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    club_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("clubs.id", ondelete="CASCADE"), index=True
    )
    role: Mapped[str] = mapped_column(String(16))
    status: Mapped[str] = mapped_column(String(16), default="active")
    invited_by: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped[User] = relationship(back_populates="memberships", foreign_keys=[user_id])


class RefreshToken(Base):
    """Opaque refresh token. DB'da faqat SHA-256 xeshi turadi."""

    __tablename__ = "refresh_tokens"
    __table_args__ = (Index("refresh_tokens_user_ix", "user_id", "revoked_at"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Rotatsiya zanjiri — o'g'irlangan token qayta ishlatilsa aniqlanadi
    replaced_by: Mapped[str | None] = mapped_column(String(64))
    user_agent: Mapped[str | None] = mapped_column(Text)
    ip: Mapped[str | None] = mapped_column(String(45))


class AuditLog(Base):
    """Xavfli va cross-tenant amallar izi."""

    __tablename__ = "audit_log"
    __table_args__ = (Index("audit_log_org_at_ix", "org_id", "at"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    actor_user_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id"))
    org_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("organizations.id"))
    action: Mapped[str] = mapped_column(String(64), index=True)
    target: Mapped[str | None] = mapped_column(String(128))
    before: Mapped[dict | None] = mapped_column(JSONB)
    after: Mapped[dict | None] = mapped_column(JSONB)
    ip: Mapped[str | None] = mapped_column(String(45))
    user_agent: Mapped[str | None] = mapped_column(Text)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
