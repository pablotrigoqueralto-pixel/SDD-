import { useTranslation } from 'react-i18next';
import { NavLink } from 'react-router-dom';

import { cn } from '@/lib/cn';

import type { NavEntry } from './navigation';

interface SidebarProps {
  entries: NavEntry[];
}

export function Sidebar({ entries }: SidebarProps) {
  const { t } = useTranslation();
  return (
    <aside className="hidden w-56 shrink-0 border-r bg-background lg:block">
      <div className="px-4 py-4 text-lg font-semibold text-primary">{t('app.name')}</div>
      <nav aria-label={t('nav.mainNavigation')}>
        <ul className="flex flex-col gap-1 px-2">
          {entries.map((entry) => (
            <li key={entry.key}>
              <NavLink
                to={entry.to}
                className={({ isActive }) =>
                  cn(
                    'flex min-h-touch items-center gap-3 rounded-md px-3 text-sm',
                    isActive ? 'bg-accent font-semibold text-accent-foreground' : 'hover:bg-muted',
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
    </aside>
  );
}
