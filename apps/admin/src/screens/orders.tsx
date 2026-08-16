import {
  advanceOrder,
  createOrder,
  errorText,
  listLiveStations,
  listOrders,
  listProducts,
  type LiveStationDto,
  type OrderDto,
  type ProductDto,
} from '@playbron/api-client';
import { Button, Modal, Panel, Select, StatusLine, toast } from '@playbron/ui';
import { useCallback, useEffect, useState, type ReactNode } from 'react';

import { api } from '../lib/api';
import { S } from '../mock/data';
import { useSession } from '../store/session';
import { Labeled } from './admin/parts';

const FLOW = ['NEW', 'ACCEPTED', 'PREPARING', 'DELIVERED'] as const;
const COL_LABEL: Record<(typeof FLOW)[number], string> = {
  NEW: 'Yangi',
  ACCEPTED: 'Qabul qilindi',
  PREPARING: 'Tayyorlanmoqda',
  DELIVERED: 'Yetkazildi',
};
const COL_LINE: Record<(typeof FLOW)[number], string> = {
  NEW: 'var(--yellow-100)',
  ACCEPTED: 'var(--line-2)',
  PREPARING: 'var(--primary-100)',
  DELIVERED: 'var(--line-1)',
};
const NEXT_LABEL: Partial<Record<(typeof FLOW)[number], string>> = {
  NEW: 'Qabul qilish',
  ACCEPTED: 'Tayyorlashga',
  PREPARING: 'Yetkazildi',
};

/** Buyurtmalar kanbani — real `orders`/`order_items` (`0013_pos.py`). */
export function OrdersScreen(): ReactNode {
  const session = useSession((state) => state.session);
  const clubId = session?.clubs[0]?.id ?? null;

  const [orders, setOrders] = useState<OrderDto[]>([]);
  const [stations, setStations] = useState<LiveStationDto[]>([]);
  const [products, setProducts] = useState<ProductDto[]>([]);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [newOpen, setNewOpen] = useState(false);
  const [busy, setBusy] = useState<number | null>(null);

  const reload = useCallback(async (): Promise<void> => {
    if (clubId === null) return;
    try {
      const [o, s, p] = await Promise.all([
        listOrders(api, clubId),
        listLiveStations(api, clubId),
        listProducts(api, clubId),
      ]);
      setOrders(o);
      setStations(s);
      setProducts(p.filter((item) => item.status === 'active'));
      setLoadError(null);
    } catch (cause) {
      setLoadError(errorText(cause));
    }
  }, [clubId]);

  useEffect(() => {
    void reload();
  }, [reload]);

  const advance = async (order: OrderDto): Promise<void> => {
    if (clubId === null) return;
    setBusy(order.id);
    try {
      await advanceOrder(api, clubId, order.id);
      toast.success('Buyurtma holati o‘zgardi');
      await reload();
    } catch (cause) {
      toast.error(errorText(cause));
    } finally {
      setBusy(null);
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--gap-panel)' }}>
      <NewOrderModal
        open={newOpen}
        onClose={() => setNewOpen(false)}
        clubId={clubId}
        stations={stations}
        products={products}
        onCreated={() => {
          setNewOpen(false);
          void reload();
        }}
      />

      <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
        <Button variant="primary" size="sm" icon="add_shopping_cart" onClick={() => setNewOpen(true)}>
          Yangi buyurtma
        </Button>
      </div>

      {loadError ? <StatusLine tone="danger" icon="error" parts={[loadError]} /> : null}

      <div className="ds-grid" style={{ alignItems: 'start' }}>
        {FLOW.map((status) => {
          const items = orders.filter((order) => order.status === status);
          return (
            <Panel key={status} title={`${COL_LABEL[status]} (${items.length})`} notch>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--gap-tight)' }}>
                {items.map((order) => (
                  <OrderCard
                    key={order.id}
                    order={order}
                    line={COL_LINE[status]}
                    nextLabel={NEXT_LABEL[status]}
                    busy={busy === order.id}
                    onAdvance={() => void advance(order)}
                  />
                ))}
                {items.length === 0 ? (
                  <div
                    style={{
                      border: '1px dashed var(--line-2)',
                      padding: 18,
                      textAlign: 'center',
                      font: 'var(--type-body-sm)',
                      color: 'var(--text-dim)',
                    }}
                  >
                    Buyurtma yo‘q
                  </div>
                ) : null}
              </div>
            </Panel>
          );
        })}
      </div>
    </div>
  );
}

function OrderCard({
  order,
  line,
  nextLabel,
  busy,
  onAdvance,
}: {
  order: OrderDto;
  line: string;
  nextLabel?: string;
  busy: boolean;
  onAdvance: () => void;
}): ReactNode {
  return (
    <div
      style={{
        padding: 'var(--card-pad)',
        background: 'var(--surface-card)',
        border: `1px solid ${line}`,
        clipPath: 'var(--clip-tr)',
        display: 'flex',
        flexDirection: 'column',
        gap: 8,
        minWidth: 0,
      }}
    >
      <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', gap: 8 }}>
        <span style={{ font: 'var(--type-data)', color: 'var(--text-muted)' }}>{`#${order.id}`}</span>
        <span style={{ font: 'var(--type-control)', color: 'var(--text-title)' }}>
          {order.stationCode ?? '—'}
        </span>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
        {order.items.map((item, index) => (
          <div
            key={index}
            style={{
              display: 'flex',
              justifyContent: 'space-between',
              gap: 10,
              font: 'var(--type-data-xs)',
              color: 'var(--text-muted)',
            }}
          >
            <span style={{ minWidth: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
              {item.productName}
            </span>
            <span>{item.qty}</span>
          </div>
        ))}
      </div>

      <div style={{ height: 1, background: 'var(--line-1)' }} />

      <span style={{ font: 'var(--type-data)', color: 'var(--text-title)' }}>{`${S(order.total)} so‘m`}</span>

      {nextLabel ? (
        <Button variant="secondary" size="sm" block disabled={busy} onClick={onAdvance}>
          {nextLabel}
        </Button>
      ) : null}
    </div>
  );
}

function NewOrderModal({
  open,
  onClose,
  clubId,
  stations,
  products,
  onCreated,
}: {
  open: boolean;
  onClose: () => void;
  clubId: number | null;
  stations: LiveStationDto[];
  products: ProductDto[];
  onCreated: () => void;
}): ReactNode {
  const occupied = stations.filter((s) => s.bookingId !== null);
  const [stationLabel, setStationLabel] = useState('');
  const [cart, setCart] = useState<Record<number, number>>({});
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const stationLabelOf = (s: LiveStationDto): string => `${s.code} · ${s.guestLabel ?? 'Mijoz'}`;

  // Faqat `open` chegarasida qayta o'rnatiladi — stansiyalar ro'yxati fon'da
  // yangilanganda savat tozalanib qolmasin (shuning uchun bog'liqlik
  // ro'yxati ataylab faqat `open`).
  useEffect(() => {
    if (open) {
      setStationLabel(occupied.length > 0 ? stationLabelOf(occupied[0] as LiveStationDto) : '');
      setCart({});
      setError(null);
    }
  }, [open]);

  const bump = (productId: number, delta: number): void => {
    setCart((current) => {
      const next = { ...current };
      next[productId] = Math.max(0, (next[productId] ?? 0) + delta);
      if (!next[productId]) delete next[productId];
      return next;
    });
  };

  const lines = Object.entries(cart).map(([id, qty]) => ({
    product: products.find((p) => p.id === Number(id)),
    qty,
  }));
  const total = lines.reduce((sum, line) => sum + (line.product?.price ?? 0) * line.qty, 0);

  const submit = async (): Promise<void> => {
    if (clubId === null || lines.length === 0) {
      setError('Kamida bitta mahsulot tanlang');
      return;
    }
    const station = occupied.find((s) => stationLabelOf(s) === stationLabel);

    setSubmitting(true);
    setError(null);
    try {
      await createOrder(api, clubId, {
        bookingId: station?.bookingId ?? null,
        items: lines.map((line) => ({ productId: (line.product as ProductDto).id, qty: line.qty })),
      });
      toast.success('Buyurtma yuborildi');
      onCreated();
    } catch (cause) {
      const message = errorText(cause);
      setError(message);
      toast.error(message);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Modal open={open} onClose={onClose} title="Yangi buyurtma" variant="drawer">
      <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--gap-block)' }}>
        {occupied.length === 0 ? (
          <StatusLine tone="warn" icon="warning" parts={['Hozir band xona yo‘q']} />
        ) : (
          <Labeled label="Xona">
            <Select
              value={stationLabel}
              items={occupied.map(stationLabelOf)}
              onChange={setStationLabel}
              size="lg"
              notch
              style={{ width: '100%' }}
            />
          </Labeled>
        )}

        {products.length === 0 ? (
          <StatusLine
            tone="warn"
            icon="inventory_2"
            parts={['Mahsulot qo‘shilmagan', 'Avval Katalogga mahsulot qo‘shing']}
          />
        ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
          {products.map((product) => (
            <div
              key={product.id}
              style={{
                display: 'grid',
                gridTemplateColumns: 'minmax(0, 1fr) auto',
                alignItems: 'center',
                gap: 8,
                padding: '8px 10px',
                background: 'var(--surface-field)',
                border: '1px solid var(--line-1)',
              }}
            >
              <span style={{ display: 'grid', gap: 2, minWidth: 0 }}>
                <span style={{ font: 'var(--type-body-sm)', color: 'var(--text-body)' }}>
                  {product.name}
                </span>
                <span style={{ font: 'var(--type-data-xs)', color: 'var(--text-dim)' }}>
                  {S(product.price)}
                </span>
              </span>
              <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                <Stepper label="−" onClick={() => bump(product.id, -1)} />
                <span style={{ font: 'var(--type-data)', minWidth: 16, textAlign: 'center' }}>
                  {cart[product.id] ?? 0}
                </span>
                <Stepper label="+" onClick={() => bump(product.id, 1)} />
              </div>
            </div>
          ))}
        </div>
        )}

        <div style={{ display: 'flex', justifyContent: 'space-between', font: 'var(--type-data)' }}>
          <span style={{ color: 'var(--text-dim)' }}>Jami</span>
          <span style={{ color: 'var(--text-title)' }}>{`${S(total)} so‘m`}</span>
        </div>

        {error ? <StatusLine tone="danger" icon="error" parts={error} /> : null}

        <Button
          variant="primary"
          size="lg"
          block
          notch
          icon="send"
          disabled={submitting || lines.length === 0}
          onClick={() => void submit()}
        >
          {submitting ? 'Yuborilmoqda…' : 'Buyurtmani yuborish'}
        </Button>
      </div>
    </Modal>
  );
}

function Stepper({ label, onClick }: { label: string; onClick: () => void }): ReactNode {
  return (
    <button
      type="button"
      onClick={onClick}
      style={{
        cursor: 'pointer',
        width: 'var(--control-h)',
        height: 'var(--control-h)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        border: '1px solid var(--line-2)',
        background: 'transparent',
        color: 'var(--text-muted)',
        font: 'var(--type-control)',
      }}
    >
      {label}
    </button>
  );
}
