import { zodResolver } from '@hookform/resolvers/zod';
import { useQueryClient } from '@tanstack/react-query';
import { ChevronDown } from 'lucide-react';
import { useState } from 'react';
import { useForm } from 'react-hook-form';
import { useTranslation } from 'react-i18next';

import { activityKeys } from '@/api/query-keys';
import { CheckboxList } from '@/components/shared/CheckboxList';
import { NativeSelect } from '@/components/shared/NativeSelect';
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
import { useIsManager, type AccountRead } from '@/features/accounts';
import { useUsers } from '@/features/admin';
import { useSessionStore } from '@/features/auth';
import { useAccountContacts } from '@/features/contacts';
import { useActivityTypes } from '@/features/reference';
import { toast } from '@/hooks/use-toast';
import { cn } from '@/lib/cn';
import { isKnownErrorCode } from '@/lib/error-codes';
import { toProblem } from '@/lib/problem';
import { useConflictStore } from '@/store/conflict.store';

import type { ActivityCreate, ActivityRead, ActivityUpdate, NextActionWrite } from '../api';
import { useAccountOpportunityOptions, useCreateActivity, useUpdateActivity } from '../queries';
import {
  activitySchema,
  fromLocalInput,
  nowLocal,
  toLocalInput,
  tomorrowAtNine,
  type ActivityInput,
} from '../schemas';
import { ActivityTypePicker } from './ActivityTypePicker';

const OUTCOMES = ['positive', 'neutral', 'negative', 'no_contact'] as const;

interface ActivityFormProps {
  account: AccountRead;
  activity?: ActivityRead;
  /** Pre-selected opportunity (from the opportunity sheet). */
  opportunityId?: string;
  onSaved: (activity: ActivityRead) => void;
}

function toDefaults(
  account: AccountRead,
  activity: ActivityRead | undefined,
  userId: string,
  opportunityId: string | undefined,
) {
  return {
    activity_type_id: activity?.activity_type_id ?? '',
    account_id: account.id,
    scheduled_at: activity ? toLocalInput(new Date(activity.scheduled_at)) : nowLocal(),
    planned: activity ? activity.status === 'planned' : false,
    contact_ids: activity?.contact_ids ?? [],
    duration_minutes: activity?.duration_minutes ? String(activity.duration_minutes) : '',
    outcome: activity?.outcome ?? '',
    subject: activity?.subject ?? '',
    notes: activity?.notes ?? '',
    owner_id: activity?.owner_id ?? userId,
    opportunity_id: activity?.opportunity_id ?? opportunityId ?? '',
    next_action_type_id: '',
    next_action_at: '',
    next_action_subject: '',
  } satisfies ActivityInput;
}

function nextActionOf(values: ActivityInput): NextActionWrite | null {
  if (!values.next_action_type_id) return null;
  return {
    activity_type_id: values.next_action_type_id,
    scheduled_at: fromLocalInput(values.next_action_at),
    subject: values.next_action_subject || null,
  };
}

/** Three taps for the common case (type, save); everything else lives under "Más datos". */
export function ActivityForm({ account, activity, opportunityId, onSaved }: ActivityFormProps) {
  const { t } = useTranslation();
  const user = useSessionStore((state) => state.user);
  const isManager = useIsManager();
  const types = useActivityTypes();
  const contacts = useAccountContacts(account.id);
  const reps = useUsers({ role: 'sales_rep', is_active: 'true', page_size: 200 });
  const create = useCreateActivity();
  const update = useUpdateActivity();
  const queryClient = useQueryClient();
  const [moreOpen, setMoreOpen] = useState(Boolean(activity) || Boolean(opportunityId));
  const options = useAccountOpportunityOptions(account.id);
  const opportunityOptions = (options.data ?? []).filter(
    (option) =>
      option.status === 'open' || option.id === (activity?.opportunity_id ?? opportunityId),
  );
  const [contactsTouched, setContactsTouched] = useState(Boolean(activity));
  const [formError, setFormError] = useState<string | null>(null);
  const form = useForm<ActivityInput>({
    resolver: zodResolver(activitySchema),
    defaultValues: toDefaults(account, activity, user?.id ?? '', opportunityId),
  });
  const pending = create.isPending || update.isPending;
  const [typeId, planned] = form.watch(['activity_type_id', 'planned']);
  const selectedType = types.data?.find((type) => type.id === typeId);
  const isNote = selectedType ? !selectedType.counts_as_contact : false;
  const primaryContact = contacts.data?.find((contact) => contact.is_primary);

  // Smart default: the primary contact is pre-checked once contacts arrive.
  if (!contactsTouched && primaryContact && !activity) {
    setContactsTouched(true);
    form.setValue('contact_ids', [primaryContact.id]);
  }

  const handleSubmit = form.handleSubmit(async (values) => {
    setFormError(null);
    try {
      let saved: ActivityRead;
      if (activity) {
        const payload: ActivityUpdate = {};
        if (values.activity_type_id !== activity.activity_type_id) {
          payload.activity_type_id = values.activity_type_id;
        }
        if (values.subject !== (activity.subject ?? '')) payload.subject = values.subject || null;
        if (values.notes !== (activity.notes ?? '')) payload.notes = values.notes || null;
        if ((values.outcome || null) !== activity.outcome) payload.outcome = values.outcome || null;
        const duration = values.duration_minutes ? Number(values.duration_minutes) : null;
        if (duration !== activity.duration_minutes) payload.duration_minutes = duration;
        const sameContacts =
          values.contact_ids.length === activity.contact_ids.length &&
          values.contact_ids.every((id) => activity.contact_ids.includes(id));
        if (!sameContacts) payload.contact_ids = values.contact_ids;
        if ((values.opportunity_id || null) !== activity.opportunity_id) {
          payload.opportunity_id = values.opportunity_id || null;
        }
        saved = await update.mutateAsync({
          id: activity.id,
          accountId: account.id,
          version: activity.version,
          payload,
        });
        toast({ description: t('activities:updated') });
      } else {
        const payload: ActivityCreate = {
          account_id: values.account_id,
          activity_type_id: values.activity_type_id,
          status: values.planned ? 'planned' : 'done',
          scheduled_at: fromLocalInput(values.scheduled_at),
          contact_ids: values.contact_ids,
        };
        if (values.subject) payload.subject = values.subject;
        if (values.notes) payload.notes = values.notes;
        if (values.outcome && !values.planned) payload.outcome = values.outcome;
        if (values.duration_minutes) payload.duration_minutes = Number(values.duration_minutes);
        if (values.opportunity_id) payload.opportunity_id = values.opportunity_id;
        if (isManager && values.owner_id && values.owner_id !== user?.id) {
          payload.owner_id = values.owner_id;
        }
        const nextAction = nextActionOf(values);
        if (nextAction) payload.next_action = nextAction;
        saved = await create.mutateAsync(payload);
        toast({ description: t('activities:created') });
      }
      onSaved(saved);
    } catch (error) {
      const problem = toProblem(error);
      if (problem.code === 'conflict' && activity) {
        useConflictStore
          .getState()
          .show(() =>
            queryClient.invalidateQueries({ queryKey: activityKeys.detail(activity.id) }),
          );
        return;
      }
      const fieldError = problem.errors[0];
      if (fieldError && isKnownErrorCode(problem.code)) {
        const field = fieldError.field.startsWith('next_action')
          ? 'next_action_at'
          : (fieldError.field as keyof ActivityInput);
        setMoreOpen(true);
        form.setError(field, { message: `errors:${problem.code}` });
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
          name="activity_type_id"
          render={({ field }) => (
            <FormItem>
              <ActivityTypePicker
                name="activity_type_id"
                value={field.value}
                onChange={(typeIdValue) => {
                  field.onChange(typeIdValue);
                  const picked = types.data?.find((type) => type.id === typeIdValue);
                  if (picked && !picked.counts_as_contact) form.setValue('planned', false);
                }}
              />
              <FormMessage />
            </FormItem>
          )}
        />
        <p className="text-sm">
          <span className="text-muted-foreground">{t('activities:form.account')}</span>
          {': '}
          <span className="font-medium">{account.name}</span>
        </p>
        <div className="grid gap-4 sm:grid-cols-2">
          <FormField
            control={form.control}
            name="scheduled_at"
            render={({ field }) => (
              <FormItem>
                <FormLabel>{t('activities:form.when')}</FormLabel>
                <FormControl>
                  <Input className="min-h-touch" type="datetime-local" {...field} />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />
          {activity ? null : (
            <FormField
              control={form.control}
              name="planned"
              render={({ field }) => (
                <FormItem>
                  <fieldset>
                    <legend className="text-sm font-medium">{t('activities:form.state')}</legend>
                    <div className="mt-2 flex gap-2">
                      {(
                        [
                          ['done', false],
                          ['planned', true],
                        ] as const
                      ).map(([key, isPlanned]) => (
                        <label
                          key={key}
                          className={cn(
                            'flex min-h-touch flex-1 cursor-pointer items-center justify-center rounded-md border px-3 text-sm',
                            field.value === isPlanned && 'border-primary bg-accent font-semibold',
                            isPlanned && isNote && 'cursor-not-allowed opacity-50',
                          )}
                        >
                          <input
                            type="radio"
                            name="planned"
                            className="sr-only"
                            checked={field.value === isPlanned}
                            disabled={isPlanned && isNote}
                            onChange={() => {
                              field.onChange(isPlanned);
                              if (isPlanned) form.setValue('scheduled_at', tomorrowAtNine());
                              else form.setValue('scheduled_at', nowLocal());
                            }}
                          />
                          {t(`activities:form.${key}`)}
                        </label>
                      ))}
                    </div>
                  </fieldset>
                </FormItem>
              )}
            />
          )}
        </div>
        {isNote && !activity ? (
          <p className="text-xs text-muted-foreground" role="note">
            {t('activities:form.noteCannotBePlanned')}
          </p>
        ) : null}

        <button
          type="button"
          className="flex min-h-touch items-center justify-between rounded-md border px-3 text-sm font-medium"
          aria-expanded={moreOpen}
          aria-controls="activity-more-data"
          onClick={() => {
            setMoreOpen((open) => !open);
          }}
        >
          <span>{t('activities:form.moreData')}</span>
          <ChevronDown
            className={cn('size-4 transition-transform', moreOpen && 'rotate-180')}
            aria-hidden="true"
          />
        </button>
        <div id="activity-more-data" className="flex flex-col gap-4" hidden={!moreOpen}>
          {opportunityOptions.length > 0 ? (
            <FormField
              control={form.control}
              name="opportunity_id"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>{t('activities:form.opportunity')}</FormLabel>
                  <FormControl>
                    <NativeSelect {...field}>
                      <option value="">{t('activities:form.none')}</option>
                      {opportunityOptions.map((option) => (
                        <option key={option.id} value={option.id}>
                          {option.name}
                        </option>
                      ))}
                    </NativeSelect>
                  </FormControl>
                </FormItem>
              )}
            />
          ) : null}
          <FormField
            control={form.control}
            name="contact_ids"
            render={({ field }) => (
              <FormItem>
                <FormLabel>{t('activities:form.contacts')}</FormLabel>
                <CheckboxList
                  name="contact_ids"
                  options={(contacts.data ?? []).map((contact) => ({
                    value: contact.id,
                    label: `${contact.first_name} ${contact.last_name}`,
                  }))}
                  value={field.value}
                  onChange={(ids) => {
                    setContactsTouched(true);
                    field.onChange(ids);
                  }}
                  emptyLabel={t('activities:form.noContacts')}
                />
                <FormMessage />
              </FormItem>
            )}
          />
          <div className="grid gap-4 sm:grid-cols-2">
            <FormField
              control={form.control}
              name="duration_minutes"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>{t('activities:form.duration')}</FormLabel>
                  <FormControl>
                    <Input className="min-h-touch" type="number" min={1} max={1440} {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            {planned ? null : (
              <FormField
                control={form.control}
                name="outcome"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>{t('activities:form.outcome')}</FormLabel>
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
                    <FormMessage />
                  </FormItem>
                )}
              />
            )}
          </div>
          <FormField
            control={form.control}
            name="subject"
            render={({ field }) => (
              <FormItem>
                <FormLabel>{t('activities:form.subject')}</FormLabel>
                <FormControl>
                  <Input className="min-h-touch" {...field} />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />
          <FormField
            control={form.control}
            name="notes"
            render={({ field }) => (
              <FormItem>
                <FormLabel>{t('activities:form.notes')}</FormLabel>
                <FormControl>
                  <textarea
                    className="min-h-24 w-full rounded-md border border-input bg-background px-3 py-2 text-base"
                    {...field}
                  />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />
          {isManager && !activity ? (
            <FormField
              control={form.control}
              name="owner_id"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>{t('activities:form.owner')}</FormLabel>
                  <FormControl>
                    <NativeSelect {...field}>
                      <option value={user?.id ?? ''}>{t('activities:today.me')}</option>
                      {reps.data?.items
                        .filter((rep) => rep.id !== user?.id)
                        .map((rep) => (
                          <option key={rep.id} value={rep.id}>
                            {rep.full_name}
                          </option>
                        ))}
                    </NativeSelect>
                  </FormControl>
                </FormItem>
              )}
            />
          ) : null}
          {activity ? null : (
            <fieldset className="flex flex-col gap-3 rounded-md border p-3">
              <legend className="px-1 text-sm font-medium">
                {t('activities:form.nextAction')}
              </legend>
              <div className="grid gap-3 sm:grid-cols-3">
                <FormField
                  control={form.control}
                  name="next_action_type_id"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>{t('activities:form.nextActionType')}</FormLabel>
                      <FormControl>
                        <NativeSelect {...field}>
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
                        <Input className="min-h-touch" type="datetime-local" {...field} />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                <FormField
                  control={form.control}
                  name="next_action_subject"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>{t('activities:form.nextActionSubject')}</FormLabel>
                      <FormControl>
                        <Input className="min-h-touch" {...field} />
                      </FormControl>
                    </FormItem>
                  )}
                />
              </div>
            </fieldset>
          )}
        </div>
        {formError ? (
          <p role="alert" className="text-sm font-medium text-destructive">
            {t(formError)}
          </p>
        ) : null}
        <Button type="submit" size="lg" className="min-h-touch" disabled={pending}>
          {pending ? t('states.saving') : t('actions.save')}
        </Button>
      </form>
    </Form>
  );
}
