import { errorText, listBotStatus, type BotStatusDto } from '@playbron/api-client';
import { Button, CyberLoaderOverlay, Panel, StatusLine, Tag, toast } from '@playbron/ui';
import { useCallback, useEffect, useState, type ReactNode } from 'react';

import { api } from '../lib/api';

/**
 * Sozlamalar (super admin) — Telegram botlari diagnostikasi.
 *
 * Loyiha egasining takroriy muammosi (2026-08-16/17): token noto'g'ri
 * yoki webhook o'rnatilmagan bo'lsa bot shunchaki JIM qoladi — hech
 * qayerda xato ko'rinmaydi va sababni topish uchun har safar tokenni
 * qo'lda tekshirish kerak edi. Endi holat shu yerda ko'rinadi.
 *
 * Token EKRANGA HECH QACHON chiqmaydi — server faqat `username`,
 * webhook manzili va Telegram bergan oxirgi xatoni qaytaradi.
 */
export function PlatformSettingsScreen(): ReactNode {
  const [rows, setRows] = useState<BotStatusDto[] | null>(null);
  const [loading, setLoading] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);

  const reload = useCallback(async (): Promise<void> => {
    setLoading(true);
    setLoadError(null);
    try {
      setRows(await listBotStatus(api));
    } catch (cause) {
      const message = errorText(cause);
      setLoadError(message);
      toast.error(message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void reload();
  }, [reload]);

  if (loading && rows === null) return <CyberLoaderOverlay />;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--gap-panel)' }}>
      <Panel
        title="Telegram botlari"
        notch
        brackets
        action={
          <Button variant="ghost" size="sm" icon="refresh" disabled={loading} onClick={() => void reload()}>
            Yangilash
          </Button>
        }
      >
        {loadError ? <StatusLine tone="danger" icon="error" parts={[loadError]} /> : null}

        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--gap-tight)' }}>
          {(rows ?? []).map((bot) => (
            <div
              key={bot.label}
              style={{
                padding: 'var(--card-pad)',
                background: 'var(--surface-card)',
                border: `1px solid ${bot.ok ? 'var(--line-1)' : 'var(--red-100)'}`,
                display: 'flex',
                flexDirection: 'column',
                gap: 8,
                minWidth: 0,
              }}
            >
              <div
                style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 10 }}
              >
                <span style={{ display: 'flex', flexDirection: 'column', gap: 3, minWidth: 0 }}>
                  <span style={{ font: 'var(--type-body)', color: 'var(--text-title)' }}>
                    {bot.label}
                  </span>
                  <span style={{ font: 'var(--type-data-xs)', color: 'var(--text-dim)' }}>
                    {bot.username ? `@${bot.username}` : 'username noma’lum'}
                  </span>
                </span>
                <Tag tone={bot.ok ? 'success' : bot.configured ? 'danger' : 'amber'}>
                  {bot.ok ? 'Ishlayapti' : bot.configured ? 'Nosoz' : 'Sozlanmagan'}
                </Tag>
              </div>

              {bot.problem ? <StatusLine tone="danger" icon="error" parts={[bot.problem]} /> : null}

              {bot.webhookUrl ? (
                <span
                  style={{
                    font: 'var(--type-data-xs)',
                    color: 'var(--text-dim)',
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                  }}
                >
                  {bot.webhookUrl}
                </span>
              ) : null}

              {bot.pendingUpdates !== null && bot.pendingUpdates > 0 ? (
                <StatusLine
                  tone="warn"
                  icon="pending"
                  parts={[`Navbatda ${bot.pendingUpdates} ta yangilanish`]}
                />
              ) : null}

              {bot.lastError ? (
                <StatusLine
                  tone="warn"
                  icon="warning"
                  parts={[`Telegram oxirgi xatosi: ${bot.lastError}`]}
                />
              ) : null}
            </div>
          ))}
        </div>

        <div style={{ marginTop: 'var(--gap-block)' }}>
          <StatusLine
            tone="neutral"
            icon="info"
            parts={[
              'Token Render → Environment’da',
              'Almashtirilgach servis qayta ishga tushishi shart',
            ]}
          />
        </div>
      </Panel>
    </div>
  );
}
