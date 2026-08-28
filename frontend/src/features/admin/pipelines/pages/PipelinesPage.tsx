import { ArrowDown, ArrowUp, Pencil } from 'lucide-react';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';

import { routes } from '@/app/routes';
import { ErrorState } from '@/components/shared/ErrorState';
import { PageHeader } from '@/components/shared/PageHeader';
import { ResponsiveFormContainer } from '@/components/shared/ResponsiveFormContainer';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { labelOf, useDivisions } from '@/features/reference';
import { toast } from '@/hooks/use-toast';

import type { PipelineRead, PipelineStageRead } from '../api';
import { StageForm } from '../components/StageForm';
import { usePipelineList, useReorderStages } from '../queries';

interface Editing {
  pipeline: PipelineRead;
  stage: PipelineStageRead;
}

export function PipelinesPage() {
  const { t } = useTranslation();
  const pipelines = usePipelineList();
  const divisions = useDivisions();
  const reorder = useReorderStages();
  const [editing, setEditing] = useState<Editing | null>(null);

  const move = async (pipeline: PipelineRead, index: number, delta: -1 | 1) => {
    const ids = pipeline.stages.map((stage) => stage.id);
    const target = index + delta;
    const current = ids[index];
    const other = ids[target];
    if (current === undefined || other === undefined) return;
    ids[index] = other;
    ids[target] = current;
    await reorder.mutateAsync({
      pipelineId: pipeline.id,
      version: pipeline.version,
      stageIds: ids,
    });
    toast({ description: t('admin:pipelines.reordered') });
  };

  let content;
  if (pipelines.isPending) {
    content = (
      <div
        role="status"
        className="grid gap-4 lg:grid-cols-2"
        aria-busy="true"
        aria-label={t('app.loading')}
      >
        <Skeleton className="h-64 w-full" />
        <Skeleton className="h-64 w-full" />
      </div>
    );
  } else if (pipelines.isError) {
    content = <ErrorState error={pipelines.error} onRetry={() => void pipelines.refetch()} />;
  } else {
    content = (
      <div className="grid gap-4 lg:grid-cols-2">
        {pipelines.data.map((pipeline) => (
          <section
            key={pipeline.id}
            aria-labelledby={`pipeline-${pipeline.id}`}
            className="rounded-lg border bg-card p-3"
          >
            <h2 id={`pipeline-${pipeline.id}`} className="text-lg font-semibold">
              {pipeline.name_es}
            </h2>
            {pipeline.division_ids.length > 0 ? (
              <p className="mb-2 text-sm text-muted-foreground">
                {t('admin:pipelines.defaultFor')}
                {': '}
                {pipeline.division_ids
                  .map((id) => labelOf(divisions.data, id, (d) => d.name_es))
                  .join(', ')}
              </p>
            ) : null}
            <ol className="flex flex-col gap-2">
              {pipeline.stages.map((stage, index) => (
                <li
                  key={stage.id}
                  className="flex flex-wrap items-center gap-2 rounded-md border px-3 py-2"
                >
                  <span className="w-6 text-sm font-semibold text-muted-foreground">
                    {stage.sort_order}
                  </span>
                  <span className="flex-1 font-medium">{stage.name_es}</span>
                  <span className="text-sm tabular-nums">
                    {t('admin:pipelines.percent', { value: stage.probability })}
                  </span>
                  {stage.is_won ? <Badge>{t('admin:pipelines.won')}</Badge> : null}
                  {stage.is_lost ? (
                    <Badge variant="destructive">{t('admin:pipelines.lost')}</Badge>
                  ) : null}
                  {stage.is_at_risk ? (
                    <Badge variant="secondary">{t('admin:pipelines.atRisk')}</Badge>
                  ) : null}
                  {stage.is_active ? null : (
                    <Badge variant="outline">{t('admin:pipelines.inactive')}</Badge>
                  )}
                  <span className="flex gap-1">
                    <Button
                      variant="ghost"
                      size="icon"
                      className="min-h-touch min-w-touch"
                      aria-label={t('admin:pipelines.moveUp', { stage: stage.name_es })}
                      disabled={index === 0 || reorder.isPending}
                      onClick={() => void move(pipeline, index, -1)}
                    >
                      <ArrowUp className="size-4" aria-hidden="true" />
                    </Button>
                    <Button
                      variant="ghost"
                      size="icon"
                      className="min-h-touch min-w-touch"
                      aria-label={t('admin:pipelines.moveDown', { stage: stage.name_es })}
                      disabled={index === pipeline.stages.length - 1 || reorder.isPending}
                      onClick={() => void move(pipeline, index, 1)}
                    >
                      <ArrowDown className="size-4" aria-hidden="true" />
                    </Button>
                    <Button
                      variant="outline"
                      size="icon"
                      className="min-h-touch min-w-touch"
                      aria-label={t('admin:pipelines.edit', { stage: stage.name_es })}
                      onClick={() => {
                        setEditing({ pipeline, stage });
                      }}
                    >
                      <Pencil className="size-4" aria-hidden="true" />
                    </Button>
                  </span>
                </li>
              ))}
            </ol>
          </section>
        ))}
      </div>
    );
  }

  return (
    <>
      <PageHeader title={t('admin:pipelines.title')} backTo={routes.admin} />
      <div className="py-3">{content}</div>
      <ResponsiveFormContainer
        open={editing !== null}
        title={t('admin:pipelines.editStage')}
        onClose={() => {
          setEditing(null);
        }}
      >
        {editing ? (
          <StageForm
            key={`${editing.stage.id}-${editing.stage.version}`}
            pipelineId={editing.pipeline.id}
            stage={editing.stage}
            onSaved={() => {
              setEditing(null);
            }}
          />
        ) : null}
      </ResponsiveFormContainer>
    </>
  );
}
