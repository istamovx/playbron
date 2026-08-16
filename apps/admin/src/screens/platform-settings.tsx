import type { ReactNode } from 'react';

/**
 * Sozlamalar (super admin) — ATAYLAB bo'shatildi.
 *
 * Loyiha egasining so'rovi (2026-08-16): "sahifani 0 qil, nima qilishni
 * keyin aytaman" — avvalgi Hisob/Parolni almashtirish paneli olib
 * tashlandi, keyingi ko'rsatmani kutmoqda. Parol almashtirish ehtiyoji
 * yo'qolmagan — `store/session.ts::changePassword` va `login.tsx`dagi
 * majburiy almashtirish oqimi tegilmagan, faqat bu ekran bo'shatildi.
 */
export function PlatformSettingsScreen(): ReactNode {
  return null;
}
