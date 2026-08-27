import { ArrowLeft } from 'lucide-react';
import type { ReactNode } from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';

import { Button } from '@/components/ui/button';

interface PageHeaderProps {
  title: string;
  backTo?: string;
  action?: ReactNode;
}

/** Sticky header: back button (history or fallback route), h1, primary action always visible. */
export function PageHeader({ title, backTo, action }: PageHeaderProps) {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const goBack = () => {
    if (window.history.length > 1) {
      navigate(-1);
    } else if (backTo) {
      navigate(backTo);
    }
  };
  return (
    <header className="sticky top-0 z-10 flex items-center gap-2 border-b bg-background/95 px-2 py-2 backdrop-blur lg:px-0">
      {backTo ? (
        <Button
          variant="ghost"
          size="icon"
          className="min-h-touch min-w-touch"
          aria-label={t('actions.back')}
          onClick={goBack}
        >
          <ArrowLeft className="size-5" aria-hidden="true" />
        </Button>
      ) : null}
      <h1 className="flex-1 truncate text-lg font-semibold lg:text-2xl">{title}</h1>
      {action}
    </header>
  );
}
