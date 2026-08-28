import { BriefcaseBusiness, GitBranch, Map as MapIcon, Tag, Users, XCircle } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';

import { routes } from '@/app/routes';
import { PageHeader } from '@/components/shared/PageHeader';

export function AdminHubPage() {
  const { t } = useTranslation();
  const cards = [
    {
      to: routes.adminUsers,
      icon: Users,
      title: t('admin:hub.users'),
      hint: t('admin:hub.usersHint'),
    },
    {
      to: routes.adminTerritories,
      icon: MapIcon,
      title: t('admin:hub.territories'),
      hint: t('admin:hub.territoriesHint'),
    },
    {
      to: routes.adminBrands,
      icon: Tag,
      title: t('admin:hub.brands'),
      hint: t('admin:hub.brandsHint'),
    },
    {
      to: routes.adminLossReasons,
      icon: XCircle,
      title: t('admin:hub.lossReasons'),
      hint: t('admin:hub.lossReasonsHint'),
    },
    {
      to: routes.adminPipelines,
      icon: GitBranch,
      title: t('admin:hub.pipelines'),
      hint: t('admin:hub.pipelinesHint'),
    },
    {
      to: routes.adminJobTitles,
      icon: BriefcaseBusiness,
      title: t('admin:hub.jobTitles'),
      hint: t('admin:hub.jobTitlesHint'),
    },
  ];
  return (
    <>
      <PageHeader title={t('admin:hub.title')} />
      <nav aria-label={t('admin:hub.title')} className="grid gap-3 py-4 sm:grid-cols-2">
        {cards.map((card) => (
          <Link
            key={card.to}
            to={card.to}
            className="flex min-h-24 items-center gap-4 rounded-lg border bg-card p-4 hover:bg-muted"
          >
            <card.icon className="size-8 text-primary" aria-hidden="true" />
            <span>
              <span className="block text-lg font-semibold">{card.title}</span>
              <span className="block text-sm text-muted-foreground">{card.hint}</span>
            </span>
          </Link>
        ))}
      </nav>
    </>
  );
}
