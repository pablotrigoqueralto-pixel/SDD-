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
import { formatPrice } from '@/features/catalogue';
import { isKnownErrorCode } from '@/lib/error-codes';
import { toProblem } from '@/lib/problem';

import type { QuoteDetail } from '../api';
import { useAcceptQuote, useRejectQuote } from '../queries';
import { rejectQuoteSchema, type RejectQuoteFormValues } from '../schemas';

interface CloseDialogProps {
  quote: QuoteDetail;
  onDone: () => void;
}

/** Accepting states the consequence before the user confirms: the opportunity is won. */
export function AcceptQuoteDialog({ quote, onDone }: CloseDialogProps) {
  const { t } = useTranslation();
  const acceptQuote = useAcceptQuote();
  const [occurredOn, setOccurredOn] = useState('');
  const [formError, setFormError] = useState<string | null>(null);

  const handleConfirm = async () => {
    setFormError(null);
    try {
      await acceptQuote.mutateAsync({
        id: quote.id,
        version: quote.version,
        accountId: quote.account_id,
        opportunityId: quote.opportunity_id,
        ...(occurredOn ? { occurredOn } : {}),
      });
      onDone();
    } catch (error) {
      const problem = toProblem(error);
      setFormError(
        isKnownErrorCode(problem.code) ? `errors:${problem.code}` : 'toasts.genericError',
      );
    }
  };

  return (
    <div className="flex flex-col gap-4">
      <p className="text-sm">
        {t('quotes:accept.consequence', { total: formatPrice(quote.total) })}
      </p>
      <label className="flex flex-col gap-1 text-sm font-medium">
        {t('quotes:accept.date')}
        <Input
          type="date"
          className="min-h-touch"
          value={occurredOn}
          onChange={(event) => {
            setOccurredOn(event.target.value);
          }}
        />
      </label>
      {formError ? (
        <p role="alert" className="text-sm font-medium text-destructive">
          {t(formError)}
        </p>
      ) : null}
      <Button
        type="button"
        className="min-h-touch"
        disabled={acceptQuote.isPending}
        onClick={() => void handleConfirm()}
      >
        {t('quotes:accept.confirm')}
      </Button>
    </div>
  );
}

export function RejectQuoteDialog({ quote, onDone }: CloseDialogProps) {
  const { t } = useTranslation();
  const rejectQuote = useRejectQuote();
  const [formError, setFormError] = useState<string | null>(null);
  const form = useForm<RejectQuoteFormValues>({
    resolver: zodResolver(rejectQuoteSchema),
    defaultValues: { note: '' },
  });

  const handleSubmit = form.handleSubmit(async (values) => {
    setFormError(null);
    try {
      await rejectQuote.mutateAsync({
        id: quote.id,
        version: quote.version,
        accountId: quote.account_id,
        opportunityId: quote.opportunity_id,
        ...(values.note ? { note: values.note } : {}),
      });
      onDone();
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
          name="note"
          render={({ field }) => (
            <FormItem>
              <FormLabel>{t('quotes:reject.note')}</FormLabel>
              <FormControl>
                <textarea
                  className="min-h-24 w-full rounded-md border border-input bg-background px-3 py-2 text-base"
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
        <Button
          type="submit"
          variant="destructive"
          className="min-h-touch"
          disabled={rejectQuote.isPending}
        >
          {t('quotes:reject.confirm')}
        </Button>
      </form>
    </Form>
  );
}
