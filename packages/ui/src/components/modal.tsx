import { useEffect, type CSSProperties, type ReactNode } from 'react';

import { Icon } from './primitives';

/**
 * Modal — ikki variant: `center` (kichikroq forma, ekran markazida) va
 * `drawer` (kattaroq forma, o'ngdan chiqadi — `apps/admin/src/app.tsx`dagi
 * mobil `Drawer`ning umumiy versiyasi).
 *
 * Fon — `rgba(0,0,0,.62)` + blur, `admin/app.tsx`dagi drawer bilan bir xil.
 * `Escape` va fonga bosish yopadi.
 */
export function Modal({
  open,
  onClose,
  title,
  children,
  variant = 'center',
  width,
}: {
  open: boolean;
  onClose: () => void;
  title?: ReactNode;
  children: ReactNode;
  variant?: 'center' | 'drawer';
  width?: number | string;
}): ReactNode {
  useEffect(() => {
    if (!open) return;
    const onKey = (event: KeyboardEvent): void => {
      if (event.key === 'Escape') onClose();
    };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [open, onClose]);

  if (!open) return null;

  const isDrawer = variant === 'drawer';

  const panelStyle: CSSProperties = isDrawer
    ? {
        width: width ?? 'min(480px, 92vw)',
        height: '100%',
      }
    : {
        width: width ?? 'min(560px, 92vw)',
        maxHeight: '86vh',
        margin: 16,
        clipPath: 'var(--clip-tr)',
      };

  return (
    <div
      style={{
        position: 'fixed',
        inset: 0,
        zIndex: 80,
        display: 'flex',
        justifyContent: isDrawer ? 'flex-end' : 'center',
        alignItems: isDrawer ? 'stretch' : 'center',
      }}
    >
      <div
        role="presentation"
        onClick={onClose}
        style={{
          position: 'absolute',
          inset: 0,
          background: 'rgba(0,0,0,.62)',
          backdropFilter: 'blur(6px)',
        }}
      />
      <div
        role="dialog"
        aria-modal="true"
        aria-label={typeof title === 'string' ? title : undefined}
        style={{
          position: 'relative',
          background: 'var(--surface-panel)',
          border: '1px solid var(--line-2)',
          boxShadow: 'var(--shadow-pop)',
          display: 'flex',
          flexDirection: 'column',
          minHeight: 0,
          minWidth: 0,
          ...panelStyle,
        }}
      >
        {title ? (
          <header
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              gap: 12,
              padding: '14px var(--gutter)',
              borderBottom: '1px solid var(--line-1)',
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
            <button
              type="button"
              onClick={onClose}
              aria-label="Yopish"
              style={{
                flex: 'none',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                width: 30,
                height: 30,
                border: '1px solid var(--line-2)',
                background: 'transparent',
                color: 'var(--text-muted)',
                cursor: 'pointer',
              }}
            >
              <Icon name="close" size={16} />
            </button>
          </header>
        ) : null}

        <div style={{ padding: 'var(--gutter)', overflowY: 'auto', minHeight: 0, flex: 1 }}>
          {children}
        </div>
      </div>
    </div>
  );
}
