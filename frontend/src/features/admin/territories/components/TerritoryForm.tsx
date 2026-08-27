import { zodResolver } from '@hookform/resolvers/zod';
import { useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import { useForm } from 'react-hook-form';
import { useTranslation } from 'react-i18next';
import { z } from 'zod';

import { territoryKeys } from '@/api/query-keys';
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

import type { TerritoryRead } from '../../types';
import { useCreateTerritory, useTerritories, useUpdateTerritory } from '../queries';
import { ProvincePicker } from './ProvincePicker';

const territorySchema = z.object({
  name: z.string().trim().min(1, 'auth:login.emailRequired').max(100),
  provinces: z.array(z.string()).min(1, 'admin:territories.form.selectAtLeastOne'),
  is_active: z.boolean(),
});

type TerritoryInput = z.infer<typeof territorySchema>;

interface TerritoryFormProps {
  territory?: TerritoryRead;
  onSaved: () => void;
}

export function TerritoryForm({ territory, onSaved }: TerritoryFormProps) {
  const { t } = useTranslation();
  const territories = useTerritories();
  const createTerritory = useCreateTerritory();
  const updateTerritory = useUpdateTerritory();
  const queryClient = useQueryClient();
  const [conflict, setConflict] = useState<{ code: string; owner: string } | null>(null);
  const [formError, setFormError] = useState<string | null>(null);
  const isEdit = Boolean(territory);

  const form = useForm<TerritoryInput>({
    resolver: zodResolver(territorySchema),
    defaultValues: {
      name: territory?.name ?? '',
      provinces: territory?.provinces ?? [],
      is_active: territory?.is_active ?? true,
    },
  });
  const pending = createTerritory.isPending || updateTerritory.isPending;

  const handleSubmit = form.handleSubmit(async (values) => {
    setFormError(null);
    setConflict(null);
    try {
      if (territory) {
        await updateTerritory.mutateAsync({
          id: territory.id,
          version: territory.version,
          payload: { name: values.name, provinces: values.provinces, is_active: values.is_active },
        });
        toast({ description: t('admin:territories.updated') });
      } else {
        await createTerritory.mutateAsync({ name: values.name, provinces: values.provinces });
        toast({ description: t('admin:territories.created') });
      }
      onSaved();
    } catch (error) {
      const problem = toProblem(error);
      if (problem.code === 'conflict' && territory) {
        useConflictStore
          .getState()
          .show(() =>
            queryClient.invalidateQueries({ queryKey: territoryKeys.detail(territory.id) }),
          );
        return;
      }
      if (problem.code === 'province_already_assigned') {
        const match = /Province (\d{2}) is already assigned to territory '(.+)'/.exec(
          problem.detail,
        );
        setConflict(match ? { code: match[1] ?? '', owner: match[2] ?? '' } : null);
        form.setError('provinces', { message: 'errors:province_already_assigned' });
        return;
      }
      if (problem.code === 'territory_in_use') {
        form.setError('is_active', { message: 'admin:territories.form.inUse' });
        return;
      }
      if (problem.code === 'territory_name_already_exists') {
        form.setError('name', { message: 'errors:territory_name_already_exists' });
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
              <FormLabel>{t('admin:territories.form.name')}</FormLabel>
              <FormControl>
                <Input className="min-h-touch" {...field} />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />
        <FormField
          control={form.control}
          name="provinces"
          render={({ field }) => (
            <FormItem>
              <FormLabel>{t('admin:territories.form.provinces')}</FormLabel>
              <ProvincePicker
                value={field.value}
                onChange={field.onChange}
                territories={territories.data?.items ?? []}
                currentTerritoryId={territory?.id}
                conflict={conflict}
              />
              <FormMessage />
            </FormItem>
          )}
        />
        {isEdit ? (
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
                  <span>{t('admin:territories.form.active')}</span>
                </label>
                <FormMessage />
              </FormItem>
            )}
          />
        ) : null}
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
