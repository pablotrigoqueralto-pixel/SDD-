import { zodResolver } from '@hookform/resolvers/zod';
import { useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import { useForm } from 'react-hook-form';
import { useTranslation } from 'react-i18next';

import { accountKeys } from '@/api/query-keys';
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
import { useTerritories, useUsers } from '@/features/admin';
import { toast } from '@/hooks/use-toast';
import { isKnownErrorCode } from '@/lib/error-codes';
import { toProblem } from '@/lib/problem';
import { useConflictStore } from '@/store/conflict.store';

import type { AccountRead } from '../api';
import { useAssignAccount } from '../queries';
import { assignmentSchema, type AssignmentInput } from '../schemas';

interface AssignmentFormProps {
  account: AccountRead;
  onSaved: () => void;
}

export function AssignmentForm({ account, onSaved }: AssignmentFormProps) {
  const { t } = useTranslation();
  const reps = useUsers({ role: 'sales_rep', is_active: 'true', page_size: 200 });
  const territories = useTerritories({ is_active: 'true' });
  const assign = useAssignAccount();
  const queryClient = useQueryClient();
  const [formError, setFormError] = useState<string | null>(null);
  const form = useForm<AssignmentInput>({
    resolver: zodResolver(assignmentSchema),
    defaultValues: { owner_id: account.owner_id ?? '', territory_id: account.territory_id ?? '' },
  });

  const handleSubmit = form.handleSubmit(async (values) => {
    setFormError(null);
    try {
      await assign.mutateAsync({
        id: account.id,
        version: account.version,
        payload: { owner_id: values.owner_id || null, territory_id: values.territory_id || null },
      });
      toast({ description: t('accounts:assigned') });
      onSaved();
    } catch (error) {
      const problem = toProblem(error);
      if (problem.code === 'conflict') {
        useConflictStore
          .getState()
          .show(() => queryClient.invalidateQueries({ queryKey: accountKeys.detail(account.id) }));
        return;
      }
      if (problem.code === 'owner_not_sales_rep') {
        form.setError('owner_id', { message: 'errors:owner_not_sales_rep' });
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
          name="owner_id"
          render={({ field }) => (
            <FormItem>
              <FormLabel>{t('accounts:assignment.owner')}</FormLabel>
              <FormControl>
                <NativeSelect {...field}>
                  <option value="">{t('accounts:assignment.keepOwner')}</option>
                  {reps.data?.items.map((rep) => (
                    <option key={rep.id} value={rep.id}>
                      {rep.full_name}
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
          name="territory_id"
          render={({ field }) => (
            <FormItem>
              <FormLabel>{t('accounts:assignment.territory')}</FormLabel>
              <FormControl>
                <NativeSelect {...field}>
                  <option value="">{t('accounts:assignment.keepTerritory')}</option>
                  {territories.data?.items.map((territory) => (
                    <option key={territory.id} value={territory.id}>
                      {territory.name}
                    </option>
                  ))}
                </NativeSelect>
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
        <Button type="submit" size="lg" className="min-h-touch" disabled={assign.isPending}>
          {assign.isPending ? t('states.saving') : t('actions.save')}
        </Button>
      </form>
    </Form>
  );
}
