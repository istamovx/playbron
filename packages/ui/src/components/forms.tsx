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
  type?: 'text' | 'password' | 'tel' | 'number' | 'date';
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

/**
 * Kalendar sana tanlagich — `input[type=date]` o'rniga: native input ba'zi
 * WebView/brauzerlarda (Telegram, eski Android) hech qanday tanlagich
 * ochmaydi, oddiy matn maydoniga aylanib qoladi (loyiha egasining
 * topilmasi, 2026-08-16 — ikki marta xabar berilgan: "kalendar hali ham
 * ochilmayapti"). `Select`dagi bilan bir xil popover naqshi.
 */
const WEEKDAYS: readonly string[] = ['Du', 'Se', 'Ch', 'Pa', 'Ju', 'Sha', 'Ya'];
const MONTHS: readonly string[] = [
  'Yanvar', 'Fevral', 'Mart', 'Aprel', 'May', 'Iyun',
  'Iyul', 'Avgust', 'Sentabr', 'Oktabr', 'Noyabr', 'Dekabr',
];

function parseDateValue(value: string): Date {
  const parsed = value ? new Date(`${value}T00:00:00`) : new Date();
  return Number.isNaN(parsed.getTime()) ? new Date() : parsed;
}

function toDateValue(d: Date): string {
  const pad = (n: number) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}

function isSameDay(a: Date, b: Date): boolean {
  return (
    a.getFullYear() === b.getFullYear() && a.getMonth() === b.getMonth() && a.getDate() === b.getDate()
  );
}

const iconBtnStyle: CSSProperties = {
  display: 'grid',
  placeItems: 'center',
  width: 24,
  height: 24,
  padding: 0,
  background: 'transparent',
  border: 'none',
  color: 'var(--fg-3)',
  cursor: 'pointer',
};

export function DatePicker({
  value,
  onChange,
  label,
  size = 'lg',
  notch,
  style,
}: {
  /** `YYYY-MM-DD`. */
  value: string;
  onChange: (value: string) => void;
  label?: string;
  size?: ControlSize;
  notch?: boolean;
  style?: CSSProperties;
}): ReactNode {
  const selected = parseDateValue(value);
  const [open, setOpen] = useState(false);
  const [cursor, setCursor] = useState(() => new Date(selected.getFullYear(), selected.getMonth(), 1));
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const off = (event: MouseEvent): void => {
      if (ref.current && !ref.current.contains(event.target as Node)) setOpen(false);
    };
    document.addEventListener('mousedown', off);
    return () => document.removeEventListener('mousedown', off);
  }, [open]);

  // Faqat ochilganda sana joriy tanlovga qaytariladi — foydalanuvchi oy
  // varag'ini varaqlab, keyin qayta ochsa oldingi joyidan boshlanmasin.
  // `selected` ATAYLAB bog'liqlik ro'yxatida emas — aks holda ochiq turgan
  // popover foydalanuvchi navigatsiya qilayotganda o'z-o'zidan boshlang'ich
  // oyga qaytib turaverardi.
  useEffect(() => {
    if (open) setCursor(new Date(selected.getFullYear(), selected.getMonth(), 1));
  }, [open]);

  const today = new Date();
  const firstOfMonth = new Date(cursor.getFullYear(), cursor.getMonth(), 1);
  const startWeekday = (firstOfMonth.getDay() + 6) % 7; // Dushanba = 0
  const daysInMonth = new Date(cursor.getFullYear(), cursor.getMonth() + 1, 0).getDate();
  const cells: Array<Date | null> = [];
  for (let i = 0; i < startWeekday; i += 1) cells.push(null);
  for (let day = 1; day <= daysInMonth; day += 1) {
    cells.push(new Date(cursor.getFullYear(), cursor.getMonth(), day));
  }
  while (cells.length % 7 !== 0) cells.push(null);

  const pad = (n: number) => String(n).padStart(2, '0');
  const formatted = `${pad(selected.getDate())}.${pad(selected.getMonth() + 1)}.${selected.getFullYear()}`;

  return (
    <div ref={ref} style={{ position: 'relative', ...style }}>
      {label ? (
        <span
          style={{
            display: 'block',
            marginBottom: 6,
            font: 'var(--type-label)',
            letterSpacing: 'var(--ls-label)',
            textTransform: 'uppercase',
            color: 'var(--text-label)',
          }}
        >
          {label}
        </span>
      ) : null}

      <button
        type="button"
        onClick={() => setOpen((current) => !current)}
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 8,
          width: '100%',
          height: controlHeight(size),
          padding: '0 10px',
          font: 'var(--type-data)',
          color: 'var(--fg-1)',
          background: 'var(--surface-field)',
          border: `1px solid ${open ? 'var(--border-accent)' : 'var(--line-2)'}`,
          borderRadius: 'var(--r-1)',
          clipPath: notch ? 'var(--clip-tr)' : undefined,
          cursor: 'pointer',
          boxShadow: open ? 'var(--glow-violet-sm)' : 'none',
          transition: 'var(--t-control)',
        }}
      >
        <Icon name="event" size={14} color="var(--fg-4)" />
        <span style={{ flex: 1, textAlign: 'left' }}>{formatted}</span>
      </button>

      {open ? (
        <div
          style={{
            position: 'absolute',
            zIndex: 40,
            top: 'calc(100% + 4px)',
            left: 0,
            width: 264,
            padding: 10,
            background: 'var(--surface-pop)',
            border: '1px solid var(--line-2)',
            borderRadius: 'var(--r-1)',
            boxShadow: 'var(--shadow-pop)',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 }}>
            <button
              type="button"
              onClick={() => setCursor(new Date(cursor.getFullYear(), cursor.getMonth() - 1, 1))}
              style={iconBtnStyle}
              aria-label="Oldingi oy"
            >
              <Icon name="chevron_left" size={16} />
            </button>
            <span style={{ font: 'var(--type-control)', color: 'var(--text-title)' }}>
              {MONTHS[cursor.getMonth()]} {cursor.getFullYear()}
            </span>
            <button
              type="button"
              onClick={() => setCursor(new Date(cursor.getFullYear(), cursor.getMonth() + 1, 1))}
              style={iconBtnStyle}
              aria-label="Keyingi oy"
            >
              <Icon name="chevron_right" size={16} />
            </button>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(7, 1fr)', gap: 2, marginBottom: 4 }}>
            {WEEKDAYS.map((w) => (
              <span key={w} style={{ textAlign: 'center', font: 'var(--type-data-xs)', color: 'var(--text-dim)' }}>
                {w}
              </span>
            ))}
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(7, 1fr)', gap: 2 }}>
            {cells.map((cell, index) => {
              if (!cell) return <span key={`empty-${index}`} />;
              const isToday = isSameDay(cell, today);
              const isSelected = isSameDay(cell, selected);
              return (
                <button
                  key={cell.getTime()}
                  type="button"
                  onClick={() => {
                    onChange(toDateValue(cell));
                    setOpen(false);
                  }}
                  style={{
                    height: 28,
                    display: 'grid',
                    placeItems: 'center',
                    font: 'var(--type-data)',
                    color: isSelected ? 'var(--bg-app)' : isToday ? 'var(--text-accent)' : 'var(--fg-2)',
                    background: isSelected ? 'var(--primary-100)' : 'transparent',
                    border: isToday && !isSelected ? '1px solid var(--border-accent)' : '1px solid transparent',
                    borderRadius: 'var(--r-1)',
                    cursor: 'pointer',
                  }}
                >
                  {cell.getDate()}
                </button>
              );
            })}
          </div>
        </div>
      ) : null}
    </div>
  );
}

function timeParts(value: string): { h: number; m: number } {
  const [rawH, rawM] = value.split(':');
  const h = Number.parseInt(rawH ?? '', 10);
  const m = Number.parseInt(rawM ?? '', 10);
  return {
    h: Number.isFinite(h) ? Math.min(23, Math.max(0, h)) : 0,
    m: Number.isFinite(m) ? Math.min(59, Math.max(0, m)) : 0,
  };
}

const timeColStyle: CSSProperties = {
  flex: 1,
  maxHeight: 216,
  overflowY: 'auto',
  display: 'flex',
  flexDirection: 'column',
  gap: 2,
};

/** Vaqt tanlagich — `DatePicker` bilan bir xil popover naqshi, lekin
 * soat va daqiqa IKKITA alohida ro'yxatdan tanlanadi (loyiha egasining
 * topilmasi, 2026-08-16: bitta "HH:MM" ro'yxati aniq daqiqani tanlashni
 * qiyinlashtirardi — 30 daqiqalik qadam bilan cheklangan edi). */
export function TimeSelect({
  value,
  onChange,
  label,
  size = 'lg',
  notch,
  minuteStep = 5,
  style,
}: {
  /** `HH:MM`. */
  value: string;
  onChange: (value: string) => void;
  label?: string;
  size?: ControlSize;
  notch?: boolean;
  minuteStep?: number;
  style?: CSSProperties;
}): ReactNode {
  const { h, m } = timeParts(value);
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const hourRefs = useRef<Record<number, HTMLButtonElement | null>>({});
  const minuteRefs = useRef<Record<number, HTMLButtonElement | null>>({});

  useEffect(() => {
    if (!open) return;
    const off = (event: MouseEvent): void => {
      if (ref.current && !ref.current.contains(event.target as Node)) setOpen(false);
    };
    document.addEventListener('mousedown', off);
    return () => document.removeEventListener('mousedown', off);
  }, [open]);

  // Ochilganda joriy soat/daqiqa ko'rinishga scroll qilinadi — ro'yxatni
  // qo'lda pastga surish shart bo'lmasin.
  useEffect(() => {
    if (!open) return;
    hourRefs.current[h]?.scrollIntoView({ block: 'nearest' });
    minuteRefs.current[m - (m % minuteStep)]?.scrollIntoView({ block: 'nearest' });
    // `h`/`m` ATAYLAB bog'liqlik ro'yxatida emas — `DatePicker`dagi bilan
    // bir xil sabab: faqat OCHILGANDA scroll qilinsin, foydalanuvchi
    // ro'yxat ichida tanlov qilayotganda popover o'z-o'zidan qayta
    // sirpanmasin.
  }, [open]);

  const pad = (n: number) => String(n).padStart(2, '0');
  const set = (nh: number, nm: number) => onChange(`${pad(nh)}:${pad(nm)}`);

  const hours = Array.from({ length: 24 }, (_, i) => i);
  const minutes = Array.from({ length: Math.ceil(60 / minuteStep) }, (_, i) => i * minuteStep);

  return (
    <div ref={ref} style={{ position: 'relative', ...style }}>
      {label ? (
        <span
          style={{
            display: 'block',
            marginBottom: 6,
            font: 'var(--type-label)',
            letterSpacing: 'var(--ls-label)',
            textTransform: 'uppercase',
            color: 'var(--text-label)',
          }}
        >
          {label}
        </span>
      ) : null}

      <button
        type="button"
        onClick={() => setOpen((current) => !current)}
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 8,
          width: '100%',
          height: controlHeight(size),
          padding: '0 10px',
          font: 'var(--type-data)',
          color: 'var(--fg-1)',
          background: 'var(--surface-field)',
          border: `1px solid ${open ? 'var(--border-accent)' : 'var(--line-2)'}`,
          borderRadius: 'var(--r-1)',
          clipPath: notch ? 'var(--clip-tr)' : undefined,
          cursor: 'pointer',
          boxShadow: open ? 'var(--glow-violet-sm)' : 'none',
          transition: 'var(--t-control)',
        }}
      >
        <Icon name="schedule" size={14} color="var(--fg-4)" />
        <span style={{ flex: 1, textAlign: 'left' }}>{`${pad(h)}:${pad(m)}`}</span>
      </button>

      {open ? (
        <div
          style={{
            position: 'absolute',
            zIndex: 40,
            top: 'calc(100% + 4px)',
            left: 0,
            width: 160,
            padding: 8,
            display: 'flex',
            gap: 6,
            background: 'var(--surface-pop)',
            border: '1px solid var(--line-2)',
            borderRadius: 'var(--r-1)',
            boxShadow: 'var(--shadow-pop)',
          }}
        >
          <div style={timeColStyle}>
            {hours.map((hh) => (
              <button
                key={hh}
                type="button"
                ref={(el) => {
                  hourRefs.current[hh] = el;
                }}
                onClick={() => set(hh, m)}
                style={{
                  height: 26,
                  flexShrink: 0,
                  textAlign: 'center',
                  font: 'var(--type-data)',
                  color: hh === h ? 'var(--bg-app)' : 'var(--fg-2)',
                  background: hh === h ? 'var(--primary-100)' : 'transparent',
                  border: 'none',
                  borderRadius: 'var(--r-1)',
                  cursor: 'pointer',
                }}
              >
                {pad(hh)}
              </button>
            ))}
          </div>
          <div style={timeColStyle}>
            {minutes.map((mm) => (
              <button
                key={mm}
                type="button"
                ref={(el) => {
                  minuteRefs.current[mm] = el;
                }}
                onClick={() => {
                  set(h, mm);
                  setOpen(false);
                }}
                style={{
                  height: 26,
                  flexShrink: 0,
                  textAlign: 'center',
                  font: 'var(--type-data)',
                  color: mm === m - (m % minuteStep) ? 'var(--bg-app)' : 'var(--fg-2)',
                  background: mm === m - (m % minuteStep) ? 'var(--primary-100)' : 'transparent',
                  border: 'none',
                  borderRadius: 'var(--r-1)',
                  cursor: 'pointer',
                }}
              >
                {pad(mm)}
              </button>
            ))}
          </div>
        </div>
      ) : null}
    </div>
  );
}
