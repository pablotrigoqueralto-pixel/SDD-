import { zodResolver } from '@hookform/resolvers/zod';
import { useState } from 'react';
import { useForm } from 'react-hook-form';
import { useTranslation } from 'react-i18next';

import { ErrorState } from '@/components/shared/ErrorState';
import { PageHeader } from '@/components/shared/PageHeader';
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
import { Skeleton } from '@/components/ui/skeleton';
import { toast } from '@/hooks/use-toast';
import { isKnownErrorCode } from '@/lib/error-codes';
import { toProblem } from '@/lib/problem';

import { ConditionsFields } from '../components/ConditionsFields';
import { useQuoteSettings, useUpdateQuoteSettings } from '../queries';
import { quoteSettingsSchema, type QuoteSettingsFormValues } from '../schemas';

/** Admin: default conditions for new quotes and the send-email template. */
export function QuoteSettingsPage() {
  const { t } = useTranslation();
  const settings = useQuoteSettings();
  const updateSettings = useUpdateQuoteSettings();
  const [formError, setFormError] = useState<string | null>(null);

  const defaults = settings.data?.conditions_defaults as
    | { validez_dias?: number; plazo_entrega?: string; forma_pago?: string; garantia?: string }
    | undefined;
  const template = settings.data?.email_template as { subject?: string; body?: string } | undefined;

  const form = useForm<QuoteSettingsFormValues>({
    resolver: zodResolver(quoteSettingsSchema),
    values: {
      conditions: {
        validez_dias: String(defaults?.validez_dias ?? 30),
        plazo_entrega: defaults?.plazo_entrega ?? '',
        forma_pago: defaults?.forma_pago ?? '',
        garantia: defaults?.garantia ?? '',
      },
      subject: template?.subject ?? '',
      body: template?.body ?? '',
    },
    resetOptions: { keepDirtyValues: true },
  });

  if (settings.isPending) return <Skeleton className="mt-4 h-64 w-full" />;
  if (settings.isError) {
    return <ErrorState error={settings.error} onRetry={() => void settings.refetch()} />;
  }

  const handleSubmit = form.handleSubmit(async (values) => {
    setFormError(null);
    try {
      await updateSettings.mutateAsync({
        conditions_defaults: {
          validez_dias: Number(values.conditions.validez_dias),
          plazo_entrega: values.conditions.plazo_entrega || null,
          forma_pago: values.conditions.forma_pago || null,
          garantia: values.conditions.garantia || null,
        },
        email_template: { subject: values.subject, body: values.body },
      });
      toast({ description: t('quotes:settings.saved') });
    } catch (error) {
      const problem = toProblem(error);
      setFormError(
        isKnownErrorCode(problem.code) ? `errors:${problem.code}` : 'toasts.genericError',
      );
    }
  });

  return (
    <>
      <PageHeader title={t('quotes:settings.title')} />
      <section className="flex flex-col gap-4 py-4">
        <Form {...form}>
          <form onSubmit={handleSubmit} className="flex max-w-2xl flex-col gap-6" noValidate>
            <div className="flex flex-col gap-3">
              <h2 className="font-medium">{t('quotes:settings.conditionsTitle')}</h2>
              <ConditionsFields control={form.control} prefix="conditions" />
            </div>
            <div className="flex flex-col gap-3">
              <h2 className="font-medium">{t('quotes:settings.templateTitle')}</h2>
              <p className="text-sm text-muted-foreground">{t('quotes:settings.placeholders')}</p>
              <FormField
                control={form.control}
                name="subject"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>{t('quotes:settings.subject')}</FormLabel>
                    <FormControl>
                      <Input className="min-h-touch" {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField
                control={form.control}
                name="body"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>{t('quotes:settings.body')}</FormLabel>
                    <FormControl>
                      <textarea
                        className="min-h-40 w-full rounded-md border border-input bg-background px-3 py-2 text-base"
                        {...field}
                      />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
            </div>
            {formError ? (
              <p role="alert" className="text-sm font-medium text-destructive">
                {t(formError)}
              </p>
            ) : null}
            <Button
              type="submit"
              className="min-h-touch self-start"
              disabled={updateSettings.isPending}
            >
              {t('actions.save')}
            </Button>
          </form>
        </Form>
      </section>
    </>
  );
}
