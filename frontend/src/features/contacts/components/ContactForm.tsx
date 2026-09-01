import { zodResolver } from '@hookform/resolvers/zod';
import { useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import { useForm } from 'react-hook-form';
import { useTranslation } from 'react-i18next';

import { contactKeys } from '@/api/query-keys';
import { CreateOptionDialog } from '@/components/shared/CreateOptionDialog';
import { NativeSelect } from '@/components/shared/NativeSelect';
import { PhoneListEditor, toPhonePayload, toPhoneRows } from '@/components/shared/PhoneListEditor';
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
import type { AccountRead } from '@/features/accounts';
import { useJobTitles, useSpecialties } from '@/features/reference';
import { toast } from '@/hooks/use-toast';
import { isKnownErrorCode } from '@/lib/error-codes';
import { toProblem } from '@/lib/problem';
import { useConflictStore } from '@/store/conflict.store';

import type { ContactCreate, ContactRead, ContactUpdate, ConsentWrite } from '../api';
import { useCreateContact, useUpdateContact } from '../queries';
import { contactSchema, today, type ContactInput } from '../schemas';

interface ContactFormProps {
  account: AccountRead;
  contact?: ContactRead;
  onSaved: () => void;
}

const CHANNELS = ['email', 'phone'] as const;
const SOURCES = ['verbal', 'email', 'form', 'imported'] as const;
const STATUSES = ['unknown', 'granted', 'denied'] as const;

function toDefaults(contact: ContactRead | undefined): ContactInput {
  return {
    first_name: contact?.first_name ?? '',
    last_name: contact?.last_name ?? '',
    job_title_id: contact?.job_title_id ?? '',
    // No specialty is guessed from the centre's commercial divisions: what a person
    // practises is not derivable from what Quermed sells them.
    specialty_id: contact?.specialty_id ?? '',
    email: contact?.email ?? '',
    phones: toPhoneRows(contact?.phones ?? []),
    is_head_of_department: contact?.is_head_of_department ?? false,
    preferred_channel: contact?.preferred_channel ?? '',
    notes: contact?.notes ?? '',
    is_primary: contact?.is_primary ?? false,
    is_active: contact?.is_active ?? true,
    consent_status: contact?.consent.status ?? 'unknown',
    consent_at: contact?.consent.at ? contact.consent.at.slice(0, 10) : '',
    consent_source: contact?.consent.source ?? '',
  };
}

function consentOf(values: ContactInput): ConsentWrite {
  if (values.consent_status === 'unknown') return { status: 'unknown' };
  return {
    status: values.consent_status,
    at: new Date(`${values.consent_at}T00:00:00`).toISOString(),
    source: values.consent_source || null,
  };
}

function consentChanged(values: ContactInput, contact: ContactRead): boolean {
  return (
    values.consent_status !== contact.consent.status ||
    (values.consent_source || null) !== contact.consent.source ||
    values.consent_at !== (contact.consent.at ? contact.consent.at.slice(0, 10) : '')
  );
}

const TEXT_FIELDS = ['email', 'notes'] as const;
type TextField = (typeof TEXT_FIELDS)[number];

export function ContactForm({ account, contact, onSaved }: ContactFormProps) {
  const { t } = useTranslation();
  const jobTitles = useJobTitles();
  const specialties = useSpecialties();
  const create = useCreateContact();
  const update = useUpdateContact();
  const queryClient = useQueryClient();
  const [formError, setFormError] = useState<string | null>(null);
  const form = useForm<ContactInput>({
    resolver: zodResolver(contactSchema),
    defaultValues: toDefaults(contact),
  });
  const pending = create.isPending || update.isPending;
  const [email, phones, consentStatus] = form.watch(['email', 'phones', 'consent_status']);
  const channelValues: Record<(typeof CHANNELS)[number], string> = {
    email,
    phone: phones.some((phone) => phone.number.trim()) ? 'ok' : '',
  };

  const handleSubmit = form.handleSubmit(async (values) => {
    setFormError(null);
    try {
      if (contact) {
        const payload: ContactUpdate = {};
        if (values.first_name !== contact.first_name) payload.first_name = values.first_name;
        if (values.last_name !== contact.last_name) payload.last_name = values.last_name;
        if ((values.job_title_id || null) !== contact.job_title_id) {
          payload.job_title_id = values.job_title_id || null;
        }
        if ((values.specialty_id || null) !== contact.specialty_id) {
          payload.specialty_id = values.specialty_id || null;
        }
        for (const key of TEXT_FIELDS) {
          const next = values[key] || null;
          if (next !== contact[key]) payload[key] = next;
        }
        const nextPhones = toPhonePayload(values.phones);
        if (
          JSON.stringify(nextPhones) !== JSON.stringify(toPhonePayload(toPhoneRows(contact.phones)))
        ) {
          payload.phones = nextPhones;
        }
        if (values.is_head_of_department !== contact.is_head_of_department) {
          payload.is_head_of_department = values.is_head_of_department;
        }
        if ((values.preferred_channel || null) !== contact.preferred_channel) {
          payload.preferred_channel = values.preferred_channel || null;
        }
        if (values.is_primary !== contact.is_primary) payload.is_primary = values.is_primary;
        if (values.is_active !== contact.is_active) payload.is_active = values.is_active;
        if (consentChanged(values, contact)) payload.consent = consentOf(values);
        await update.mutateAsync({
          id: contact.id,
          accountId: account.id,
          version: contact.version,
          payload,
        });
        toast({ description: t('contacts:updated') });
      } else {
        const payload: ContactCreate = {
          first_name: values.first_name,
          last_name: values.last_name,
          is_primary: values.is_primary,
        };
        if (values.job_title_id) payload.job_title_id = values.job_title_id;
        if (values.specialty_id) payload.specialty_id = values.specialty_id;
        for (const key of TEXT_FIELDS) {
          if (values[key]) payload[key] = values[key];
        }
        const createPhones = toPhonePayload(values.phones);
        if (createPhones.length > 0) payload.phones = createPhones;
        if (values.is_head_of_department) payload.is_head_of_department = true;
        if (values.preferred_channel) payload.preferred_channel = values.preferred_channel;
        if (values.consent_status !== 'unknown') payload.consent = consentOf(values);
        await create.mutateAsync({ accountId: account.id, payload });
        toast({ description: t('contacts:created') });
      }
      onSaved();
    } catch (error) {
      const problem = toProblem(error);
      if (problem.code === 'conflict' && contact) {
        useConflictStore
          .getState()
          .show(() => queryClient.invalidateQueries({ queryKey: contactKeys.all }));
        return;
      }
      const fieldError = problem.errors[0];
      if (fieldError && problem.code !== 'validation_error') {
        const field = fieldError.field === 'consent' ? 'consent_source' : fieldError.field;
        form.setError(field as keyof ContactInput, {
          message: isKnownErrorCode(problem.code)
            ? `errors:${problem.code}`
            : 'errors:validation_error',
        });
        return;
      }
      setFormError(
        isKnownErrorCode(problem.code) ? `errors:${problem.code}` : 'toasts.genericError',
      );
    }
  });

  const textField = (name: TextField, label: string, type = 'text') => (
    <FormField
      key={name}
      control={form.control}
      name={name}
      render={({ field }) => (
        <FormItem>
          <FormLabel>{label}</FormLabel>
          <FormControl>
            <Input className="min-h-touch" type={type} {...field} />
          </FormControl>
          <FormMessage />
        </FormItem>
      )}
    />
  );

  return (
    <Form {...form}>
      <form onSubmit={handleSubmit} className="flex flex-col gap-4" noValidate>
        <div className="grid gap-4 sm:grid-cols-2">
          <FormField
            control={form.control}
            name="first_name"
            render={({ field }) => (
              <FormItem>
                <FormLabel>{t('contacts:form.firstName')}</FormLabel>
                <FormControl>
                  <Input className="min-h-touch" {...field} />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />
          <FormField
            control={form.control}
            name="last_name"
            render={({ field }) => (
              <FormItem>
                <FormLabel>{t('contacts:form.lastName')}</FormLabel>
                <FormControl>
                  <Input className="min-h-touch" {...field} />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />
        </div>
        <div className="grid gap-4 sm:grid-cols-2">
          <FormField
            control={form.control}
            name="job_title_id"
            render={({ field }) => (
              <FormItem>
                <FormLabel>{t('contacts:form.jobTitle')}</FormLabel>
                <FormControl>
                  <NativeSelect {...field}>
                    <option value="">{t('contacts:form.none')}</option>
                    {jobTitles.data
                      ?.filter((title) => title.is_active || title.id === field.value)
                      .map((title) => (
                        <option key={title.id} value={title.id}>
                          {title.name_es}
                        </option>
                      ))}
                  </NativeSelect>
                </FormControl>
                <CreateOptionDialog kind="job_title" onCreated={field.onChange} />
                <FormMessage />
              </FormItem>
            )}
          />
          <FormField
            control={form.control}
            name="specialty_id"
            render={({ field }) => (
              <FormItem>
                <FormLabel>{t('contacts:form.speciality')}</FormLabel>
                <FormControl>
                  <NativeSelect {...field}>
                    <option value="">{t('contacts:form.none')}</option>
                    {specialties.data
                      ?.filter((specialty) => specialty.is_active || specialty.id === field.value)
                      .map((specialty) => (
                        <option key={specialty.id} value={specialty.id}>
                          {specialty.name_es}
                        </option>
                      ))}
                  </NativeSelect>
                </FormControl>
                <CreateOptionDialog kind="specialty" onCreated={field.onChange} />
                <FormMessage />
              </FormItem>
            )}
          />
        </div>
        {textField('email', t('contacts:form.email'), 'email')}
        <div className="grid gap-4 sm:grid-cols-2">
          <FormField
            control={form.control}
            name="phones"
            render={({ field }) => (
              <FormItem>
                <FormLabel>{t('contacts:form.phones')}</FormLabel>
                <FormControl>
                  <PhoneListEditor value={field.value} onChange={field.onChange} />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />
          <FormField
            control={form.control}
            name="is_head_of_department"
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
                  <span>{t('contacts:form.headOfDepartment')}</span>
                </label>
                <p className="text-xs text-muted-foreground">
                  {t('contacts:form.headOfDepartmentHint')}
                </p>
              </FormItem>
            )}
          />
        </div>
        <FormField
          control={form.control}
          name="preferred_channel"
          render={({ field }) => (
            <FormItem>
              <fieldset>
                <legend className="text-sm font-medium">
                  {t('contacts:form.preferredChannel')}
                </legend>
                <div className="mt-1 flex flex-wrap gap-2">
                  {(['', ...CHANNELS] as const).map((channel) => (
                    <label
                      key={channel || 'none'}
                      className="flex min-h-touch items-center gap-2 rounded-md border px-3 text-sm has-[:disabled]:opacity-50"
                    >
                      <input
                        type="radio"
                        name="preferred_channel"
                        value={channel}
                        checked={field.value === channel}
                        disabled={channel !== '' && !channelValues[channel]}
                        onChange={() => {
                          field.onChange(channel);
                        }}
                        className="accent-primary"
                      />
                      <span>{t(`contacts:channels.${channel || 'none'}`)}</span>
                    </label>
                  ))}
                </div>
              </fieldset>
              <FormMessage />
            </FormItem>
          )}
        />
        <fieldset className="flex flex-col gap-3 rounded-md border p-3">
          <legend className="px-1 text-sm font-medium">{t('contacts:consent.title')}</legend>
          <div className="grid gap-3 sm:grid-cols-3">
            <FormField
              control={form.control}
              name="consent_status"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>{t('contacts:consent.status')}</FormLabel>
                  <FormControl>
                    <NativeSelect
                      {...field}
                      onChange={(event) => {
                        field.onChange(event.target.value);
                        if (event.target.value !== 'unknown' && !form.getValues('consent_at')) {
                          form.setValue('consent_at', today());
                        }
                      }}
                    >
                      {STATUSES.map((status) => (
                        <option key={status} value={status}>
                          {t(`contacts:consent.statuses.${status}`)}
                        </option>
                      ))}
                    </NativeSelect>
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="consent_at"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>{t('contacts:consent.date')}</FormLabel>
                  <FormControl>
                    <Input
                      className="min-h-touch"
                      type="date"
                      disabled={consentStatus === 'unknown'}
                      {...field}
                    />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="consent_source"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>{t('contacts:consent.source')}</FormLabel>
                  <FormControl>
                    <NativeSelect {...field} disabled={consentStatus === 'unknown'}>
                      <option value="">{t('contacts:form.none')}</option>
                      {SOURCES.map((source) => (
                        <option key={source} value={source}>
                          {t(`contacts:consent.sources.${source}`)}
                        </option>
                      ))}
                    </NativeSelect>
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
          </div>
        </fieldset>
        <FormField
          control={form.control}
          name="is_primary"
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
                <span>{t('contacts:form.isPrimary')}</span>
              </label>
            </FormItem>
          )}
        />
        {contact ? (
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
                  <span>{t('contacts:form.active')}</span>
                </label>
              </FormItem>
            )}
          />
        ) : null}
        {textField('notes', t('contacts:form.notes'))}
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
