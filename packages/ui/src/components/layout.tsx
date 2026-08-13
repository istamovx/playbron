import { useEffect, useRef, useState, type CSSProperties, type ReactNode } from 'react';

import { Icon } from './primitives';

/**
 * SystemX `components/surfaces/Panel.jsx` dan aynan ko'chirilgan:
 * 1px hairline, deyarli qora fon, ixtiyoriy chamfer (`notch`) va
 * L-shaklidagi burchak qavslari (`brackets`) — HUD belgisi.
 */
export function Panel({
  title,
  action,
  actions,
  children,
  notch,
  brackets,
  dashed,
  glow,
  pad = 'var(--panel-pad)',
  padded = true,
  surface = 'var(--surface-panel)',
  style,
  bodyStyle,
}: {
  title?: ReactNode;
  action?: ReactNode;
  /** Eski nom — `action` bilan bir xil. */
  actions?: ReactNode;
  children: ReactNode;
  notch?: boolean;
  brackets?: boolean;
  dashed?: boolean;
  glow?: boolean;
  pad?: string | number;
  padded?: boolean;
  surface?: string;
  style?: CSSProperties;
  bodyStyle?: CSSProperties;
}): ReactNode {
  const headerAction = action ?? actions;
  const padValue = padded ? pad : 0;

  return (
    <section
      style={{
        position: 'relative',
        background: surface,
        border: `1px ${dashed ? 'dashed' : 'solid'} ${glow ? 'var(--border-accent)' : 'var(--border-panel)'}`,
        borderRadius: 'var(--r-1)',
        boxShadow: glow ? 'var(--glow-violet)' : 'none',
        clipPath: notch ? 'var(--clip-tr)' : undefined,
        display: 'flex',
        flexDirection: 'column',
        minHeight: 0,
        ...style,
      }}
    >
      {brackets ? <Brackets /> : null}

      {title || headerAction ? (
        <header
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            // Tor ekranda amal tugmasi/qidiruvi sarlavha ostiga tushadi
            flexWrap: 'wrap',
            gap: 12,
            padding: `10px ${typeof pad === 'number' ? `${pad}px` : pad} 8px`,
            borderBottom: title ? '1px solid var(--line-1)' : 'none',
            flex: 'none',
          }}
        >
          <h2
            style={{
              margin: 0,
              minWidth: 0,
              font: 'var(--type-panel-title)',
              color: 'var(--text-title)',
              letterSpacing: 'var(--ls-title)',
            }}
          >
            {title}
          </h2>
          {headerAction}
        </header>
      ) : null}

      <div style={{ padding: padValue, minHeight: 0, flex: 1, ...bodyStyle }}>{children}</div>
    </section>
  );
}

function Brackets(): ReactNode {
  const corner: CSSProperties = {
    position: 'absolute',
    width: 10,
    height: 10,
    borderColor: 'var(--line-3)',
    borderStyle: 'solid',
    pointerEvents: 'none',
  };

  return (
    <>
      <i style={{ ...corner, top: -1, left: -1, borderWidth: '1px 0 0 1px' }} />
      <i style={{ ...corner, top: -1, right: -1, borderWidth: '1px 1px 0 0' }} />
      <i style={{ ...corner, bottom: -1, left: -1, borderWidth: '0 0 1px 1px' }} />
      <i style={{ ...corner, bottom: -1, right: -1, borderWidth: '0 1px 1px 0' }} />
    </>
  );
}

/** Auto-fit grid — dizayndagi `repeat(auto-fit,minmax(min(190px,100%),1fr))` naqshi. */
export function Grid({
  min = 190,
  gap = 'var(--gap-panel)',
  children,
}: {
  min?: number;
  gap?: string;
  children: ReactNode;
}): ReactNode {
  return (
    <div
      style={{
        display: 'grid',
        minWidth: 0,
        gridTemplateColumns: `repeat(auto-fit, minmax(min(${min}px, 100%), 1fr))`,
        gap,
      }}
    >
      {children}
    </div>
  );
}

/**
 * Sahifa sarlavhasi: ALL CAPS display face, ostida meta yorliqlari,
 * o'ngda soat va foydalanuvchi. Ostidan bracket tick chizig'i o'tadi.
 */
export function PageHeader({
  title,
  meta = [],
  right,
}: {
  title: string;
  meta?: string[];
  right?: ReactNode;
}): ReactNode {
  return (
    <>
      <header
        style={{
          display: 'flex',
          alignItems: 'flex-end',
          justifyContent: 'space-between',
          gap: 'var(--gap-block)',
          flexWrap: 'wrap',
          padding: 'var(--gutter) var(--gutter) 0',
          flex: 'none',
        }}
      >
        <div style={{ minWidth: 0, flex: 1 }}>
          <div
            style={{
              font: 'var(--fw-bold) var(--fs-title-fluid)/var(--lh-tight) var(--font-display)',
              color: 'var(--text-title)',
              textTransform: 'uppercase',
              letterSpacing: '.02em',
            }}
          >
            {title}
          </div>
          <div style={{ display: 'flex', gap: 14, flexWrap: 'wrap', marginTop: 7 }}>
            {meta.map((item) => (
              <span
                key={item}
                style={{
                  font: 'var(--type-label)',
                  letterSpacing: 'var(--ls-label)',
                  textTransform: 'uppercase',
                  color: 'var(--text-muted)',
                }}
              >
                {item}
              </span>
            ))}
          </div>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12, paddingBottom: 2 }}>
          {right}
        </div>
      </header>

      <div
        style={{
          display: 'flex',
          gap: 4,
          alignItems: 'center',
          padding: 'var(--gap-block) var(--gutter) 0',
          flex: 'none',
        }}
      >
        <div style={{ height: 1, width: 38, background: 'var(--line-3)' }} />
        <div style={{ height: 1, flex: 1, background: 'var(--line-1)' }} />
        <div style={{ height: 1, width: 14, background: 'var(--line-3)' }} />
      </div>
    </>
  );
}

export interface NavItem {
  key: string;
  label: string;
  icon: string;
  badge?: number;
}

/** 208px docked sidebar: violet aktiv holat, hairline chegara, chap rail. */
export function SidebarNav({
  items,
  active,
  onSelect,
  brand,
  footer,
}: {
  items: NavItem[];
  active: string;
  onSelect: (key: string) => void;
  brand?: ReactNode;
  footer?: ReactNode;
}): ReactNode {
  return (
    <nav
      style={{
        width: 'var(--nav-w, 208px)',
        height: '100%',
        flex: 'none',
        background: 'var(--bg-frame)',
        borderRight: '1px solid var(--line-1)',
        display: 'flex',
        flexDirection: 'column',
        justifyContent: 'space-between',
        gap: 8,
        padding: '14px 10px',
      }}
    >
      <div style={{ display: 'grid', gap: 14, minWidth: 0 }}>
        {brand ? <div style={{ padding: '0 4px' }}>{brand}</div> : null}

        <ul style={{ listStyle: 'none', margin: 0, padding: 0, display: 'grid', gap: 2 }}>
          {items.map((item) => {
            const isActive = item.key === active;
            return (
              <li key={item.key}>
                <button
                  type="button"
                  onClick={() => onSelect(item.key)}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 10,
                    width: '100%',
                    height: 'var(--control-h-lg)',
                    padding: '0 10px',
                    border: '1px solid transparent',
                    boxShadow: isActive ? 'inset 2px 0 0 var(--primary-100)' : 'none',
                    background: isActive ? 'var(--surface-selected)' : 'transparent',
                    color: isActive ? 'var(--text-title)' : 'var(--fg-3)',
                    font: 'var(--type-control)',
                    // Navigatsiya matni ham minimal 16px dan past tushmaydi
                    fontSize: 'var(--fs-base)',
                    borderRadius: 'var(--r-1)',
                    cursor: 'pointer',
                    textAlign: 'left',
                    transition: 'var(--t-control)',
                  }}
                >
                  <Icon name={item.icon} size={20} />
                  <span style={{ flex: 1 }}>{item.label}</span>
                  {item.badge ? (
                    <span
                      style={{
                        font: 'var(--type-data-xs)',
                        fontSize: 'var(--fs-sm)',
                        color: 'var(--risk-crit)',
                        border: '1px solid color-mix(in srgb,var(--risk-high) 50%,transparent)',
                        borderRadius: 'var(--r-1)',
                        padding: '0 4px',
                      }}
                    >
                      {item.badge}
                    </span>
                  ) : null}
                </button>
              </li>
            );
          })}
        </ul>
      </div>

      {footer}
    </nav>
  );
}

/** Foydalanuvchi menyusi — holat nuqtasi, ism/rol va ochiladigan ro'yxat. */
export function UserMenu({
  name,
  role,
  status = 'online',
  items = ['Profil', 'Sozlamalar', 'Chiqish'],
  onSelect,
  style,
}: {
  name: string;
  role?: string;
  status?: 'online' | 'busy' | 'offline';
  items?: string[];
  onSelect?: (item: string) => void;
  style?: CSSProperties;
}): ReactNode {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const off = (event: MouseEvent): void => {
      if (ref.current && !ref.current.contains(event.target as Node)) setOpen(false);
    };
    document.addEventListener('mousedown', off);
    return () => document.removeEventListener('mousedown', off);
  }, [open]);

  const dot =
    status === 'online'
      ? 'var(--green-400)'
      : status === 'busy'
        ? 'var(--yellow-100)'
        : 'var(--fg-4)';

  return (
    <div ref={ref} style={{ position: 'relative', ...style }}>
      <button
        type="button"
        onClick={() => setOpen((current) => !current)}
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 9,
          height: 'var(--control-h-lg)',
          padding: '0 10px',
          background: 'var(--surface-field)',
          border: `1px solid ${open ? 'var(--border-accent)' : 'var(--border-control)'}`,
          borderRadius: 'var(--r-1)',
          cursor: 'pointer',
          transition: 'var(--t-control)',
          minWidth: 0,
        }}
      >
        <i
          style={{
            width: 7,
            height: 7,
            flex: 'none',
            borderRadius: '50%',
            background: dot,
            boxShadow: `0 0 6px ${dot}`,
          }}
        />
        <span style={{ display: 'grid', gap: 1, textAlign: 'left', minWidth: 0 }}>
          <span
            style={{
              font: 'var(--type-body-sm)',
              color: 'var(--fg-1)',
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              whiteSpace: 'nowrap',
            }}
          >
            {name}
          </span>
          {role ? (
            <span
              style={{
                font: 'var(--type-label)',
                fontSize: 'var(--fs-micro)',
                letterSpacing: 'var(--ls-label)',
                textTransform: 'uppercase',
                color: 'var(--fg-5)',
                whiteSpace: 'nowrap',
                overflow: 'hidden',
                textOverflow: 'ellipsis',
              }}
            >
              {role}
            </span>
          ) : null}
        </span>
        <Icon
          name="expand_more"
          size={15}
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
            zIndex: 50,
            top: 'calc(100% + 4px)',
            right: 0,
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
                  onSelect?.(item);
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
                  padding: '8px 10px',
                  font: 'var(--type-control)',
                  color: 'var(--fg-2)',
                  background: 'transparent',
                  border: 'none',
                  borderRadius: 'var(--r-1)',
                  cursor: 'pointer',
                  whiteSpace: 'nowrap',
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

/** Bo'sh holat — dashed hairline va bir qatorli faktik matn. */
export function EmptyState({ children }: { children: ReactNode }): ReactNode {
  return (
    <div
      style={{
        border: '1px dashed var(--line-2)',
        borderRadius: 'var(--r-1)',
        padding: 'var(--card-pad)',
        color: 'var(--text-muted)',
        font: 'var(--type-body-sm)',
        textAlign: 'center',
      }}
    >
      {children}
    </div>
  );
}
