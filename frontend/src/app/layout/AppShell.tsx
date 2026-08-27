import { Outlet } from 'react-router-dom';

import { OfflineBanner } from '@/components/shared/OfflineBanner';
import { useSessionStore } from '@/features/auth';

import { BottomNav } from './BottomNav';
import { navigationFor } from './navigation';
import { Sidebar } from './Sidebar';

/** Mobile: content + bottom navigation. Desktop (lg+): sidebar + centred content. */
export function AppShell() {
  const user = useSessionStore((state) => state.user);
  const entries = navigationFor(user);
  return (
    <div className="flex min-h-dvh">
      <Sidebar entries={entries} />
      <div className="flex min-w-0 flex-1 flex-col">
        <OfflineBanner />
        <main className="container flex-1 pb-24 lg:pb-8">
          <Outlet />
        </main>
      </div>
      <BottomNav entries={entries} />
    </div>
  );
}
