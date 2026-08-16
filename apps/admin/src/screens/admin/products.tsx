import {
  createProduct,
  errorText,
  listProducts,
  updateProduct,
  type ProductDto,
} from '@playbron/api-client';
import {
  Button,
  EntityTable,
  Modal,
  Panel,
  Select,
  StatTile,
  StatusLine,
  Tag,
  TextField,
  toast,
} from '@playbron/ui';
import { useCallback, useEffect, useState, type ReactNode } from 'react';

import { api } from '../../lib/api';
import { S } from '../../mock/data';
import { useBoard } from '../../store/board';
import { useSession } from '../../store/session';
import { FormGrid, Labeled } from './parts';

/**
 * Mahsulotlar — bar/menyu katalogi + qoldiq.
 *
 * Qoldiq (`stockQty`, `0028_stock_and_order_cancel.py`) loyiha egasining
 * so'rovi bilan qo'shildi (2026-08-16): "biror mahsulot qo'shganda sonini
 * ham kiritishi kerak". Sotuvda avtomatik kamayadi, buyurtma bekor
 * qilinsa qaytadi.
 *
 * TANNARX va omborxona harakati (kirim hujjati, inventarizatsiya) hali
 * YO'Q — bu alohida, ancha kattaroq ish (reja #21). Shuning uchun bu
 * yerda foyda/marja ko'rsatilmaydi: soxta raqam chiqarishdan ko'ra
 * ko'rsatmaslik.
 */

interface Draft {
  id: number | null;
  category: string;
  name: string;
  price: string;
  stockQty: string;
  status: 'active' | 'archived';
}

const EMPTY_DRAFT: Draft = {
  id: null,
  category: 'Ichimliklar',
  name: '',
  price: '',
  stockQty: '0',
  status: 'active',
};

export function ProductsScreen(): ReactNode {
  const session = useSession((state) => state.session);
  // Faol klub — header'dagi almashtirgichdan (`store/board.ts::activeClubId`);
  // hali sinxronlanmagan bo'lsa (App() darhol sozlaydi) birinchi a'zolikka tushadi.
  const activeClubId = useBoard((state) => state.activeClubId);
  const clubId = activeClubId ?? session?.clubs[0]?.id ?? null;

  const [products, setProducts] = useState<ProductDto[]>([]);
  const [loading, setLoading] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [draft, setDraft] = useState<Draft | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const reload = useCallback(async (): Promise<void> => {
    if (clubId === null) return;
    setLoading(true);
    setLoadError(null);
    try {
      setProducts(await listProducts(api, clubId));
    } catch (cause) {
      const message = errorText(cause);
      setLoadError(message);
      toast.error(message);
    } finally {
      setLoading(false);
    }
  }, [clubId]);

  useEffect(() => {
    void reload();
  }, [reload]);

  const activeCount = products.filter((p) => p.status === 'active').length;
  const categories = [...new Set(products.map((p) => p.category))];

  const submit = async (): Promise<void> => {
    if (!draft || clubId === null) return;
    const price = Number(draft.price);
    const stockQty = Number(draft.stockQty);
    if (draft.name.trim().length < 1) {
      setError('Mahsulot nomini kiriting');
      return;
    }
    if (!Number.isFinite(price) || price <= 0) {
      setError('Narx musbat bo‘lsin');
      return;
    }
    if (!Number.isInteger(stockQty) || stockQty < 0) {
      setError('Miqdor butun va manfiy bo‘lmagan son bo‘lsin');
      return;
    }

    setSubmitting(true);
    setError(null);
    try {
      if (draft.id === null) {
        await createProduct(api, clubId, {
          category: draft.category,
          name: draft.name.trim(),
          price,
          stockQty,
        });
        toast.success(`Mahsulot qo‘shildi — ${draft.name.trim()}`);
      } else {
        await updateProduct(api, clubId, draft.id, {
          category: draft.category,
          name: draft.name.trim(),
          price,
          status: draft.status,
          stockQty,
        });
        toast.success('Mahsulot yangilandi');
      }
      setDraft(null);
      await reload();
    } catch (cause) {
      const message = errorText(cause);
      setError(message);
      toast.error(message);
    } finally {
      setSubmitting(false);
    }
  };

  const toggleArchive = async (product: ProductDto): Promise<void> => {
    if (clubId === null) return;
    try {
      await updateProduct(api, clubId, product.id, {
        category: product.category,
        name: product.name,
        price: product.price,
        status: product.status === 'active' ? 'archived' : 'active',
        // Arxivlash qoldiqqa TEGMAYDI — `null` yuborilsa server saqlab qoladi
        stockQty: null,
      });
      toast.success(product.status === 'active' ? 'Arxivlandi' : 'Qayta faollashtirildi');
      await reload();
    } catch (cause) {
      toast.error(errorText(cause));
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--gap-panel)' }}>
      <div className="pb-tiles-2">
        <StatTile label="Mahsulotlar" value={String(products.length)} unit="ta" icon="inventory_2" />
        <StatTile label="Faol" value={String(activeCount)} unit="ta" icon="check_circle" />
      </div>

      <Modal
        open={draft !== null}
        onClose={() => {
          setDraft(null);
          setError(null);
        }}
        title={draft?.id === null ? 'Mahsulot qo‘shish' : 'Mahsulotni tahrirlash'}
        variant="drawer"
      >
        {draft ? (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--gap-block)' }}>
            <FormGrid>
              <TextField
                label="Nomi"
                value={draft.name}
                onChange={(value) => setDraft({ ...draft, name: value })}
                icon="local_cafe"
                placeholder="Pepsi 0.5"
              />
              <Labeled label="Kategoriya">
                <Select
                  value={draft.category}
                  items={[...new Set([draft.category, 'Ichimliklar', 'Snack', 'Ovqat', ...categories])]}
                  onChange={(value) => setDraft({ ...draft, category: value })}
                  style={{ width: '100%' }}
                />
              </Labeled>
              <TextField
                label="Narx"
                value={draft.price}
                onChange={(value) => setDraft({ ...draft, price: value })}
                icon="sell"
                inputMode="numeric"
                placeholder="15000"
              />
              <TextField
                label="Miqdor (dona)"
                value={draft.stockQty}
                onChange={(value) => setDraft({ ...draft, stockQty: value })}
                icon="inventory_2"
                inputMode="numeric"
                placeholder="0"
              />
            </FormGrid>

            {error ? <StatusLine tone="danger" icon="error" parts={error} /> : null}

            <div style={{ display: 'flex', gap: 'var(--gap-tight)', flexWrap: 'wrap' }}>
              <Button variant="primary" notch icon="check" disabled={submitting} onClick={() => void submit()}>
                {submitting ? 'Saqlanmoqda…' : 'Saqlash'}
              </Button>
              <Button
                variant="ghost"
                disabled={submitting}
                onClick={() => {
                  setDraft(null);
                  setError(null);
                }}
              >
                Bekor
              </Button>
            </div>
          </div>
        ) : null}
      </Modal>

      <Panel
        title={`Katalog (${products.length})`}
        notch
        brackets
        action={
          <Button
            variant="primary"
            size="sm"
            icon="add"
            onClick={() => {
              setError(null);
              setDraft(EMPTY_DRAFT);
            }}
          >
            Mahsulot qo‘shish
          </Button>
        }
      >
        {loadError ? <StatusLine tone="danger" icon="error" parts={[loadError]} /> : null}

        <EntityTable
          rows={products}
          rowKey={(row) => String(row.id)}
          empty={loading ? 'Yuklanmoqda…' : 'Mahsulot qo‘shilmagan'}
          columns={[
            {
              key: 'name',
              header: 'Mahsulot',
              render: (row) => (
                <span style={{ display: 'flex', flexDirection: 'column', gap: 3, minWidth: 0 }}>
                  <span style={{ color: 'var(--text-title)' }}>{row.name}</span>
                  <span style={{ font: 'var(--type-data-xs)', color: 'var(--text-dim)' }}>
                    {row.category}
                  </span>
                </span>
              ),
            },
            {
              key: 'price',
              header: 'Narx',
              align: 'right',
              render: (row) => (
                <span style={{ font: 'var(--type-data)', color: 'var(--text-title)', whiteSpace: 'nowrap' }}>
                  {S(row.price)}
                </span>
              ),
            },
            {
              key: 'stock',
              header: 'Qoldiq',
              align: 'right',
              render: (row) => (
                // Manfiy — hisobga olinmagan sotuv belgisi (`0028` izohi),
                // shuning uchun ogohlantirish rangida ko'rsatiladi.
                <Tag tone={row.stockQty < 0 ? 'danger' : row.stockQty === 0 ? 'amber' : 'neutral'}>
                  {row.stockQty} dona
                </Tag>
              ),
            },
            {
              key: 'status',
              header: 'Holat',
              render: (row) => (
                <Tag tone={row.status === 'active' ? 'success' : 'neutral'}>
                  {row.status === 'active' ? 'Faol' : 'Arxiv'}
                </Tag>
              ),
            },
            {
              key: 'actions',
              header: '',
              align: 'right',
              render: (row) => (
                <div style={{ display: 'flex', gap: 6, justifyContent: 'flex-end' }}>
                  <Button
                    variant="ghost"
                    size="sm"
                    icon="edit"
                    onClick={() => {
                      setError(null);
                      setDraft({
                        id: row.id,
                        category: row.category,
                        name: row.name,
                        price: String(row.price),
                        stockQty: String(row.stockQty),
                        status: row.status === 'active' ? 'active' : 'archived',
                      });
                    }}
                  />
                  <Button
                    variant="ghost"
                    size="sm"
                    icon={row.status === 'active' ? 'archive' : 'unarchive'}
                    onClick={() => void toggleArchive(row)}
                  />
                </div>
              ),
            },
          ]}
        />
      </Panel>
    </div>
  );
}
