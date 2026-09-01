import { zodResolver } from '@hookform/resolvers/zod';
import { useQueryClient } from '@tanstack/react-query';
import { ChevronDown } from 'lucide-react';
import { useState } from 'react';
import { useForm } from 'react-hook-form';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';

import { accountKeys } from '@/api/query-keys';
import { routes } from '@/app/routes';
import { CheckboxList } from '@/components/shared/CheckboxList';
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
import { useSessionStore } from '@/features/auth';
import { useAccountTypes, useBrands, useDivisions } from '@/features/reference';
import { toast } from '@/hooks/use-toast';
import { cn } from '@/lib/cn';
import { isKnownErrorCode } from '@/lib/error-codes';
import { toProblem } from '@/lib/problem';
import { PROVINCES } from '@/lib/provinces';
import { useConflictStore } from '@/store/conflict.store';

import type { AccountCreate, AccountRead, AccountUpdate } from '../api';
import { territoryForProvince, useKnownTerritories } from '../hooks';
import { useCreateAccount, useUpdateAccount } from '../queries';
import { accountSchema, type AccountInput } from '../schemas';

interface AccountFormProps {
  account?: AccountRead;
  onSaved: (account: AccountRead) => void;
}

const TEXT_FIELDS = [
  'tax_id',
  'street',
  'postal_code',
  'city',
  'email',
  'website',
  'customer_code',
  'notes',
  'billing_notes',
] as const;
type TextField = (typeof TEXT_FIELDS)[number];

function toDefaults(account: AccountRead | undefined): AccountInput {
  return {
    name: account?.name ?? '',
    account_type_id: account?.account_type_id ?? '',
    province_code: account?.province_code ?? '',
    tax_id: account?.tax_id ?? '',
    street: account?.street ?? '',
    postal_code: account?.postal_code ?? '',
    city: account?.city ?? '',
    phones: toPhoneRows(account?.phones ?? []),
    email: account?.email ?? '',
    website: account?.website ?? '',
    customer_code: account?.customer_code ?? '',
    notes: account?.notes ?? '',
    billing_notes: account?.billing_notes ?? '',
    division_ids: account?.division_ids ?? [],
    brand_ids: account?.brand_ids ?? [],
    is_active: account?.is_active ?? true,
  };
}

function sameSet(a: string[], b: string[]): boolean {
  return a.length === b.length && a.every((item) => b.includes(item));
}

/** Only fields whose value changed travel in the PATCH (null clears an optional one). */
function toUpdate(values: AccountInput, account: AccountRead): AccountUpdate {
  const payload: AccountUpdate = {};
  if (values.name !== account.name) payload.name = values.name;
  if (values.account_type_id !== account.account_type_id) {
    payload.account_type_id = values.account_type_id;
  }
  if (values.province_code !== account.province_code) payload.province_code = values.province_code;
  for (const key of TEXT_FIELDS) {
    const next = values[key] || null;
    if (next !== account[key]) payload[key] = next;
  }
  const phones = toPhonePayload(values.phones);
  if (JSON.stringify(phones) !== JSON.stringify(toPhonePayload(toPhoneRows(account.phones)))) {
    payload.phones = phones;
  }
  if (!sameSet(values.division_ids, account.division_ids)) {
    payload.division_ids = values.division_ids;
  }
  if (!sameSet(values.brand_ids, account.brand_ids)) payload.brand_ids = values.brand_ids;
  if (values.is_active !== account.is_active) payload.is_active = values.is_active;
  return payload;
}

function toCreate(values: AccountInput): AccountCreate {
  const payload: AccountCreate = {
    name: values.name,
    account_type_id: values.account_type_id,
    province_code: values.province_code,
    division_ids: values.division_ids,
    brand_ids: values.brand_ids,
  };
  for (const key of TEXT_FIELDS) {
    if (values[key]) payload[key] = values[key];
  }
  const phones = toPhonePayload(values.phones);
  if (phones.length > 0) payload.phones = phones;
  return payload;
}

export function AccountForm({ account, onSaved }: AccountFormProps) {
  const { t } = useTranslation();
  const user = useSessionStore((state) => state.user);
  const accountTypes = useAccountTypes();
  const divisions = useDivisions();
  const brands = useBrands();
  const territories = useKnownTerritories();
  const create = useCreateAccount();
  const update = useUpdateAccount();
  const queryClient = useQueryClient();
  const [moreOpen, setMoreOpen] = useState(Boolean(account));
  const [formError, setFormError] = useState<string | null>(null);
  const [existingAccountId, setExistingAccountId] = useState<string | null>(null);
  const form = useForm<AccountInput>({
    resolver: zodResolver(accountSchema),
    defaultValues: toDefaults(account),
  });
  const pending = create.isPending || update.isPending;
  const province = form.watch('province_code');
  const territory = territoryForProvince(territories, province);
  const canDeactivate = Boolean(account) && user?.role !== 'back_office';

  const handleSubmit = form.handleSubmit(async (values) => {
    setFormError(null);
    setExistingAccountId(null);
    try {
      let saved: AccountRead;
      if (account) {
        saved = await update.mutateAsync({
          id: account.id,
          version: account.version,
          payload: toUpdate(values, account),
        });
        toast({ description: t('accounts:updated') });
      } else {
        saved = await create.mutateAsync(toCreate(values));
        toast({ description: t('accounts:created') });
      }
      onSaved(saved);
    } catch (error) {
      const problem = toProblem(error);
      if (problem.code === 'conflict' && account) {
        useConflictStore
          .getState()
          .show(() => queryClient.invalidateQueries({ queryKey: accountKeys.detail(account.id) }));
        return;
      }
      if (problem.code === 'tax_id_already_exists') {
        setMoreOpen(true);
        setExistingAccountId(problem.extensions.existing_account_id ?? null);
        form.setError('tax_id', { message: 'accounts:form.taxIdExists' });
        return;
      }
      const fieldErrors = problem.errors.filter((fieldError) =>
        (TEXT_FIELDS as readonly string[]).includes(fieldError.field),
      );
      if (fieldErrors.length > 0) {
        setMoreOpen(true);
        for (const fieldError of fieldErrors) {
          form.setError(fieldError.field as TextField, {
            message: isKnownErrorCode(fieldError.code)
              ? `errors:${fieldError.code}`
              : 'errors:validation_error',
          });
        }
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
          {name === 'tax_id' && existingAccountId ? (
            <Link to={routes.account(existingAccountId)} className="text-sm underline">
              {t('accounts:form.taxIdExistsLink')}
            </Link>
          ) : null}
        </FormItem>
      )}
    />
  );

  return (
    <Form {...form}>
      <form onSubmit={handleSubmit} className="flex flex-col gap-4" noValidate>
        <FormField
          control={form.control}
          name="name"
          render={({ field }) => (
            <FormItem>
              <FormLabel>{t('accounts:form.name')}</FormLabel>
              <FormControl>
                <Input className="min-h-touch" {...field} />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />
        <div className="grid gap-4 sm:grid-cols-2">
          <FormField
            control={form.control}
            name="account_type_id"
            render={({ field }) => (
              <FormItem>
                <FormLabel>{t('accounts:form.type')}</FormLabel>
                <FormControl>
                  <NativeSelect {...field}>
                    <option value="">{t('accounts:form.selectType')}</option>
                    {accountTypes.data
                      ?.filter((type) => type.is_active || type.id === field.value)
                      .map((type) => (
                        <option key={type.id} value={type.id}>
                          {type.name_es}
                        </option>
                      ))}
                  </NativeSelect>
                </FormControl>
                <CreateOptionDialog kind="account_type" onCreated={field.onChange} />
                <FormMessage />
              </FormItem>
            )}
          />
          <FormField
            control={form.control}
            name="province_code"
            render={({ field }) => (
              <FormItem>
                <FormLabel>{t('accounts:form.province')}</FormLabel>
                <FormControl>
                  <NativeSelect {...field}>
                    <option value="">{t('accounts:form.selectProvince')}</option>
                    {PROVINCES.map((item) => (
                      <option key={item.code} value={item.code}>
                        {item.name}
                      </option>
                    ))}
                  </NativeSelect>
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />
        </div>
        {!account && province ? (
          <p className="text-sm text-muted-foreground" role="note">
            {territory
              ? t('accounts:form.territoryHint', { territory: territory.name })
              : t('accounts:form.territoryNone')}
            {' · '}
            {user?.role === 'sales_rep'
              ? t('accounts:form.ownerHintSelf')
              : t('accounts:form.ownerHintAuto')}
          </p>
        ) : null}

        <button
          type="button"
          className="flex min-h-touch items-center justify-between rounded-md border px-3 text-sm font-medium"
          aria-expanded={moreOpen}
          aria-controls="account-more-data"
          onClick={() => {
            setMoreOpen((open) => !open);
          }}
        >
          <span>{t('accounts:form.moreData')}</span>
          <ChevronDown
            className={cn('size-4 transition-transform', moreOpen && 'rotate-180')}
            aria-hidden="true"
          />
        </button>
        <div id="account-more-data" className="flex flex-col gap-4" hidden={!moreOpen}>
          {textField('tax_id', t('accounts:form.taxId'))}
          {textField('street', t('accounts:form.street'))}
          <div className="grid gap-4 sm:grid-cols-2">
            {textField('postal_code', t('accounts:form.postalCode'))}
            {textField('city', t('accounts:form.city'))}
          </div>
          <div className="grid gap-4 sm:grid-cols-2">
            <FormField
              control={form.control}
              name="phones"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>{t('accounts:phones.title')}</FormLabel>
                  <FormControl>
                    <PhoneListEditor value={field.value} onChange={field.onChange} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            {textField('email', t('accounts:form.email'), 'email')}
          </div>
          {textField('website', t('accounts:form.website'), 'url')}
          {textField('customer_code', t('accounts:form.customerCode'))}
          <FormField
            control={form.control}
            name="division_ids"
            render={({ field }) => (
              <FormItem>
                <FormLabel>{t('accounts:form.divisions')}</FormLabel>
                <CheckboxList
                  name="division_ids"
                  options={(divisions.data ?? []).map((division) => ({
                    value: division.id,
                    label: division.name_es,
                  }))}
                  value={field.value}
                  onChange={field.onChange}
                  emptyLabel={t('accounts:form.noDivisions')}
                />
              </FormItem>
            )}
          />
          <FormField
            control={form.control}
            name="brand_ids"
            render={({ field }) => (
              <FormItem>
                <FormLabel>{t('accounts:form.brands')}</FormLabel>
                <CheckboxList
                  name="brand_ids"
                  options={(brands.data ?? [])
                    .filter((brand) => brand.is_active || field.value.includes(brand.id))
                    .map((brand) => ({
                      value: brand.id,
                      label: brand.name,
                      hint: brand.is_own
                        ? t('reference:brandKind.own')
                        : t('reference:brandKind.competitor'),
                    }))}
                  value={field.value}
                  onChange={field.onChange}
                  emptyLabel={t('accounts:form.noBrands')}
                />
              </FormItem>
            )}
          />
          <FormField
            control={form.control}
            name="billing_notes"
            render={({ field }) => (
              <FormItem>
                <FormLabel>{t('accounts:form.billingNotes')}</FormLabel>
                <FormControl>
                  <textarea
                    {...field}
                    rows={4}
                    className="w-full rounded-md border bg-background p-2 text-sm"
                  />
                </FormControl>
                <p className="text-xs text-muted-foreground">
                  {t('accounts:form.billingNotesHint')}
                </p>
                <FormMessage />
              </FormItem>
            )}
          />
          {textField('notes', t('accounts:form.notes'))}
          {canDeactivate ? (
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
                    <span>{t('accounts:form.active')}</span>
                  </label>
                </FormItem>
              )}
            />
          ) : null}
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
