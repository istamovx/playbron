import { Button, Panel } from '@playbron/ui';
import type { ReactNode } from 'react';

import { ORDER_COL, ORDER_FLOW, ORDER_LN, ORDER_NEXT, S, type MockOrder } from '../mock/data';
import { useBoard } from '../store/board';

/** Buyurtmalar kanbani — `PlayBron Xodim.dc.html` BUYURTMALAR bo'limi. */
export function OrdersScreen(): ReactNode {
  const orders = useBoard((state) => state.orders);
  const advance = useBoard((state) => state.advance);

  return (
    <div className="ds-grid" style={{ alignItems: 'start' }}>
      {ORDER_FLOW.map((status) => {
        const items = orders.filter((order) => order.status === status);

        return (
          <Panel key={status} title={`${ORDER_COL[status]} (${items.length})`} notch>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--gap-tight)' }}>
              {items.map((order) => (
                <OrderCard
                  key={order.id}
                  order={order}
                  line={ORDER_LN[status]}
                  nextLabel={ORDER_NEXT[status]}
                  onAdvance={() => advance(order.id)}
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
  );
}

function OrderCard({
  order,
  line,
  nextLabel,
  onAdvance,
}: {
  order: MockOrder;
  line: string;
  nextLabel?: string;
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
        <span style={{ font: 'var(--type-data)', color: 'var(--text-muted)' }}>{order.id}</span>
        <span style={{ font: 'var(--type-control)', color: 'var(--text-title)' }}>
          {order.station}
        </span>
      </div>

      <div style={{ font: 'var(--type-body-sm)', color: 'var(--text-body)' }}>{order.guest}</div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
        {order.lines.map((item) => (
          <div
            key={item.name}
            style={{
              display: 'flex',
              justifyContent: 'space-between',
              gap: 10,
              font: 'var(--type-data-xs)',
              color: 'var(--text-muted)',
            }}
          >
            <span
              style={{
                minWidth: 0,
                overflow: 'hidden',
                textOverflow: 'ellipsis',
                whiteSpace: 'nowrap',
              }}
            >
              {item.name}
            </span>
            <span>{item.qty}</span>
          </div>
        ))}
      </div>

      <div style={{ height: 1, background: 'var(--line-1)' }} />

      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: 8,
          flexWrap: 'wrap',
        }}
      >
        <span style={{ font: 'var(--type-data)', color: 'var(--text-title)' }}>
          {`${S(order.total)} so‘m`}
        </span>
        <span style={{ font: 'var(--type-data-xs)', color: 'var(--text-dim)' }}>{order.ago}</span>
      </div>

      {order.note ? (
        <div style={{ font: 'var(--type-data-xs)', color: 'var(--yellow-100)' }}>
          {`Izoh: ${order.note}`}
        </div>
      ) : null}

      {nextLabel ? (
        <Button variant="secondary" size="sm" block onClick={onAdvance}>
          {nextLabel}
        </Button>
      ) : null}
    </div>
  );
}
