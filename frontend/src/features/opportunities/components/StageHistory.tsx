import { useTranslation } from 'react-i18next';

import { formatWhen } from '@/features/activities';
import { usePipelines } from '@/features/reference';

import type { OpportunityRead } from '../api';

interface StageHistoryProps {
  opportunity: OpportunityRead;
}

/** Chronological stage changes, newest first, with actor and date. */
export function StageHistory({ opportunity }: StageHistoryProps) {
  const { t } = useTranslation();
  const pipelines = usePipelines();
  const stages = new Map(
    (pipelines.data ?? [])
      .flatMap((pipeline) => pipeline.stages)
      .map((stage) => [stage.id, stage.name_es]),
  );
  if (opportunity.stage_history.length === 0) return null;
  return (
    <ol className="flex flex-col gap-2">
      {opportunity.stage_history.map((entry) => (
        <li
          key={`${entry.to_stage_id}-${entry.occurred_at}`}
          className="flex flex-wrap items-baseline gap-x-2 text-sm"
        >
          <span className="font-medium">
            {entry.from_stage_id
              ? t('opportunities:sheet.historyEntry', {
                  from: stages.get(entry.from_stage_id) ?? '',
                  to: stages.get(entry.to_stage_id) ?? '',
                })
              : t('opportunities:sheet.historyStart', {
                  to: stages.get(entry.to_stage_id) ?? '',
                })}
          </span>
          <span className="text-muted-foreground">
            {formatWhen(entry.occurred_at, 'both')}
            {' · '}
            {entry.actor_id
              ? t('opportunities:sheet.historyBy', { name: '' }).trim()
              : t('opportunities:sheet.historySystem')}
          </span>
        </li>
      ))}
    </ol>
  );
}
