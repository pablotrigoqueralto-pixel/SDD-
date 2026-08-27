import { zodResolver } from '@hookform/resolvers/zod';
import { useState } from 'react';
import { useForm } from 'react-hook-form';
import { useTranslation } from 'react-i18next';

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
import { toProblem } from '@/lib/problem';

import { useLogin } from '../queries';
import { loginSchema, type LoginInput } from '../schemas';

interface LoginFormProps {
  onSuccess: () => void;
}

const MESSAGE_BY_CODE: Record<string, string> = {
  invalid_credentials: 'auth:login.invalidCredentials',
  account_locked: 'auth:login.accountLocked',
  rate_limited: 'auth:login.rateLimited',
};

export function LoginForm({ onSuccess }: LoginFormProps) {
  const { t } = useTranslation();
  const login = useLogin();
  const [formError, setFormError] = useState<string | null>(null);
  const form = useForm<LoginInput>({
    resolver: zodResolver(loginSchema),
    defaultValues: { email: '', password: '' },
  });

  const handleSubmit = form.handleSubmit(async (values) => {
    setFormError(null);
    try {
      await login.mutateAsync(values);
      onSuccess();
    } catch (error) {
      const problem = toProblem(error);
      setFormError(MESSAGE_BY_CODE[problem.code] ?? `errors:${problem.code}`);
      form.resetField('password');
    }
  });

  return (
    <Form {...form}>
      <form onSubmit={handleSubmit} className="flex flex-col gap-5" noValidate>
        <FormField
          control={form.control}
          name="email"
          render={({ field }) => (
            <FormItem>
              <FormLabel>{t('auth:login.email')}</FormLabel>
              <FormControl>
                <Input
                  type="email"
                  autoComplete="email"
                  inputMode="email"
                  autoCapitalize="none"
                  className="min-h-touch"
                  {...field}
                />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />
        <FormField
          control={form.control}
          name="password"
          render={({ field }) => (
            <FormItem>
              <FormLabel>{t('auth:login.password')}</FormLabel>
              <FormControl>
                <Input
                  type="password"
                  autoComplete="current-password"
                  className="min-h-touch"
                  {...field}
                />
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
        <Button type="submit" size="lg" className="min-h-touch w-full" disabled={login.isPending}>
          {login.isPending ? t('auth:login.submitting') : t('auth:login.submit')}
        </Button>
      </form>
    </Form>
  );
}
