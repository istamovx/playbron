import { Panel, StatusLine } from '@playbron/ui';
import type { ReactNode } from 'react';

/**
 * Prototipdan hali ko'chirilmagan ekranlar uchun vaqtinchalik joy.
 * Live board va Buyurtmalar tayyor; qolganlari shu tartibda ko'chiriladi.
 */
export function PendingScreen({
  title,
  section,
}: {
  title: string;
  section: string;
}): ReactNode {
  return (
    <Panel title={title} notch brackets>
      <div style={{ display: 'grid', gap: 'var(--gap-block)' }}>
        <StatusLine tone="amber" icon="pending" parts={['Ko‘chirilmoqda', section]} />
        <div
          style={{
            border: '1px dashed var(--line-2)',
            padding: 18,
            textAlign: 'center',
            font: 'var(--type-body-sm)',
            color: 'var(--text-dim)',
          }}
        >
          Bu ekran prototipdagi «{section}» bo‘limidan aynan ko‘chiriladi
        </div>
      </div>
    </Panel>
  );
}
