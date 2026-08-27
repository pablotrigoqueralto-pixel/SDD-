import type { ReactNode } from 'react';
import { useTranslation } from 'react-i18next';

import { Skeleton } from '@/components/ui/skeleton';
import { useIsDesktop } from '@/hooks/useMediaQuery';

import { EmptyState } from './EmptyState';
import { ErrorState } from './ErrorState';

export interface DataListColumn<T> {
  key: string;
  header: string;
  cell: (item: T) => ReactNode;
  /** Hide the column on the mobile card (default: shown). */
  hideOnCard?: boolean;
}

interface DataListProps<T> {
  items: T[] | undefined;
  columns: DataListColumn<T>[];
  getKey: (item: T) => string;
  /** Card title on mobile (first column by default). */
  renderTitle?: (item: T) => ReactNode;
  onSelect?: (item: T) => void;
  isLoading: boolean;
  error?: unknown;
  onRetry?: () => void;
  emptyTitle: string;
  emptyAction?: ReactNode;
}

/** Column definitions written once: cards below `lg`, a table at `lg` and above. */
export function DataList<T>({
  items,
  columns,
  getKey,
  renderTitle,
  onSelect,
  isLoading,
  error,
  onRetry,
  emptyTitle,
  emptyAction,
}: DataListProps<T>) {
  const { t } = useTranslation();
  const isDesktop = useIsDesktop();

  if (isLoading) {
    return (
      <div className="flex flex-col gap-3" aria-busy="true" aria-label={t('app.loading')}>
        {Array.from({ length: 4 }, (_, index) => (
          <Skeleton key={index} className="h-16 w-full" />
        ))}
      </div>
    );
  }
  if (error) {
    return <ErrorState error={error} {...(onRetry ? { onRetry } : {})} />;
  }
  if (!items || items.length === 0) {
    return <EmptyState title={emptyTitle} action={emptyAction} />;
  }

  const [first, ...rest] = columns;
  const title = renderTitle ?? first?.cell ?? (() => null);

  if (!isDesktop) {
    return (
      <ul className="flex flex-col gap-2">
        {items.map((item) => (
          <li key={getKey(item)}>
            <CardRow item={item} title={title(item)} columns={rest} onSelect={onSelect} />
          </li>
        ))}
      </ul>
    );
  }

  return (
    <div className="overflow-x-auto rounded-lg border">
      <table className="w-full text-sm">
        <thead className="bg-muted/50 text-left">
          <tr>
            {columns.map((column) => (
              <th key={column.key} scope="col" className="px-3 py-2 font-medium">
                {column.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {items.map((item) => (
            <tr
              key={getKey(item)}
              className={onSelect ? 'cursor-pointer hover:bg-muted/40' : undefined}
              onClick={
                onSelect
                  ? () => {
                      onSelect(item);
                    }
                  : undefined
              }
            >
              {columns.map((column) => (
                <td key={column.key} className="border-t px-3 py-2">
                  {column.cell(item)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

interface CardRowProps<T> {
  item: T;
  title: ReactNode;
  columns: DataListColumn<T>[];
  onSelect?: ((item: T) => void) | undefined;
}

function CardRow<T>({ item, title, columns, onSelect }: CardRowProps<T>) {
  const body = (
    <>
      <div className="font-medium">{title}</div>
      <dl className="mt-1 flex flex-wrap gap-x-3 gap-y-0.5 text-sm text-muted-foreground">
        {columns
          .filter((column) => !column.hideOnCard)
          .map((column) => (
            <div key={column.key} className="flex gap-1">
              <dt className="sr-only">{column.header}</dt>
              <dd>{column.cell(item)}</dd>
            </div>
          ))}
      </dl>
    </>
  );
  if (onSelect) {
    return (
      <button
        type="button"
        onClick={() => {
          onSelect(item);
        }}
        className="min-h-touch w-full rounded-lg border bg-card p-3 text-left active:bg-muted"
      >
        {body}
      </button>
    );
  }
  return <div className="rounded-lg border bg-card p-3">{body}</div>;
}
