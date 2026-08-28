import { useQueryClient } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';

import { opportunityKeys } from '@/api/query-keys';
import { NativeSelect } from '@/components/shared/NativeSelect';
import { usePipelines } from '@/features/reference';
import { toast } from '@/hooks/use-toast';
import { toProblem } from '@/lib/problem';
import { useConflictStore } from '@/store/conflict.store';

import type { OpportunityRead } from '../api';
import { useMoveStage } from '../queries';

interface StagePickerProps {
  opportunity: OpportunityRead;
  disabled: boolean;
}

/** Native select over the pipeline's open stages: the mobile way to move a card. */
export function StagePicker({ opportunity, disabled }: StagePickerProps) {
  const { t } = useTranslation();
  const pipelines = usePipelines();
  const move = useMoveStage();
  const queryClient = useQueryClient();
  const pipeline = pipelines.data?.find((candidate) => candidate.id === opportunity.pipeline_id);
  const openStages = (pipeline?.stages ?? []).filter(
    (stage) => !stage.is_won && !stage.is_lost && !stage.is_at_risk && stage.is_active,
  );

  const handleChange = async (stageId: string) => {
    if (!stageId || stageId === opportunity.stage_id) return;
    try {
      await move.mutateAsync({
        id: opportunity.id,
        accountId: opportunity.account_id,
        version: opportunity.version,
        stageId,
      });
      const stage = openStages.find((candidate) => candidate.id === stageId);
      toast({ description: t('opportunities:moved', { stage: stage?.name_es ?? '' }) });
    } catch (error) {
      const problem = toProblem(error);
      if (problem.code === 'conflict') {
        useConflictStore
          .getState()
          .show(() =>
            queryClient.invalidateQueries({ queryKey: opportunityKeys.detail(opportunity.id) }),
          );
      } else {
        toast({ description: t('toasts.genericError'), variant: 'destructive' });
      }
    }
  };

  return (
    <NativeSelect
      aria-label={t('opportunities:sheet.stage')}
      value={opportunity.stage_id}
      disabled={disabled || opportunity.status !== 'open' || move.isPending}
      onChange={(event) => void handleChange(event.target.value)}
      className="lg:w-56"
    >
      {opportunity.status !== 'open' ? (
        <option value={opportunity.stage_id}>{opportunity.stage_name}</option>
      ) : null}
      {openStages.map((stage) => (
        <option key={stage.id} value={stage.id}>
          {stage.name_es}
        </option>
      ))}
    </NativeSelect>
  );
}
