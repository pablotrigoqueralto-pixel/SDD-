import { zodResolver } from '@hookform/resolvers/zod';
import { FileText, Plus, X } from 'lucide-react';
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
import { useSessionStore } from '@/features/auth';
import { useAccountContacts } from '@/features/contacts';
import { isKnownErrorCode } from '@/lib/error-codes';
import { toProblem } from '@/lib/problem';

import type { QuoteDetail } from '../api';
import { downloadQuotePdf } from '../hooks';
import { useQuoteSettings, useSendQuote } from '../queries';
import { interpolateTemplate, sendQuoteSchema, type SendQuoteFormValues } from '../schemas';

interface SendQuoteDialogProps {
  quote: QuoteDetail;
  onSent: () => void;
}

/** Recipients from the account contacts, subject/body from the admin template. */
export function SendQuoteDialog({ quote, onSent }: SendQuoteDialogProps) {
  const { t } = useTranslation();
  const sendQuote = useSendQuote();
  const contacts = useAccountContacts(quote.account_id);
  const settings = useQuoteSettings();
  const user = useSessionStore((state) => state.user);
  const [freeEmail, setFreeEmail] = useState('');
  const [formError, setFormError] = useState<string | null>(null);

  const template = settings.data?.email_template as { subject?: string; body?: string } | undefined;
  const interpolation = {
    numero: quote.display_number,
    centro: quote.account_name,
    comercial: user?.full_name ?? '',
  };
  const contactEmails = (contacts.data ?? [])
    .filter((contact) => contact.email)
    .map((contact) => ({
      email: contact.email ?? '',
      name: `${contact.first_name} ${contact.last_name}`,
    }));

  const form = useForm<SendQuoteFormValues>({
    resolver: zodResolver(sendQuoteSchema),
    values: {
      recipients: contactEmails.map((contact) => contact.email),
      subject: interpolateTemplate(template?.subject ?? '', interpolation),
      body: interpolateTemplate(template?.body ?? '', interpolation),
      valid_until: '',
      skip_email: false,
    },
    resetOptions: { keepDirtyValues: true },
  });
  const recipients = form.watch('recipients');
  const skipEmail = form.watch('skip_email');

  const removeRecipient = (email: string) => {
    form.setValue(
      'recipients',
      recipients.filter((entry) => entry !== email),
      { shouldValidate: true },
    );
  };

  const addRecipient = () => {
    const email = freeEmail.trim();
    if (!email || recipients.includes(email)) return;
    form.setValue('recipients', [...recipients, email], { shouldValidate: true });
    setFreeEmail('');
  };

  const handleSubmit = form.handleSubmit(async (values) => {
    setFormError(null);
    try {
      await sendQuote.mutateAsync({
        id: quote.id,
        version: quote.version,
        accountId: quote.account_id,
        opportunityId: quote.opportunity_id,
        payload: {
          recipients: values.skip_email
            ? []
            : values.recipients.map((email) => ({
                email,
                name: contactEmails.find((contact) => contact.email === email)?.name ?? null,
              })),
          subject: values.subject,
          body: values.body,
          skip_email: values.skip_email,
          ...(values.valid_until ? { valid_until: values.valid_until } : {}),
        },
      });
      onSent();
    } catch (error) {
      const problem = toProblem(error);
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
          name="skip_email"
          render={({ field }) => (
            <FormItem>
              <label className="flex min-h-touch items-center gap-2 text-sm">
                <input
                  type="checkbox"
                  className="size-4"
                  checked={field.value}
                  onChange={field.onChange}
                />
                {t('quotes:send.skipEmail')}
              </label>
              <p className="text-sm text-muted-foreground">{t('quotes:send.skipHint')}</p>
            </FormItem>
          )}
        />
        {!skipEmail ? (
          <>
            <FormField
              control={form.control}
              name="recipients"
              render={() => (
                <FormItem>
                  <FormLabel>{t('quotes:send.recipients')}</FormLabel>
                  <ul className="flex flex-wrap gap-2">
                    {recipients.map((email) => (
                      <li
                        key={email}
                        className="flex items-center gap-1 rounded-full border px-3 py-1 text-sm"
                      >
                        {email}
                        <button
                          type="button"
                          aria-label={`${t('actions.delete')} ${email}`}
                          onClick={() => {
                            removeRecipient(email);
                          }}
                        >
                          <X className="size-3" aria-hidden="true" />
                        </button>
                      </li>
                    ))}
                  </ul>
                  <div className="flex gap-2">
                    <Input
                      type="email"
                      className="min-h-touch"
                      placeholder={t('quotes:send.recipientPlaceholder')}
                      aria-label={t('quotes:send.addRecipient')}
                      value={freeEmail}
                      onChange={(event) => {
                        setFreeEmail(event.target.value);
                      }}
                    />
                    <Button
                      type="button"
                      variant="outline"
                      className="min-h-touch"
                      onClick={addRecipient}
                    >
                      <Plus className="size-4" aria-hidden="true" />
                      {t('quotes:send.addRecipient')}
                    </Button>
                  </div>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="subject"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>{t('quotes:send.subject')}</FormLabel>
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
                  <FormLabel>{t('quotes:send.body')}</FormLabel>
                  <FormControl>
                    <textarea
                      className="min-h-32 w-full rounded-md border border-input bg-background px-3 py-2 text-base"
                      {...field}
                    />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
          </>
        ) : null}
        <FormField
          control={form.control}
          name="valid_until"
          render={({ field }) => (
            <FormItem>
              <FormLabel>{t('quotes:send.validUntil')}</FormLabel>
              <FormControl>
                <Input type="date" className="min-h-touch" {...field} />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />
        <Button
          type="button"
          variant="outline"
          className="min-h-touch self-start"
          onClick={() => void downloadQuotePdf(quote.id, `${quote.display_number}.pdf`)}
        >
          <FileText className="size-4" aria-hidden="true" />
          {t('quotes:actions.previewPdf')}
        </Button>
        {formError ? (
          <p role="alert" className="text-sm font-medium text-destructive">
            {t(formError)}
          </p>
        ) : null}
        <Button type="submit" className="min-h-touch" disabled={sendQuote.isPending}>
          {t('quotes:send.confirm')}
        </Button>
      </form>
    </Form>
  );
}
