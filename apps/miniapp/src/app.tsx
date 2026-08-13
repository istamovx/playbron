import { Icon, prepayAmount } from '@playbron/ui';
import { useEffect, type ReactNode } from 'react';

import {
  CLK,
  HM,
  MENU,
  S,
  STATIONS,
  TABS,
  TAB_ROOT,
  TITLES,
  freeStations,
  type ScreenId,
} from './mock/data';
import { useTelegramAuth } from './lib/auth';
import { setBackButton, setMainButton } from './lib/telegram';
import { BillScreen } from './screens/bill';
import { BookingsScreen } from './screens/bookings';
import { ClubScreen } from './screens/club';
import { ClubsScreen } from './screens/clubs';
import { PendingScreen } from './screens/pending';
import { ProfileScreen } from './screens/profile';
import { RegisterScreen } from './screens/register';
import { SessionScreen } from './screens/session';
import { SlotsScreen } from './screens/slots';
import { useApp, useClock, useNow, useProfile } from './store/app';

/** Mijoz Mini App — `docs/designs/PlayBron Mijoz.dc.html` shelli. */
export function App(): ReactNode {
  useClock();
  const now = useNow();
  const state = useApp();
  const profile = useProfile((current) => current.profile);
  const signedIn = useProfile((current) => current.signedIn);
  // Telegram ichida sessiya jimgina ochiladi; brauzerda darhol `ready` bo'ladi
  const boot = useTelegramAuth();

  const main = mainButton(state);
  const canBack = state.stack.length > 0;
  const activeTab = TAB_ROOT[state.screen] ?? state.screen;
  const [title] = TITLES[state.screen];

  // Telegram ichida native tugmalar, brauzerda ekrandagi variantlar ishlaydi
  useEffect(() => (canBack ? setBackButton(state.back) : setBackButton(null)), [canBack, state.back]);
  useEffect(
    () =>
      main
        ? setMainButton({ text: main.label, onClick: main.act, enabled: main.enabled })
        : setMainButton(null),
    [main],
  );

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
        ) : profile && signedIn ? (
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
              {state.screen === 'confirm' ? <PendingScreen section="Tasdiqlash" /> : null}
              {state.screen === 'qr' ? <PendingScreen section="QR kod" /> : null}
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
            <RegisterScreen />
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

/** Prototipdagi `MAIN` jadvali — ekranga qarab MainButton. */
function mainButton(state: ReturnType<typeof useApp.getState>): MainAction | null {
  const free = freeStations(state.day, state.start, state.hours, {
    room: state.room,
    console: state.console,
  });
  const picked = free.find((item) => item.code === state.station) ?? free[0];
  const station =
    picked ??
    STATIONS.find((item) => item.code === state.station) ??
    (STATIONS[0] as (typeof STATIONS)[number]);

  const price = state.hours * station.rate;
  // Depozit yo'q: bron uchun 1 soatlik summa to'lanadi (kelsa hisobga, kelmasa jarimaga)
  const prepay = prepayAmount(station.rate);
  const ordersAmount = Object.entries(state.cart).reduce(
    (sum, [id, qty]) => sum + (MENU.find((item) => item.id === id)?.price ?? 0) * qty,
    0,
  );

  switch (state.screen) {
    case 'club':
      return { label: 'Bron qilish', act: () => state.go('slots') };
    case 'slots':
      return picked
        ? {
            label: `${HM(state.start)} → ${HM(state.start + state.hours * 60)} · ${S(price)} so‘m`,
            act: () => state.go('confirm'),
          }
        : { label: 'Bo‘sh vaqtni tanlang', act: () => undefined, enabled: false };
    case 'confirm':
      return { label: `${S(prepay)} so‘m to‘lash · ${state.pay}`, act: () => state.go('qr') };
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
