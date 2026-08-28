import { zodResolver } from '@hookform/resolvers/zod';
import { useQueryClient } from '@tanstack/react-query';
import { ChevronDown } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';
import { FormProvider, useForm } from 'react-hook-form';
import { useTranslation } from 'react-i18next';

import { opportunityKeys } from '@/api/query-keys';
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
import { useAccount, useAccounts, useIsManager } from '@/features/accounts';
import { useUsers } from '@/features/admin';
import { parsePrice } from '@/features/catalogue';
import { useAccountTypes, useDivisions, usePipelines } from '@/features/reference';
import { toast } from '@/hooks/use-toast';
import { cn } from '@/lib/cn';
import { isKnownErrorCode } from '@/lib/error-codes';
import { toProblem } from '@/lib/problem';
import { useConflictStore } from '@/store/conflict.store';

import type { OpportunityCreate, OpportunityRead, OpportunityUpdate } from '../api';
import { useCreateOpportunity, useUpdateOpportunity } from '../queries';
import { opportunitySchema, toDateInput, type OpportunityInput } from '../schemas';
import { TenderFields } from './TenderFields';

interface OpportunityFormProps {
  /** Pre-filled centre (from the 360º page); otherwise a search box appears. */
  accountId?: string;
  opportunity?: OpportunityRead;
  onSaved: (opportunity: OpportunityRead) => void;
}

function toDefaults(
  opportunity: OpportunityRead | undefined,
  accountId: string | undefined,
): OpportunityInput {
  return {
    account_id: opportunity?.account_id ?? accountId ?? '',
    division_id: opportunity?.division_id ?? '',
    estimated_amount: opportunity ? opportunity.estimated_amount.replace('.', ',') : '',
    name: opportunity?.name ?? '',
    description: opportunity?.description ?? '',
    expected_close_date: toDateInput(opportunity?.expected_close_date),
    owner_id: '',
    is_tender: opportunity?.is_tender ?? false,
    tender_reference: opportunity?.tender_reference ?? '',
    tender_deadline: toDateInput(opportunity?.tender_deadline),
    estimated_award_date: toDateInput(opportunity?.estimated_award_date),
  };
}

export function OpportunityForm({ accountId, opportunity, onSaved }: OpportunityFormProps) {
  const { t } = useTranslation();
  const isManager = useIsManager();
  const divisions = useDivisions();
  const pipelines = usePipelines();
  const create = useCreateOpportunity();
  const update = useUpdateOpportunity();
  const queryClient = useQueryClient();
  const [moreOpen, setMoreOpen] = useState(Boolean(opportunity));
  const [formError, setFormError] = useState<string | null>(null);
  const [accountSearch, setAccountSearch] = useState('');
  const form = useForm<OpportunityInput>({
    resolver: zodResolver(opportunitySchema),
    defaultValues: toDefaults(opportunity, accountId),
  });
  const pending = create.isPending || update.isPending;
  const needsAccountPicker = !accountId && !opportunity;
  const accounts = useAccounts(
    needsAccountPicker
      ? { ...(accountSearch ? { q: accountSearch } : {}), page_size: 20 }
      : { page_size: 1 },
  );
  const selectedAccountId = form.watch('account_id');
  const selectedAccount = useAccount(
    !opportunity && selectedAccountId ? selectedAccountId : undefined,
  );
  const reps = useUsers(
    isManager ? { role: 'sales_rep', is_active: 'true', page_size: 200 } : { page_size: 1 },
  );
  const accountTypes = useAccountTypes();
  const tenderPrefilled = useRef(false);
  useEffect(() => {
    // Public-buyer centres default to a tender opportunity (once, still editable).
    if (opportunity || tenderPrefilled.current) return;
    const type = accountTypes.data?.find(
      (candidate) => candidate.id === selectedAccount.data?.account_type_id,
    );
    if (type?.buys_via_tender) {
      form.setValue('is_tender', true);
      tenderPrefilled.current = true;
    }
  }, [accountTypes.data, selectedAccount.data, opportunity, form]);
  const divisionId = form.watch('division_id');
  const defaultPipeline = pipelines.data?.find((pipeline) =>
    pipeline.division_ids.includes(divisionId),
  );
  const accountDivisions = selectedAccount.data?.division_ids ?? [];
  const orderedDivisions = [...(divisions.data ?? [])].sort(
    (a, b) => Number(accountDivisions.includes(b.id)) - Number(accountDivisions.includes(a.id)),
  );

  const handleSubmit = form.handleSubmit(async (values) => {
    setFormError(null);
    try {
      let saved: OpportunityRead;
      if (opportunity) {
        const payload: OpportunityUpdate = {};
        if (values.name && values.name !== opportunity.name) payload.name = values.name;
        const description = values.description || null;
        if (description !== opportunity.description) payload.description = description;
        const amount = parsePrice(values.estimated_amount);
        if (amount && amount !== opportunity.estimated_amount && opportunity.lines.length === 0) {
          payload.estimated_amount = amount;
        }
        if (
          values.expected_close_date &&
          values.expected_close_date !== opportunity.expected_close_date
        ) {
          payload.expected_close_date = values.expected_close_date;
        }
        if (values.is_tender !== opportunity.is_tender) payload.is_tender = values.is_tender;
        if (values.is_tender) {
          payload.tender_reference = values.tender_reference || null;
          payload.tender_deadline = values.tender_deadline || null;
          payload.estimated_award_date = values.estimated_award_date || null;
        }
        saved = await update.mutateAsync({
          id: opportunity.id,
          accountId: opportunity.account_id,
          version: opportunity.version,
          payload,
        });
        toast({ description: t('opportunities:updated') });
      } else {
        const payload: OpportunityCreate = {
          account_id: values.account_id,
          division_id: values.division_id,
          estimated_amount: parsePrice(values.estimated_amount) ?? '0.00',
        };
        if (values.name) payload.name = values.name;
        if (values.description) payload.description = values.description;
        if (values.expected_close_date) payload.expected_close_date = values.expected_close_date;
        if (values.owner_id && isManager) payload.owner_id = values.owner_id;
        if (values.is_tender) {
          payload.is_tender = true;
          if (values.tender_reference) payload.tender_reference = values.tender_reference;
          if (values.tender_deadline) payload.tender_deadline = values.tender_deadline;
          if (values.estimated_award_date) {
            payload.estimated_award_date = values.estimated_award_date;
          }
        }
        saved = await create.mutateAsync(payload);
        toast({ description: t('opportunities:created') });
      }
      onSaved(saved);
    } catch (error) {
      const problem = toProblem(error);
      if (problem.code === 'conflict' && opportunity) {
        useConflictStore
          .getState()
          .show(() =>
            queryClient.invalidateQueries({ queryKey: opportunityKeys.detail(opportunity.id) }),
          );
        return;
      }
      if (problem.code === 'opportunity_has_lines') {
        form.setError('estimated_amount', {
          message: 'opportunities:form.amountLockedByLines',
        });
        return;
      }
      setFormError(
        isKnownErrorCode(problem.code) ? `errors:${problem.code}` : 'toasts.genericError',
      );
    }
  });

  return (
    <FormProvider {...form}>
      <Form {...form}>
        <form onSubmit={handleSubmit} className="flex flex-col gap-4" noValidate>
          {needsAccountPicker ? (
            <FormField
              control={form.control}
              name="account_id"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>{t('opportunities:form.account')}</FormLabel>
                  <Input
                    type="search"
                    className="min-h-touch"
                    placeholder={t('opportunities:form.searchAccount')}
                    value={accountSearch}
                    onChange={(event) => {
                      setAccountSearch(event.target.value);
                    }}
                  />
                  <FormControl>
                    <NativeSelect {...field}>
                      <option value="">{t('opportunities:form.selectAccount')}</option>
                      {accounts.data?.items.map((account) => (
                        <option key={account.id} value={account.id}>
                          {account.name}
                        </option>
                      ))}
                    </NativeSelect>
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
          ) : null}
          {opportunity ? null : (
            <FormField
              control={form.control}
              name="division_id"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>{t('opportunities:form.division')}</FormLabel>
                  <FormControl>
                    <NativeSelect {...field}>
                      <option value="">{t('opportunities:form.selectDivision')}</option>
                      {orderedDivisions.map((division) => (
                        <option key={division.id} value={division.id}>
                          {division.name_es}
                        </option>
                      ))}
                    </NativeSelect>
                  </FormControl>
                  {defaultPipeline ? (
                    <p className="text-sm text-muted-foreground" role="note">
                      {t('opportunities:form.pipelineHint', {
                        pipeline: defaultPipeline.name_es,
                      })}
                    </p>
                  ) : null}
                  <FormMessage />
                </FormItem>
              )}
            />
          )}
          <FormField
            control={form.control}
            name="estimated_amount"
            render={({ field }) => (
              <FormItem>
                <FormLabel>{t('opportunities:form.estimatedAmount')}</FormLabel>
                <FormControl>
                  <Input
                    className="min-h-touch"
                    inputMode="decimal"
                    placeholder={t('opportunities:form.amountHint')}
                    disabled={Boolean(opportunity && opportunity.lines.length > 0)}
                    {...field}
                  />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />

          <button
            type="button"
            className="flex min-h-touch items-center justify-between rounded-md border px-3 text-sm font-medium"
            aria-expanded={moreOpen}
            aria-controls="opportunity-more-data"
            onClick={() => {
              setMoreOpen((open) => !open);
            }}
          >
            <span>{t('opportunities:form.moreData')}</span>
            <ChevronDown
              className={cn('size-4 transition-transform', moreOpen && 'rotate-180')}
              aria-hidden="true"
            />
          </button>
          <div id="opportunity-more-data" className="flex flex-col gap-4" hidden={!moreOpen}>
            <FormField
              control={form.control}
              name="name"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>{t('opportunities:form.name')}</FormLabel>
                  <FormControl>
                    <Input
                      className="min-h-touch"
                      placeholder={t('opportunities:form.namePlaceholder')}
                      {...field}
                    />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="expected_close_date"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>{t('opportunities:form.closeDate')}</FormLabel>
                  <FormControl>
                    <Input className="min-h-touch" type="date" {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <TenderFields />
            <FormField
              control={form.control}
              name="description"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>{t('opportunities:form.description')}</FormLabel>
                  <FormControl>
                    <Input className="min-h-touch" {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            {isManager && !opportunity ? (
              <FormField
                control={form.control}
                name="owner_id"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>{t('opportunities:form.owner')}</FormLabel>
                    <FormControl>
                      <NativeSelect {...field}>
                        <option value="">{t('activities:form.none')}</option>
                        {reps.data?.items.map((rep) => (
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
    </FormProvider>
  );
}
