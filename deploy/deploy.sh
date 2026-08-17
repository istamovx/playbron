#!/usr/bin/env bash
#
# PlayBron — yangi versiyani chiqarish.
#
#   cd /opt/playbron/deploy && ./deploy.sh
#   ./deploy.sh --no-pull      # git pull qilmasdan (lokal o'zgarish bilan)
#
# Ketma-ketlik ATAYLAB shunday:
#   kod olish -> frontend yig'ish -> API image -> MIGRATSIYA -> API almashtirish
#
# Migratsiya API'dan OLDIN va ALOHIDA yuradi. Aks holda bir nechta API
# nusxasi bir vaqtda `alembic upgrade` yurgizib bir-birini bosardi.
set -Eeuo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(dirname "$HERE")"
cd "$HERE"

[[ -r .env.prod ]] || { echo "deploy/.env.prod topilmadi (.env.prod.example dan nusxa oling)" >&2; exit 1; }

COMPOSE=(docker compose -f docker-compose.prod.yml --env-file .env.prod)
PULL=1
[[ "${1:-}" == "--no-pull" ]] && PULL=0

step() { printf '\n══ %s ══\n' "$*"; }

if (( PULL )); then
  step "Kod olinmoqda"
  git -C "$ROOT" pull --ff-only
fi

# Image tegi commit'dan — qaysi versiya jonli ekani doim aniq bo'lsin
IMAGE_TAG="$(git -C "$ROOT" rev-parse --short HEAD)"
export IMAGE_TAG
echo "  versiya: $IMAGE_TAG"

step "Frontend yig'ilmoqda"
./build-web.sh

step "API image quriladi"
"${COMPOSE[@]}" build api

step "MIGRATSIYA"
# `--exit-code-from` bilan: migratsiya yiqilsa deploy SHU YERDA to'xtaydi
# va eski API ishlab turaveradi (buzuq sxema bilan yangi kod ko'tarilmaydi).
if ! "${COMPOSE[@]}" --profile migrate run --rm migrate; then
  echo >&2
  echo "MIGRATSIYA YIQILDI — deploy to'xtatildi, eski nusxa ishlab turibdi." >&2
  echo "Loglarni ko'ring, tuzating va qaytadan urinib ko'ring." >&2
  exit 1
fi

step "Servislar ko'tarilmoqda"
"${COMPOSE[@]}" up -d --remove-orphans

step "Sog'liq tekshiruvi"
ok=0
for i in $(seq 1 30); do
  if "${COMPOSE[@]}" exec -T api python -c "
import urllib.request, sys
sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/healthz', timeout=5).status == 200 else 1)
" 2>/dev/null; then ok=1; break; fi
  sleep 3
done

if (( ok )); then
  echo "  API javob beryapti"
else
  echo "  API JAVOB BERMADI — loglar:" >&2
  "${COMPOSE[@]}" logs --tail 60 api >&2
  exit 1
fi

step "Tashqaridan tekshiruv"
for url in https://api.playbron.uz/healthz https://app.playbron.uz/ https://mini.playbron.uz/ https://playbron.uz/; do
  code=$(curl -sS -o /dev/null -w '%{http_code}' --max-time 20 "$url" 2>/dev/null || echo 000)
  printf '  %-34s %s\n' "$url" "$code"
done

# Eski image'lar diskni yeb qo'ymasin
docker image prune -f --filter 'until=168h' >/dev/null 2>&1 || true

printf '\nDEPLOY TAYYOR — versiya %s\n' "$IMAGE_TAG"
