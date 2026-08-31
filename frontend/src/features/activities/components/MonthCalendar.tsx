import { Check, ChevronLeft, ChevronRight } from 'lucide-react';
import { useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';

import { routes } from '@/app/routes';
import { ErrorState } from '@/components/shared/ErrorState';
import { NativeSelect } from '@/components/shared/NativeSelect';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { useIsStaff } from '@/features/accounts';
import { useUsers } from '@/features/admin';
import { cn } from '@/lib/cn';

import type { CalendarEntryRead } from '../api';
import { useActivityCalendar } from '../queries';

/** Deterministic 8-color palette: per rep in team view, per activity type in own view. */
const DOT_PALETTE = [
  'bg-blue-500',
  'bg-emerald-500',
  'bg-amber-500',
  'bg-violet-500',
  'bg-rose-500',
  'bg-cyan-500',
  'bg-lime-600',
  'bg-fuchsia-500',
] as const;

const MAX_DOTS = 4;

function paletteIndex(key: string): number {
  let hash = 0;
  for (const char of key) {
    hash = (hash * 31 + char.charCodeAt(0)) | 0;
  }
  return Math.abs(hash) % DOT_PALETTE.length;
}

const DAY_LONG = new Intl.DateTimeFormat('es-ES', { day: 'numeric', month: 'long' });
const MONTH_TITLE = new Intl.DateTimeFormat('es-ES', { month: 'long', year: 'numeric' });
const WEEKDAY = new Intl.DateTimeFormat('es-ES', { weekday: 'short' });

// 2024-01-01 was a Monday; Monday-first headers per Spanish convention.
const WEEKDAYS = Array.from({ length: 7 }, (_, i) => WEEKDAY.format(new Date(2024, 0, 1 + i)));

function isoDay(year: number, month: number, day: number): string {
  return `${String(year)}-${String(month).padStart(2, '0')}-${String(day).padStart(2, '0')}`;
}

interface MonthState {
  year: number;
  month: number; // 1-12
}

function currentMonth(): MonthState {
  const now = new Date();
  return { year: now.getFullYear(), month: now.getMonth() + 1 };
}

function shiftMonth({ year, month }: MonthState, delta: number): MonthState {
  const total = year * 12 + (month - 1) + delta;
  return { year: Math.floor(total / 12), month: (((total % 12) + 12) % 12) + 1 };
}

function DayList({ dateLabel, entries }: { dateLabel: string; entries: CalendarEntryRead[] }) {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const isStaff = useIsStaff();
  return (
    <section aria-label={dateLabel} className="flex flex-col gap-2 rounded-lg border p-3">
      <h3 className="text-sm font-semibold">{dateLabel}</h3>
      {entries.length === 0 ? (
        <p className="text-sm text-muted-foreground">{t('activities:month.emptyDay')}</p>
      ) : (
        <ul className="flex flex-col gap-2">
          {entries.map((entry) => (
            <li key={entry.id}>
              <button
                type="button"
                onClick={() => {
                  navigate(routes.activity(entry.account_id, entry.id));
                }}
                className={cn(
                  'flex min-h-touch w-full flex-wrap items-center gap-2 rounded-lg border p-2 text-left text-sm hover:bg-muted',
                  entry.status === 'done' && 'opacity-60',
                )}
              >
                <span className="tabular-nums text-muted-foreground">{entry.occurred_time}</span>
                <span className="font-medium">{entry.activity_type.name}</span>
                <span className="min-w-0 flex-1 truncate text-muted-foreground">
                  {entry.account_name}
                  {isStaff ? ` · ${entry.owner_name}` : ''}
                </span>
                {entry.status === 'done' ? (
                  <span className="flex items-center gap-1 rounded-full border px-2 text-xs">
                    <Check className="size-3" aria-hidden="true" />
                    {t('activities:month.done')}
                  </span>
                ) : null}
              </button>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

/** The Mes view of Hoy: Monday-first month grid, dots, day expansion (design D4/D5). */
export function MonthCalendar() {
  const { t } = useTranslation();
  const isStaff = useIsStaff();
  const [{ year, month }, setMonthState] = useState<MonthState>(currentMonth);
  const [ownerId, setOwnerId] = useState('');
  const [selectedDay, setSelectedDay] = useState<string>(() => {
    const now = new Date();
    return isoDay(now.getFullYear(), now.getMonth() + 1, now.getDate());
  });
  const reps = useUsers({ role: 'sales_rep', is_active: 'true', page_size: 200 });
  const query = useActivityCalendar(year, month, ownerId || undefined);

  const byDay = useMemo(() => {
    const buckets = new Map<string, CalendarEntryRead[]>();
    for (const entry of query.data?.items ?? []) {
      const bucket = buckets.get(entry.occurred_on) ?? [];
      bucket.push(entry);
      buckets.set(entry.occurred_on, bucket);
    }
    return buckets;
  }, [query.data]);

  const owners = useMemo(() => {
    const seen = new Map<string, string>();
    for (const entry of query.data?.items ?? []) {
      seen.set(entry.owner_id, entry.owner_name);
    }
    return [...seen.entries()];
  }, [query.data]);

  if (query.isPending) {
    return <Skeleton className="h-72 w-full" />;
  }
  if (query.isError) {
    return <ErrorState error={query.error} onRetry={() => void query.refetch()} />;
  }

  const daysInMonth = new Date(year, month, 0).getDate();
  const firstWeekday = (new Date(year, month - 1, 1).getDay() + 6) % 7; // Monday = 0
  const today = new Date();
  const todayIso = isoDay(today.getFullYear(), today.getMonth() + 1, today.getDate());
  const weeks: (number | null)[][] = [];
  const cells: (number | null)[] = [
    ...Array.from({ length: firstWeekday }, () => null),
    ...Array.from({ length: daysInMonth }, (_, i) => i + 1),
  ];
  while (cells.length % 7 !== 0) cells.push(null);
  for (let i = 0; i < cells.length; i += 7) weeks.push(cells.slice(i, i + 7));

  const monthTitle = MONTH_TITLE.format(new Date(year, month - 1, 1));
  const selectedEntries = byDay.get(selectedDay) ?? [];
  const selectedDate = new Date(`${selectedDay}T00:00:00`);

  return (
    <div className="flex flex-col gap-3 lg:grid lg:grid-cols-[2fr_1fr] lg:items-start">
      <div className="flex flex-col gap-3">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div className="flex items-center gap-1">
            <Button
              variant="outline"
              size="icon"
              className="min-h-touch"
              aria-label={t('activities:month.prev')}
              onClick={() => {
                setMonthState((state) => shiftMonth(state, -1));
              }}
            >
              <ChevronLeft className="size-4" aria-hidden="true" />
            </Button>
            <span className="min-w-36 text-center font-semibold capitalize">{monthTitle}</span>
            <Button
              variant="outline"
              size="icon"
              className="min-h-touch"
              aria-label={t('activities:month.next')}
              onClick={() => {
                setMonthState((state) => shiftMonth(state, 1));
              }}
            >
              <ChevronRight className="size-4" aria-hidden="true" />
            </Button>
          </div>
          <div className="flex items-center gap-2">
            <Button
              variant="ghost"
              size="sm"
              className="min-h-touch"
              onClick={() => {
                setMonthState(currentMonth());
                setSelectedDay(todayIso);
              }}
            >
              {t('activities:month.todayShortcut')}
            </Button>
            {isStaff ? (
              <NativeSelect
                aria-label={t('activities:month.rep')}
                value={ownerId}
                onChange={(event) => {
                  setOwnerId(event.target.value);
                }}
                className="w-44"
              >
                <option value="">{t('activities:month.all')}</option>
                {reps.data?.items.map((rep) => (
                  <option key={rep.id} value={rep.id}>
                    {rep.full_name}
                  </option>
                ))}
              </NativeSelect>
            ) : null}
          </div>
        </div>

        {isStaff && !ownerId && owners.length > 0 ? (
          <section
            aria-label={t('activities:month.legend')}
            className="flex flex-wrap items-center gap-3 text-xs text-muted-foreground"
          >
            {owners.map(([id, name]) => (
              <span key={id} className="flex items-center gap-1">
                <span
                  className={cn('size-2 rounded-full', DOT_PALETTE[paletteIndex(id)])}
                  aria-hidden="true"
                />
                {name}
              </span>
            ))}
          </section>
        ) : null}

        <div role="grid" aria-label={monthTitle} className="flex flex-col gap-1">
          <div role="row" className="grid grid-cols-7 gap-1">
            {WEEKDAYS.map((name) => (
              <div
                key={name}
                role="columnheader"
                className="text-center text-xs font-medium text-muted-foreground"
              >
                {name}
              </div>
            ))}
          </div>
          {weeks.map((week, index) => (
            <div role="row" key={index} className="grid grid-cols-7 gap-1">
              {week.map((day, position) => {
                if (day === null) {
                  return <div role="gridcell" key={`empty-${String(position)}`} />;
                }
                const iso = isoDay(year, month, day);
                const entries = byDay.get(iso) ?? [];
                const label = t('activities:month.dayLabel', {
                  date: DAY_LONG.format(new Date(year, month - 1, day)),
                  count: entries.length,
                });
                return (
                  <div role="gridcell" key={iso}>
                    <button
                      type="button"
                      aria-label={label}
                      onClick={() => {
                        setSelectedDay(iso);
                      }}
                      className={cn(
                        'flex min-h-touch w-full flex-col items-center gap-0.5 rounded-md border p-1 text-sm hover:bg-muted',
                        iso === todayIso && 'border-primary',
                        iso === selectedDay && 'bg-primary/10',
                      )}
                    >
                      <span>{day}</span>
                      <span className="flex h-2 items-center gap-0.5" aria-hidden="true">
                        {entries.slice(0, MAX_DOTS).map((entry) => (
                          <span
                            key={entry.id}
                            className={cn(
                              'size-1.5 rounded-full',
                              entry.status === 'done' && 'opacity-50',
                              DOT_PALETTE[
                                paletteIndex(isStaff ? entry.owner_id : entry.activity_type.code)
                              ],
                            )}
                          />
                        ))}
                        {entries.length > MAX_DOTS ? (
                          <span className="text-[10px] leading-none text-muted-foreground">
                            {t('activities:month.more', { count: entries.length - MAX_DOTS })}
                          </span>
                        ) : null}
                      </span>
                    </button>
                  </div>
                );
              })}
            </div>
          ))}
        </div>
      </div>

      <DayList dateLabel={DAY_LONG.format(selectedDate)} entries={selectedEntries} />
    </div>
  );
}
