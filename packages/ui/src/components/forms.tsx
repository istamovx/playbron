import { useEffect, useRef, useState, type CSSProperties, type ReactNode } from 'react';

import { Icon } from './primitives';

/** SystemX `components/forms/{Select,TextField}.jsx` dan aynan ko'chirilgan. */

export type ControlSize = 'sm' | 'md' | 'lg';

function controlHeight(size: ControlSize): string {
  return size === 'lg'
    ? 'var(--control-h-lg)'
    : size === 'sm'
      ? 'var(--control-h-sm)'
      : 'var(--control-h)';
}

/**
 * Konsol dropdown'i: chegarali boshqaruv + chevron, menyu — absolut ro'yxat.
 * `fixedLabel` berilsa yorliq o'zgarmaydi ("Actions" naqshi).
 *
 * Sukut `size='lg'` — `TextField` balandligi hech qanday `size` moslamasisiz
 * doim `--control-h-lg`; avvalgi sukut (`'md'`) formada yonma-yon turgan
 * Select'larni Inputlardan 8px pastroq ko'rsatardi (loyiha egasining
 * topilmasi, 2026-08-16). `bookings.tsx`/`orders.tsx` buni allaqachon
 * qo'lda `size="lg"` bilan chetlab o'tgan edi — endi hammasi bir xil.
 */
export function Select({
  value,
  items = [],
  onChange,
  fixedLabel,
  size = 'lg',
  notch,
  disabled,
  style,
}: {
  value: string;
  items: string[];
  onChange?: (value: string) => void;
  fixedLabel?: string;
  size?: ControlSize;
  notch?: boolean;
  disabled?: boolean;
  style?: CSSProperties;
}): ReactNode {
  const [open, setOpen] = useState(false);
  const [hover, setHover] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const off = (event: MouseEvent): void => {
      if (ref.current && !ref.current.contains(event.target as Node)) setOpen(false);
    };
    document.addEventListener('mousedown', off);
    return () => document.removeEventListener('mousedown', off);
  }, [open]);

  return (
    <div ref={ref} style={{ position: 'relative', display: 'inline-block', ...style }}>
      <button
        type="button"
        disabled={disabled}
        onClick={() => setOpen((current) => !current)}
        onMouseEnter={() => setHover(true)}
        onMouseLeave={() => setHover(false)}
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: 10,
          width: '100%',
          height: controlHeight(size),
          padding: '0 8px 0 10px',
          font: 'var(--type-control)',
          color: disabled ? 'var(--fg-4)' : 'var(--fg-1)',
          background: hover && !disabled ? 'var(--surface-hover)' : 'var(--surface-field)',
          border: `1px solid ${open ? 'var(--border-accent)' : 'var(--line-2)'}`,
          borderRadius: 'var(--r-1)',
          cursor: disabled ? 'not-allowed' : 'pointer',
          clipPath: notch ? 'var(--clip-tr)' : undefined,
          boxShadow: open ? 'var(--glow-violet-sm)' : 'none',
          transition: 'var(--t-control)',
        }}
      >
        <span>{fixedLabel || value}</span>
        <Icon
          name="expand_more"
          size={14}
          color="var(--fg-3)"
          style={{
            transform: open ? 'rotate(180deg)' : 'none',
            transition: 'transform var(--dur-2) var(--ease-out)',
          }}
        />
      </button>

      {open ? (
        <ul
          style={{
            position: 'absolute',
            zIndex: 40,
            top: 'calc(100% + 4px)',
            left: 0,
            minWidth: '100%',
            margin: 0,
            padding: 4,
            listStyle: 'none',
            background: 'var(--surface-pop)',
            border: '1px solid var(--line-2)',
            borderRadius: 'var(--r-1)',
            boxShadow: 'var(--shadow-pop)',
          }}
        >
          {items.map((item) => (
            <li key={item}>
              <button
                type="button"
                onClick={() => {
                  setOpen(false);
                  onChange?.(item);
                }}
                onMouseEnter={(event) => {
                  event.currentTarget.style.background = 'var(--surface-hover)';
                }}
                onMouseLeave={(event) => {
                  event.currentTarget.style.background = 'transparent';
                }}
                style={{
                  display: 'block',
                  width: '100%',
                  textAlign: 'left',
                  padding: '6px 8px',
                  font: 'var(--type-control)',
                  color: item === value ? 'var(--text-accent)' : 'var(--fg-2)',
                  background: 'transparent',
                  border: 'none',
                  borderRadius: 'var(--r-1)',
                  cursor: 'pointer',
                }}
              >
                {item}
              </button>
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}

/** Bir qatorli input. Geometriya FieldRow bilan bir xil — bitta ladderda turadi. */
export function TextField({
  value,
  onChange,
  type = 'text',
  placeholder,
  label,
  icon,
  error,
  disabled,
  autoComplete,
  name,
  inputMode,
  revealable,
  onSubmitKey,
  style,
}: {
  value: string;
  onChange?: (value: string) => void;
  type?: 'text' | 'password' | 'tel' | 'number';
  placeholder?: string;
  label?: string;
  icon?: string;
  error?: string;
  disabled?: boolean;
  autoComplete?: string;
  name?: string;
  inputMode?: 'text' | 'numeric' | 'tel';
  revealable?: boolean;
  onSubmitKey?: () => void;
  style?: CSSProperties;
}): ReactNode {
  const [focus, setFocus] = useState(false);
  const [shown, setShown] = useState(false);
  const resolvedType = revealable && shown ? 'text' : type;

  return (
    <label style={{ display: 'grid', gap: 6, minWidth: 0, ...style }}>
      {label ? (
        <span
          style={{
            font: 'var(--type-label)',
            letterSpacing: 'var(--ls-label)',
            textTransform: 'uppercase',
            color: error ? 'var(--risk-high)' : focus ? 'var(--fg-2)' : 'var(--text-label)',
          }}
        >
          {label}
        </span>
      ) : null}

      <span
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 8,
          height: 'var(--control-h-lg)',
          padding: '0 10px',
          background: disabled ? 'var(--surface-panel-quiet)' : 'var(--surface-field)',
          border: `1px solid ${error ? 'var(--risk-high)' : focus ? 'var(--border-focus)' : 'var(--line-2)'}`,
          borderRadius: 'var(--r-1)',
          clipPath: 'var(--clip-tr)',
          boxShadow: focus ? 'var(--glow-violet-sm)' : 'none',
          transition: 'var(--t-control)',
        }}
      >
        {icon ? (
          <Icon name={icon} size={14} color={focus ? 'var(--violet-200)' : 'var(--fg-4)'} />
        ) : null}

        <input
          name={name}
          type={resolvedType}
          value={value}
          placeholder={placeholder}
          disabled={disabled}
          autoComplete={autoComplete}
          inputMode={inputMode}
          onChange={(event) => onChange?.(event.target.value)}
          onFocus={() => setFocus(true)}
          onBlur={() => setFocus(false)}
          onKeyDown={(event) => {
            if (event.key === 'Enter' && onSubmitKey) onSubmitKey();
          }}
          style={{
            flex: 1,
            minWidth: 0,
            background: 'transparent',
            border: 'none',
            outline: 'none',
            font: 'var(--type-data)',
            color: disabled ? 'var(--fg-4)' : 'var(--fg-1)',
          }}
        />

        {revealable ? (
          <button
            type="button"
            onClick={() => setShown((current) => !current)}
            aria-label={shown ? 'Hide' : 'Show'}
            style={{
              display: 'grid',
              placeItems: 'center',
              width: 20,
              height: 20,
              padding: 0,
              background: 'transparent',
              border: 'none',
              cursor: 'pointer',
              color: 'var(--fg-4)',
            }}
          >
            <Icon name={shown ? 'ri-eye-off' : 'ri-eye'} size={14} />
          </button>
        ) : null}
      </span>

      {error ? (
        <span style={{ font: 'var(--type-data-xs)', color: 'var(--risk-high)' }}>{error}</span>
      ) : null}
    </label>
  );
}
