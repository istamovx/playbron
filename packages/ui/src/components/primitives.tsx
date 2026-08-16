import { useState, type ButtonHTMLAttributes, type CSSProperties, type ReactNode } from 'react';

/**
 * SystemX komponentlari — claude.ai/design "SystemX" loyihasidagi manbadan
 * (`components/primitives/*.jsx`) aynan ko'chirilgan. Qiymatlarni o'zgartirmang:
 * dizayn manbai o'zgarsa, `/design-sync` orqali qayta olinadi.
 */

// ─────────────────────────────── Icon ───────────────────────────────

export interface IconProps {
  name: string;
  size?: number;
  variant?: 'fill' | 'line' | 'none';
  color?: string;
  style?: CSSProperties;
}

/** Remix Icon (`ri-*`) yoki Material Symbols Rounded (FILL=1). */
export function Icon({
  name,
  size = 16,
  variant = 'fill',
  color = 'currentColor',
  style,
}: IconProps): ReactNode {
  const base: CSSProperties = {
    fontSize: size,
    lineHeight: 1,
    width: size,
    height: size,
    display: 'inline-flex',
    alignItems: 'center',
    justifyContent: 'center',
    flex: 'none',
    color,
    userSelect: 'none',
    overflow: 'hidden',
    fontStyle: 'normal',
    ...style,
  };

  if (name.startsWith('ri-')) {
    const className =
      variant === 'none' || /-(line|fill)$/.test(name)
        ? name
        : `${name}-${variant === 'line' ? 'line' : 'fill'}`;
    return <i aria-hidden className={className} style={base} />;
  }

  return (
    <span
      aria-hidden
      className="material-symbols-rounded"
      style={{
        ...base,
        fontFamily: 'var(--font-icon)',
        fontVariationSettings: `'FILL' 1, 'wght' 400, 'GRAD' 0, 'opsz' 24`,
      }}
    >
      {name}
    </span>
  );
}

// ─────────────────────────────── Button ───────────────────────────────

export type ButtonVariant = 'primary' | 'secondary' | 'ghost' | 'outline' | 'danger';
export type ButtonSize = 'sm' | 'md' | 'lg';

const BUTTON_VARIANTS: Record<
  ButtonVariant,
  { bg: string; border: string; fg: string; hover: string; glow: string }
> = {
  primary: {
    bg: 'var(--surface-accent)',
    border: 'var(--border-accent)',
    fg: 'var(--text-on-accent)',
    hover: 'var(--surface-accent-hover)',
    glow: 'var(--glow-violet-sm)',
  },
  secondary: {
    bg: 'var(--surface-field)',
    border: 'var(--line-2)',
    fg: 'var(--fg-1)',
    hover: 'var(--surface-press)',
    glow: 'none',
  },
  ghost: {
    bg: 'transparent',
    border: 'transparent',
    fg: 'var(--fg-3)',
    hover: 'var(--surface-hover)',
    glow: 'none',
  },
  outline: {
    bg: 'transparent',
    border: 'var(--border-accent)',
    fg: 'var(--text-accent)',
    hover: 'var(--surface-selected)',
    glow: 'none',
  },
  danger: {
    bg: 'color-mix(in srgb,var(--risk-high) 12%,transparent)',
    border: 'var(--risk-high)',
    fg: 'var(--risk-crit)',
    hover: 'color-mix(in srgb,var(--risk-high) 22%,transparent)',
    glow: 'none',
  },
};

const BUTTON_SIZES: Record<ButtonSize, { h: string; px: string; fs: string; icon: number }> = {
  sm: { h: 'var(--control-h-sm)', px: '8px', fs: 'var(--fs-xs)', icon: 12 },
  md: { h: 'var(--control-h)', px: 'var(--control-px)', fs: 'var(--fs-sm)', icon: 14 },
  lg: { h: 'var(--control-h-lg)', px: 'var(--control-px-lg)', fs: 'var(--fs-md)', icon: 16 },
};

export interface ButtonProps extends Omit<ButtonHTMLAttributes<HTMLButtonElement>, 'type'> {
  variant?: ButtonVariant;
  size?: ButtonSize;
  icon?: string;
  iconRight?: string;
  block?: boolean;
  /** 14px 45° yuqori-o'ng chamfer. */
  notch?: boolean;
  type?: 'button' | 'submit';
}

export function Button({
  children,
  variant = 'secondary',
  size = 'md',
  icon,
  iconRight,
  block,
  disabled,
  notch,
  style,
  type = 'button',
  ...rest
}: ButtonProps): ReactNode {
  const v = BUTTON_VARIANTS[variant];
  const s = BUTTON_SIZES[size];
  const [hover, setHover] = useState(false);
  const [down, setDown] = useState(false);

  return (
    <button
      type={type}
      disabled={disabled}
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => {
        setHover(false);
        setDown(false);
      }}
      onMouseDown={() => setDown(true)}
      onMouseUp={() => setDown(false)}
      style={{
        display: block ? 'flex' : 'inline-flex',
        width: block ? '100%' : undefined,
        alignItems: 'center',
        justifyContent: 'center',
        gap: 6,
        height: s.h,
        padding: `0 ${s.px}`,
        font: 'var(--type-control)',
        fontSize: s.fs,
        fontWeight: 'var(--fw-medium)' as CSSProperties['fontWeight'],
        letterSpacing: 'var(--ls-title)',
        whiteSpace: 'nowrap',
        color: disabled ? 'var(--fg-4)' : v.fg,
        background: disabled ? 'var(--surface-panel-quiet)' : hover && !down ? v.hover : v.bg,
        border: `1px solid ${disabled ? 'var(--line-1)' : v.border}`,
        borderRadius: 'var(--r-1)',
        cursor: disabled ? 'not-allowed' : 'pointer',
        boxShadow: hover && !disabled ? v.glow : 'none',
        transform: down && !disabled ? 'translateY(1px)' : 'none',
        transition: 'var(--t-control),transform var(--dur-1) var(--ease-out)',
        clipPath: notch ? 'var(--clip-tr)' : undefined,
        ...style,
      }}
      {...rest}
    >
      {icon ? <Icon name={icon} size={s.icon} /> : null}
      {children ? <span>{children}</span> : null}
      {iconRight ? <Icon name={iconRight} size={s.icon} /> : null}
    </button>
  );
}

// ─────────────────────────────── Chip ───────────────────────────────

export interface ChipProps {
  children: ReactNode;
  selected?: boolean;
  /** Eski nom — `selected` bilan bir xil. */
  active?: boolean;
  onClick?: () => void;
  style?: CSSProperties;
}

export function Chip({ children, selected, active, onClick, style }: ChipProps): ReactNode {
  const [hover, setHover] = useState(false);
  const on = selected ?? active ?? false;
  const interactive = typeof onClick === 'function';

  return (
    <span
      onClick={onClick}
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => setHover(false)}
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        height: 'var(--control-h-sm)',
        padding: '0 9px',
        font: 'var(--type-control)',
        fontSize: 'var(--fs-xs)',
        color: on ? 'var(--text-accent)' : hover && interactive ? 'var(--fg-1)' : 'var(--fg-2)',
        background: on
          ? 'var(--surface-selected)'
          : hover && interactive
            ? 'var(--chart-track)'
            : 'transparent',
        border: `1px solid ${on ? 'var(--border-accent)' : 'var(--line-2)'}`,
        borderRadius: 'var(--r-1)',
        cursor: interactive ? 'pointer' : 'default',
        transition: 'var(--t-control)',
        ...style,
      }}
    >
      {children}
    </span>
  );
}

// ─────────────────────────────── Tag ───────────────────────────────

export type TagTone = 'neutral' | 'violet' | 'amber' | 'danger' | 'success';
/** Eski nomlar ham qabul qilinadi. */
export type Tone = TagTone | 'accent' | 'ok' | 'warn';

const TAG_TONES: Record<TagTone, { fg: string; bg: string; bd: string }> = {
  neutral: { fg: 'var(--fg-2)', bg: 'var(--surface-hover)', bd: 'var(--line-2)' },
  violet: {
    fg: 'var(--text-on-accent)',
    bg: 'var(--surface-accent)',
    bd: 'var(--border-accent)',
  },
  amber: {
    fg: 'var(--amber-400)',
    bg: 'color-mix(in srgb,var(--amber-400) 14%,transparent)',
    bd: 'color-mix(in srgb,var(--amber-400) 50%,transparent)',
  },
  danger: {
    fg: 'var(--risk-crit)',
    bg: 'color-mix(in srgb,var(--risk-high) 14%,transparent)',
    bd: 'color-mix(in srgb,var(--risk-high) 50%,transparent)',
  },
  success: {
    fg: 'var(--green-400)',
    bg: 'color-mix(in srgb,var(--green-400) 12%,transparent)',
    bd: 'color-mix(in srgb,var(--green-400) 45%,transparent)',
  },
};

export function normalizeTone(tone: Tone | undefined): TagTone {
  switch (tone) {
    case 'accent':
      return 'violet';
    case 'ok':
      return 'success';
    case 'warn':
      return 'amber';
    case undefined:
      return 'neutral';
    default:
      return tone;
  }
}

export function Tag({
  children,
  tone = 'neutral',
  icon,
  style,
}: {
  children: ReactNode;
  tone?: Tone;
  icon?: string;
  style?: CSSProperties;
}): ReactNode {
  const t = TAG_TONES[normalizeTone(tone)];

  return (
    <span
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: 5,
        height: 20,
        padding: '0 7px',
        font: 'var(--type-control)',
        fontSize: 'var(--fs-xs)',
        color: t.fg,
        whiteSpace: 'nowrap',
        background: t.bg,
        border: `1px solid ${t.bd}`,
        borderRadius: 'var(--r-1)',
        ...style,
      }}
    >
      {icon ? <Icon name={icon} size={11} /> : null}
      {children}
    </span>
  );
}

// ─────────────────────────────── StatusLine ───────────────────────────────

const STATUS_TONES: Record<string, string> = {
  neutral: 'var(--text-muted)',
  violet: 'var(--text-accent)',
  accent: 'var(--text-accent)',
  amber: 'var(--amber-400)',
  warn: 'var(--amber-400)',
  danger: 'var(--risk-crit)',
  success: 'var(--green-400)',
  ok: 'var(--green-400)',
};

/** Nuqta bilan ajratilgan ALL CAPS holat qatori. */
export function StatusLine({
  parts,
  children,
  tone = 'neutral',
  icon,
  align = 'left',
  style,
}: {
  parts?: ReactNode | ReactNode[];
  children?: ReactNode;
  tone?: Tone;
  icon?: string;
  align?: 'left' | 'center' | 'right';
  style?: CSSProperties;
}): ReactNode {
  const color = STATUS_TONES[tone] ?? 'var(--text-muted)';
  const source = parts ?? children;
  const list = Array.isArray(source) ? source : [source];

  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: 6,
        flexWrap: 'wrap',
        justifyContent: align === 'center' ? 'center' : align === 'right' ? 'flex-end' : 'flex-start',
        font: 'var(--type-label)',
        fontSize: 'var(--fs-xs)',
        letterSpacing: 'var(--ls-caps)',
        textTransform: 'uppercase',
        color,
        ...style,
      }}
    >
      {icon ? <Icon name={icon} size={13} color={color} /> : null}
      {list.map((part, index) => (
        // Ajratuvchi "·" belgisi olib tashlandi — uzun matn ikki qatorga
        // tushganda qatordagi birinchi so'z bilan qo'shilib chiroyli
        // ko'rinmasdi (loyiha egasining topilmasi, 2026-08-16).
        <span key={index}>{part}</span>
      ))}
    </div>
  );
}

// ─────────────────────────────── Tabs ───────────────────────────────

/** Ekran ichidagi bo'lim tanlagich. `chamfer` — 36px balandlik va yuqori-o'ng kesim. */
export function Tabs({
  items = [],
  value,
  onChange,
  variant = 'chamfer',
  style,
}: {
  items: string[];
  value: string;
  onChange?: (label: string) => void;
  variant?: 'chamfer' | 'flat';
  style?: CSSProperties;
}): ReactNode {
  return (
    <div
      role="tablist"
      style={{
        display: 'flex',
        alignItems: 'flex-end',
        gap: variant === 'chamfer' ? 3 : 2,
        ...style,
      }}
    >
      {items.map((label) => (
        <Tab
          key={label}
          label={label}
          active={label === value}
          variant={variant}
          onClick={() => onChange?.(label)}
        />
      ))}
    </div>
  );
}

function Tab({
  label,
  active,
  variant,
  onClick,
}: {
  label: string;
  active: boolean;
  variant: 'chamfer' | 'flat';
  onClick: () => void;
}): ReactNode {
  const [hover, setHover] = useState(false);

  return (
    <button
      type="button"
      role="tab"
      aria-selected={active}
      onClick={onClick}
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => setHover(false)}
      style={{
        height: variant === 'chamfer' ? 36 : 30,
        padding: '0 18px',
        font: 'var(--type-control)',
        fontSize: 'var(--fs-md)',
        color: active ? 'var(--text-on-accent)' : hover ? 'var(--fg-1)' : 'var(--fg-3)',
        background: active
          ? 'var(--violet-600)'
          : hover
            ? 'var(--chart-track)'
            : 'var(--surface-panel-quiet)',
        border: `1px solid ${active ? 'var(--border-accent)' : 'var(--line-1)'}`,
        borderBottom:
          variant === 'chamfer' ? 'none' : `1px solid ${active ? 'var(--border-accent)' : 'var(--line-1)'}`,
        borderRadius: 'var(--r-1) var(--r-1) 0 0',
        clipPath: variant === 'chamfer' ? 'var(--clip-tr)' : undefined,
        cursor: 'pointer',
        transition: 'var(--t-control)',
        boxShadow: active ? 'var(--glow-violet-sm)' : 'none',
      }}
    >
      {label}
    </button>
  );
}

// ─────────────────────── SegmentedControl ───────────────────────

export type SegmentItem = string | { label: string; icon?: string };

/** Qiymat — segment yorlig'i (dizayn shartnomasi shunday). */
export function SegmentedControl({
  items = [],
  value,
  onChange,
  brackets,
  size = 'md',
  style,
}: {
  items: SegmentItem[];
  value: string;
  onChange?: (label: string) => void;
  brackets?: boolean;
  size?: 'sm' | 'md';
  style?: CSSProperties;
}): ReactNode {
  const height = size === 'sm' ? 'var(--control-h-sm)' : 'var(--control-h)';

  return (
    <div style={{ display: 'inline-flex', alignItems: 'center', gap: 6, ...style }}>
      {brackets ? <Tick /> : null}
      <div style={{ display: 'inline-flex', gap: 4 }}>
        {items.map((item) => {
          const label = typeof item === 'string' ? item : item.label;
          const icon = typeof item === 'string' ? undefined : item.icon;
          return (
            <Segment
              key={label}
              label={label}
              icon={icon}
              active={label === value}
              height={height}
              onClick={() => onChange?.(label)}
            />
          );
        })}
      </div>
      {brackets ? <Tick flip /> : null}
    </div>
  );
}

function Segment({
  label,
  icon,
  active,
  height,
  onClick,
}: {
  label: string;
  icon?: string;
  active: boolean;
  height: string;
  onClick: () => void;
}): ReactNode {
  const [hover, setHover] = useState(false);

  return (
    <button
      type="button"
      onClick={onClick}
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => setHover(false)}
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: 6,
        height,
        padding: '0 10px',
        font: 'var(--type-control)',
        color: active ? 'var(--text-on-accent)' : hover ? 'var(--fg-1)' : 'var(--fg-2)',
        background: active
          ? 'var(--surface-accent)'
          : hover
            ? 'var(--surface-hover)'
            : 'transparent',
        border: `1px solid ${active ? 'var(--border-accent)' : 'var(--line-2)'}`,
        borderRadius: 'var(--r-1)',
        cursor: 'pointer',
        transition: 'var(--t-control)',
        boxShadow: active ? 'var(--glow-violet-sm)' : 'none',
      }}
    >
      {icon ? <Icon name={icon} size={13} /> : null}
      {label}
    </button>
  );
}

function Tick({ flip }: { flip?: boolean }): ReactNode {
  return (
    <span
      style={{
        display: 'inline-flex',
        gap: 3,
        opacity: 0.55,
        transform: flip ? 'scaleX(-1)' : 'none',
      }}
    >
      <i style={{ width: 1, height: 10, background: 'var(--line-3)' }} />
      <i style={{ width: 1, height: 6, background: 'var(--line-3)', alignSelf: 'center' }} />
    </span>
  );
}
