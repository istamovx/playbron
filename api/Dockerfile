FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY pyproject.toml ./
COPY src ./src
COPY migrations ./migrations
COPY scripts ./scripts
COPY alembic.ini ./

# Prod'da test bog'liqliklari kerak emas
RUN pip install --upgrade pip && pip install -e .

EXPOSE 8000

# Render `$PORT` beradi; lokalda 8000. Migratsiya start'dan oldin bajariladi —
# Render'ning bepul rejasida alohida `preDeployCommand` yo'q.
#
# `--forwarded-allow-ips='*'` — Render LB manzillari barqaror emas, ularni
# ro'yxatga kiritib bo'lmaydi. Oqibati: `request.client.host` XFF'ning mijoz
# boshqaradigan eng chap elementidan olinadi va unga ISHONIB BO'LMAYDI.
# Xavfsizlikka daxldor IP kod ichida XFF'ning eng o'ng elementidan olinadi
# (src/playbron/core/http.py dagi `client_ip`).
CMD ["sh", "-c", "alembic upgrade head && uvicorn playbron.main:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers --forwarded-allow-ips='*'"]
