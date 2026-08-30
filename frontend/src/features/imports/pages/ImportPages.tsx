import { useTranslation } from 'react-i18next';

import { ImportFlow } from '../components/ImportFlow';

export function ImportCataloguePage() {
  const { t } = useTranslation();
  return (
    <ImportFlow
      target="products"
      title={t('imports:catalogue.title')}
      columnsHelp={t('imports:catalogue.columns')}
    />
  );
}

export function ImportAccountsPage() {
  const { t } = useTranslation();
  return (
    <ImportFlow
      target="accounts"
      title={t('imports:accounts.title')}
      columnsHelp={t('imports:accounts.columns')}
    />
  );
}
