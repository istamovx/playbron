import { Button } from '@playbron/ui';
import type { ClubDto } from '@playbron/api-client';
import type { ReactNode } from 'react';

import { useT } from '../i18n';
import { openExternalLink } from '../lib/telegram';

/** Manzil qidiruvi — klub xarita havolasini kiritmagan bo'lsa. */
const searchUrl = (club: ClubDto): string =>
  `https://yandex.uz/maps/?text=${encodeURIComponent(`${club.name} ${club.address}`.trim())}`;

/**
 * Manzilni xaritada ochadigan FAQAT-BELGILI tugma (loyiha egasi,
 * 2026-08-17: asosiy menyuda klub rasmi emas, nomi/manzili/ish vaqti va
 * xarita tugmasi bo'lsin).
 *
 * O'zbekistonda Yandex Xaritalar keng tarqalgan — klubning `yandexMapsUrl`
 * i bo'lsa birinchi o'rinda, bo'lmasa `googleMapsUrl`. Ikkalasi ham
 * kiritilmagan bo'lsa manzil bo'yicha QIDIRUV havolasi ochiladi: bu
 * o'ylab topilgan koordinata emas, klub o'zi kiritgan manzil matni.
 * Manzil ham bo'sh bo'lsa tugma umuman chizilmaydi.
 */
export function MapButton({ club }: { club: ClubDto }): ReactNode {
  const t = useT();
  const url = club.yandexMapsUrl ?? club.googleMapsUrl ?? (club.address ? searchUrl(club) : null);
  if (!url) return null;

  return (
    <Button
      variant="secondary"
      size="md"
      icon="map"
      aria-label={t('openInMaps')}
      title={t('openInMaps')}
      onClick={(event) => {
        // Klub kartasi bosilganda uning sahifasi ochiladi — xarita
        // tugmasi buni qo'zg'atmasligi kerak.
        event.stopPropagation();
        openExternalLink(url);
      }}
    />
  );
}
