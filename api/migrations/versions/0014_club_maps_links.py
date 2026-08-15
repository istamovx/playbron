"""Klub xarita havolalari — Google Maps va Yandex Maps.

Loyiha egasining so'rovi (2026-08-16): klub admini klub ma'lumotini
kiritishda Google/Yandex Maps havolasini ham qo'shsin; mijoz ilovasida
shu havola bo'yicha ochiladigan "Manzil" tugmasi navigatorga yo'naltiradi.

`clubs`da allaqachon `lat`/`lng` (Numeric) ustunlari bor edi, lekin ular
hech qayerda ishlatilmaydi va hozir ham tegilmaydi — xom havolani saqlash
ancha ishonchli: qisqartirilgan (`maps.app.goo.gl/...`) havolalarda
koordinata umuman yo'q, uni ajratib olish server tomonida qo'shimcha
tarmoq so'rovisiz mumkin emas. Havola o'zi to'g'ridan-to'g'ri "Manzil"
tugmasida ochiladi — Google/Yandex ilovasi o'rnatilgan bo'lsa native
ilovaga o'tkazadi, aks holda brauzerda.

Xavfsizlik: havola keyin BOSHQA foydalanuvchi (mijoz) tomonidan ochiladi,
shuning uchun faqat `https://` bilan boshlanishi CHECK bilan majburlanadi —
`javascript:`/`data:` sxemasi orqali saqlanadigan havola orqali hujum
imkoniyati yopiladi. API qatlamida ham xuddi shu tekshiruv takrorlanadi
(`bookings/service.py::update_club`).

RLS/GRANT o'zgarmaydi: bu ikkita ustun `clubs`ning MAVJUD qator darajasidagi
policy'lari ostida — ular ustun emas, qator asosida ishlaydi, `address`/`about`
kabi ustunlar allaqachon ochiq. `0003_rls_hardening.py` faqat `status`
ustunini alohida `REVOKE UPDATE` qilgan, boshqa hech narsa cheklanmagan.

Revision ID: 0014_club_maps_links
Revises: 0013_pos
"""

import sqlalchemy as sa
from alembic import op

revision = "0014_club_maps_links"
down_revision = "0013_pos"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        sa.text(
            """
            ALTER TABLE clubs ADD COLUMN google_maps_url text;
            ALTER TABLE clubs ADD COLUMN yandex_maps_url text;

            ALTER TABLE clubs ADD CONSTRAINT clubs_google_maps_url_https_ck
                CHECK (google_maps_url IS NULL OR google_maps_url LIKE 'https://%');
            ALTER TABLE clubs ADD CONSTRAINT clubs_yandex_maps_url_https_ck
                CHECK (yandex_maps_url IS NULL OR yandex_maps_url LIKE 'https://%');
            """
        )
    )


def downgrade() -> None:
    raise NotImplementedError("PlayBron migratsiyalari faqat oldinga")
