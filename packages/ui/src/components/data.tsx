import { useState, type CSSProperties, type ReactNode } from 'react';

import { formatSum, type Sum } from '../format';
import { useNarrow } from '../hooks';
import { Icon, normalizeTone, type Tone } from './primitives';

/** SystemX `components/data/*.jsx` va `Metric.jsx` dan aynan ko'chirilgan. */

export type MetricTone = 'neutral' | 'med' | 'high';

function metricTone(tone: Tone | MetricTone | undefined): MetricTone {
  if (tone === 'med' || tone === 'high' || tone === 'neutral') return tone;
  const normalized = normalizeTone(tone);
  if (normalized === 'danger') return 'high';
  if (normalized === 'amber') return 'med';
  return 'neutral';
}

/**
 * Kichik ko'rsatkich plitasi: 4px 8px 5px padding, hairline chegara, chamfer.
 * Yorliq `--fs-micro`, qiymat `--fs-2xl` — bu katta "card" emas.
 */
export function MetricCell({
  label,
  value,
  tone,
  style,
}: {
  label: string;
  value: ReactNode;
  tone?: Tone | MetricTone;
  style?: CSSProperties;
}): ReactNode {
  const resolved = metricTone(tone);
  const color =
    resolved === 'high' ? 'var(--risk-high)' : resolved === 'med' ? 'var(--risk-low)' : 'var(--fg-1)';

  return (
    <div
      style={{
        position: 'relative',
        minWidth: 62,
        padding: '4px 8px 5px',
        background: 'var(--surface-panel-quiet)',
        border: '1px solid var(--line-2)',
        borderRadius: 'var(--r-1)',
        clipPath: 'var(--clip-tr)',
        ...style,
      }}
    >
      <div
        style={{
          font: 'var(--type-label)',
          fontSize: 'var(--fs-micro)',
          letterSpacing: 'var(--ls-label)',
          textTransform: 'uppercase',
          color: 'var(--text-label)',
        }}
      >
        {label}
      </div>
      <div style={{ font: 'var(--type-metric)', fontSize: 'var(--fs-2xl)', color, lineHeight: 1.1 }}>
        {value}
      </div>
    </div>
  );
}

/**
 * Katta ko'rsatkich plitasi (`components/charts/StatTile.jsx`):
 * ikonka + yorliq, ostida `--fs-3xl` qiymat va birlik.
 */
export function StatTile({
  label,
  value,
  unit,
  icon,
  style,
}: {
  label: string;
  value: ReactNode;
  unit?: string;
  icon?: string;
  style?: CSSProperties;
}): ReactNode {
  return (
    <div
      style={{
        padding: '10px 12px 12px',
        background: 'var(--surface-panel-quiet)',
        minWidth: 0,
        border: '1px solid var(--line-1)',
        borderRadius: 'var(--r-1)',
        clipPath: 'var(--clip-tr)',
        ...style,
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 6, minWidth: 0 }}>
        {icon ? <Icon name={icon} size={13} color="var(--fg-3)" /> : null}
        <span
          style={{
            font: 'var(--type-label)',
            letterSpacing: 'var(--ls-label)',
            textTransform: 'uppercase',
            color: 'var(--text-label)',
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            whiteSpace: 'nowrap',
          }}
        >
          {label}
        </span>
      </div>

      <div style={{ display: 'flex', alignItems: 'flex-end', gap: 7, minWidth: 0 }}>
        <span
          style={{
            font: 'var(--type-metric)',
            fontSize: 'var(--fs-3xl)',
            color: 'var(--fg-1)',
            lineHeight: 1,
            // Pul qiymati hech qachon ikki qatorga bo'linmaydi
            whiteSpace: 'nowrap',
            minWidth: 0,
          }}
        >
          {value}
        </span>
        {unit ? (
          <span style={{ font: 'var(--type-data-xs)', color: 'var(--fg-3)', marginBottom: 3 }}>
            {unit}
          </span>
        ) : null}
      </div>
    </div>
  );
}

/**
 * Yorliq → qiymat qatori: `--field-h` balandlik, `--surface-field` fon,
 * hairline chegara. Qiymat doim mono (`--type-data`).
 */
export function FieldRow({
  label,
  value,
  tone,
  dots,
  children,
  style,
}: {
  label?: string;
  value?: ReactNode;
  tone?: Tone;
  dots?: boolean;
  /** Qabul qilinadi, lekin ta'sir qilmaydi — qiymat SystemX'da doim mono. */
  mono?: boolean;
  children?: ReactNode;
  style?: CSSProperties;
}): ReactNode {
  const normalized = normalizeTone(tone);
  const valueColor =
    normalized === 'violet'
      ? 'var(--text-accent)'
      : normalized === 'danger'
        ? 'var(--risk-crit)'
        : normalized === 'success'
          ? 'var(--green-400)'
          : normalized === 'amber'
            ? 'var(--amber-400)'
            : 'var(--fg-1)';

  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: 6,
        minHeight: 'var(--field-h)',
        padding: '0 10px',
        background: 'var(--surface-field)',
        border: '1px solid var(--line-1)',
        borderRadius: 'var(--r-1)',
        ...style,
      }}
    >
      {label ? (
        <span style={{ font: 'var(--type-body-sm)', color: 'var(--fg-3)', flex: 'none' }}>
          {label}:
        </span>
      ) : null}
      {dots ? (
        <span
          style={{
            width: 9,
            height: 11,
            backgroundImage: 'var(--bg-dots)',
            backgroundSize: '4px 4px',
            opacity: 0.6,
            flex: 'none',
          }}
        />
      ) : null}
      <span
        style={{
          font: 'var(--type-data)',
          color: valueColor,
          marginLeft: 'auto',
          overflow: 'hidden',
          textOverflow: 'ellipsis',
          whiteSpace: 'nowrap',
        }}
      >
        {value}
      </span>
      {children}
    </div>
  );
}

/** Ladder — FieldRow'lar 2px oraliq bilan (dizayndagi detal panellari). */
export function FieldLadder({ children }: { children: ReactNode }): ReactNode {
  return <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>{children}</div>;
}

/** Pul: mono, 3 xonali guruh, valyuta yorlig'i alohida. */
export function Money({ value, currency = false }: { value: Sum; currency?: boolean }): ReactNode {
  return (
    <span style={{ font: 'var(--type-data)', letterSpacing: '.03em' }}>
      {formatSum(value)}
      {currency ? (
        <span
          style={{
            font: 'var(--type-label)',
            letterSpacing: 'var(--ls-label)',
            color: 'var(--text-muted)',
            marginLeft: 4,
          }}
        >
          SO‘M
        </span>
      ) : null}
    </span>
  );
}

/** 3px progress chizig'i — `--chart-track` ustida rangli qism. */
export function ProgressMeter({
  percent,
  color = 'var(--primary-100)',
  tip,
}: {
  percent: number;
  color?: string;
  /** Sichqoncha tekkanda ko'rsatiladigan matn. Berilmasa tooltip chiqmaydi
   * (`ActivityBars`dagi bilan bir xil naqsh). */
  tip?: () => string;
}): ReactNode {
  const clamped = Math.max(0, Math.min(100, Math.round(percent)));
  const [hover, setHover] = useState(false);
  const tipText = tip && hover ? tip() : null;

  return (
    <div
      role="progressbar"
      aria-valuenow={clamped}
      aria-valuemin={0}
      aria-valuemax={100}
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => setHover(false)}
      style={{
        height: 3,
        background: 'var(--chart-track)',
        position: 'relative',
        overflow: tipText !== null ? 'visible' : 'hidden',
        cursor: tip ? 'default' : undefined,
      }}
    >
      {tipText !== null ? (
        <span
          style={{
            position: 'absolute',
            bottom: 'calc(100% + 8px)',
            left: `${clamped}%`,
            transform: 'translateX(-50%)',
            padding: '4px 8px',
            background: 'var(--surface-raised)',
            border: '1px solid var(--line-2)',
            clipPath: 'var(--clip-tr)',
            boxShadow: 'var(--shadow-pop)',
            font: 'var(--type-data)',
            color: 'var(--text-title)',
            whiteSpace: 'nowrap',
            pointerEvents: 'none',
            zIndex: 2,
          }}
        >
          {tipText}
        </span>
      ) : null}
      <div
        className="pb-fill"
        style={{
          position: 'absolute',
          inset: '0 auto 0 0',
          width: `${clamped}%`,
          background: color,
        }}
      />
    </div>
  );
}

function seeded(seed: number): () => number {
  let state = seed;
  return () => (state = (state * 16807) % 2147483647) / 2147483647;
}

/**
 * Ustun balandligiga qarab binafsha shkala — past qiymat so'nik, yuqorisi yorqin.
 * Faqat brend tokenlari ishlatiladi, hardcode rang yo'q.
 */
function ramp(share: number): string {
  if (share > 0.85) return 'var(--primary-100)';
  if (share > 0.65) return 'var(--primary-200)';
  if (share > 0.45) return 'var(--primary-400)';
  if (share > 0.25) return 'var(--primary-600)';
  return 'var(--primary-700)';
}

/**
 * Hajm gistogrammasi. Ustunlar kirishda pastdan o'sadi, sichqoncha tekkanda
 * yorishadi; `active` berilsa o'sha ustun urg'uli va sekin pulsatsiya qiladi.
 * Balandligiga qarab uch bosqichli kontrast — grafik tekis kulrang bo'lib qolmaydi.
 */
export function ActivityBars({
  seed = 3,
  bars = 44,
  height = 54,
  labels,
  values,
  active,
  tip,
  style,
}: {
  seed?: number;
  bars?: number;
  height?: number;
  labels?: string[];
  /** Tashqi qiymatlar (0…1). Berilmasa seed bo'yicha hosil qilinadi. */
  values?: number[];
  /** Joriy ustun indeksi — urg'u va pulsatsiya shunga tushadi. */
  active?: number;
  /** Sichqoncha tekkanda ko'rsatiladigan matn. Berilmasa tooltip chiqmaydi. */
  tip?: (value: number, index: number) => string;
  style?: CSSProperties;
}): ReactNode {
  const random = seeded(seed);
  const data =
    values ??
    Array.from({ length: bars }, (_, index) => 0.18 + (index / bars) * 0.35 + random() * 0.45);
  const ticks = labels ?? ['12:00', '02:00', '04:00', '06:00', '08:00', '10:00'];
  const peak = Math.max(...data);
  const [hover, setHover] = useState<number | null>(null);

  const shown = hover;
  const tipText = tip && shown !== null ? tip(data[shown] as number, shown) : null;

  return (
    <div style={style}>
      <div
        onMouseLeave={() => setHover(null)}
        style={{
          position: 'relative',
          display: 'flex',
          alignItems: 'flex-end',
          gap: 3,
          height,
          borderBottom: '1px solid var(--line-2)',
        }}
      >
        {tipText !== null && shown !== null ? (
          <span
            style={{
              position: 'absolute',
              bottom: '100%',
              // Chetdagi ustunlarda ham panel ichida qoladi
              left: `${Math.min(94, Math.max(6, ((shown + 0.5) / data.length) * 100))}%`,
              transform: 'translate(-50%, -8px)',
              padding: '4px 8px',
              background: 'var(--surface-raised)',
              border: '1px solid var(--line-2)',
              clipPath: 'var(--clip-tr)',
              boxShadow: 'var(--shadow-pop)',
              font: 'var(--type-data)',
              color: 'var(--text-title)',
              whiteSpace: 'nowrap',
              pointerEvents: 'none',
              zIndex: 2,
            }}
          >
            {tipText}
          </span>
        ) : null}

        {data.map((value, index) => {
          const share = peak === 0 ? 0 : value / peak;
          const now = index === active;
          const lit = index === hover;

          return (
            <i
              key={index}
              onMouseEnter={() => setHover(index)}
              className={now ? 'pb-bar pb-bar-now' : 'pb-bar'}
              style={{
                flex: 1,
                height: `${Math.min(1, value) * 100}%`,
                background: lit ? 'var(--purple-100)' : now ? 'var(--purple-100)' : ramp(share),
                boxShadow: now || lit ? 'var(--glow-violet-sm)' : undefined,
                // Ustunlar birin-ketin ko'tariladi — chapdan o'ngga to'lqin
                animationDelay: `${Math.min(index * 22, 700)}ms`,
              }}
            />
          );
        })}
      </div>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 7 }}>
        {ticks.map((tick, index) => (
          <span
            key={`${tick}-${index}`}
            style={{ font: 'var(--type-data-xs)', fontSize: 'var(--fs-xs)', color: 'var(--fg-4)' }}
          >
            {tick}
          </span>
        ))}
      </div>
    </div>
  );
}

export interface Column<T> {
  key: string;
  header: string;
  render: (row: T) => ReactNode;
  align?: 'left' | 'right';
}

/**
 * Jadval. Telefon kengligida gorizontal scroll o'rniga har bir qator kartaga
 * aylanadi: birinchi ustun sarlavha, qolganlari yorliq/qiymat juftligi,
 * sarlavhasiz ustun (amallar) pastda butun kenglikda.
 */
export function EntityTable<T>({
  columns,
  rows,
  rowKey,
  empty = 'Ma’lumot yo‘q',
}: {
  columns: Column<T>[];
  rows: T[];
  rowKey: (row: T) => string;
  empty?: string;
}): ReactNode {
  const narrow = useNarrow();

  if (rows.length === 0) {
    return (
      <div
        style={{
          border: '1px dashed var(--line-2)',
          padding: 'var(--card-pad)',
          color: 'var(--text-muted)',
          font: 'var(--type-body-sm)',
          textAlign: 'center',
        }}
      >
        {empty}
      </div>
    );
  }

  if (narrow) {
    const [lead, ...rest] = columns;
    const fields = rest.filter((column) => column.header !== '');
    const actions = rest.filter((column) => column.header === '');

    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--gap-tight)' }}>
        {rows.map((row) => (
          <div
            key={rowKey(row)}
            style={{
              padding: 'var(--card-pad)',
              background: 'var(--surface-card)',
              border: '1px solid var(--line-1)',
              display: 'flex',
              flexDirection: 'column',
              gap: 8,
              minWidth: 0,
            }}
          >
            {lead ? (
              <div style={{ font: 'var(--type-body)', color: 'var(--text-title)', minWidth: 0 }}>
                {lead.render(row)}
              </div>
            ) : null}

            <div style={{ display: 'flex', flexDirection: 'column', gap: 5 }}>
              {fields.map((column) => (
                <div
                  key={column.key}
                  style={{
                    display: 'flex',
                    alignItems: 'baseline',
                    justifyContent: 'space-between',
                    gap: 10,
                    minWidth: 0,
                  }}
                >
                  <span
                    style={{
                      flex: 'none',
                      font: 'var(--type-label)',
                      letterSpacing: 'var(--ls-label)',
                      textTransform: 'uppercase',
                      color: 'var(--text-label)',
                    }}
                  >
                    {column.header}
                  </span>
                  <span
                    style={{
                      minWidth: 0,
                      textAlign: 'right',
                      font: 'var(--type-body-sm)',
                      color: 'var(--text-body)',
                    }}
                  >
                    {column.render(row)}
                  </span>
                </div>
              ))}
            </div>

            {actions.length > 0 ? (
              <div
                style={{
                  display: 'flex',
                  flexWrap: 'wrap',
                  justifyContent: 'flex-end',
                  gap: 6,
                  paddingTop: 6,
                  borderTop: '1px solid var(--line-1)',
                }}
              >
                {actions.map((column) => (
                  <span key={column.key}>{column.render(row)}</span>
                ))}
              </div>
            ) : null}
          </div>
        ))}
      </div>
    );
  }

  return (
    <div style={{ overflowX: 'auto' }}>
      <table style={{ width: '100%', borderCollapse: 'collapse', minWidth: 480 }}>
        <thead>
          <tr>
            {columns.map((column) => (
              <th
                key={column.key}
                style={{
                  textAlign: column.align ?? 'left',
                  padding: '7px 10px',
                  borderBottom: '1px solid var(--line-2)',
                  font: 'var(--type-label)',
                  fontSize: 'var(--fs-micro)',
                  letterSpacing: 'var(--ls-label)',
                  textTransform: 'uppercase',
                  color: 'var(--text-label)',
                  whiteSpace: 'nowrap',
                }}
              >
                {column.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={rowKey(row)}>
              {columns.map((column) => (
                <td
                  key={column.key}
                  style={{
                    textAlign: column.align ?? 'left',
                    padding: '7px 10px',
                    borderBottom: '1px solid var(--line-1)',
                    font: 'var(--type-body-sm)',
                    color: 'var(--text-body)',
                  }}
                >
                  {column.render(row)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
