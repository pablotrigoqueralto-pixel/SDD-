import {
  Building2,
  CalendarCheck,
  KanbanSquare,
  Menu,
  Settings,
  type LucideIcon,
} from 'lucide-react';

import type { SessionUser } from '@/features/auth';

import { routes } from '../routes';

export interface NavEntry {
  key: 'today' | 'accounts' | 'pipeline' | 'more' | 'admin';
  to: string;
  icon: LucideIcon;
  labelKey: string;
}

const ENTRIES: NavEntry[] = [
  { key: 'today', to: routes.today, icon: CalendarCheck, labelKey: 'nav.today' },
  { key: 'accounts', to: routes.accounts, icon: Building2, labelKey: 'nav.accounts' },
  { key: 'pipeline', to: routes.opportunities, icon: KanbanSquare, labelKey: 'nav.pipeline' },
  { key: 'more', to: routes.more, icon: Menu, labelKey: 'nav.more' },
  { key: 'admin', to: routes.admin, icon: Settings, labelKey: 'nav.admin' },
];

/** At most five entries; admin only for administrators. A later change swaps in Buscar. */
export function navigationFor(user: SessionUser | null): NavEntry[] {
  return ENTRIES.filter((entry) => entry.key !== 'admin' || user?.role === 'admin');
}
