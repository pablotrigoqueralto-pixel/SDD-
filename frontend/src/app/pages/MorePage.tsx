import { BookOpen, Building2, FileText, LogOut, Settings, Upload } from 'lucide-react';
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
  const isAdmin = user?.role === 'admin';
  const canImport = isAdmin || user?.role === 'back_office';

  const handleLogout = async () => {
    await logout.mutateAsync();
    navigate(routes.login, { replace: true });
  };

  const cards = [
    ...(isAdmin
      ? [
          {
            to: routes.admin,
            icon: Settings,
            title: t('more.admin'),
            hint: t('more.adminHint'),
          },
        ]
      : []),
    {
      to: routes.catalogue,
      icon: BookOpen,
      title: t('more.catalogue'),
      hint: t('more.catalogueHint'),
    },
    {
      to: routes.quotes,
      icon: FileText,
      title: t('more.quotes'),
      hint: t('more.quotesHint'),
    },
    ...(canImport
      ? [
          {
            to: routes.importCatalogue,
            icon: Upload,
            title: t('more.importCatalogue'),
            hint: t('more.importCatalogueHint'),
          },
          {
            to: routes.importAccounts,
            icon: Building2,
            title: t('more.importAccounts'),
            hint: t('more.importAccountsHint'),
          },
        ]
      : []),
  ];

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
          {cards.map((card) => (
            <Link
              key={card.to}
              to={card.to}
              className="flex min-h-touch items-center gap-4 rounded-lg border bg-card p-4 hover:bg-muted"
            >
              <card.icon className="size-6 text-primary" aria-hidden="true" />
              <span>
                <span className="block font-semibold">{card.title}</span>
                <span className="block text-sm text-muted-foreground">{card.hint}</span>
              </span>
            </Link>
          ))}
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
