"""HTTP so'rov yordamchilari."""

from fastapi import Request


def client_ip(request: Request) -> str | None:
    """Xavfsizlikka daxldor joylar uchun ishonchli mijoz IP'si.

    Render LB manzillari barqaror emas, shuning uchun uvicorn
    `--forwarded-allow-ips='*'` bilan yuradi — bu holatda `request.client.host`
    `X-Forwarded-For` ning **eng chap** elementidan olinadi, uni esa mijoz o'zi
    yozib yuborishi mumkin. Ishonchli qiymat — **eng o'ng** element: uni so'rovni
    bizga yetkazgan LB'ning o'zi qo'shadi, mijoz unga ta'sir qilolmaydi.
    Proksisiz (lokal) muhitda sarlavha bo'lmaydi — haqiqiy peer IP qaytadi.
    """
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.rsplit(",", 1)[-1].strip() or None
    return request.client.host if request.client else None
