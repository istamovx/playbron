#!/usr/bin/env bash
#
# Uchala frontendni yig'adi va Caddy o'qiydigan `deploy/www/` ga qo'yadi.
#
# Yig'ish KONTEYNER ichida bo'ladi — serverga Node/pnpm o'rnatish shart
# emas va yig'ish muhiti har safar bir xil bo'ladi.
#
# `VITE_*` qiymatlari BUILD paytida kodga singdiriladi, shuning uchun
# ular `.env.prod` dan shu yerda uzatiladi (ish vaqtida o'qilmaydi).
set -Eeuo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(dirname "$HERE")"

[[ -r "$HERE/.env.prod" ]] || { echo "deploy/.env.prod topilmadi" >&2; exit 1; }
set -a && . "$HERE/.env.prod" && set +a

: "${VITE_API_URL:?VITE_API_URL kerak}"
: "${VITE_LANDING_URL:?VITE_LANDING_URL kerak}"
: "${SITE_URL:?SITE_URL kerak}"

echo "  API manzili: $VITE_API_URL"

docker run --rm \
  -v "$ROOT:/w" \
  -w /w \
  -e VITE_API_URL="$VITE_API_URL" \
  -e VITE_LANDING_URL="$VITE_LANDING_URL" \
  -e SITE_URL="$SITE_URL" \
  -e CI=1 \
  node:22-alpine sh -eu -c '
    corepack enable
    pnpm install --frozen-lockfile --prefer-offline
    pnpm --filter admin build
    pnpm --filter miniapp build
    pnpm --filter landing build
  '

# Caddy `/srv/{admin,mini,landing}` dan o'qiydi
mkdir -p "$HERE/www"
for pair in "admin:apps/admin/dist" "mini:apps/miniapp/dist" "landing:apps/landing/dist"; do
  name="${pair%%:*}"; src="$ROOT/${pair#*:}"
  [[ -d "$src" ]] || { echo "Yig'ilmadi: $src" >&2; exit 1; }
  # `rsync --delete` — eski bundle'lar qolib ketmasin
  rsync -a --delete "$src/" "$HERE/www/$name/"
  echo "  www/$name  ($(find "$HERE/www/$name" -type f | wc -l) fayl)"
done
