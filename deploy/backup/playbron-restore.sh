#!/usr/bin/env bash
#
# PlayBron — zaxiradan tiklash.
#
# Bu skript BUZUVCHI: mavjud bazani almashtiradi. Shuning uchun har bir
# qadam ekranga chiqadi va tasdiq so'raladi.
#
#   playbron-restore.sh /var/backups/playbron/daily/playbron-2026...dump
#   playbron-restore.sh --into playbron_sinov <fayl>   # mashq uchun
#
# `--into` bilan boshqa bazaga tiklanadi — ishlayotgan tizimga TEGMAYDI.
# Oyiga bir marta aynan shu usulda mashq qilib turing: tiklab ko'rilmagan
# zaxira — hali zaxira emas.
set -Eeuo pipefail

CONFIG="${PLAYBRON_BACKUP_ENV:-/etc/playbron/backup.env}"
[[ -r "$CONFIG" ]] || { echo "Sozlama topilmadi: $CONFIG" >&2; exit 1; }
# shellcheck source=/dev/null
set -a && . "$CONFIG" && set +a

TARGET_DB="$DB_NAME"
if [[ "${1:-}" == "--into" ]]; then TARGET_DB="$2"; shift 2; fi

ARCHIVE="${1:-}"
[[ -n "$ARCHIVE" && -r "$ARCHIVE" ]] || {
  echo "Foydalanish: $0 [--into <baza>] <zaxira-fayli>" >&2
  echo >&2
  echo "Mavjud zaxiralar:" >&2
  find "${BACKUP_DIR:-/var/backups/playbron}" -name 'playbron-*' -printf '%TY-%Tm-%Td %10s  %p\n' 2>/dev/null |
    sort -r | head -20 >&2
  exit 1
}

compose() { docker compose --project-directory "$COMPOSE_DIR" "$@"; }

WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

# Shifr ochilgandan keyin `$ARCHIVE` vaqtinchalik faylga o'zgaradi —
# rollar faylini topish uchun ASL nom kerak.
ORIGINAL_ARCHIVE="$ARCHIVE"

# ── Shifr ochish ──────────────────────────────────────────────────────────
if [[ "$ARCHIVE" == *.age ]]; then
  KEY="${AGE_SECRET_KEY_FILE:-/root/.config/playbron-age.key}"
  [[ -r "$KEY" ]] || { echo "Maxfiy kalit topilmadi: $KEY" >&2; exit 1; }
  echo "Shifr ochilmoqda…"
  age -d -i "$KEY" -o "$WORK/restore.dump" "$ARCHIVE"
  ARCHIVE="$WORK/restore.dump"
fi

# ── Nima tiklanayotganini KO'RSATISH ──────────────────────────────────────
echo
echo "Zaxira: $ARCHIVE"
echo "Hajm:   $(numfmt --to=iec "$(stat -c%s "$ARCHIVE")")"
echo
echo "Ichidagi asosiy jadvallar:"
compose exec -T "$DB_SERVICE" pg_restore --list < "$ARCHIVE" |
  grep 'TABLE DATA' | awk '{print "  " $6}' | sort | head -30
echo

if [[ "$TARGET_DB" == "$DB_NAME" ]]; then
  echo "!!! DIQQAT: ISHLAYOTGAN baza '$DB_NAME' TO'LIQ ALMASHTIRILADI !!!"
  echo "Mashq qilmoqchi bo'lsangiz: $0 --into playbron_sinov $ARCHIVE"
else
  echo "Nishon: '$TARGET_DB' (ishlayotgan baza tegilmaydi)"
fi
echo
read -r -p "Davom etilsinmi? 'ha' deb yozing: " ok
[[ "$ok" == "ha" ]] || { echo "Bekor qilindi."; exit 1; }

# ── Xavfsizlik: tiklashdan OLDIN joriy holatni dump qilib olamiz ──────────
if [[ "$TARGET_DB" == "$DB_NAME" ]]; then
  SAFETY="${BACKUP_DIR}/tiklashdan-oldin-$(date -u +%Y%m%dT%H%M%SZ).dump"
  echo "Joriy holat saqlanmoqda: $SAFETY"
  compose exec -T "$DB_SERVICE" \
    pg_dump -U "$DB_SUPERUSER" -d "$DB_NAME" -Fc --no-password > "$SAFETY"
  echo "Saqlandi (xato bo'lsa shundan qaytarasiz)."
fi

# ── Tiklash ───────────────────────────────────────────────────────────────
# Ilova konteynerini to'xtatamiz: tiklash paytida yozuv bo'lmasin.
echo "API to'xtatilmoqda…"
compose stop api 2>/dev/null || true

# ── ROLLAR (bazadan OLDIN) ────────────────────────────────────────────────
# Rollar klaster darajasida yashaydi va `pg_dump` ichiga TUSHMAYDI. Toza
# serverda ular bo'lmasa `pg_restore` birinchi `ALTER ... OWNER TO
# playbron_platform` da yiqiladi. Zaxira skripti ularni yonma-yon
# `.roles.sql` fayliga saqlaydi.
ROLES_FILE="${ARCHIVE%.dump}.roles.sql"
[[ -r "$ROLES_FILE" ]] || ROLES_FILE="${ORIGINAL_ARCHIVE%.dump.age}.roles.sql.age"

if [[ -r "$ROLES_FILE" ]]; then
  if [[ "$ROLES_FILE" == *.age ]]; then
    age -d -i "${AGE_SECRET_KEY_FILE:-/root/.config/playbron-age.key}" \
      -o "$WORK/roles.sql" "$ROLES_FILE"
    ROLES_FILE="$WORK/roles.sql"
  fi
  echo "Rollar tiklanmoqda…"
  # `ON_ERROR_STOP` ATAYLAB yoqilmagan: mavjud serverga tiklaganda rollar
  # allaqachon bor va "role already exists" KUTILGAN holat.
  compose exec -T "$DB_SERVICE" psql -U "$DB_SUPERUSER" -d postgres < "$ROLES_FILE" 2>&1 |
    grep -vi 'already exists' | tail -5 || true
  echo "  tayyor"
else
  echo "OGOHLANTIRISH: rollar fayli topilmadi."
  echo "  Toza serverga tiklayotgan bo'lsangiz pg_restore 'role does not exist'"
  echo "  bilan yiqiladi. Rollarni avval qo'lda yarating."
fi

echo "Baza qayta yaratilmoqda: $TARGET_DB"
compose exec -T "$DB_SERVICE" psql -U "$DB_SUPERUSER" -d postgres -v ON_ERROR_STOP=1 \
  -c "DROP DATABASE IF EXISTS \"$TARGET_DB\" WITH (FORCE);" \
  -c "CREATE DATABASE \"$TARGET_DB\" OWNER \"$DB_SUPERUSER\";"

echo "Tiklanmoqda…"
# `--no-owner`/`--no-privileges` EMAS: rollar va GRANT'lar aynan
# tiklanishi kerak, aks holda RLS va huquqlar buziladi.
compose exec -T "$DB_SERVICE" \
  pg_restore -U "$DB_SUPERUSER" -d "$TARGET_DB" --exit-on-error < "$ARCHIVE"

echo "API qayta ishga tushmoqda…"
compose start api 2>/dev/null || true

echo
echo "TAYYOR. Tekshiring:"
echo "  docker compose --project-directory $COMPOSE_DIR exec $DB_SERVICE \\"
echo "    psql -U $DB_SUPERUSER -d $TARGET_DB -c 'SELECT count(*) FROM bookings;'"
