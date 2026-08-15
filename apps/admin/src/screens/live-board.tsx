import { errorText, listLiveStations, type LiveStationDto } from '@playbron/api-client';
import { Grid, MetricCell, Panel, StatusLine } from '@playbron/ui';
import { useCallback, useEffect, useState, type ReactNode } from 'react';

import { api } from '../lib/api';
import { S } from '../mock/data';
import { useSession } from '../store/session';

const CONSOLE_LABEL: Record<string, string> = {
  ps3: 'PS3',
  ps4: 'PS4',
  ps4pro: 'PS4 Pro',
  ps5: 'PS5',
  ps5pro: 'PS5 Pro',
};

function formatClock(iso: string): string {
  return new Date(iso).toLocaleTimeString('uz-UZ', { hour: '2-digit', minute: '2-digit' });
}

/**
 * Live board — real bandlik: CONFIRMED bron `period`i shu lahzani o'z ichiga
 * olsa xona band. Prototipdagi kelmadi/uzaytirish/rezerv oqimlari hozircha
 * yo'q — backend'da mos amal yo'q (`stations.status='maintenance'` bundan
 * mustasno). 20 soniyada avtomatik yangilanadi.
 */
export function LiveBoardScreen(): ReactNode {
  const session = useSession((state) => state.session);
  const clubId = session?.clubs[0]?.id ?? null;

  const [stations, setStations] = useState<LiveStationDto[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const reload = useCallback(async (): Promise<void> => {
    if (clubId === null) return;
    try {
      setStations(await listLiveStations(api, clubId));
      setError(null);
    } catch (cause) {
      setError(errorText(cause));
    } finally {
      setLoading(false);
    }
  }, [clubId]);

  useEffect(() => {
    setLoading(true);
    void reload();
    const timer = setInterval(() => void reload(), 20_000);
    return () => clearInterval(timer);
  }, [reload]);

  const occupied = stations.filter((s) => s.bookingId !== null).length;
  const free = stations.filter((s) => s.bookingId === null && s.status === 'active').length;
  const maintenance = stations.filter((s) => s.status === 'maintenance').length;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--gap-panel)' }}>
      <div className="pb-tiles-4">
        <MetricCell label="Band" value={`${occupied} / ${stations.length}`} />
        <MetricCell label="Bo‘sh" value={String(free)} />
        <MetricCell label="Ta’mirda" value={String(maintenance)} />
      </div>

      {error ? <StatusLine tone="danger" icon="error" parts={[error]} /> : null}

      <Panel title="Xonalar" notch brackets>
        {!loading && stations.length === 0 && !error ? (
          <div
            style={{
              border: '1px dashed var(--line-2)',
              padding: 18,
              textAlign: 'center',
              font: 'var(--type-body-sm)',
              color: 'var(--text-dim)',
            }}
          >
            Xona qo‘shilmagan
          </div>
        ) : (
          <Grid min={235}>
            {stations.map((station) => (
              <StationCard key={station.id} station={station} />
            ))}
          </Grid>
        )}
      </Panel>
    </div>
  );
}

function StationCard({ station }: { station: LiveStationDto }): ReactNode {
  const occupied = station.bookingId !== null;
  const tone =
    station.status === 'maintenance'
      ? 'var(--fg-4)'
      : occupied
        ? 'var(--yellow-100)'
        : 'var(--slot-free)';
  const label =
    station.status === 'maintenance' ? 'Ta’mirda' : occupied ? 'Band' : 'Bo‘sh';

  return (
    <div
      style={{
        minWidth: 0,
        padding: 'var(--card-pad)',
        background: 'var(--surface-panel)',
        border: '1px solid var(--line-1)',
        boxShadow: `inset 3px 0 0 ${tone}`,
        clipPath: 'var(--clip-tr)',
        display: 'flex',
        flexDirection: 'column',
        gap: 9,
      }}
    >
      <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', gap: 8 }}>
        <span
          style={{
            font: 'var(--fw-regular) var(--fs-panel-fluid)/var(--lh-snug) var(--font-display)',
            color: 'var(--text-title)',
          }}
        >
          {station.code}
        </span>
        <span
          style={{
            font: 'var(--type-label)',
            letterSpacing: 'var(--ls-label)',
            textTransform: 'uppercase',
            color: tone,
            whiteSpace: 'nowrap',
          }}
        >
          {label}
        </span>
      </div>

      <div style={{ font: 'var(--type-data-xs)', color: 'var(--text-dim)' }}>
        {`${station.roomLabel} · ${CONSOLE_LABEL[station.consoleType] ?? station.consoleType} · ${S(station.rate)} / soat`}
      </div>

      <div style={{ height: 1, background: 'var(--line-1)' }} />

      {occupied ? (
        <div style={{ font: 'var(--type-body-sm)', color: 'var(--text-title)' }}>
          {station.guestLabel ?? 'Mijoz'}
          {station.endsAt ? (
            <span style={{ color: 'var(--text-dim)' }}>{` · ${formatClock(station.endsAt)} gacha`}</span>
          ) : null}
        </div>
      ) : (
        <div style={{ font: 'var(--type-body-sm)', color: 'var(--text-dim)' }}>—</div>
      )}
    </div>
  );
}
