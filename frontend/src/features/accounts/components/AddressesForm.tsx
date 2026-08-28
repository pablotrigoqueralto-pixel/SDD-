import { zodResolver } from '@hookform/resolvers/zod';
import { useQueryClient } from '@tanstack/react-query';
import { Plus, Trash2 } from 'lucide-react';
import { useState } from 'react';
import { useFieldArray, useForm } from 'react-hook-form';
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
import { Input } from '@/components/ui/input';
import { toast } from '@/hooks/use-toast';
import { isKnownErrorCode } from '@/lib/error-codes';
import { toProblem } from '@/lib/problem';
import { PROVINCES } from '@/lib/provinces';
import { useConflictStore } from '@/store/conflict.store';

import type { AccountRead } from '../api';
import { useReplaceAddresses } from '../queries';
import { addressesSchema, type AddressesInput } from '../schemas';

interface AddressesFormProps {
  account: AccountRead;
  onSaved: () => void;
}

const EMPTY_ADDRESS: AddressesInput['addresses'][number] = {
  label: '',
  street: '',
  postal_code: '',
  city: '',
  province_code: '',
  notes: '',
};

export function AddressesForm({ account, onSaved }: AddressesFormProps) {
  const { t } = useTranslation();
  const replace = useReplaceAddresses();
  const queryClient = useQueryClient();
  const [formError, setFormError] = useState<string | null>(null);
  const form = useForm<AddressesInput>({
    resolver: zodResolver(addressesSchema),
    defaultValues: {
      addresses: account.addresses.map((address) => ({ ...address, notes: address.notes ?? '' })),
    },
  });
  const { fields, append, remove } = useFieldArray({ control: form.control, name: 'addresses' });

  const handleSubmit = form.handleSubmit(async (values) => {
    setFormError(null);
    try {
      await replace.mutateAsync({
        id: account.id,
        version: account.version,
        addresses: values.addresses.map((address) => ({
          ...address,
          notes: address.notes || null,
        })),
      });
      toast({ description: t('accounts:addressesUpdated') });
      onSaved();
    } catch (error) {
      const problem = toProblem(error);
      if (problem.code === 'conflict') {
        useConflictStore
          .getState()
          .show(() => queryClient.invalidateQueries({ queryKey: accountKeys.detail(account.id) }));
        return;
      }
      setFormError(
        isKnownErrorCode(problem.code) ? `errors:${problem.code}` : 'toasts.genericError',
      );
    }
  });

  const rootError = form.formState.errors.addresses?.root?.message;

  return (
    <Form {...form}>
      <form onSubmit={handleSubmit} className="flex flex-col gap-4" noValidate>
        {fields.map((item, index) => (
          <fieldset key={item.id} className="flex flex-col gap-3 rounded-md border p-3">
            <div className="flex items-center justify-between">
              <legend className="font-medium">{form.watch(`addresses.${index}.label`)}</legend>
              <Button
                type="button"
                variant="ghost"
                size="icon"
                className="min-h-touch min-w-touch"
                aria-label={t('accounts:addresses.remove', {
                  label: form.watch(`addresses.${index}.label`) || index + 1,
                })}
                onClick={() => {
                  remove(index);
                }}
              >
                <Trash2 className="size-4" aria-hidden="true" />
              </Button>
            </div>
            <FormField
              control={form.control}
              name={`addresses.${index}.label`}
              render={({ field }) => (
                <FormItem>
                  <FormLabel>{t('accounts:addresses.label')}</FormLabel>
                  <FormControl>
                    <Input className="min-h-touch" {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name={`addresses.${index}.street`}
              render={({ field }) => (
                <FormItem>
                  <FormLabel>{t('accounts:addresses.street')}</FormLabel>
                  <FormControl>
                    <Input className="min-h-touch" {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <div className="grid gap-3 sm:grid-cols-3">
              <FormField
                control={form.control}
                name={`addresses.${index}.postal_code`}
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>{t('accounts:addresses.postalCode')}</FormLabel>
                    <FormControl>
                      <Input className="min-h-touch" inputMode="numeric" {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField
                control={form.control}
                name={`addresses.${index}.city`}
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>{t('accounts:addresses.city')}</FormLabel>
                    <FormControl>
                      <Input className="min-h-touch" {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField
                control={form.control}
                name={`addresses.${index}.province_code`}
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>{t('accounts:addresses.province')}</FormLabel>
                    <FormControl>
                      <NativeSelect {...field}>
                        <option value="">{t('accounts:form.selectProvince')}</option>
                        {PROVINCES.map((province) => (
                          <option key={province.code} value={province.code}>
                            {province.name}
                          </option>
                        ))}
                      </NativeSelect>
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
            </div>
            <FormField
              control={form.control}
              name={`addresses.${index}.notes`}
              render={({ field }) => (
                <FormItem>
                  <FormLabel>{t('accounts:addresses.notes')}</FormLabel>
                  <FormControl>
                    <Input className="min-h-touch" {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
          </fieldset>
        ))}
        {rootError ? (
          <p role="alert" className="text-sm font-medium text-destructive">
            {t(rootError)}
          </p>
        ) : null}
        <Button
          type="button"
          variant="outline"
          className="min-h-touch"
          disabled={fields.length >= 10}
          onClick={() => {
            append(EMPTY_ADDRESS);
          }}
        >
          <Plus className="size-4" aria-hidden="true" />
          {t('accounts:addresses.add')}
        </Button>
        {formError ? (
          <p role="alert" className="text-sm font-medium text-destructive">
            {t(formError)}
          </p>
        ) : null}
        <Button type="submit" size="lg" className="min-h-touch" disabled={replace.isPending}>
          {replace.isPending ? t('states.saving') : t('actions.save')}
        </Button>
      </form>
    </Form>
  );
}
