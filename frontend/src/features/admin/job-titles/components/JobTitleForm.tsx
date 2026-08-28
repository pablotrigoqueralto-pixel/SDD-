import { zodResolver } from '@hookform/resolvers/zod';
import { useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import { useForm } from 'react-hook-form';
import { useTranslation } from 'react-i18next';
import { z } from 'zod';

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

import type { JobTitleRead } from '../api';
import { jobTitleKeys, useCreateJobTitle, useUpdateJobTitle } from '../queries';

const schema = z.object({
  name: z.string().trim().min(1, 'auth:login.emailRequired').max(100),
  is_active: z.boolean(),
});

type JobTitleInput = z.infer<typeof schema>;

interface JobTitleFormProps {
  jobTitle?: JobTitleRead;
  onSaved: () => void;
}

export function JobTitleForm({ jobTitle, onSaved }: JobTitleFormProps) {
  const { t } = useTranslation();
  const create = useCreateJobTitle();
  const update = useUpdateJobTitle();
  const queryClient = useQueryClient();
  const [formError, setFormError] = useState<string | null>(null);
  const form = useForm<JobTitleInput>({
    resolver: zodResolver(schema),
    defaultValues: { name: jobTitle?.name_es ?? '', is_active: jobTitle?.is_active ?? true },
  });
  const pending = create.isPending || update.isPending;

  const handleSubmit = form.handleSubmit(async (values) => {
    setFormError(null);
    try {
      if (jobTitle) {
        await update.mutateAsync({
          id: jobTitle.id,
          version: jobTitle.version,
          payload: { name: values.name, is_active: values.is_active },
        });
        toast({ description: t('admin:jobTitles.updated') });
      } else {
        await create.mutateAsync({ name: values.name });
        toast({ description: t('admin:jobTitles.created') });
      }
      onSaved();
    } catch (error) {
      const problem = toProblem(error);
      if (problem.code === 'conflict' && jobTitle) {
        useConflictStore
          .getState()
          .show(() => queryClient.invalidateQueries({ queryKey: jobTitleKeys.all }));
        return;
      }
      if (problem.code === 'job_title_name_already_exists') {
        form.setError('name', { message: 'admin:jobTitles.form.nameExists' });
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
              <FormLabel>{t('admin:jobTitles.form.name')}</FormLabel>
              <FormControl>
                <Input className="min-h-touch" {...field} />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />
        {jobTitle ? (
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
                  <span>{t('admin:jobTitles.form.active')}</span>
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
