import { zodResolver } from '@hookform/resolvers/zod';
import { CalendarClock, Check, XCircle } from 'lucide-react';
import { useState } from 'react';
import { useForm } from 'react-hook-form';
import { useTranslation } from 'react-i18next';

import { NativeSelect } from '@/components/shared/NativeSelect';
import { ResponsiveFormContainer } from '@/components/shared/ResponsiveFormContainer';
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
import { useActivityTypes } from '@/features/reference';
import { toast } from '@/hooks/use-toast';
import { isKnownErrorCode } from '@/lib/error-codes';
import { toProblem } from '@/lib/problem';

import type { ActivityRead } from '../api';
import { useCancelActivity, useCompleteActivity, useRescheduleActivity } from '../queries';
import {
  cancelSchema,
  completeSchema,
  fromLocalInput,
  nowLocal,
  rescheduleSchema,
  toLocalInput,
  tomorrowAtNine,
  type CancelInput,
  type CompleteInput,
  type RescheduleInput,
} from '../schemas';

const OUTCOMES = ['positive', 'neutral', 'negative', 'no_contact'] as const;
type Sheet = 'complete' | 'reschedule' | 'cancel' | null;

interface ActivityActionsProps {
  activity: ActivityRead;
  /** Show the cancel action too (timeline/detail), not only Hecha/Reprogramar (Hoy). */
  withCancel?: boolean;
}

function errorKey(error: unknown): string {
  const problem = toProblem(error);
  return isKnownErrorCode(problem.code) ? `errors:${problem.code}` : 'toasts.genericError';
}

/** One-tap lifecycle actions for a planned activity; each opens a compact sheet. */
export function ActivityActions({ activity, withCancel = false }: ActivityActionsProps) {
  const { t } = useTranslation();
  const [sheet, setSheet] = useState<Sheet>(null);
  if (activity.status !== 'planned') return null;
  const close = () => {
    setSheet(null);
  };
  return (
    <>
      <div className="flex flex-wrap gap-2">
        <Button
          size="sm"
          className="min-h-touch"
          onClick={() => {
            setSheet('complete');
          }}
        >
          <Check className="size-4" aria-hidden="true" />
          {t('activities:actions.complete')}
        </Button>
        <Button
          size="sm"
          variant="outline"
          className="min-h-touch"
          onClick={() => {
            setSheet('reschedule');
          }}
        >
          <CalendarClock className="size-4" aria-hidden="true" />
          {t('activities:actions.reschedule')}
        </Button>
        {withCancel ? (
          <Button
            size="sm"
            variant="ghost"
            className="min-h-touch text-destructive"
            onClick={() => {
              setSheet('cancel');
            }}
          >
            <XCircle className="size-4" aria-hidden="true" />
            {t('activities:actions.cancel')}
          </Button>
        ) : null}
      </div>
      <ResponsiveFormContainer
        open={sheet === 'complete'}
        title={t('activities:complete.title')}
        description={activity.account_name}
        onClose={close}
      >
        {sheet === 'complete' ? <CompleteForm activity={activity} onDone={close} /> : null}
      </ResponsiveFormContainer>
      <ResponsiveFormContainer
        open={sheet === 'reschedule'}
        title={t('activities:reschedule.title')}
        description={activity.account_name}
        onClose={close}
      >
        {sheet === 'reschedule' ? <RescheduleForm activity={activity} onDone={close} /> : null}
      </ResponsiveFormContainer>
      <ResponsiveFormContainer
        open={sheet === 'cancel'}
        title={t('activities:cancel.title')}
        description={activity.account_name}
        onClose={close}
      >
        {sheet === 'cancel' ? <CancelForm activity={activity} onDone={close} /> : null}
      </ResponsiveFormContainer>
    </>
  );
}

interface SheetFormProps {
  activity: ActivityRead;
  onDone: () => void;
}

export function CompleteForm({ activity, onDone }: SheetFormProps) {
  const { t } = useTranslation();
  const types = useActivityTypes();
  const complete = useCompleteActivity();
  const [formError, setFormError] = useState<string | null>(null);
  const form = useForm<CompleteInput>({
    resolver: zodResolver(completeSchema),
    defaultValues: {
      done_at: nowLocal(),
      outcome: '',
      notes: activity.notes ?? '',
      next_action_type_id: '',
      next_action_at: '',
    },
  });
  const nextType = form.watch('next_action_type_id');

  const handleSubmit = form.handleSubmit(async (values) => {
    setFormError(null);
    try {
      await complete.mutateAsync({
        id: activity.id,
        accountId: activity.account_id,
        version: activity.version,
        payload: {
          done_at: fromLocalInput(values.done_at),
          outcome: values.outcome || null,
          notes: values.notes || null,
          next_action: values.next_action_type_id
            ? {
                activity_type_id: values.next_action_type_id,
                scheduled_at: fromLocalInput(values.next_action_at),
              }
            : null,
        },
      });
      toast({ description: t('activities:completed') });
      onDone();
    } catch (error) {
      setFormError(errorKey(error));
    }
  });

  return (
    <Form {...form}>
      <form onSubmit={handleSubmit} className="flex flex-col gap-4" noValidate>
        <FormField
          control={form.control}
          name="done_at"
          render={({ field }) => (
            <FormItem>
              <FormLabel>{t('activities:complete.doneAt')}</FormLabel>
              <FormControl>
                <Input className="min-h-touch" type="datetime-local" {...field} />
              </FormControl>
            </FormItem>
          )}
        />
        <FormField
          control={form.control}
          name="outcome"
          render={({ field }) => (
            <FormItem>
              <FormLabel>{t('activities:complete.outcome')}</FormLabel>
              <FormControl>
                <NativeSelect {...field}>
                  <option value="">{t('activities:form.none')}</option>
                  {OUTCOMES.map((outcome) => (
                    <option key={outcome} value={outcome}>
                      {t(`activities:outcome.${outcome}`)}
                    </option>
                  ))}
                </NativeSelect>
              </FormControl>
            </FormItem>
          )}
        />
        <FormField
          control={form.control}
          name="notes"
          render={({ field }) => (
            <FormItem>
              <FormLabel>{t('activities:complete.notes')}</FormLabel>
              <FormControl>
                <textarea
                  className="min-h-20 w-full rounded-md border border-input bg-background px-3 py-2 text-base"
                  {...field}
                />
              </FormControl>
            </FormItem>
          )}
        />
        <fieldset className="flex flex-col gap-3 rounded-md border p-3">
          <legend className="px-1 text-sm font-medium">
            {t('activities:complete.nextAction')}
          </legend>
          <div className="grid gap-3 sm:grid-cols-2">
            <FormField
              control={form.control}
              name="next_action_type_id"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>{t('activities:form.nextActionType')}</FormLabel>
                  <FormControl>
                    <NativeSelect
                      {...field}
                      onChange={(event) => {
                        field.onChange(event.target.value);
                        if (event.target.value && !form.getValues('next_action_at')) {
                          form.setValue('next_action_at', tomorrowAtNine());
                        }
                      }}
                    >
                      <option value="">{t('activities:form.none')}</option>
                      {types.data
                        ?.filter((type) => type.is_active && type.counts_as_contact)
                        .map((type) => (
                          <option key={type.id} value={type.id}>
                            {type.name_es}
                          </option>
                        ))}
                    </NativeSelect>
                  </FormControl>
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="next_action_at"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>{t('activities:form.nextActionWhen')}</FormLabel>
                  <FormControl>
                    <Input
                      className="min-h-touch"
                      type="datetime-local"
                      disabled={!nextType}
                      {...field}
                    />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
          </div>
        </fieldset>
        {formError ? (
          <p role="alert" className="text-sm font-medium text-destructive">
            {t(formError)}
          </p>
        ) : null}
        <Button type="submit" size="lg" className="min-h-touch" disabled={complete.isPending}>
          {complete.isPending ? t('states.saving') : t('actions.save')}
        </Button>
      </form>
    </Form>
  );
}

export function RescheduleForm({ activity, onDone }: SheetFormProps) {
  const { t } = useTranslation();
  const reschedule = useRescheduleActivity();
  const [formError, setFormError] = useState<string | null>(null);
  const form = useForm<RescheduleInput>({
    resolver: zodResolver(rescheduleSchema),
    defaultValues: { scheduled_at: toLocalInput(new Date(activity.scheduled_at)) },
  });

  const handleSubmit = form.handleSubmit(async (values) => {
    setFormError(null);
    try {
      await reschedule.mutateAsync({
        id: activity.id,
        accountId: activity.account_id,
        version: activity.version,
        scheduledAt: fromLocalInput(values.scheduled_at),
      });
      toast({ description: t('activities:rescheduled') });
      onDone();
    } catch (error) {
      setFormError(errorKey(error));
    }
  });

  return (
    <Form {...form}>
      <form onSubmit={handleSubmit} className="flex flex-col gap-4" noValidate>
        <FormField
          control={form.control}
          name="scheduled_at"
          render={({ field }) => (
            <FormItem>
              <FormLabel>{t('activities:reschedule.when')}</FormLabel>
              <FormControl>
                <Input className="min-h-touch" type="datetime-local" {...field} />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />
        {formError ? (
          <p role="alert" className="text-sm font-medium text-destructive">
            {t(formError)}
          </p>
        ) : null}
        <Button type="submit" size="lg" className="min-h-touch" disabled={reschedule.isPending}>
          {reschedule.isPending ? t('states.saving') : t('actions.save')}
        </Button>
      </form>
    </Form>
  );
}

export function CancelForm({ activity, onDone }: SheetFormProps) {
  const { t } = useTranslation();
  const cancel = useCancelActivity();
  const [formError, setFormError] = useState<string | null>(null);
  const form = useForm<CancelInput>({
    resolver: zodResolver(cancelSchema),
    defaultValues: { reason: '' },
  });

  const handleSubmit = form.handleSubmit(async (values) => {
    setFormError(null);
    try {
      await cancel.mutateAsync({
        id: activity.id,
        accountId: activity.account_id,
        version: activity.version,
        reason: values.reason,
      });
      toast({ description: t('activities:cancelled') });
      onDone();
    } catch (error) {
      setFormError(errorKey(error));
    }
  });

  return (
    <Form {...form}>
      <form onSubmit={handleSubmit} className="flex flex-col gap-4" noValidate>
        <FormField
          control={form.control}
          name="reason"
          render={({ field }) => (
            <FormItem>
              <FormLabel>{t('activities:cancel.reason')}</FormLabel>
              <FormControl>
                <Input className="min-h-touch" {...field} />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />
        {formError ? (
          <p role="alert" className="text-sm font-medium text-destructive">
            {t(formError)}
          </p>
        ) : null}
        <Button
          type="submit"
          size="lg"
          variant="destructive"
          className="min-h-touch"
          disabled={cancel.isPending}
        >
          {cancel.isPending ? t('states.saving') : t('activities:actions.cancel')}
        </Button>
      </form>
    </Form>
  );
}
