import type { CSSProperties, ReactNode } from 'react';

import { WORDMARK_ACCENT_PATH, WORDMARK_MAIN_PATH, WORDMARK_VIEWBOX } from './wordmark-paths';

/** So'z-belgining tabiiy nisbati (93 × 9). */
export const WORDMARK_RATIO = 93 / 9;

/**
 * PLAYBRON so'z-belgisi.
 *
 * Ranglar dizayn faylida `#5700FF` va `white` edi — ular tokenlarga bog'landi
 * (`--primary-100` va `--text-title`), shuning uchun belgi mavzu bilan birga
 * o'zgaradi va hardcode rang qolmaydi.
 *
 * O'lchamni **kenglik** bilan bering: belgi juda uzun (nisbat ≈ 10:1), balandlik
 * bo'yicha o'lchash tor ustunlarda chetdan chiqib ketadi.
 */
export function Wordmark({
  width = 160,
  accent = 'var(--primary-100)',
  color = 'var(--text-title)',
  title = 'PlayBron',
  style,
}: {
  width?: number | string;
  accent?: string;
  color?: string;
  /** Ekran o'quvchisi uchun nom. Bo'sh bo'lsa belgi bezak deb hisoblanadi. */
  title?: string;
  style?: CSSProperties;
}): ReactNode {
  return (
    <svg
      viewBox={WORDMARK_VIEWBOX}
      role={title ? 'img' : 'presentation'}
      aria-label={title || undefined}
      aria-hidden={title ? undefined : true}
      focusable="false"
      style={{
        width,
        height: 'auto',
        display: 'block',
        flex: 'none',
        ...style,
      }}
    >
      {title ? <title>{title}</title> : null}
      <path d={WORDMARK_ACCENT_PATH} fill={accent} />
      <path d={WORDMARK_MAIN_PATH} fill={color} />
    </svg>
  );
}
