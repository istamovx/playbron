"""`audit_log` yozuvchisi — xavfli/muhim CRUD amallar izi.

Production-readiness audit (2026-08-16, loyiha egasining so'rovi: "super
admin va klub adminida o'ziga hos bo'lgan loglar yursin"): `audit_log`
jadvali va uning RLS'i (`0001_core.py`, qattiqlashtirilgan `0003_rls_
hardening.py`, `club_id` + o'qish policy'si kengaytirilgan `0005_two_
worlds_auth.py`) ANCHADAN to'g'ri sozlangan edi — klub OWNER/ADMIN o'z
`club_id`sidagi, tashkilot egasi o'z `org_id`sidagi (`club_id IS NULL`)
qatorlarni allaqachon o'qiy olardi. Yetishmayotgani FAQAT yozuvchi edi:
`grep -r "INSERT INTO audit_log" src/` bo'sh natija berardi.

**Chaqiruvchining tranzaksiyasidan ATAYLAB MUSTAQIL** — o'z alohida
sessiyasini ochadi, chaqiruvchining `session`iga hech qachon yozmaydi.
Birinchi urinish chaqiruvchining sessiyasi ICHIDA `SAVEPOINT` bilan edi,
lekin amalda sinovlarda navbatdagi, umuman aloqasi yo'q so'rovlarni ham
"current transaction is aborted" bilan buzib qo'ydi — sabab aniq
bo'lmasa-da (asyncpg pool'idagi ulanish savepoint'dan keyin ham "iflos"
holda qaytgan bo'lishi mumkin), natija bir xil: log yozuvi ASOSIY
amalning ishonchliligiga umuman ta'sir qilmasligi kerak edi, aksincha
bo'ldi. Alohida ulanish bu xavfni butunlay yo'qotadi — narxi: agar
chaqiruvchining ASOSIY tranzaksiyasi keyinroq (log yozilgandan SO'NG)
boshqa sababdan orqaga qaytarilsa, log yozuvi baribir qoladi. Bu audit
yozuvi uchun qabul qilinadigan kelishuv (`docs/06-super-admin.md`dagi
kabi — "eng yaxshi urinish", HAKAM emas).
"""

from __future__ import annotations

import json
import logging
from typing import Any

from sqlalchemy import text

from playbron.core import context
from playbron.core.db import AppSession

log = logging.getLogger("playbron.audit")


async def log_action(
    *,
    action: str,
    target: str | None = None,
    org_id: int | None = None,
    club_id: int | None = None,
    before: dict[str, Any] | None = None,
    after: dict[str, Any] | None = None,
    ip: str | None = None,
    user_agent: str | None = None,
) -> None:
    """`audit_log`ga bitta yozuv qo'shadi — chaqiruvchini HECH QACHON to'xtatmaydi.

    RLS `audit_log_insert` policy'si yagona shartni tekshiradi:
    `WITH CHECK (actor_user_id = app_user_id())` — shuning uchun bu yerda
    HAR DOIM joriy `context.current().user_id` ishlatiladi.
    """
    actor_user_id = context.current().user_id
    try:
        async with AppSession() as session, session.begin():
            await session.execute(
                text("SELECT set_config('app.user_id', :user_id, true)"),
                {"user_id": str(actor_user_id or 0)},
            )
            await session.execute(
                text(
                    "INSERT INTO audit_log"
                    " (actor_user_id, org_id, club_id, action, target, before, after,"
                    "  ip, user_agent)"
                    " VALUES (:actor, :org, :club, :action, :target,"
                    "         CAST(:before AS jsonb), CAST(:after AS jsonb), :ip, :ua)"
                ),
                {
                    "actor": actor_user_id,
                    "org": org_id,
                    "club": club_id,
                    "action": action,
                    "target": target,
                    "before": json.dumps(before) if before is not None else None,
                    "after": json.dumps(after) if after is not None else None,
                    "ip": ip,
                    "ua": user_agent,
                },
            )
    except Exception:  # noqa: BLE001 — atayin keng: log yozuvi hech qachon 500 bermasin
        log.warning("audit_log yozib bo'lmadi: action=%s target=%s", action, target, exc_info=True)
