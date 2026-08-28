import { BookOpen, LogOut } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { Link, useNavigate } from 'react-router-dom';

import { PageHeader } from '@/components/shared/PageHeader';
import { Button } from '@/components/ui/button';
import { useLogout, useSessionStore } from '@/features/auth';

import { routes } from '../routes';

export function MorePage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const user = useSessionStore((state) => state.user);
  const logout = useLogout();

  const handleLogout = async () => {
    await logout.mutateAsync();
    navigate(routes.login, { replace: true });
  };

  return (
    <>
      <PageHeader title={t('more.title')} />
      <section className="flex flex-col gap-4 py-4">
        {user ? (
          <div className="rounded-lg border p-4">
            <p className="font-medium">{user.full_name}</p>
            <p className="text-sm text-muted-foreground">{user.email}</p>
            <p className="text-sm text-muted-foreground">{t(`roles.${user.role}`)}</p>
          </div>
        ) : null}
        <nav aria-label={t('more.sections')} className="grid gap-3">
          <Link
            to={routes.catalogue}
            className="flex min-h-touch items-center gap-4 rounded-lg border bg-card p-4 hover:bg-muted"
          >
            <BookOpen className="size-6 text-primary" aria-hidden="true" />
            <span>
              <span className="block font-semibold">{t('more.catalogue')}</span>
              <span className="block text-sm text-muted-foreground">{t('more.catalogueHint')}</span>
            </span>
          </Link>
        </nav>
        <Button
          variant="outline"
          size="lg"
          className="min-h-touch justify-start"
          onClick={handleLogout}
          disabled={logout.isPending}
        >
          <LogOut className="size-4" aria-hidden="true" />
          {t('actions.logout')}
        </Button>
      </section>
    </>
  );
}
