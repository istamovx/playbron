import { Icon } from '@playbron/ui';
import { type ReactNode } from 'react';

import { CLK, HM, MENU, S, TABS, TAB_ROOT, TITLES, type ScreenId } from './mock/data';
import { freeStations, isoDateOf, startInstantIso } from './lib/slots';
import { useTelegramAuth } from './lib/auth';
import { BillScreen } from './screens/bill';
import { BookingsScreen } from './screens/bookings';
import { BootScreen } from './screens/boot';
import { ClubScreen } from './screens/club';
import { ClubsScreen } from './screens/clubs';
import { ConfirmScreen } from './screens/confirm';
import { ProfileScreen } from './screens/profile';
import { SentScreen } from './screens/sent';
import { SessionScreen } from './screens/session';
import { SlotsScreen } from './screens/slots';
import { useApp, useClock, useNow, useProfile } from './store/app';
import { useBooking } from './store/booking';

/** Mijoz Mini App — `docs/designs/PlayBron Mijoz.dc.html` shelli. */
export function App(): ReactNode {
  useClock();
  const now = useNow();
  const state = useApp();
  const profile = useProfile((current) => current.profile);
  const signedIn = useProfile((current) => current.signedIn);
  // Telegram ichida sessiya jimgina ochiladi — qo'lda forma yo'q (§lib/auth.ts)
  const boot = useTelegramAuth();
  const authenticated = boot.state === 'authenticated' && profile && signedIn;
  const bookingSubmitting = useBooking((s) => s.submitting);

  const main = mainButton(state, bookingSubmitting);
  const canBack = state.stack.length > 0;
  const activeTab = TAB_ROOT[state.screen] ?? state.screen;
  const [title] = TITLES[state.screen];

  // Telegram'ning MainButton va BackButton'i ATAYLAB ishlatilmaydi: ekranda
  // o'z tugmamiz va o'z header'imiz bor, ikkalasi birga chiqsa foydalanuvchi
  // pastda bir xil yozuvli ikkita tugma ko'radi. Ular `initTelegram()` da
  // bir marta yashiriladi.

  return (
    <div className="pb-stage">
      <div
        className="pb-phone"
        style={{
          background: 'var(--bg-frame)',
          display: 'flex',
          flexDirection: 'column',
          font: 'var(--type-body)',
          color: 'var(--text-body)',
          position: 'relative',
        }}
      >
        {boot.state === 'checking' ? (
          <main
            style={{
              flex: 1,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              padding: 'var(--gutter)',
              font: 'var(--type-body-sm)',
              color: 'var(--text-dim)',
            }}
          >
            Yuklanmoqda…
          </main>
        ) : authenticated ? (
          <>
            <header
              style={{
                flex: 'none',
                minHeight: 52,
                display: 'flex',
                alignItems: 'center',
                gap: 10,
                padding: '0 var(--gutter)',
                background: 'var(--void-2)',
                borderBottom: '1px solid var(--line-1)',
              }}
            >
              {canBack ? (
                <button
                  type="button"
                  onClick={state.back}
                  aria-label="Orqaga"
                  style={{
                    cursor: 'pointer',
                    width: 30,
                    height: 30,
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    border: 'none',
                    background: 'transparent',
                    color: 'var(--text-muted)',
                  }}
                >
                  <Icon name="arrow_back" size={20} />
                </button>
              ) : null}

              {/* Bir qatorli mobil header: faqat sarlavha — subtitr olib tashlandi */}
              <span
                style={{
                  flex: 1,
                  minWidth: 0,
                  font: 'var(--fw-medium) var(--fs-lg)/1.2 var(--font-display)',
                  color: 'var(--text-title)',
                  whiteSpace: 'nowrap',
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                }}
              >
                {title}
              </span>

              <span style={{ font: 'var(--type-data-xs)', color: 'var(--text-dim)' }}>
                {CLK(now)}
              </span>
            </header>

            <main
              style={{
                flex: 1,
                minHeight: 0,
                minWidth: 0,
                overflowY: 'auto',
                overflowX: 'hidden',
                padding: 'var(--gutter)',
              }}
            >
              {state.screen === 'clubs' ? <ClubsScreen /> : null}
              {state.screen === 'club' ? <ClubScreen /> : null}
              {state.screen === 'slots' ? <SlotsScreen /> : null}
              {state.screen === 'confirm' ? <ConfirmScreen /> : null}
              {state.screen === 'qr' ? <SentScreen /> : null}
              {state.screen === 'session' ? <SessionScreen /> : null}
              {state.screen === 'bill' ? <BillScreen /> : null}
              {state.screen === 'bookings' ? <BookingsScreen /> : null}
              {state.screen === 'profile' ? <ProfileScreen /> : null}
            </main>

            {main ? (
              <button
                type="button"
                onClick={main.act}
                disabled={main.enabled === false}
                style={{
                  flex: 'none',
                  cursor: main.enabled === false ? 'not-allowed' : 'pointer',
                  minHeight: 50,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: 8,
                  border: 'none',
                  background: main.enabled === false ? 'var(--surface-inset)' : 'var(--primary-100)',
                  color: main.enabled === false ? 'var(--text-dim)' : 'var(--text-on-accent)',
                  font: 'var(--fw-medium) var(--fs-base)/1 var(--font-display)',
                  letterSpacing: '.02em',
                  transition: 'background 140ms cubic-bezier(.22,.61,.36,1)',
                }}
              >
                {main.label}
              </button>
            ) : null}

            <nav
              style={{
                flex: 'none',
                display: 'grid',
                gridTemplateColumns: 'repeat(4, 1fr)',
                background: 'var(--void-2)',
                borderTop: '1px solid var(--line-1)',
              }}
            >
              {TABS.map((tab) => {
                const on = activeTab === tab.id;
                return (
                  <button
                    key={tab.id}
                    type="button"
                    onClick={() => state.tab(tab.id)}
                    aria-label={tab.label}
                    title={tab.label}
                    aria-current={on ? 'page' : undefined}
                    style={{
                      cursor: 'pointer',
                      minHeight: 54,
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      border: 'none',
                      borderTop: `2px solid ${on ? 'var(--primary-100)' : 'transparent'}`,
                      background: on ? 'var(--surface-selected)' : 'transparent',
                      color: on ? 'var(--text-title)' : 'var(--text-dim)',
                      transition: 'var(--t-control)',
                    }}
                  >
                    <Icon name={tab.icon} size={22} />
                  </button>
                );
              })}
            </nav>
          </>
        ) : (
          <main style={{ flex: 1, minHeight: 0, overflowY: 'auto', padding: 'var(--gutter)' }}>
            <BootScreen state={boot.state} error={boot.error} onRetry={boot.retry} />
          </main>
        )}
      </div>
    </div>
  );
}

interface MainAction {
  label: string;
  act: () => void;
  enabled?: boolean;
}

/**
 * Prototipdagi `MAIN` jadvali — ekranga qarab MainButton.
 *
 * `club`/`slots`/`confirm`/`qr` — real bron oqimi (`store/booking.ts`),
 * qolgani hali mock (seans, bar, hisob — backend yo'q).
 */
function mainButton(
  state: ReturnType<typeof useApp.getState>,
  bookingSubmitting: boolean,
): MainAction | null {
  const booking = useBooking.getState();
  const clubId = state.clubId;
  const stationScope = { room: state.room, console: state.console };
  const club = clubId === null ? null : booking.clubs.find((c) => c.id === clubId) ?? null;
  const timezone = club?.timezone ?? 'Asia/Tashkent';
  const dayBookings = clubId === null ? [] : booking.dayBookings[isoDateOf(state.day, timezone)] ?? [];
  const closeMin = club?.closesAtMin ?? 0;

  const free = freeStations(
    booking.stations,
    dayBookings,
    state.start,
    state.hours,
    closeMin,
    stationScope,
    timezone,
  );
  const station = free.find((item) => item.id === state.station) ?? null;

  const ordersAmount = Object.entries(state.cart).reduce(
    (sum, [id, qty]) => sum + (MENU.find((item) => item.id === id)?.price ?? 0) * qty,
    0,
  );

  switch (state.screen) {
    case 'club':
      return { label: 'Bron qilish', act: () => state.go('slots') };
    case 'slots':
      return station
        ? {
            label: `${HM(state.start)} → ${HM(state.start + state.hours * 60)} · ${S(station.rate * state.hours)} so‘m`,
            act: () => state.go('confirm'),
          }
        : { label: 'Bo‘sh vaqtni tanlang', act: () => undefined, enabled: false };
    case 'confirm':
      if (!station || clubId === null) {
        return { label: 'Xona tanlanmagan', act: () => undefined, enabled: false };
      }
      return {
        label: bookingSubmitting ? 'Yuborilmoqda…' : 'Bronni yuborish',
        enabled: !bookingSubmitting,
        act: () => {
          if (useBooking.getState().submitting) return;
          const iso = startInstantIso(state.day, state.start, timezone);
          void useBooking
            .getState()
            .submitBooking(clubId, station.id, iso, state.hours)
            .then((ok) => {
              if (ok) state.go('qr');
            });
        },
      };
    case 'qr':
      return { label: 'Bronlarim', act: () => state.tab('bookings') };
    case 'session':
      // Savat bo'sh bo'lsa yuboradigan narsa yo'q — tugma sababni aytadi
      return ordersAmount > 0
        ? {
            label: `Buyurtmani yuborish · ${S(ordersAmount)} so‘m`,
            act: state.sendOrder,
          }
        : { label: 'Savat bo‘sh', act: () => undefined, enabled: false };
    case 'bill':
      return state.payFinal === 'O‘tkazma' && state.receipt === 'none'
        ? { label: 'Chekni yuklash', act: () => state.setReceipt('sent') }
        : null;
    case 'bookings':
      return { label: 'Yangi bron', act: () => state.tab('clubs') };
    default:
      return null;
  }
}

export type { ScreenId };
