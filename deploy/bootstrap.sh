#!/usr/bin/env bash
#
# Toza Hetzner serverini PlayBron uchun tayyorlaydi. BIR MARTA yuriladi.
#
#   ssh root@<server-ip>
#   apt-get update && apt-get install -y git
#   git clone <repo> /opt/playbron
#   cd /opt/playbron/deploy && ./bootstrap.sh
#
# Idempotent: qayta yurgizsa bo'ladi.
set -Eeuo pipefail

[[ $EUID -eq 0 ]] || { echo "root kerak" >&2; exit 1; }

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "══ 1/6  Tizim yangilanishi ══"
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get upgrade -y -qq
apt-get install -y -qq ca-certificates curl git ufw rsync age unattended-upgrades

echo "══ 2/6  Vaqt zonasi ══"
timedatectl set-timezone Asia/Tashkent
echo "  $(date)"

echo "══ 3/6  Docker ══"
if ! command -v docker >/dev/null; then
  curl -fsSL https://get.docker.com | sh
else
  echo "  allaqachon o'rnatilgan"
fi
systemctl enable --now docker

echo "══ 4/6  Firewall ══"
# Faqat SSH va veb. Postgres (5432) va Redis (6379) TASHQARIGA
# UMUMAN ochilmaydi — ular compose tarmog'i ichida qoladi.
ufw --force reset >/dev/null
ufw default deny incoming
ufw default allow outgoing
ufw allow 22/tcp   comment 'SSH'
ufw allow 80/tcp   comment 'HTTP (Let us Encrypt)'
ufw allow 443/tcp  comment 'HTTPS'
ufw allow 443/udp  comment 'HTTP/3'
ufw --force enable
ufw status numbered | sed 's/^/  /'

echo "══ 5/6  Swap ══"
# 4 GB RAM'da Postgres + Redis + API + build — swap bo'lgani ma'qul,
# aks holda `pnpm build` OOM bilan o'ldiriladi.
if ! swapon --show | grep -q .; then
  fallocate -l 2G /swapfile
  chmod 600 /swapfile
  mkswap /swapfile >/dev/null
  swapon /swapfile
  grep -q '/swapfile' /etc/fstab || echo '/swapfile none swap sw 0 0' >> /etc/fstab
  # Serverda swap faqat zaxira sifatida kerak
  sysctl -w vm.swappiness=10 >/dev/null
  grep -q 'vm.swappiness' /etc/sysctl.conf || echo 'vm.swappiness=10' >> /etc/sysctl.conf
  echo "  2 GB swap yoqildi"
else
  echo "  allaqachon bor"
fi

echo "══ 6/6  Xavfsizlik yangilanishlari ══"
dpkg-reconfigure -f noninteractive unattended-upgrades >/dev/null 2>&1 || true
systemctl enable --now unattended-upgrades >/dev/null 2>&1 || true
echo "  avtomatik xavfsizlik yangilanishlari yoqildi"

cat <<'TXT'

════════════════════════════════════════════════════════════════
SERVER TAYYOR. Keyingi qadamlar:

  1. Sozlamani to'ldiring:
       cp /opt/playbron/deploy/.env.prod.example /opt/playbron/deploy/.env.prod
       chmod 600 /opt/playbron/deploy/.env.prod
       nano /opt/playbron/deploy/.env.prod

     Tasodifiy parollar:
       openssl rand -hex 32     # har bir parol/sekret uchun alohida

  2. DNS'ni shu serverga qarating (A yozuvlar):
       playbron.uz  www  app  mini  api   ->  <server-ip>

     TEKSHIRING (DNS tarqalmasdan Caddy sertifikat ololmaydi):
       dig +short api.playbron.uz

  3. Ishga tushiring:
       cd /opt/playbron/deploy && ./deploy.sh

  4. Zaxirani sozlang:
       cd /opt/playbron/deploy/backup && ./install.sh

════════════════════════════════════════════════════════════════
TXT
