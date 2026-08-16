import { errorText, listPlatformLogs, type PlatformLogDto } from '@playbron/api-client';
import { EntityTable, Panel, StatusLine, Tag } from '@playbron/ui';
import { useCallback, useEffect, useState, type ReactNode } from 'react';

import { api } from '../lib/api';

const ACTION_LABEL: Record<string, string> = {
  platform_manual_org_create: 'Klub qo‘lda qo‘shildi',
  platform_payment_record: 'To‘lov yozildi',
};

function actionLabel(action: string): string {
  return ACTION_LABEL[action] ?? action;
}

function formatAt(iso: string): string {
  return new Date(iso).toLocaleString('uz-UZ', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

/** `detail` JSONB'dan qisqa, o'qiladigan xulosa — xom JSON ko'rsatilmaydi. */
function detailSummary(row: PlatformLogDto): string {
  const d = row.detail;
  if (!d) return '—';
  const parts = Object.entries(d)
    .filter(([, value]) => value !== null && value !== undefined && value !== '')
    .map(([key, value]) => `${key}: ${String(value)}`);
  return parts.length > 0 ? parts.join(' · ') : '—';
}

/**
 * Platforma faoliyat jurnali — FAQAT platforma darajasidagi amallar
 * (qo'lda klub qo'shish, to'lov yozish). Bitta klub ICHIDAGI amallar
 * (xodim/mahsulot/xona) bu yerda emas — ular klub egasining o'z
 * jurnalida (Sozlamalar → Jurnal), "o'ziga hos loglar" talabi shu ikkiga
 * ajratilgan (loyiha egasining so'rovi, 2026-08-16).
 */
export function PlatformLogsScreen(): ReactNode {
  const [rows, setRows] = useState<PlatformLogDto[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const reload = useCallback(async (): Promise<void> => {
    setLoading(true);
    setError(null);
    try {
      setRows(await listPlatformLogs(api));
    } catch (cause) {
      setError(errorText(cause));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void reload();
  }, [reload]);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--gap-panel)' }}>
      <StatusLine
        tone="neutral"
        icon="info"
        parts={[
          'Bu — platforma darajasidagi amallar (klub qo‘shish, to‘lov)',
          'Klub ichidagi amallar klub eganing o‘z jurnalida',
        ]}
      />

      {error ? <StatusLine tone="danger" icon="error" parts={[error]} /> : null}

      <Panel title={`Jurnal (${rows.length})`} notch brackets>
        <EntityTable
          rows={rows}
          rowKey={(row) => row.id}
          empty={loading ? 'Yuklanmoqda…' : 'Hozircha yozuv yo‘q'}
          columns={[
            {
              key: 'at',
              header: 'Vaqt',
              render: (row) => (
                <span style={{ font: 'var(--type-data)', color: 'var(--text-title)', whiteSpace: 'nowrap' }}>
                  {formatAt(row.at)}
                </span>
              ),
            },
            {
              key: 'action',
              header: 'Amal',
              render: (row) => <Tag tone="violet">{actionLabel(row.action)}</Tag>,
            },
            {
              key: 'actor',
              header: 'Kim',
              render: (row) => (
                <span style={{ display: 'flex', flexDirection: 'column', gap: 3, minWidth: 0 }}>
                  <span style={{ color: 'var(--text-title)' }}>{row.actorName ?? '—'}</span>
                  <span style={{ font: 'var(--type-data-xs)', color: 'var(--text-dim)' }}>
                    {row.actorLogin ?? '—'}
                  </span>
                </span>
              ),
            },
            {
              key: 'target',
              header: 'Nishon',
              render: (row) => row.target ?? '—',
            },
            {
              key: 'detail',
              header: 'Tafsilot',
              render: (row) => (
                <span style={{ font: 'var(--type-data-xs)', color: 'var(--text-dim)' }}>
                  {detailSummary(row)}
                </span>
              ),
            },
          ]}
        />
      </Panel>
    </div>
  );
}
