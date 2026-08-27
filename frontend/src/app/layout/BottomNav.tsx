import { useTranslation } from 'react-i18next';
import { NavLink } from 'react-router-dom';

import { cn } from '@/lib/cn';

import type { NavEntry } from './navigation';

interface BottomNavProps {
  entries: NavEntry[];
}

export function BottomNav({ entries }: BottomNavProps) {
  const { t } = useTranslation();
  return (
    <nav
      aria-label={t('nav.mainNavigation')}
      className="fixed inset-x-0 bottom-0 z-20 border-t bg-background pb-[env(safe-area-inset-bottom)] lg:hidden"
    >
      <ul className="flex">
        {entries.map((entry) => (
          <li key={entry.key} className="flex-1">
            <NavLink
              to={entry.to}
              className={({ isActive }) =>
                cn(
                  'flex min-h-touch flex-col items-center justify-center gap-0.5 py-2 text-xs',
                  isActive ? 'font-semibold text-primary' : 'text-muted-foreground',
                )
              }
            >
              <entry.icon className="size-5" aria-hidden="true" />
              <span>{t(entry.labelKey)}</span>
            </NavLink>
          </li>
        ))}
      </ul>
    </nav>
  );
}
