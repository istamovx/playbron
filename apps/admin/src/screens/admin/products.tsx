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
import { useSession } from '../../store/session';
import { FormGrid, Labeled } from './parts';

/**
 * Mahsulotlar — bar/menyu katalogi.
 *
 * Prototipda tannarx, kirim/qoldiq va avtomatik sotuv hisobi bor edi —
 * backend'da inventar kuzatuvi yo'q (bu alohida, ancha katta loyiha:
 * omborxona harakati, inventarizatsiya). Shu bosqichda faqat KATALOG:
 * nomi, kategoriya, narx, faol/arxiv. Qoldiq keyingi bosqichda qo'shiladi.
 */

interface Draft {
  id: number | null;
  category: string;
  name: string;
  price: string;
  status: 'active' | 'archived';
}

const EMPTY_DRAFT: Draft = { id: null, category: 'Ichimliklar', name: '', price: '', status: 'active' };

export function ProductsScreen(): ReactNode {
  const session = useSession((state) => state.session);
  const clubId = session?.clubs[0]?.id ?? null;

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
    if (draft.name.trim().length < 1) {
      setError('Mahsulot nomini kiriting');
      return;
    }
    if (!Number.isFinite(price) || price <= 0) {
      setError('Narx musbat bo‘lsin');
      return;
    }

    setSubmitting(true);
    setError(null);
    try {
      if (draft.id === null) {
        await createProduct(api, clubId, { category: draft.category, name: draft.name.trim(), price });
        toast.success(`Mahsulot qo‘shildi — ${draft.name.trim()}`);
      } else {
        await updateProduct(api, clubId, draft.id, {
          category: draft.category,
          name: draft.name.trim(),
          price,
          status: draft.status,
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
      });
      toast.success(product.status === 'active' ? 'Arxivlandi' : 'Qayta faollashtirildi');
      await reload();
    } catch (cause) {
      toast.error(errorText(cause));
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--gap-panel)' }}>
      <div className="pb-tiles-4">
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
