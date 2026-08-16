import type { CSSProperties, ReactNode } from 'react';

/**
 * Umumiy yuklanish indikatori (loyiha egasining so'rovi, 2026-08-16).
 * SystemX manbasidan KELMAGAN (`primitives.tsx`dagilardan farqli,
 * `/design-sync` bunga tegmaydi).
 *
 * IKKINCHI versiya: birinchisi aylanuvchi HUD halqasi + burchak
 * kvadratchalari edi — loyiha egasi rad etdi ("juda ham g'alati"). Endi
 * loyihaning O'Z terminal tiliga suyanadi (`.pb-scan` skan chizig'i,
 * `.pb-caret` kursori, `ProgressMeter` segmentlari): tik chiziqlardan
 * iborat teng o'lchamli poloса bo'ylab yorug'lik yuguradi. Aylanma
 * harakat umuman yo'q — shovqinsiz, ekran markazida tinch turadi.
 */

const BARS = 7;

export function CyberLoader({
  width = 132,
  label,
  style,
}: {
  /** Poloса kengligi (piksel). */
  width?: number;
  /** Ixtiyoriy matn — poloса ostida, uppercase/keng oraliqli. */
  label?: ReactNode;
  style?: CSSProperties;
}): ReactNode {
  return (
    <div
      style={{
        display: 'inline-flex',
        flexDirection: 'column',
        alignItems: 'center',
        gap: 14,
        ...style,
      }}
    >
      <div
        style={{
          display: 'flex',
          gap: 4,
          width,
          height: 26,
          padding: 4,
          border: '1px solid var(--line-2)',
          clipPath: 'var(--clip-tr)',
          background: 'var(--surface-inset)',
        }}
      >
        {Array.from({ length: BARS }, (_, index) => (
          <span
            key={index}
            style={{
              flex: 1,
              background: 'var(--primary-100)',
              // Har segment navbat bilan yonadi — chapdan o'ngga yuguruvchi
              // to'lqin. `steps()` emas, silliq: HUD emas, terminal sathi.
              animation: `pb-loader-wave 1.1s var(--ease-in-out) ${(index * 0.11).toFixed(2)}s infinite`,
            }}
          />
        ))}
      </div>

      {label ? (
        <span
          style={{
            font: 'var(--type-label)',
            letterSpacing: 'var(--ls-label)',
            textTransform: 'uppercase',
            color: 'var(--text-dim)',
          }}
        >
          {label}
        </span>
      ) : null}
    </div>
  );
}

/**
 * Ekranni to'ldiruvchi yuklanish holati — API kutilayotganda.
 *
 * `minHeight: '100%'` + `flex: 1` — loyiha egasining topilmasi
 * (2026-08-16): avval `minHeight: 160` edi va loader kontent maydonining
 * YUQORISIDA osilib turardi, markazda emas. Foiz `min-height` ota
 * balandligi noaniq bo'lsa `auto`ga tushadi (`height: 100%` kabi nolga
 * QISILMAYDI — `timeline.tsx`dagi xato aynan shundan edi), shuning uchun
 * `60vh` ham quyi chegara sifatida qo'yiladi.
 */
export function CyberLoaderOverlay({ label = 'Yuklanmoqda…' }: { label?: ReactNode }): ReactNode {
  return (
    <div
      style={{
        flex: 1,
        minHeight: 'max(60vh, 100%)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: 'var(--gap-panel)',
      }}
    >
      <CyberLoader label={label} />
    </div>
  );
}
