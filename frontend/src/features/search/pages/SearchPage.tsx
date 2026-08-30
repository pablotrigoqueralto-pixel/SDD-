import { Building2, Clock, FileText, KanbanSquare, User } from 'lucide-react';
import { useEffect, useState, type ReactNode } from 'react';
import { useTranslation } from 'react-i18next';
import { Link, useNavigate } from 'react-router-dom';

import { routes } from '@/app/routes';
import { EmptyState } from '@/components/shared/EmptyState';
import { PageHeader } from '@/components/shared/PageHeader';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { Skeleton } from '@/components/ui/skeleton';
import { formatPrice } from '@/features/catalogue';

import { SEARCH_MIN_LENGTH, type SearchResultsRead } from '../api';
import { useGlobalSearch } from '../queries';
import {
  recentRecords,
  recentSearches,
  rememberRecord,
  rememberSearch,
  type RecentKind,
  type RecentRecord,
} from '../recents';

const SEARCH_DEBOUNCE_MS = 300;

const KIND_GROUP_KEYS: Record<RecentKind, string> = {
  account: 'accounts',
  contact: 'contacts',
  opportunity: 'opportunities',
  quote: 'quotes',
};

const KIND_ROUTES: Record<RecentKind, (id: string) => string> = {
  account: routes.account,
  contact: routes.account, // contacts live on their account's 360º page
  opportunity: routes.opportunity,
  quote: routes.quote,
};

interface RowProps {
  label: string;
  detail: string;
  badge?: ReactNode;
  onOpen: () => void;
}

function ResultRow({ label, detail, badge, onOpen }: RowProps) {
  return (
    <li>
      <button
        type="button"
        onClick={onOpen}
        className="flex min-h-touch w-full flex-wrap items-center justify-between gap-2 rounded-lg border p-3 text-left text-sm hover:bg-muted"
      >
        <span className="min-w-0 flex-1">
          <span className="block truncate font-medium">{label}</span>
          <span className="block truncate text-muted-foreground">{detail}</span>
        </span>
        {badge}
      </button>
    </li>
  );
}

interface GroupProps {
  title: string;
  total: number;
  hasMore: boolean;
  seeAllTo?: string;
  children: ReactNode;
}

function Group({ title, total, hasMore, seeAllTo, children }: GroupProps) {
  const { t } = useTranslation();
  if (total === 0) return null;
  return (
    <section className="flex flex-col gap-2">
      <h2 className="flex items-center justify-between text-base font-semibold">
        {title}
        {hasMore && seeAllTo ? (
          <Link to={seeAllTo} className="text-sm font-normal underline">
            {t('search:seeAll')}
          </Link>
        ) : null}
      </h2>
      <ul className="flex flex-col gap-2">{children}</ul>
    </section>
  );
}

function Recents({ onSearch }: { onSearch: (term: string) => void }) {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const searches = recentSearches();
  const records = recentRecords();
  if (searches.length === 0 && records.length === 0) {
    return <p className="text-sm text-muted-foreground">{t('search:recents.empty')}</p>;
  }
  return (
    <section className="flex flex-col gap-4" aria-label={t('search:recents.title')}>
      {searches.length > 0 ? (
        <div className="flex flex-col gap-2">
          <h2 className="text-sm font-medium text-muted-foreground">
            {t('search:recents.searches')}
          </h2>
          <ul className="flex flex-wrap gap-2">
            {searches.map((term) => (
              <li key={term}>
                <button
                  type="button"
                  className="flex min-h-touch items-center gap-1 rounded-full border px-3 py-1 text-sm hover:bg-muted"
                  onClick={() => {
                    onSearch(term);
                  }}
                >
                  <Clock className="size-3" aria-hidden="true" />
                  {term}
                </button>
              </li>
            ))}
          </ul>
        </div>
      ) : null}
      {records.length > 0 ? (
        <div className="flex flex-col gap-2">
          <h2 className="text-sm font-medium text-muted-foreground">
            {t('search:recents.records')}
          </h2>
          <ul className="flex flex-col gap-2">
            {records.map((record) => (
              <ResultRow
                key={`${record.kind}-${record.id}`}
                label={record.label}
                detail={t(`search:groups.${KIND_GROUP_KEYS[record.kind]}`)}
                onOpen={() => {
                  navigate(KIND_ROUTES[record.kind](record.id));
                }}
              />
            ))}
          </ul>
        </div>
      ) : null}
    </section>
  );
}

function Results({ term, results }: { term: string; results: SearchResultsRead }) {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const open = (record: RecentRecord, to: string) => {
    rememberRecord(record);
    navigate(to);
  };
  const totalHits =
    results.accounts.total +
    results.contacts.total +
    results.opportunities.total +
    results.quotes.total;
  if (totalHits === 0) {
    return <EmptyState title={t('search:empty', { term })} />;
  }
  const encoded = encodeURIComponent(term);
  return (
    <div className="flex flex-col gap-6">
      <Group
        title={t('search:groups.accounts')}
        total={results.accounts.total}
        hasMore={results.accounts.has_more}
        seeAllTo={`${routes.accounts}?q=${encoded}`}
      >
        {results.accounts.items.map((hit) => (
          <ResultRow
            key={hit.id}
            label={hit.name}
            detail={[hit.city, hit.province_code].filter(Boolean).join(' · ')}
            badge={<Building2 className="size-4 text-muted-foreground" aria-hidden="true" />}
            onOpen={() => {
              open({ kind: 'account', id: hit.id, label: hit.name }, routes.account(hit.id));
            }}
          />
        ))}
      </Group>
      <Group title={t('search:groups.contacts')} total={results.contacts.total} hasMore={false}>
        {results.contacts.items.map((hit) => (
          <ResultRow
            key={hit.id}
            label={hit.full_name}
            detail={[hit.account_name, hit.email ?? hit.mobile].filter(Boolean).join(' · ')}
            badge={<User className="size-4 text-muted-foreground" aria-hidden="true" />}
            onOpen={() => {
              open(
                { kind: 'contact', id: hit.account_id, label: hit.full_name },
                routes.account(hit.account_id),
              );
            }}
          />
        ))}
      </Group>
      <Group
        title={t('search:groups.opportunities')}
        total={results.opportunities.total}
        hasMore={results.opportunities.has_more}
        seeAllTo={`${routes.opportunities}?q=${encoded}&status=all`}
      >
        {results.opportunities.items.map((hit) => (
          <ResultRow
            key={hit.id}
            label={hit.name}
            detail={`${hit.account_name} · ${formatPrice(hit.amount)}`}
            badge={
              <span className="flex items-center gap-1">
                <Badge variant={hit.status === 'open' ? 'secondary' : 'outline'}>
                  {hit.stage_name}
                </Badge>
                <KanbanSquare className="size-4 text-muted-foreground" aria-hidden="true" />
              </span>
            }
            onOpen={() => {
              open(
                { kind: 'opportunity', id: hit.id, label: hit.name },
                routes.opportunity(hit.id),
              );
            }}
          />
        ))}
      </Group>
      <Group
        title={t('search:groups.quotes')}
        total={results.quotes.total}
        hasMore={results.quotes.has_more}
        seeAllTo={`${routes.quotes}?q=${encoded}&status=all`}
      >
        {results.quotes.items.map((hit) => (
          <ResultRow
            key={hit.id}
            label={hit.display_number}
            detail={`${hit.account_name} · ${formatPrice(hit.total)}`}
            badge={
              <span className="flex items-center gap-1">
                <Badge
                  variant={
                    hit.status === 'sent' && hit.is_expired
                      ? 'destructive'
                      : hit.status === 'accepted'
                        ? 'default'
                        : 'secondary'
                  }
                >
                  {t(
                    hit.status === 'sent' && hit.is_expired
                      ? 'quotes:status.expired'
                      : `quotes:status.${hit.status}`,
                  )}
                </Badge>
                <FileText className="size-4 text-muted-foreground" aria-hidden="true" />
              </span>
            }
            onOpen={() => {
              open({ kind: 'quote', id: hit.id, label: hit.display_number }, routes.quote(hit.id));
            }}
          />
        ))}
      </Group>
    </div>
  );
}

/** The Buscar page: one box, grouped scoped results, device-local recents. */
export function SearchPage() {
  const { t } = useTranslation();
  const [input, setInput] = useState('');
  const [term, setTerm] = useState('');

  useEffect(() => {
    const handle = window.setTimeout(() => {
      const cleaned = input.trim();
      setTerm(cleaned.length >= SEARCH_MIN_LENGTH ? cleaned : '');
      if (cleaned.length >= SEARCH_MIN_LENGTH) rememberSearch(cleaned);
    }, SEARCH_DEBOUNCE_MS);
    return () => {
      window.clearTimeout(handle);
    };
  }, [input]);

  const query = useGlobalSearch(term);

  return (
    <>
      <PageHeader title={t('search:title')} />
      <section className="flex flex-col gap-4 py-4">
        <Input
          type="search"
          className="min-h-touch"
          placeholder={t('search:placeholder')}
          aria-label={t('search:title')}
          value={input}
          onChange={(event) => {
            setInput(event.target.value);
          }}
        />
        {term === '' ? (
          <>
            <p className="text-sm text-muted-foreground">{t('search:hint')}</p>
            <Recents onSearch={setInput} />
          </>
        ) : query.isPending ? (
          <Skeleton className="h-40 w-full" />
        ) : query.isError ? (
          <p role="alert" className="text-sm text-destructive">
            {t('toasts.genericError')}
          </p>
        ) : (
          <Results term={term} results={query.data} />
        )}
      </section>
    </>
  );
}
