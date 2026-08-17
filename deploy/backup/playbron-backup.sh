#!/usr/bin/env bash
#
# PlayBron — PostgreSQL zaxirasi (Hetzner VPS uchun).
#
# Ketma-ketlik: dump -> TEKSHIRUV -> shifrlash -> tashqi nusxa -> eskisini
# tozalash -> xabar.
#
# "Tekshiruv" qadami ataylab bor: tekshirilmagan zaxira — zaxira emas.
# Faylning bor-yo'g'i emas, ICHI o'qilishi va kutilgan jadvallar mavjudligi
# nazorat qilinadi. Aks holda nol baytli yoki yarim yozilgan fayl haftalab
# "muvaffaqiyatli" bo'lib turaveradi.
#
# Ishga tushirish: `playbron-backup.timer` (systemd) yoki qo'lda:
#   /usr/local/bin/playbron-backup.sh
set -Eeuo pipefail

CONFIG="${PLAYBRON_BACKUP_ENV:-/etc/playbron/backup.env}"
[[ -r "$CONFIG" ]] || { echo "Sozlama topilmadi: $CONFIG" >&2; exit 1; }
# shellcheck source=/dev/null
set -a && . "$CONFIG" && set +a

: "${COMPOSE_DIR:?COMPOSE_DIR kerak}"
: "${DB_SERVICE:=postgres}"
: "${DB_SUPERUSER:?DB_SUPERUSER kerak}"
: "${DB_NAME:?DB_NAME kerak}"
: "${BACKUP_DIR:=/var/backups/playbron}"
: "${KEEP_DAILY:=14}"
: "${KEEP_WEEKLY:=8}"
: "${KEEP_MONTHLY:=6}"
: "${NOTIFY_ON_SUCCESS:=0}"

STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
DOW="$(date -u +%u)"    # 7 = yakshanba
DOM="$(date -u +%d)"

# Kunlik/haftalik/oylik — bitta dump, uchta papkaga qattiq havola (hard
# link). Ya'ni joy bir marta band bo'ladi, lekin saqlash muddati har xil.
if [[ "$DOM" == "01" ]]; then TIER=monthly
elif [[ "$DOW" == "7" ]]; then TIER=weekly
else TIER=daily; fi

WORK="$(mktemp -d)"
FAILED_STEP="boshlanmadi"

log() { printf '[%s] %s\n' "$(date -u +%H:%M:%S)" "$*"; }

notify() {
  local text="$1"
  [[ -n "${TELEGRAM_BOT_TOKEN:-}" && -n "${TELEGRAM_CHAT_ID:-}" ]] || return 0
  curl -sS --max-time 15 -o /dev/null \
    "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
    --data-urlencode "chat_id=${TELEGRAM_CHAT_ID}" \
    --data-urlencode "text=${text}" || true
}

cleanup() { rm -rf "$WORK"; }
on_error() {
  local code=$?
  cleanup
  log "YIQILDI (qadam: $FAILED_STEP, kod: $code)"
  notify "🔴 PlayBron zaxirasi YIQILDI
Server: $(hostname)
Qadam: ${FAILED_STEP}
Vaqt: ${STAMP}

journalctl -u playbron-backup -n 50"
  exit "$code"
}
trap on_error ERR
trap cleanup EXIT

mkdir -p "$BACKUP_DIR"/{daily,weekly,monthly}

# Bir vaqtda ikkita zaxira yurmasin (sekin tashqi nusxa cho'zilib ketsa).
# Qulf ATAYLAB `BACKUP_DIR` ichida: `/var/lock` hamma tizimda ham
# mavjud emas va u yerda skript tushunarsiz joyda yiqilardi.
#
# `flock` yo'qligi va qulf bandligi ATAYLAB ajratilgan: ilgari ikkalasi
# bitta shoxda edi va `flock` o'rnatilmagan tizimda skript "oldingi
# zaxira hali tugamagan" degan YOLG'ON sabab bilan jimgina chiqib
# ketardi — ya'ni zaxira hech qachon olinmasdi va buni hech kim sezmasdi.
if command -v flock >/dev/null; then
  exec 9>"$BACKUP_DIR/.backup.lock"
  if ! flock -n 9; then
    log "Oldingi zaxira hali tugamagan — o'tkazib yuborildi"
    exit 0
  fi
else
  log "OGOHLANTIRISH: flock yo'q — bir vaqtda ikkita zaxira yurishi mumkin"
fi

# ── 1. Dump ───────────────────────────────────────────────────────────────
FAILED_STEP="pg_dump"
DUMP="$WORK/playbron-${STAMP}.dump"
log "pg_dump boshlandi (rol: $DB_SUPERUSER)"

# `-Fc` — siqilgan, `pg_restore` bilan tanlab tiklash mumkin.
#
# Rol SUPERUSER bo'lishi SHART: jadvallarda `FORCE ROW LEVEL SECURITY` bor
# va u EGAGA HAM tegishli. `pg_dump` ma'lumotni to'liq olish uchun
# `SET row_security = off` qiladi — buni faqat superuser/BYPASSRLS uddalaydi.
# Oddiy rol bilan quyidagi xato chiqadi (sinalgan):
#   ERROR: query would be affected by row-level security policy for table "users"
docker compose --project-directory "$COMPOSE_DIR" exec -T "$DB_SERVICE" \
  pg_dump -U "$DB_SUPERUSER" -d "$DB_NAME" -Fc --no-password > "$DUMP"

SIZE=$(stat -c%s "$DUMP")
log "dump tayyor: $(numfmt --to=iec "$SIZE")"

# ── 2. TEKSHIRUV ──────────────────────────────────────────────────────────
# Uch bosqich: hajm -> ichki tuzilma -> kutilgan jadvallar.
FAILED_STEP="zaxira tekshiruvi"

(( SIZE > 20000 )) || { log "dump juda kichik ($SIZE bayt)"; false; }

# `pg_restore --list` faylni to'liq o'qiydi — kesilgan/buzilgan arxiv shu
# yerda ushlanadi (tiklash paytida emas).
TOC="$WORK/toc.txt"
docker compose --project-directory "$COMPOSE_DIR" exec -T "$DB_SERVICE" \
  pg_restore --list < "$DUMP" > "$TOC"

# Asosiy jadvallar dump ichida BO'LISHI shart. Bu "sxema bor, ma'lumot
# yo'q" holatini ham, noto'g'ri bazani dump qilishni ham ushlaydi.
for tbl in users clubs bookings orders memberships; do
  grep -q "TABLE DATA public $tbl " "$TOC" || {
    log "dump ichida '$tbl' ma'lumoti yo'q"; false
  }
done
log "tekshiruv o'tdi ($(wc -l < "$TOC") ta obyekt)"

# ── 3. Shifrlash (ixtiyoriy) ──────────────────────────────────────────────
FINAL="$DUMP"
if [[ -n "${AGE_PUBLIC_KEY:-}" ]]; then
  FAILED_STEP="shifrlash"
  command -v age >/dev/null || { log "age o'rnatilmagan"; false; }
  age -r "$AGE_PUBLIC_KEY" -o "$DUMP.age" "$DUMP"
  FINAL="$DUMP.age"
  log "shifrlandi"
fi

# ── 4. Saqlash + qattiq havolalar ─────────────────────────────────────────
FAILED_STEP="mahalliy saqlash"
NAME="$(basename "$FINAL")"
cp "$FINAL" "$BACKUP_DIR/$TIER/$NAME"
# Kunlik nusxa doim bo'lsin (haftalik/oylik ham kunlik ro'yxatda ko'rinadi)
[[ "$TIER" == "daily" ]] || ln -f "$BACKUP_DIR/$TIER/$NAME" "$BACKUP_DIR/daily/$NAME"
log "saqlandi: $TIER/$NAME"

# ── 5. Tashqi nusxa ───────────────────────────────────────────────────────
if [[ -n "${REMOTE_TARGET:-}" ]]; then
  FAILED_STEP="tashqi nusxa"
  log "tashqariga yuborilmoqda"
  rsync -a --timeout=120 \
    -e "ssh -p ${REMOTE_SSH_PORT:-22} -i ${REMOTE_SSH_KEY} -o StrictHostKeyChecking=accept-new" \
    "$BACKUP_DIR/$TIER/$NAME" "$REMOTE_TARGET/$TIER/"
  log "tashqi nusxa tayyor"
else
  log "OGOHLANTIRISH: REMOTE_TARGET sozlanmagan — zaxira FAQAT shu serverda"
fi

# ── 6. Eskisini tozalash ──────────────────────────────────────────────────
FAILED_STEP="eskilarini tozalash"
prune() {
  local dir="$1" keep="$2"
  # Nomda UTC vaqt tamg'asi bor, ya'ni nom bo'yicha saralash = vaqt bo'yicha
  local total; total=$(find "$dir" -maxdepth 1 -type f -name 'playbron-*' | wc -l)
  (( total > keep )) || return 0
  find "$dir" -maxdepth 1 -type f -name 'playbron-*' | sort | head -n -"$keep" |
    while read -r old; do rm -f -- "$old"; log "o'chirildi: $(basename "$old")"; done
}
prune "$BACKUP_DIR/daily" "$KEEP_DAILY"
prune "$BACKUP_DIR/weekly" "$KEEP_WEEKLY"
prune "$BACKUP_DIR/monthly" "$KEEP_MONTHLY"

FAILED_STEP=""
log "TAYYOR"

if [[ "$NOTIFY_ON_SUCCESS" == "1" ]]; then
  notify "🟢 PlayBron zaxirasi tayyor
Hajm: $(numfmt --to=iec "$SIZE")
Tur: ${TIER}
Tashqi nusxa: $([[ -n "${REMOTE_TARGET:-}" ]] && echo "bor" || echo "YO'Q")"
fi
