import { zodResolver } from '@hookform/resolvers/zod';
import { Plus, Trash2 } from 'lucide-react';
import { useState } from 'react';
import { useForm } from 'react-hook-form';
import { useTranslation } from 'react-i18next';

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
import { parsePrice, useProducts } from '@/features/catalogue';
import { isKnownErrorCode } from '@/lib/error-codes';
import { toProblem } from '@/lib/problem';

import type { OpportunityRead } from '../api';
import { useAddLine, useRemoveLine } from '../queries';
import { lineSchema, type LineInput } from '../schemas';
import { AmountText } from './AmountText';

interface LinesEditorProps {
  opportunity: OpportunityRead;
  canWrite: boolean;
}

/** Product lines with a small add form; the amount is recomputed by the backend. */
export function LinesEditor({ opportunity, canWrite }: LinesEditorProps) {
  const { t } = useTranslation();
  const addLine = useAddLine();
  const removeLine = useRemoveLine();
  const [productSearch, setProductSearch] = useState('');
  const [formError, setFormError] = useState<string | null>(null);
  const products = useProducts({
    ...(productSearch ? { q: productSearch } : {}),
    page_size: 20,
  });
  const form = useForm<LineInput>({
    resolver: zodResolver(lineSchema),
    defaultValues: { product_id: '', quantity: '1', unit_price: '' },
  });

  const handleSubmit = form.handleSubmit(async (values) => {
    setFormError(null);
    try {
      await addLine.mutateAsync({
        id: opportunity.id,
        accountId: opportunity.account_id,
        version: opportunity.version,
        payload: {
          product_id: values.product_id,
          quantity: parsePrice(values.quantity) ?? '1.00',
          ...(values.unit_price ? { unit_price: parsePrice(values.unit_price) ?? '0.00' } : {}),
        },
      });
      form.reset({ product_id: '', quantity: '1', unit_price: '' });
    } catch (error) {
      const problem = toProblem(error);
      setFormError(
        isKnownErrorCode(problem.code) ? `errors:${problem.code}` : 'toasts.genericError',
      );
    }
  });

  return (
    <div className="flex flex-col gap-3">
      {opportunity.lines.length === 0 ? (
        <p className="text-sm text-muted-foreground">{t('opportunities:sheet.noLines')}</p>
      ) : (
        <ul className="flex flex-col gap-2">
          {opportunity.lines.map((line) => (
            <li
              key={line.id}
              className="flex flex-wrap items-center justify-between gap-2 rounded-lg border p-3 text-sm"
            >
              <span className="min-w-0 flex-1">
                {t('opportunities:lines.lineLabel', {
                  quantity: line.quantity,
                })}
                <AmountText amount={line.unit_price} />
              </span>
              <AmountText amount={line.total} className="font-medium tabular-nums" />
              {canWrite ? (
                <Button
                  variant="ghost"
                  size="icon"
                  className="min-h-touch min-w-touch"
                  aria-label={t('opportunities:actions.removeLine')}
                  disabled={removeLine.isPending}
                  onClick={() =>
                    void removeLine.mutateAsync({
                      id: opportunity.id,
                      accountId: opportunity.account_id,
                      lineId: line.id,
                      version: opportunity.version,
                    })
                  }
                >
                  <Trash2 className="size-4" aria-hidden="true" />
                </Button>
              ) : null}
            </li>
          ))}
        </ul>
      )}
      {canWrite ? (
        <Form {...form}>
          <form onSubmit={handleSubmit} className="flex flex-col gap-3" noValidate>
            <FormField
              control={form.control}
              name="product_id"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>{t('opportunities:lines.product')}</FormLabel>
                  <Input
                    type="search"
                    className="min-h-touch"
                    placeholder={t('opportunities:lines.searchProduct')}
                    value={productSearch}
                    onChange={(event) => {
                      setProductSearch(event.target.value);
                    }}
                  />
                  <FormControl>
                    <NativeSelect {...field}>
                      <option value="">{t('opportunities:lines.product')}</option>
                      {products.data?.items.map((product) => (
                        <option key={product.id} value={product.id}>
                          {product.name}
                          {' · '}
                          {product.sku}
                        </option>
                      ))}
                    </NativeSelect>
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <div className="grid gap-3 sm:grid-cols-2">
              <FormField
                control={form.control}
                name="quantity"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>{t('opportunities:lines.quantity')}</FormLabel>
                    <FormControl>
                      <Input className="min-h-touch" inputMode="decimal" {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField
                control={form.control}
                name="unit_price"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>{t('opportunities:lines.unitPrice')}</FormLabel>
                    <FormControl>
                      <Input className="min-h-touch" inputMode="decimal" {...field} />
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
              variant="outline"
              className="min-h-touch"
              disabled={addLine.isPending}
            >
              <Plus className="size-4" aria-hidden="true" />
              {t('opportunities:actions.addLine')}
            </Button>
          </form>
        </Form>
      ) : null}
    </div>
  );
}
