import { zodResolver } from '@hookform/resolvers/zod';
import { useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import { useForm } from 'react-hook-form';
import { useTranslation } from 'react-i18next';
import { z } from 'zod';

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

import type { ProductFamilyRead, ProductFamilyUpdate } from '../api';
import { productFamilyKeys, useCreateProductFamily, useUpdateProductFamily } from '../queries';

const schema = z.object({
  name: z.string().trim().min(1, 'admin:productFamilies.form.nameRequired').max(100),
  division_id: z.string().min(1, 'admin:productFamilies.form.divisionRequired'),
  sort_order: z.string().trim().regex(/^\d*$/),
  is_active: z.boolean(),
});

type ProductFamilyInput = z.infer<typeof schema>;

interface ProductFamilyFormProps {
  family?: ProductFamilyRead;
  onSaved: () => void;
}

export function ProductFamilyForm({ family, onSaved }: ProductFamilyFormProps) {
  const { t } = useTranslation();
  const divisions = useDivisions();
  const create = useCreateProductFamily();
  const update = useUpdateProductFamily();
  const queryClient = useQueryClient();
  const [formError, setFormError] = useState<string | null>(null);
  const form = useForm<ProductFamilyInput>({
    resolver: zodResolver(schema),
    defaultValues: {
      name: family?.name_es ?? '',
      division_id: family?.division_id ?? '',
      sort_order: family ? String(family.sort_order) : '',
      is_active: family?.is_active ?? true,
    },
  });
  const pending = create.isPending || update.isPending;

  const handleSubmit = form.handleSubmit(async (values) => {
    setFormError(null);
    try {
      if (family) {
        const payload: ProductFamilyUpdate = {};
        if (values.name !== family.name_es) payload.name = values.name;
        const sortOrder = values.sort_order === '' ? family.sort_order : Number(values.sort_order);
        if (sortOrder !== family.sort_order) payload.sort_order = sortOrder;
        if (values.is_active !== family.is_active) payload.is_active = values.is_active;
        await update.mutateAsync({ id: family.id, version: family.version, payload });
        toast({ description: t('admin:productFamilies.updated') });
      } else {
        await create.mutateAsync({ name: values.name, division_id: values.division_id });
        toast({ description: t('admin:productFamilies.created') });
      }
      onSaved();
    } catch (error) {
      const problem = toProblem(error);
      if (problem.code === 'conflict' && family) {
        useConflictStore
          .getState()
          .show(() => queryClient.invalidateQueries({ queryKey: productFamilyKeys.all }));
        return;
      }
      if (problem.code === 'product_family_exists') {
        form.setError('name', { message: 'admin:productFamilies.form.nameExists' });
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
              <FormLabel>{t('admin:productFamilies.form.name')}</FormLabel>
              <FormControl>
                <Input className="min-h-touch" {...field} />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />
        <FormField
          control={form.control}
          name="division_id"
          render={({ field }) => (
            <FormItem>
              <FormLabel>{t('admin:productFamilies.form.division')}</FormLabel>
              <FormControl>
                <NativeSelect {...field} disabled={Boolean(family)}>
                  <option value="">{t('admin:productFamilies.form.selectDivision')}</option>
                  {divisions.data?.map((division) => (
                    <option key={division.id} value={division.id}>
                      {division.name_es}
                    </option>
                  ))}
                </NativeSelect>
              </FormControl>
              {family ? (
                <p className="text-sm text-muted-foreground">
                  {t('admin:productFamilies.form.divisionLocked')}
                </p>
              ) : null}
              <FormMessage />
            </FormItem>
          )}
        />
        {family ? (
          <>
            <FormField
              control={form.control}
              name="sort_order"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>{t('admin:productFamilies.form.sortOrder')}</FormLabel>
                  <FormControl>
                    <Input className="min-h-touch" inputMode="numeric" {...field} />
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
                    <span>{t('admin:productFamilies.form.active')}</span>
                  </label>
                </FormItem>
              )}
            />
          </>
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
