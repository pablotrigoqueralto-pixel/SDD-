import { zodResolver } from '@hookform/resolvers/zod';
import { useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import { useForm, type FieldPath } from 'react-hook-form';
import { useTranslation } from 'react-i18next';

import { userKeys } from '@/api/query-keys';
import { CheckboxList } from '@/components/shared/CheckboxList';
import { NativeSelect } from '@/components/shared/NativeSelect';
import { Button } from '@/components/ui/button';
import {
  Form,
  FormControl,
  FormDescription,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from '@/components/ui/form';
import { Input } from '@/components/ui/input';
import { toast } from '@/hooks/use-toast';
import { isKnownErrorCode } from '@/lib/error-codes';
import { fieldErrorsOf, toProblem } from '@/lib/problem';
import { useConflictStore } from '@/store/conflict.store';

import { useDivisions, useTerritories } from '../../territories/queries';
import { ROLES, type UserRead } from '../../types';
import { useCreateUser, useUpdateUser } from '../queries';
import {
  userCreateSchema,
  userUpdateSchema,
  type UserCreateInput,
  type UserUpdateInput,
} from '../schemas';

interface UserFormProps {
  user?: UserRead;
  onSaved: () => void;
}

type FormValues = UserCreateInput & Partial<Pick<UserUpdateInput, 'is_active'>>;

export function UserForm({ user, onSaved }: UserFormProps) {
  const { t } = useTranslation();
  const isEdit = Boolean(user);
  const territories = useTerritories({ is_active: 'true' });
  const divisions = useDivisions();
  const createUser = useCreateUser();
  const updateUser = useUpdateUser();
  const queryClient = useQueryClient();
  const [showReset, setShowReset] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  const form = useForm<FormValues>({
    resolver: zodResolver(isEdit ? userUpdateSchema : userCreateSchema),
    defaultValues: {
      full_name: user?.full_name ?? '',
      email: user?.email ?? '',
      role: user?.role ?? 'sales_rep',
      password: '',
      territory_ids: user?.territory_ids ?? [],
      division_ids: user?.division_ids ?? [],
      is_active: user?.is_active ?? true,
    },
  });

  const role = form.watch('role');
  const territoryIds = form.watch('territory_ids');
  const divisionIds = form.watch('division_ids');
  const scopeWarning =
    role === 'sales_rep' && (territoryIds.length === 0 || divisionIds.length === 0);
  const pending = createUser.isPending || updateUser.isPending;

  const handleSubmit = form.handleSubmit(async (values) => {
    setFormError(null);
    try {
      if (user) {
        await updateUser.mutateAsync({
          id: user.id,
          version: user.version,
          payload: {
            full_name: values.full_name,
            role: values.role as UserRead['role'],
            is_active: values.is_active ?? true,
            territory_ids: values.territory_ids,
            division_ids: values.division_ids,
            ...(values.password ? { password: values.password } : {}),
          },
        });
        toast({ description: t('admin:users.updated') });
      } else {
        await createUser.mutateAsync({
          email: values.email,
          full_name: values.full_name,
          role: values.role as UserRead['role'],
          password: values.password,
          territory_ids: values.territory_ids,
          division_ids: values.division_ids,
        });
        toast({ description: t('admin:users.created') });
      }
      onSaved();
    } catch (error) {
      const problem = toProblem(error);
      if (problem.code === 'conflict' && user) {
        // "Recargar" refetches the user; UserFormRoute remounts the form with the new version.
        useConflictStore
          .getState()
          .show(() => queryClient.invalidateQueries({ queryKey: userKeys.detail(user.id) }));
        return;
      }
      if (problem.code === 'email_already_exists') {
        form.setError('email', { message: 'admin:users.form.emailExists' });
        return;
      }
      const fieldErrors = fieldErrorsOf(problem);
      if (Object.keys(fieldErrors).length > 0) {
        for (const [field, fieldError] of Object.entries(fieldErrors)) {
          form.setError(field as FieldPath<FormValues>, {
            message: isKnownErrorCode(fieldError.code)
              ? `errors:${fieldError.code}`
              : fieldError.message,
          });
        }
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
          name="full_name"
          render={({ field }) => (
            <FormItem>
              <FormLabel>{t('admin:users.form.fullName')}</FormLabel>
              <FormControl>
                <Input autoComplete="name" className="min-h-touch" {...field} />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />
        <FormField
          control={form.control}
          name="email"
          render={({ field }) => (
            <FormItem>
              <FormLabel>{t('admin:users.form.email')}</FormLabel>
              <FormControl>
                <Input
                  type="email"
                  inputMode="email"
                  autoCapitalize="none"
                  className="min-h-touch"
                  disabled={isEdit}
                  {...field}
                />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />
        <FormField
          control={form.control}
          name="role"
          render={({ field }) => (
            <FormItem>
              <FormLabel>{t('admin:users.form.role')}</FormLabel>
              <FormControl>
                <NativeSelect {...field}>
                  {ROLES.map((option) => (
                    <option key={option} value={option}>
                      {t(`roles.${option}`)}
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
          name="territory_ids"
          render={({ field }) => (
            <FormItem>
              <FormLabel>{t('admin:users.form.territories')}</FormLabel>
              <CheckboxList
                name="territory_ids"
                value={field.value}
                onChange={field.onChange}
                emptyLabel={t('admin:users.form.noTerritories')}
                options={(territories.data?.items ?? []).map((territory) => ({
                  value: territory.id,
                  label: territory.name,
                }))}
              />
              <FormMessage />
            </FormItem>
          )}
        />
        <FormField
          control={form.control}
          name="division_ids"
          render={({ field }) => (
            <FormItem>
              <FormLabel>{t('admin:users.form.divisions')}</FormLabel>
              <CheckboxList
                name="division_ids"
                value={field.value}
                onChange={field.onChange}
                emptyLabel={t('admin:users.form.noDivisions')}
                options={(divisions.data ?? []).map((division) => ({
                  value: division.id,
                  label: division.name_es,
                }))}
              />
              <FormMessage />
            </FormItem>
          )}
        />
        {scopeWarning ? (
          <p role="note" className="rounded-md bg-accent px-3 py-2 text-sm text-accent-foreground">
            {t('admin:users.form.scopeWarning')}
          </p>
        ) : null}
        {isEdit && !showReset ? (
          <Button
            type="button"
            variant="outline"
            className="min-h-touch"
            onClick={() => {
              setShowReset(true);
            }}
          >
            {t('admin:users.form.resetPassword')}
          </Button>
        ) : (
          <FormField
            control={form.control}
            name="password"
            render={({ field }) => (
              <FormItem>
                <FormLabel>
                  {isEdit ? t('admin:users.form.newPassword') : t('admin:users.form.password')}
                </FormLabel>
                <FormControl>
                  <Input
                    type="password"
                    autoComplete="new-password"
                    className="min-h-touch"
                    {...field}
                  />
                </FormControl>
                <FormDescription>{t('admin:users.form.passwordHint')}</FormDescription>
                <FormMessage />
              </FormItem>
            )}
          />
        )}
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
                    checked={field.value ?? true}
                    onChange={(event) => {
                      field.onChange(event.target.checked);
                    }}
                  />
                  <span>{t('admin:users.form.active')}</span>
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

export const USER_FORM_CONFLICT_KEYS = [userKeys.lists()];
