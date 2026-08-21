"""Fon vazifalari — arq worker (B-bosqich).

Nega arq (`tasks/B-fon-vazifalari.md` B0): Redis allaqachon bor, alohida
worker jarayoni bir nechta API instansiyasida vazifa ikki marta
bajarilishining oldini oladi, deploy'ga bitta servis qo'shish yetarli.

Qayerda ishlaydi: lokal `docker compose` va Hetzner
(`deploy/docker-compose.prod.yml`). Render bepul rejasida worker servisi
YO'Q — u yerda fon vazifalari ishlamaydi; Render oraliq ko'rsatuv muhiti,
maqsad Hetzner (loyiha egasining qarori, 2026-08-20).
"""
