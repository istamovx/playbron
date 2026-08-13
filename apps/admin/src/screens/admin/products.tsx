import {
  Button,
  Chip,
  EntityTable,
  Panel,
  ProgressMeter,
  Select,
  StatTile,
  StatusLine,
  TextField,
} from '@playbron/ui';
import { useState, type ReactNode } from 'react';

import { PRODUCT_CATS, stockRow, type Product } from '../../mock/club';
import { S } from '../../mock/data';
import { nextId, useClub } from '../../store/club';
import { FormGrid, Labeled, RowActions } from './parts';

const ALL = 'Barchasi';

const EMPTY: Product = {
  id: '',
  cat: PRODUCT_CATS[0] as string,
  name: '',
  cost: 0,
  price: 0,
  start: 0,
  sold: 0,
};

/**
 * Mahsulotlar — katalog va reestr.
 * Qoldiq qo'lda kiritilmaydi: kirim (`start`) minus kassadan kelgan sotuv (`sold`).
 */
export function ProductsScreen(): ReactNode {
  const products = useClub((state) => state.products);
  const saveProduct = useClub((state) => state.saveProduct);
  const removeProduct = useClub((state) => state.removeProduct);
  const restock = useClub((state) => state.restock);

  const [cat, setCat] = useState(ALL);
  const [query, setQuery] = useState('');
  const [draft, setDraft] = useState<Product | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [restockFor, setRestockFor] = useState<string | null>(null);
  const [amount, setAmount] = useState('');

  const search = query.trim().toLocaleLowerCase('uz-UZ');
  const rows = products
    .filter((product) => (cat === ALL ? true : product.cat === cat))
    .filter((product) =>
      search ? product.name.toLocaleLowerCase('uz-UZ').includes(search) : true,
    )
    .map(stockRow);

  const all = products.map(stockRow);
  const revenue = all.reduce((sum, row) => sum + row.revenue, 0);
  const profit = all.reduce((sum, row) => sum + row.profit, 0);
  const stockValue = all.reduce((sum, row) => sum + row.left * row.product.cost, 0);
  const low = all.filter((row) => row.low).length;

  const submit = (): void => {
    if (!draft) return;
    if (draft.name.trim().length < 2) {
      setError('Mahsulot nomini kiriting');
      return;
    }
    if (draft.price <= 0) {
      setError('Sotuv narxi 0 dan katta bo‘lsin');
      return;
    }
    if (draft.cost > draft.price) {
      setError('Tannarx sotuv narxidan katta bo‘lmasin');
      return;
    }

    saveProduct({ ...draft, id: draft.id || nextId('p'), name: draft.name.trim() });
    setDraft(null);
    setError(null);
  };

  const applyRestock = (id: string): void => {
    const value = Number(amount);
    if (!Number.isFinite(value) || value <= 0) return;
    restock(id, Math.round(value));
    setRestockFor(null);
    setAmount('');
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--gap-panel)' }}>
      <div className="pb-tiles-4">
        <StatTile label="Bar tushumi" value={S(revenue)} unit="so‘m" icon="payments" />
        <StatTile label="Foyda" value={S(profit)} unit="so‘m" icon="trending_up" />
        <StatTile label="Qoldiq qiymati" value={S(stockValue)} unit="so‘m" icon="inventory_2" />
        <StatTile label="Tugayapti" value={String(low)} unit="pozitsiya" icon="warning" />
      </div>

      <Panel
        title={`Katalog (${products.length})`}
        notch
        brackets
        action={
          draft ? null : (
            <Button variant="primary" size="sm" icon="add" onClick={() => setDraft(EMPTY)}>
              Mahsulot qo‘shish
            </Button>
          )
        }
      >
        {draft ? (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--gap-block)', marginBottom: 'var(--gap-panel)' }}>
            <FormGrid>
              <TextField
                label="Nomi"
                value={draft.name}
                onChange={(value) => setDraft({ ...draft, name: value })}
                icon="local_cafe"
              />
              <Labeled label="Kategoriya">
                <Select
                  value={draft.cat}
                  items={PRODUCT_CATS}
                  onChange={(value) => setDraft({ ...draft, cat: value })}
                  style={{ width: '100%' }}
                />
              </Labeled>
              <TextField
                label="Tannarx"
                value={String(draft.cost)}
                onChange={(value) => setDraft({ ...draft, cost: Number(value) || 0 })}
                icon="shopping_cart"
                inputMode="numeric"
              />
              <TextField
                label="Sotuv narxi"
                value={String(draft.price)}
                onChange={(value) => setDraft({ ...draft, price: Number(value) || 0 })}
                icon="sell"
                inputMode="numeric"
              />
              <TextField
                label="Kirim (dona)"
                value={String(draft.start)}
                onChange={(value) => setDraft({ ...draft, start: Number(value) || 0 })}
                icon="inventory"
                inputMode="numeric"
                onSubmitKey={submit}
              />
            </FormGrid>

            {error ? <StatusLine tone="danger" icon="error" parts={error} /> : null}

            <div style={{ display: 'flex', gap: 'var(--gap-tight)', flexWrap: 'wrap' }}>
              <Button variant="primary" notch icon="check" onClick={submit}>
                Saqlash
              </Button>
              <Button variant="ghost" onClick={() => setDraft(null)}>
                Bekor
              </Button>
            </div>
          </div>
        ) : null}

        <div style={{ display: 'flex', gap: 'var(--gap-block)', flexWrap: 'wrap', alignItems: 'center', marginBottom: 'var(--gap-block)' }}>
          <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
            {[ALL, ...PRODUCT_CATS].map((item) => (
              <Chip key={item} selected={cat === item} onClick={() => setCat(item)}>
                {item}
              </Chip>
            ))}
          </div>
          <TextField
            value={query}
            onChange={setQuery}
            icon="search"
            placeholder="Mahsulot izlash"
            style={{ flex: 1, minWidth: 200 }}
          />
        </div>

        <EntityTable
          rows={rows}
          rowKey={(row) => row.product.id}
          empty="Mos mahsulot topilmadi"
          columns={[
            {
              key: 'name',
              header: 'Mahsulot',
              render: (row) => (
                <span style={{ display: 'flex', flexDirection: 'column', gap: 3, minWidth: 0 }}>
                  <span style={{ color: 'var(--text-title)' }}>{row.product.name}</span>
                  <span style={{ font: 'var(--type-data-xs)', color: 'var(--text-dim)' }}>
                    {row.product.cat}
                  </span>
                </span>
              ),
            },
            {
              key: 'price',
              header: 'Narx',
              align: 'right',
              render: (row) => (
                <span style={{ display: 'flex', flexDirection: 'column', gap: 3, alignItems: 'flex-end' }}>
                  <span style={{ font: 'var(--type-data)', color: 'var(--text-title)' }}>
                    {S(row.product.price)}
                  </span>
                  <span style={{ font: 'var(--type-data-xs)', color: 'var(--text-dim)' }}>
                    tannarx {S(row.product.cost)}
                  </span>
                </span>
              ),
            },
            {
              key: 'stock',
              header: 'Qoldiq',
              render: (row) => (
                <span style={{ display: 'flex', flexDirection: 'column', gap: 5, minWidth: 90 }}>
                  <span
                    style={{
                      font: 'var(--type-data)',
                      color: row.low ? 'var(--yellow-100)' : 'var(--text-title)',
                    }}
                  >
                    {row.left} / {row.product.start}
                  </span>
                  <ProgressMeter
                    percent={row.percent}
                    color={row.low ? 'var(--yellow-100)' : 'var(--primary-100)'}
                  />
                </span>
              ),
            },
            {
              key: 'sold',
              header: 'Sotildi',
              align: 'right',
              render: (row) => <span style={{ font: 'var(--type-data)' }}>{row.product.sold}</span>,
            },
            {
              key: 'profit',
              header: 'Foyda',
              align: 'right',
              render: (row) => (
                <span style={{ font: 'var(--type-data)', color: 'var(--secondary-500)', whiteSpace: 'nowrap' }}>
                  {S(row.profit)}
                </span>
              ),
            },
            {
              key: 'actions',
              header: '',
              align: 'right',
              render: (row) =>
                restockFor === row.product.id ? (
                  <span style={{ display: 'inline-flex', gap: 4, alignItems: 'center', justifyContent: 'flex-end' }}>
                    <TextField
                      value={amount}
                      onChange={setAmount}
                      inputMode="numeric"
                      placeholder="Dona"
                      style={{ width: 90 }}
                      onSubmitKey={() => applyRestock(row.product.id)}
                    />
                    <Button
                      variant="primary"
                      size="sm"
                      icon="check"
                      onClick={() => applyRestock(row.product.id)}
                    >
                      Kirim
                    </Button>
                    <Button variant="ghost" size="sm" onClick={() => setRestockFor(null)}>
                      Bekor
                    </Button>
                  </span>
                ) : (
                  <span style={{ display: 'inline-flex', gap: 4, justifyContent: 'flex-end' }}>
                    <Button
                      variant="ghost"
                      size="sm"
                      icon="add_box"
                      onClick={() => {
                        setRestockFor(row.product.id);
                        setAmount('');
                      }}
                    >
                      Kirim
                    </Button>
                    <RowActions
                      onEdit={() => setDraft(row.product)}
                      onRemove={() => removeProduct(row.product.id)}
                    />
                  </span>
                ),
            },
          ]}
        />

        <div style={{ marginTop: 'var(--gap-block)' }}>
          <StatusLine
            tone="neutral"
            icon="sync"
            parts={[
              'Sotilgan miqdor kassadan avtomatik keladi',
              'Admin faqat kirim kiritadi',
            ]}
          />
        </div>
      </Panel>
    </div>
  );
}
