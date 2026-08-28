import { useTranslation } from 'react-i18next';

import { AccountSection } from './AccountSection';

interface PlaceholderSectionProps {
  sectionKey: string;
  title: string;
}

/** Reserved for later changes (opportunities, activities, quotes, equipment). */
export function PlaceholderSection({ sectionKey, title }: PlaceholderSectionProps) {
  const { t } = useTranslation();
  return (
    <AccountSection sectionKey={sectionKey} title={title} defaultOpen={false}>
      <p className="text-sm text-muted-foreground">{t('states.comingSoon')}</p>
    </AccountSection>
  );
}
