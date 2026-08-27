import { LogOut } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';

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
