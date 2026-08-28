import { zodResolver } from '@hookform/resolvers/zod';
import { useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import { useForm } from 'react-hook-form';
import { useTranslation } from 'react-i18next';
import { z } from 'zod';

import { Button } from '@/components/ui/button';
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from '@/components/ui/form';
import { Input } from '@/components/ui/input';
import { toast } from '@/hooks/use-toast';
import { isKnownErrorCode } from '@/lib/error-codes';
import { toProblem } from '@/lib/problem';
import { useConflictStore } from '@/store/conflict.store';

import type { PipelineStageRead } from '../api';
import { pipelineKeys, useUpdateStage } from '../queries';

const schema = z.object({
  name: z.string().trim().min(1, 'auth:login.emailRequired').max(100),
  probability: z.coerce
    .number({ invalid_type_error: 'admin:pipelines.form.probabilityRange' })
    .int('admin:pipelines.form.probabilityRange')
    .min(0, 'admin:pipelines.form.probabilityRange')
    .max(100, 'admin:pipelines.form.probabilityRange'),
  is_active: z.boolean(),
});

type StageInput = z.infer<typeof schema>;

interface StageFormProps {
  pipelineId: string;
  stage: PipelineStageRead;
  onSaved: () => void;
}

export function StageForm({ pipelineId, stage, onSaved }: StageFormProps) {
  const { t } = useTranslation();
  const update = useUpdateStage();
  const queryClient = useQueryClient();
  const [formError, setFormError] = useState<string | null>(null);
  const form = useForm<StageInput>({
    resolver: zodResolver(schema),
    defaultValues: {
      name: stage.name_es,
      probability: stage.probability,
      is_active: stage.is_active,
    },
  });

  const handleSubmit = form.handleSubmit(async (values) => {
    setFormError(null);
    try {
      await update.mutateAsync({
        pipelineId,
        stageId: stage.id,
        version: stage.version,
        payload: {
          name: values.name,
          probability: values.probability,
          is_active: values.is_active,
        },
      });
      toast({ description: t('admin:pipelines.updated') });
      onSaved();
    } catch (error) {
      const problem = toProblem(error);
      if (problem.code === 'conflict') {
        useConflictStore
          .getState()
          .show(() => queryClient.invalidateQueries({ queryKey: pipelineKeys.all }));
        return;
      }
      if (problem.code === 'stage_probability_invalid') {
        form.setError('probability', { message: 'errors:stage_probability_invalid' });
        return;
      }
      if (problem.code === 'last_active_stage') {
        form.setError('is_active', { message: 'errors:last_active_stage' });
        return;
      }
      setFormError(
        isKnownErrorCode(problem.code) ? `errors:${problem.code}` : 'toasts.genericError',
      );
    }
  });

  return (
    <Form {...form}>
      <form onSubmit={handleSubmit} className="flex flex-col gap-4" noValidate>
        <FormField
          control={form.control}
          name="name"
          render={({ field }) => (
            <FormItem>
              <FormLabel>{t('admin:pipelines.form.name')}</FormLabel>
              <FormControl>
                <Input className="min-h-touch" {...field} />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />
        <FormField
          control={form.control}
          name="probability"
          render={({ field }) => (
            <FormItem>
              <FormLabel>{t('admin:pipelines.form.probability')}</FormLabel>
              <FormControl>
                <Input
                  type="number"
                  inputMode="numeric"
                  min={0}
                  max={100}
                  step={1}
                  className="min-h-touch"
                  {...field}
                />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />
        <FormField
          control={form.control}
          name="is_active"
          render={({ field }) => (
            <FormItem>
              <label className="flex min-h-touch items-center gap-3 text-sm">
                <input
                  type="checkbox"
                  className="size-5 accent-primary"
                  checked={field.value}
                  onChange={(event) => {
                    field.onChange(event.target.checked);
                  }}
                />
                <span>{t('admin:pipelines.form.active')}</span>
              </label>
              <FormMessage />
            </FormItem>
          )}
        />
        {formError ? (
          <p role="alert" className="text-sm font-medium text-destructive">
            {t(formError)}
          </p>
        ) : null}
        <Button type="submit" size="lg" className="min-h-touch" disabled={update.isPending}>
          {update.isPending ? t('states.saving') : t('actions.save')}
        </Button>
      </form>
    </Form>
  );
}
