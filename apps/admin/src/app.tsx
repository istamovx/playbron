import { Icon, SidebarNav, UserMenu, Wordmark, useMedia } from '@playbron/ui';
import { useCallback, useEffect, type ReactNode } from 'react';
import { useLocation, useNavigate } from 'react-router';

import { CLK, NAV_ADMIN, NAV_STAFF, TITLES, type NavItem, type ScreenId } from './mock/data';
import { ClubInfoScreen } from './screens/admin/club-info';
import { DashboardScreen } from './screens/admin/dashboard';
import { ExpensesScreen } from './screens/admin/expenses';
import { ProductsScreen } from './screens/admin/products';
import { ReportsScreen } from './screens/admin/reports';
import { SettingsScreen } from './screens/admin/settings';
import { StaffScreen } from './screens/admin/staff';
import { BlacklistScreen } from './screens/blacklist';
import { LiveBoardScreen } from './screens/live-board';
import { OrdersScreen } from './screens/orders';
import { PosScreen } from './screens/pos';
import { ShiftScreen } from './screens/shift';
import { LoginScreen } from './screens/login';
import { TimelineScreen } from './screens/timeline';
import { pathOf, screenOf } from './routes';
import { useBoard, useClock, useNow } from './store/board';
import { ROLE_LABEL, remainingText, useSession } from './store/session';

/**
 * Klub konsoli — bitta shell, rolga qarab menyu.
 * Xodim ish ekranlarini, klub admini boshqaruv bo'limlarini ko'radi
 * (`docs/designs/PlayBron Xodim.dc.html` shelli).
 */
export function App(): ReactNode {
  useClock();
  const now = useNow();
  const session = useSession((state) => state.session);
  const prune = useSession((state) => state.prune);
  const signOut = useSession((state) => state.signOut);
  const restore = useSession((state) => state.restore);
  const setScreen = useBoard((state) => state.setScreen);
  const drawerOpen = useBoard((state) => state.drawerOpen);
  const setDrawer = useBoard((state) => state.setDrawer);
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

  // Super admin hozircha klub admini menyusini ko'radi; platforma paneli — Faza 7
  const items = session && session.role !== 'STAFF' ? NAV_ADMIN : NAV_STAFF;

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

  if (!session) return <LoginScreen />;

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
                className="ds-hide-xs"
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

              <div className="ds-hide-xs" style={{ width: 1, height: 30, background: 'var(--line-1)' }} />

              <UserMenu
                name={session.name}
                // Tor ekranda sessiya qoldig'i sig'maydi — faqat rol qoladi
                role={
                  compact
                    ? ROLE_LABEL[session.role]
                    : `${ROLE_LABEL[session.role]} · ${remainingText(session.expiresAt)}`
                }
                status="online"
                items={['Chiqish']}
                onSelect={signOut}
              />
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
            {active === 'pos' ? <PosScreen /> : null}
            {active === 'shift' ? <ShiftScreen /> : null}
            {active === 'blacklist' ? <BlacklistScreen /> : null}

            {active === 'dashboard' ? <DashboardScreen /> : null}
            {active === 'staff' ? <StaffScreen /> : null}
            {active === 'club' ? <ClubInfoScreen /> : null}
            {active === 'products' ? <ProductsScreen /> : null}
            {active === 'reports' ? <ReportsScreen /> : null}
            {active === 'expenses' ? <ExpensesScreen /> : null}
            {active === 'settings' ? <SettingsScreen /> : null}
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
