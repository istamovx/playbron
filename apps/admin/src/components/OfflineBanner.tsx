import { Button, Modal, Panel, StatusLine, Tag } from '@playbron/ui';
import { type ReactNode, useState } from 'react';

import { useT } from '../i18n';
import { dismissConflict, useOfflineSync } from '../offline/useOfflineSync';

/**
 * Doimiy holat indikatori — audit §25 ("Xodim uchun real offline UX").
 * Hech qachon jimgina yashirilmaydi: online+bo'sh navbat holatida ham
 * (kichik yashil nuqta sifatida) turadi, xodim "saqlangani aniqmi?" deb
 * o'ylamasligi kerak (audit, aynan shu jumla bilan).
 */
export function OfflineBanner(): ReactNode {
  const t = useT();
  const { online, pendingCount, syncingCount, failed, conflicts } = useOfflineSync();
  const [open, setOpen] = useState(false);

  const attention = failed.length + conflicts.length;
  const tone = !online ? 'danger' : attention > 0 ? 'warn' : syncingCount > 0 ? 'accent' : 'ok';
  const icon = !online ? 'cloud_off' : attention > 0 ? 'error' : syncingCount > 0 ? 'sync' : 'cloud_done';
  const label = !online
    ? t('statusOffline')
    : syncingCount > 0
      ? t('offlineSyncing')
      : t('statusOnline');

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 'var(--gap-2)',
          background: 'transparent',
          border: 'none',
          padding: 0,
          cursor: 'pointer',
        }}
      >
        <StatusLine tone={tone} icon={icon} parts={[label]} />
        {pendingCount > 0 ? <Tag tone={tone}>{pendingCount}</Tag> : null}
        {attention > 0 ? <Tag tone="danger">{attention}</Tag> : null}
      </button>

      <Modal open={open} onClose={() => setOpen(false)} title={t('offlineDrawerTitle')} variant="drawer">
        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--gap-panel)' }}>
          {pendingCount === 0 && failed.length === 0 && conflicts.length === 0 ? (
            <Panel padded>
              <StatusLine tone="ok" icon="cloud_done" parts={[t('offlineNoItems')]} />
            </Panel>
          ) : null}

          {conflicts.length > 0 ? (
            <Panel title={t('offlineConflictLabel')}>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--gap-2)' }}>
                {conflicts.map((c) => (
                  <div
                    key={c.id}
                    style={{ display: 'flex', flexDirection: 'column', gap: 'var(--gap-1)' }}
                  >
                    <StatusLine tone="danger" icon="error" parts={[c.label]} />
                    <span style={{ font: 'var(--type-body)', color: 'var(--text-muted)' }}>
                      {c.reason}
                    </span>
                    <span style={{ font: 'var(--type-body)', color: 'var(--text-muted)' }}>
                      {t('offlineConflictNote')}
                    </span>
                    <Button
                      size="sm"
                      variant="secondary"
                      onClick={() => void dismissConflict(c.id)}
                    >
                      {t('offlineDismiss')}
                    </Button>
                  </div>
                ))}
              </div>
            </Panel>
          ) : null}

          {failed.length > 0 ? (
            <Panel title={t('offlineFailedLabel')}>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--gap-2)' }}>
                {failed.map((item) => (
                  <div key={item.id} style={{ display: 'flex', flexDirection: 'column', gap: 'var(--gap-1)' }}>
                    <StatusLine tone="danger" icon="error" parts={[item.label]} />
                    <span style={{ font: 'var(--type-body)', color: 'var(--text-muted)' }}>
                      {item.lastError}
                    </span>
                  </div>
                ))}
              </div>
            </Panel>
          ) : null}

          {pendingCount > 0 ? (
            <Panel title={t('offlinePendingLabel')}>
              <StatusLine tone="warn" icon="schedule" parts={[String(pendingCount)]} />
            </Panel>
          ) : null}
        </div>
      </Modal>
    </>
  );
}
