import {
  Building2,
  CalendarCheck,
  KanbanSquare,
  Menu,
  Search,
  type LucideIcon,
} from 'lucide-react';

import type { SessionUser } from '@/features/auth';

import { routes } from '../routes';

export interface NavEntry {
  key: 'today' | 'accounts' | 'pipeline' | 'search' | 'more';
  to: string;
  icon: LucideIcon;
  labelKey: string;
}

const ENTRIES: NavEntry[] = [
  { key: 'today', to: routes.today, icon: CalendarCheck, labelKey: 'nav.today' },
  { key: 'accounts', to: routes.accounts, icon: Building2, labelKey: 'nav.accounts' },
  { key: 'pipeline', to: routes.opportunities, icon: KanbanSquare, labelKey: 'nav.pipeline' },
  { key: 'search', to: routes.search, icon: Search, labelKey: 'nav.search' },
  { key: 'more', to: routes.more, icon: Menu, labelKey: 'nav.more' },
];

/** Five entries for every role; Administración lives as the first card inside Más. */
export function navigationFor(_user: SessionUser | null): NavEntry[] {
  return ENTRIES;
}
