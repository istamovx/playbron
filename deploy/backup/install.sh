#!/usr/bin/env bash
#
# Zaxira tizimini Hetzner serveriga o'rnatadi.
#
#   cd /opt/playbron/deploy/backup && sudo ./install.sh
#
# Idempotent: qayta-qayta yurgizsa bo'ladi. Mavjud `backup.env` USTIDAN
# YOZILMAYDI.
set -Eeuo pipefail

[[ $EUID -eq 0 ]] || { echo "root kerak: sudo ./install.sh" >&2; exit 1; }

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "== kerakli dasturlar =="
missing=()
for cmd in docker rsync curl flock numfmt; do
  command -v "$cmd" >/dev/null || missing+=("$cmd")
done
if (( ${#missing[@]} )); then
  echo "Yetishmayapti: ${missing[*]}"
  echo "O'rnating:  apt-get update && apt-get install -y rsync curl util-linux coreutils"
  exit 1
fi
command -v age >/dev/null || echo "  (age yo'q — shifrlash ishlatilmaydi; xohlasangiz: apt-get install -y age)"

echo "== skriptlar =="
install -m 755 "$HERE/playbron-backup.sh"  /usr/local/bin/playbron-backup.sh
install -m 755 "$HERE/playbron-restore.sh" /usr/local/bin/playbron-restore.sh
echo "  /usr/local/bin/playbron-backup.sh"
echo "  /usr/local/bin/playbron-restore.sh"

echo "== sozlama =="
mkdir -p /etc/playbron
if [[ -e /etc/playbron/backup.env ]]; then
  echo "  /etc/playbron/backup.env allaqachon bor — TEGILMADI"
else
  install -m 600 "$HERE/backup.env.example" /etc/playbron/backup.env
  echo "  /etc/playbron/backup.env yaratildi — QIYMATLARNI TO'LDIRING"
fi

echo "== systemd =="
install -m 644 "$HERE/playbron-backup.service" /etc/systemd/system/
install -m 644 "$HERE/playbron-backup.timer"   /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now playbron-backup.timer
echo "  timer yoqildi"

mkdir -p /var/backups/playbron/{daily,weekly,monthly}
chmod 700 /var/backups/playbron   # ichida shaxsiy ma'lumot bor

cat <<'TXT'

O'RNATILDI. Keyingi qadamlar:

  1. Sozlamani to'ldiring:
       nano /etc/playbron/backup.env

  2. Tashqi nusxa uchun Storage Box kaliti (JUDA tavsiya etiladi):
       ssh-keygen -t ed25519 -f /root/.ssh/playbron_backup -N ''
       ssh-copy-id -p 23 -i /root/.ssh/playbron_backup u123456@u123456.your-storagebox.de

  3. QO'LDA bir marta sinang (kutmasdan):
       playbron-backup.sh

  4. Natijani ko'ring:
       systemctl list-timers playbron-backup
       journalctl -u playbron-backup -n 50

  5. Oyiga bir marta TIKLASHNI mashq qiling (ishlayotgan bazaga tegmaydi):
       playbron-restore.sh --into playbron_sinov /var/backups/playbron/daily/<fayl>

TXT
