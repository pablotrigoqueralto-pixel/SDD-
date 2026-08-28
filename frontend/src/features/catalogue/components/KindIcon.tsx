import { Monitor, Package, Wrench, type LucideIcon } from 'lucide-react';
import { useTranslation } from 'react-i18next';

import type { ProductKind } from '../api';

const ICONS: Record<ProductKind, LucideIcon> = {
  equipment: Monitor,
  consumable: Package,
  service: Wrench,
};

interface KindIconProps {
  kind: ProductKind;
  className?: string;
  /** Skip the screen-reader label when the visible text already names the kind. */
  labelled?: boolean;
}

/** Kind icon with the Spanish label for screen readers. */
export function KindIcon({ kind, className = 'size-5', labelled = true }: KindIconProps) {
  const { t } = useTranslation();
  const Icon = ICONS[kind];
  return (
    <>
      <Icon className={className} aria-hidden="true" />
      {labelled ? <span className="sr-only">{t(`catalogue:kind.${kind}`)}</span> : null}
    </>
  );
}
