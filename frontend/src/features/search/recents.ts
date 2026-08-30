/** Device-local recents: last searches and last opened records. Never sent to the server;
 * a missing or failing localStorage simply behaves as "no recents". */

const SEARCHES_KEY = 'quermed.search.recentSearches';
const RECORDS_KEY = 'quermed.search.recentRecords';
const MAX_ENTRIES = 8;

export type RecentKind = 'account' | 'contact' | 'opportunity' | 'quote';

export interface RecentRecord {
  kind: RecentKind;
  id: string;
  label: string;
}

function read<T>(key: string): T[] {
  try {
    const raw = window.localStorage.getItem(key);
    if (!raw) return [];
    const parsed: unknown = JSON.parse(raw);
    return Array.isArray(parsed) ? (parsed as T[]) : [];
  } catch {
    return [];
  }
}

function write(key: string, value: unknown): void {
  try {
    window.localStorage.setItem(key, JSON.stringify(value));
  } catch {
    // Private mode or blocked storage: recents silently stay off.
  }
}

export function recentSearches(): string[] {
  return read<string>(SEARCHES_KEY);
}

export function rememberSearch(term: string): void {
  const cleaned = term.trim();
  if (!cleaned) return;
  const next = [cleaned, ...recentSearches().filter((entry) => entry !== cleaned)];
  write(SEARCHES_KEY, next.slice(0, MAX_ENTRIES));
}

export function recentRecords(): RecentRecord[] {
  return read<RecentRecord>(RECORDS_KEY);
}

export function rememberRecord(record: RecentRecord): void {
  const next = [record, ...recentRecords().filter((entry) => entry.id !== record.id)];
  write(RECORDS_KEY, next.slice(0, MAX_ENTRIES));
}
