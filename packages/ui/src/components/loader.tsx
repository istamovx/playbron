import type { CSSProperties, ReactNode } from 'react';

/**
 * Umumiy yuklanish indikatori — "cyber" uslubda (loyiha egasining so'rovi,
 * 2026-08-16: "Web loyihaga bitta cyber loader kerak"). SystemX manbasidan
 * KELMAGAN (`primitives.tsx`dagilardan farqli, `/design-sync` bunga
 * tegmaydi) — loyihaning o'z HUD/skanerlash naqshiga (`.pb-scan`) mos
 * qilib qurilgan: burchakli aylanuvchi halqa + markazda pulslovchi nuqta.
 */
export function CyberLoader({
  size = 56,
  label,
  style,
}: {
  /** Halqa diametri (piksel). */
  size?: number;
  /** Ixtiyoriy matn — soat ostida, uppercase/keng oraliqli. */
  label?: ReactNode;
  style?: CSSProperties;
}): ReactNode {
  const stroke = Math.max(2, Math.round(size / 20));

  return (
    <div
      style={{
        display: 'inline-flex',
        flexDirection: 'column',
        alignItems: 'center',
        gap: 12,
        ...style,
      }}
    >
      <div style={{ position: 'relative', width: size, height: size }}>
        <svg
          width={size}
          height={size}
          viewBox="0 0 100 100"
          style={{ animation: 'pb-cyber-spin 1.4s linear infinite' }}
        >
          <circle
            cx="50"
            cy="50"
            r="42"
            fill="none"
            stroke="var(--line-2)"
            strokeWidth={stroke}
          />
          <circle
            cx="50"
            cy="50"
            r="42"
            fill="none"
            stroke="var(--primary-100)"
            strokeWidth={stroke}
            strokeLinecap="square"
            strokeDasharray="66 197"
            style={{ filter: 'drop-shadow(0 0 4px var(--primary-100))' }}
          />
          {/* To'rt burchak — HUD nishonga o'xshash, teskari yo'nalishda aylanadi */}
          <g style={{ transformOrigin: '50px 50px', animation: 'pb-cyber-spin-rev 2.4s linear infinite' }}>
            {[0, 90, 180, 270].map((deg) => (
              <rect
                key={deg}
                x="47"
                y="2"
                width="6"
                height="6"
                fill="var(--primary-100)"
                transform={`rotate(${deg} 50 50)`}
              />
            ))}
          </g>
        </svg>
        <div
          style={{
            position: 'absolute',
            inset: 0,
            display: 'grid',
            placeItems: 'center',
          }}
        >
          <span
            style={{
              width: Math.round(size * 0.14),
              height: Math.round(size * 0.14),
              background: 'var(--primary-100)',
              clipPath: 'var(--clip-tr)',
              animation: 'pb-cyber-pulse 1.1s var(--ease-in-out) infinite',
            }}
          />
        </div>
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

/** To'liq ekran/panel ustiga qoplaydigan holat — API kutilayotganda. */
export function CyberLoaderOverlay({ label = 'Yuklanmoqda…' }: { label?: ReactNode }): ReactNode {
  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: 'var(--gap-panel)',
        minHeight: 160,
      }}
    >
      <CyberLoader label={label} />
    </div>
  );
}
