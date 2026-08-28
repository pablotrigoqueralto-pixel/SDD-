import { zodResolver } from '@hookform/resolvers/zod';
import { useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import { useForm } from 'react-hook-form';
import { useTranslation } from 'react-i18next';
import { z } from 'zod';

import { referenceKeys } from '@/api/query-keys';
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
import { useDivisions } from '@/features/reference';
import { toast } from '@/hooks/use-toast';
import { isKnownErrorCode } from '@/lib/error-codes';
import { toProblem } from '@/lib/problem';
import { useConflictStore } from '@/store/conflict.store';

import type { BrandRead } from '../api';
import { brandKeys, useCreateBrand, useUpdateBrand } from '../queries';

const brandSchema = z.object({
  name: z.string().trim().min(1, 'auth:login.emailRequired').max(100),
  kind: z.enum(['own', 'competitor']),
  division_ids: z.array(z.string()),
  is_active: z.boolean(),
});

type BrandInput = z.infer<typeof brandSchema>;

interface BrandFormProps {
  brand?: BrandRead;
  onSaved: () => void;
}

export function BrandForm({ brand, onSaved }: BrandFormProps) {
  const { t } = useTranslation();
  const divisions = useDivisions();
  const createBrand = useCreateBrand();
  const updateBrand = useUpdateBrand();
  const queryClient = useQueryClient();
  const [formError, setFormError] = useState<string | null>(null);
  const isEdit = Boolean(brand);

  const form = useForm<BrandInput>({
    resolver: zodResolver(brandSchema),
    defaultValues: {
      name: brand?.name ?? '',
      kind: brand ? (brand.is_own ? 'own' : 'competitor') : 'own',
      division_ids: brand?.division_ids ?? [],
      is_active: brand?.is_active ?? true,
    },
  });
  const pending = createBrand.isPending || updateBrand.isPending;

  const handleSubmit = form.handleSubmit(async (values) => {
    setFormError(null);
    try {
      if (brand) {
        await updateBrand.mutateAsync({
          id: brand.id,
          version: brand.version,
          payload: {
            name: values.name,
            is_own: values.kind === 'own',
            is_active: values.is_active,
            division_ids: values.division_ids,
          },
        });
        toast({ description: t('admin:brands.updated') });
      } else {
        await createBrand.mutateAsync({
          name: values.name,
          is_own: values.kind === 'own',
          division_ids: values.division_ids,
        });
        toast({ description: t('admin:brands.created') });
      }
      onSaved();
    } catch (error) {
      const problem = toProblem(error);
      if (problem.code === 'conflict' && brand) {
        useConflictStore.getState().show(async () => {
          await Promise.all([
            queryClient.invalidateQueries({ queryKey: brandKeys.all }),
            queryClient.invalidateQueries({ queryKey: referenceKeys.all }),
          ]);
        });
        return;
      }
      if (problem.code === 'brand_name_already_exists') {
        form.setError('name', { message: 'admin:brands.form.nameExists' });
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
              <FormLabel>{t('admin:brands.form.name')}</FormLabel>
              <FormControl>
                <Input className="min-h-touch" {...field} />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />
        <FormField
          control={form.control}
          name="kind"
          render={({ field }) => (
            <FormItem>
              <FormLabel>{t('admin:brands.form.kind')}</FormLabel>
              <FormControl>
                <NativeSelect {...field}>
                  <option value="own">{t('reference:brandKind.own')}</option>
                  <option value="competitor">{t('reference:brandKind.competitor')}</option>
                </NativeSelect>
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />
        <FormField
          control={form.control}
          name="division_ids"
          render={({ field }) => (
            <FormItem>
              <FormLabel>{t('admin:brands.form.divisions')}</FormLabel>
              <CheckboxList
                name="division_ids"
                value={field.value}
                onChange={field.onChange}
                emptyLabel={t('admin:brands.form.noDivisions')}
                options={(divisions.data ?? []).map((division) => ({
                  value: division.id,
                  label: division.name_es,
                }))}
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
                  <span>{t('admin:brands.form.active')}</span>
                </label>
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
