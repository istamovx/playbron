import { getCurrentShift } from '@playbron/api-client';
import { Button, Icon, SidebarNav, StatusLine, ToastHost, UserMenu, Wordmark, useMedia } from '@playbron/ui';
import { useCallback, useEffect, useRef, useState, type ReactNode } from 'react';
import { useLocation, useNavigate } from 'react-router';

import {
  CLK,
  NAV_ADMIN,
  NAV_STAFF,
  NAV_SUPER_ADMIN,
  TITLES,
  type NavItem,
  type ScreenId,
} from './mock/data';
import { DashboardScreen } from './screens/admin/dashboard';
import { ExpensesScreen } from './screens/admin/expenses';
import { ProductsScreen } from './screens/admin/products';
import { ReportsScreen } from './screens/admin/reports';
import { SettingsScreen } from './screens/admin/settings';
import { StaffScreen } from './screens/admin/staff';
import { BlacklistScreen } from './screens/blacklist';
import { BookingsScreen } from './screens/bookings';
import { LiveBoardScreen } from './screens/live-board';
import { OrdersScreen } from './screens/orders';
import { PlatformScreen } from './screens/platform';
import { PlatformClubsScreen } from './screens/platform-clubs';
import { PlatformLogsScreen } from './screens/platform-logs';
import { PlatformReportScreen } from './screens/platform-report';
import { PlatformSettingsScreen } from './screens/platform-settings';
import { PosScreen } from './screens/pos';
import { ShiftScreen } from './screens/shift';
import { LoginScreen } from './screens/login';
import { TimelineScreen } from './screens/timeline';
import { api } from './lib/api';
import { pathOf, screenOf } from './routes';
import { useBoard, useClock, useNow } from './store/board';
import { useSession } from './store/session';

/**
 * Klub konsoli — bitta shell, rolga qarab menyu.
 * Xodim ish ekranlarini, klub admini boshqaruv bo'limlarini ko'radi
 * (`docs/designs/PlayBron Xodim.dc.html` shelli).
 */
export function App(): ReactNode {
  useClock();
  const now = useNow();
  const session = useSession((state) => state.session);
  const mustChangePassword = useSession((state) => state.mustChangePassword);
  const prune = useSession((state) => state.prune);
  const signOut = useSession((state) => state.signOut);
  const restore = useSession((state) => state.restore);
  const setScreen = useBoard((state) => state.setScreen);
  const drawerOpen = useBoard((state) => state.drawerOpen);
  const setDrawer = useBoard((state) => state.setDrawer);
  const activeClubId = useBoard((state) => state.activeClubId);
  const setActiveClub = useBoard((state) => state.setActiveClub);
  const compact = useCompact();
  const location = useLocation();
  const navigate = useNavigate();

  /** Navigatsiya URL orqali; store keyingi fazalar uchun sinxron qoladi. */
  const go = useCallback(
    (id: ScreenId) => {
      setScreen(id);
      navigate(pathOf(id));
    },
    [navigate, setScreen],
  );

  // Saqlangan sessiyani tiklaymiz (sahifa yangilangan bo'lsa)
  useEffect(() => {
    void restore();
  }, [restore]);

  // Muddati tugagan sessiya ochiq qolmasin — har daqiqada tekshiriladi
  useEffect(() => {
    prune();
    const timer = setInterval(prune, 60_000);
    return () => clearInterval(timer);
  }, [prune]);

  // `X-Club-Id` sarlavhasi shu yerdan o'qiladi (`lib/api.ts`) — hech qanday
  // ekran o'zi tanlamagan, ko'p klublik almashtirgich hali yo'q, shuning
  // uchun birinchi a'zolik sukut bo'ladi. Sessiya almashsa ham qayta sinxron.
  useEffect(() => {
    if (!session) return;
    if (activeClubId !== null && session.clubs.some((c) => c.id === activeClubId)) return;
    setActiveClub(session.clubs[0]?.id ?? null);
  }, [session, activeClubId, setActiveClub]);

  const items =
    session?.role === 'SUPER_ADMIN'
      ? NAV_SUPER_ADMIN
      : session && session.role !== 'STAFF'
        ? NAV_ADMIN
        : NAV_STAFF;

  // Manba — URL. Noma'lum yoki rolga tegishli bo'lmagan manzil bo'lsa rolning
  // birinchi bo'limi ochiladi (route guard shu yerda).
  const fromUrl = screenOf(location.pathname);
  const active =
    fromUrl && items.some((item) => item.id === fromUrl) ? fromUrl : (items[0] as NavItem).id;

  // Manzil ekranga mos kelmasa (begona rol marshruti yoki noma'lum yo'l) —
  // URL jimgina to'g'rilanadi, aks holda manzil qatorida yolg'on yo'l qolardi.
  useEffect(() => {
    if (session && location.pathname !== pathOf(active)) {
      navigate(pathOf(active), { replace: true });
    }
  }, [session, location.pathname, active, navigate]);

  // `must_change` holatida BOSHQA hech qanday marshrut ochilmaydi: aks holda
  // vaqtinchalik parol bilan kirgan hisob mijoz ma'lumotlarini va hisobotlarni
  // o'qiy olardi (docs/05-auth-redesign.md §7.3)
  if (!session || mustChangePassword) {
    return (
      <>
        <ToastHost />
        <LoginScreen />
      </>
    );
  }

  const [title, meta] = TITLES[active];

  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        height: '100vh',
        background: 'var(--bg-app)',
        font: 'var(--type-body)',
        color: 'var(--text-body)',
        overflow: 'hidden',
      }}
    >
      <ToastHost />
      <div style={{ display: 'flex', flex: 1, minHeight: 0 }}>
        {compact ? null : <Nav items={items} active={active} onSelect={go} />}

        <div
          style={{
            flex: 1,
            minWidth: 0,
            display: 'flex',
            flexDirection: 'column',
            overflow: 'hidden',
          }}
        >
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
            {compact ? (
              <button
                type="button"
                onClick={() => setDrawer(true)}
                aria-label="Menyu"
                style={{
                  flex: 'none',
                  width: 'var(--control-h-lg)',
                  height: 'var(--control-h-lg)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  border: '1px solid var(--line-2)',
                  background: 'transparent',
                  color: 'var(--text-body)',
                  alignSelf: 'center',
                  cursor: 'pointer',
                }}
              >
                <Icon name="menu" size={20} />
              </button>
            ) : null}

            <div style={{ minWidth: 0, flex: 1, overflow: 'hidden' }}>
              <div
                style={{
                  font: compact
                    ? 'var(--fw-bold) 15px/var(--lh-tight) var(--font-display)'
                    : 'var(--fw-bold) var(--fs-title-fluid)/var(--lh-tight) var(--font-display)',
                  color: 'var(--text-title)',
                  textTransform: 'uppercase',
                  letterSpacing: '.02em',
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                  whiteSpace: 'nowrap',
                }}
              >
                {title}
              </div>
              {compact ? null : (
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
              )}
            </div>

            {compact ? (
              <MobileHeaderMenu time={CLK(now)} name={session.name} onSignOut={signOut} />
            ) : (
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 12,
                  paddingBottom: 2,
                  minWidth: 0,
                  flexShrink: 1,
                }}
              >
                <div
                  style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: 3 }}
                >
                  <span
                    style={{
                      font: 'var(--type-label)',
                      letterSpacing: 'var(--ls-label)',
                      textTransform: 'uppercase',
                      color: 'var(--text-dim)',
                    }}
                  >
                    Klub vaqti
                  </span>
                  <span
                    style={{
                      font: 'var(--type-data)',
                      color: 'var(--text-title)',
                      letterSpacing: '.04em',
                    }}
                  >
                    {CLK(now)}
                  </span>
                </div>

                <div style={{ width: 1, height: 30, background: 'var(--line-1)' }} />

                <UserMenu name={session.name} status="online" items={['Chiqish']} onSelect={signOut} />
              </div>
            )}
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

          {session.role === 'STAFF' && active !== 'shift' ? (
            <div style={{ padding: 'var(--gap-block) var(--gutter) 0', flex: 'none' }}>
              <ShiftReminderBanner clubId={activeClubId} onOpenShift={() => go('shift')} />
            </div>
          ) : null}

          <main
            style={{
              flex: 1,
              minHeight: 0,
              minWidth: 0,
              overflowY: 'auto',
              overflowX: 'hidden',
              padding: 'var(--gap-block) var(--gutter) var(--gutter)',
            }}
          >
            {active === 'live' ? <LiveBoardScreen /> : null}
            {active === 'timeline' ? <TimelineScreen /> : null}
            {active === 'orders' ? <OrdersScreen /> : null}
            {active === 'bookings' ? <BookingsScreen /> : null}
            {active === 'pos' ? <PosScreen /> : null}
            {active === 'shift' ? <ShiftScreen /> : null}
            {active === 'blacklist' ? <BlacklistScreen /> : null}

            {active === 'dashboard' ? <DashboardScreen /> : null}
            {active === 'staff' ? <StaffScreen /> : null}
            {active === 'products' ? <ProductsScreen /> : null}
            {active === 'reports' ? <ReportsScreen /> : null}
            {active === 'expenses' ? <ExpensesScreen /> : null}
            {active === 'settings' ? <SettingsScreen /> : null}

            {active === 'platform' ? <PlatformScreen /> : null}
            {active === 'platform-clubs' ? <PlatformClubsScreen /> : null}
            {active === 'platform-report' ? <PlatformReportScreen /> : null}
            {active === 'platform-logs' ? <PlatformLogsScreen /> : null}
            {active === 'platform-settings' ? <PlatformSettingsScreen /> : null}
          </main>
        </div>
      </div>

      {compact && drawerOpen ? (
        <Drawer
          items={items}
          active={active}
          // Bo'lim tanlangach drawer o'zi yopiladi — telefonda ikkinchi bosish kerak emas
          onSelect={(id) => {
            go(id);
            setDrawer(false);
          }}
          onClose={() => setDrawer(false)}
        />
      ) : null}
    </div>
  );
}

/**
 * Kun boshlanganda smena ochish esidan chiqib qolishi mumkin (loyiha
 * egasining topilmasi, 2026-08-16) — smena hali ochilmagan bo'lsa header
 * ostida doimiy eslatma. `clubId` yo'q (sessiya hali sinxronlanmagan)
 * holatda hech narsa ko'rsatilmaydi.
 */
function ShiftReminderBanner({
  clubId,
  onOpenShift,
}: {
  clubId: number | null;
  onOpenShift: () => void;
}): ReactNode {
  const [needsShift, setNeedsShift] = useState(false);

  useEffect(() => {
    if (clubId === null) return;
    let cancelled = false;
    void getCurrentShift(api, clubId)
      .then((shift) => {
        if (!cancelled) setNeedsShift(shift === null);
      })
      .catch(() => {
        // Tarmoq xatosi — eslatma ko'rsatilmaydi, keyingi ekran o'zi xato beradi
      });
    return () => {
      cancelled = true;
    };
  }, [clubId]);

  if (!needsShift) return null;

  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        gap: 'var(--gap-block)',
        flexWrap: 'wrap',
        padding: '8px 12px',
        background: 'var(--surface-panel-quiet)',
        border: '1px solid var(--amber-400)',
        clipPath: 'var(--clip-tr)',
      }}
    >
      <StatusLine tone="warn" icon="schedule" parts={['Smena hali ochilmagan']} />
      <Button variant="ghost" size="sm" icon="lock_open" onClick={onOpenShift}>
        Smenani ochish
      </Button>
    </div>
  );
}

/**
 * Prototipdagi `compact` — 905px va undan tor ekran.
 * `resize` hodisasi emas, `matchMedia` ishlatiladi: brauzer oynasi dastur orqali
 * o'zgarganda ham (mobil emulyatsiya, Telegram WebView) ishonchli ishlaydi.
 */
const useCompact = (): boolean => useMedia('(max-width: 905px)');

function Nav({
  items,
  active,
  onSelect,
}: {
  items: NavItem[];
  active: ScreenId;
  onSelect: (id: ScreenId) => void;
}): ReactNode {
  return (
    <SidebarNav
      items={items.map((item) => ({
        key: item.id,
        label: item.label,
        icon: item.icon,
        badge: item.count,
      }))}
      active={active}
      onSelect={(key) => onSelect(key as ScreenId)}
      brand={<Wordmark width="min(150px, 100%)" />}
    />
  );
}

/** ≤905px: yon panel drawer'ga aylanadi (prototipdagi kabi blur fon bilan). */
function Drawer({
  items,
  active,
  onSelect,
  onClose,
}: {
  items: NavItem[];
  active: ScreenId;
  onSelect: (id: ScreenId) => void;
  onClose: () => void;
}): ReactNode {
  return (
    <div style={{ position: 'fixed', inset: 0, zIndex: 60, display: 'flex' }}>
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
        style={{
          position: 'relative',
          width: 240,
          maxWidth: '82vw',
          height: '100%',
          boxShadow: 'var(--shadow-pop)',
        }}
      >
        <Nav items={items} active={active} onSelect={onSelect} />
      </div>
    </div>
  );
}

/**
 * Mobil holatda o'ng tomondagi ikkinchi hamburger — "Klub vaqti" + chiqish
 * shu ostiga tushadi (loyiha egasining topilmasi, 2026-08-16): avval bular
 * `.ds-hide-xs` klassi bilan yashirilgan edi, lekin xuddi shu elementda
 * INLINE `display: 'flex'` ham bor edi — inline uslub CSS klassdan HAR
 * DOIM ustun turadi, shuning uchun ≤600px'da ham ko'rinishda qolib,
 * sarlavha bilan ustma-ust chiqardi. Endi butunlay JS orqali
 * (`compact` boolean) boshqariladi, klass ziddiyati yo'q.
 */
function MobileHeaderMenu({
  time,
  name,
  onSignOut,
}: {
  time: string;
  name: string;
  onSignOut: () => void;
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

  return (
    <div ref={ref} style={{ position: 'relative', flex: 'none' }}>
      <button
        type="button"
        onClick={() => setOpen((current) => !current)}
        aria-label="Profil va vaqt"
        style={{
          flex: 'none',
          width: 'var(--control-h-lg)',
          height: 'var(--control-h-lg)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          border: `1px solid ${open ? 'var(--border-accent)' : 'var(--line-2)'}`,
          background: 'transparent',
          color: 'var(--text-body)',
          cursor: 'pointer',
        }}
      >
        <Icon name="menu" size={20} />
      </button>

      {open ? (
        <div
          style={{
            position: 'absolute',
            top: 'calc(100% + 6px)',
            right: 0,
            zIndex: 60,
            minWidth: 200,
            padding: 12,
            display: 'flex',
            flexDirection: 'column',
            gap: 10,
            background: 'var(--surface-panel)',
            border: '1px solid var(--line-2)',
            borderRadius: 'var(--r-1)',
            boxShadow: 'var(--shadow-pop)',
          }}
        >
          <div style={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
            <span
              style={{
                font: 'var(--type-label)',
                letterSpacing: 'var(--ls-label)',
                textTransform: 'uppercase',
                color: 'var(--text-dim)',
              }}
            >
              Klub vaqti
            </span>
            <span style={{ font: 'var(--type-data)', color: 'var(--text-title)', letterSpacing: '.04em' }}>
              {time}
            </span>
          </div>

          <div style={{ height: 1, background: 'var(--line-1)' }} />

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

          <button
            type="button"
            onClick={() => {
              setOpen(false);
              onSignOut();
            }}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 8,
              background: 'transparent',
              border: 'none',
              color: 'var(--risk-high)',
              cursor: 'pointer',
              padding: 0,
              font: 'var(--type-body-sm)',
            }}
          >
            <Icon name="logout" size={16} />
            Chiqish
          </button>
        </div>
      ) : null}
    </div>
  );
}
