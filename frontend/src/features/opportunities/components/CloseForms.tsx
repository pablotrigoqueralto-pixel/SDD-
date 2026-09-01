import { zodResolver } from '@hookform/resolvers/zod';
import { useState } from 'react';
import { useForm } from 'react-hook-form';
import { useTranslation } from 'react-i18next';

import { CreateOptionDialog } from '@/components/shared/CreateOptionDialog';
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
import { parsePrice } from '@/features/catalogue';
import { useBrands, useLossReasons } from '@/features/reference';
import { toast } from '@/hooks/use-toast';
import { isKnownErrorCode } from '@/lib/error-codes';
import { toProblem } from '@/lib/problem';

import type { OpportunityRead } from '../api';
import { useLoseOpportunity, useWinOpportunity } from '../queries';
import { loseSchema, winSchema, type LoseInput, type WinInput } from '../schemas';

interface CloseFormProps {
  opportunity: OpportunityRead;
  onSaved: (opportunity: OpportunityRead) => void;
}

export function WinForm({ opportunity, onSaved }: CloseFormProps) {
  const { t } = useTranslation();
  const win = useWinOpportunity();
  const [formError, setFormError] = useState<string | null>(null);
  const form = useForm<WinInput>({
    resolver: zodResolver(winSchema),
    defaultValues: {
      won_amount: opportunity.amount.replace('.', ','),
      won_at: new Date().toISOString().slice(0, 10),
    },
  });

  const handleSubmit = form.handleSubmit(async (values) => {
    setFormError(null);
    try {
      const saved = await win.mutateAsync({
        id: opportunity.id,
        accountId: opportunity.account_id,
        version: opportunity.version,
        payload: {
          won_amount: parsePrice(values.won_amount) ?? opportunity.amount,
          ...(values.won_at ? { won_at: new Date(values.won_at).toISOString() } : {}),
        },
      });
      toast({ description: t('opportunities:wonToast') });
      onSaved(saved);
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
          name="won_amount"
          render={({ field }) => (
            <FormItem>
              <FormLabel>{t('opportunities:win.amount')}</FormLabel>
              <FormControl>
                <Input className="min-h-touch" inputMode="decimal" {...field} />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />
        <FormField
          control={form.control}
          name="won_at"
          render={({ field }) => (
            <FormItem>
              <FormLabel>{t('opportunities:win.date')}</FormLabel>
              <FormControl>
                <Input className="min-h-touch" type="date" {...field} />
              </FormControl>
            </FormItem>
          )}
        />
        {formError ? (
          <p role="alert" className="text-sm font-medium text-destructive">
            {t(formError)}
          </p>
        ) : null}
        <Button type="submit" size="lg" className="min-h-touch" disabled={win.isPending}>
          {win.isPending ? t('states.saving') : t('opportunities:actions.win')}
        </Button>
      </form>
    </Form>
  );
}

export function LoseForm({ opportunity, onSaved }: CloseFormProps) {
  const { t } = useTranslation();
  const lose = useLoseOpportunity();
  const reasons = useLossReasons();
  const brands = useBrands();
  const [formError, setFormError] = useState<string | null>(null);
  const form = useForm<LoseInput>({
    resolver: zodResolver(loseSchema),
    defaultValues: { loss_reason_id: '', competitor_brand_id: '', note: '' },
  });
  const reasonId = form.watch('loss_reason_id');
  const reason = reasons.data?.find((candidate) => candidate.id === reasonId);

  const handleSubmit = form.handleSubmit(async (values) => {
    setFormError(null);
    if (reason?.requires_brand && !values.competitor_brand_id) {
      form.setError('competitor_brand_id', { message: 'opportunities:lose.brandRequired' });
      return;
    }
    if (reason?.requires_note && !values.note.trim()) {
      form.setError('note', { message: 'opportunities:lose.noteRequired' });
      return;
    }
    try {
      const saved = await lose.mutateAsync({
        id: opportunity.id,
        accountId: opportunity.account_id,
        version: opportunity.version,
        payload: {
          loss_reason_id: values.loss_reason_id,
          ...(values.competitor_brand_id
            ? { competitor_brand_id: values.competitor_brand_id }
            : {}),
          ...(values.note.trim() ? { note: values.note.trim() } : {}),
        },
      });
      toast({ description: t('opportunities:lostToast') });
      onSaved(saved);
    } catch (error) {
      const problem = toProblem(error);
      if (problem.code === 'loss_reason_requires_brand') {
        form.setError('competitor_brand_id', { message: 'opportunities:lose.brandRequired' });
        return;
      }
      if (problem.code === 'loss_reason_requires_note') {
        form.setError('note', { message: 'opportunities:lose.noteRequired' });
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
          name="loss_reason_id"
          render={({ field }) => (
            <FormItem>
              <FormLabel>{t('opportunities:lose.reason')}</FormLabel>
              <FormControl>
                <NativeSelect {...field}>
                  <option value="">{t('opportunities:lose.selectReason')}</option>
                  {reasons.data
                    ?.filter((candidate) => candidate.is_active)
                    .map((candidate) => (
                      <option key={candidate.id} value={candidate.id}>
                        {candidate.name_es}
                      </option>
                    ))}
                </NativeSelect>
              </FormControl>
              <CreateOptionDialog kind="loss_reason" onCreated={field.onChange} />
              <FormMessage />
            </FormItem>
          )}
        />
        {reason?.requires_brand ? (
          <FormField
            control={form.control}
            name="competitor_brand_id"
            render={({ field }) => (
              <FormItem>
                <FormLabel>{t('opportunities:lose.brand')}</FormLabel>
                <FormControl>
                  <NativeSelect {...field}>
                    <option value="">{t('opportunities:lose.selectBrand')}</option>
                    {brands.data
                      ?.filter((brand) => brand.is_active)
                      .map((brand) => (
                        <option key={brand.id} value={brand.id}>
                          {brand.name}
                        </option>
                      ))}
                  </NativeSelect>
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />
        ) : null}
        <FormField
          control={form.control}
          name="note"
          render={({ field }) => (
            <FormItem>
              <FormLabel>{t('opportunities:lose.note')}</FormLabel>
              <FormControl>
                <Input className="min-h-touch" {...field} />
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
          size="lg"
          variant="destructive"
          className="min-h-touch"
          disabled={lose.isPending}
        >
          {lose.isPending ? t('states.saving') : t('opportunities:actions.lose')}
        </Button>
      </form>
    </Form>
  );
}
