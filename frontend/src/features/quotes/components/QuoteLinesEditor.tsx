import { Plus, Trash2 } from 'lucide-react';
import { useState } from 'react';
import { useFieldArray, useWatch, type Control } from 'react-hook-form';
import { useTranslation } from 'react-i18next';

import { NativeSelect } from '@/components/shared/NativeSelect';
import { Button } from '@/components/ui/button';
import { FormControl, FormField, FormItem, FormLabel, FormMessage } from '@/components/ui/form';
import { Input } from '@/components/ui/input';
import { formatPrice, useProducts } from '@/features/catalogue';

import { VAT_RATES, type QuoteFormValues } from '../schemas';
import { computeQuoteTotals } from '../totals';

interface QuoteLinesEditorProps {
  control: Control<QuoteFormValues>;
}

/** Draft lines with live per-line base: product lines and free-text lines mix freely. */
export function QuoteLinesEditor({ control }: QuoteLinesEditorProps) {
  const { t } = useTranslation();
  const { fields, append, remove } = useFieldArray({ control, name: 'lines' });
  const lines = useWatch({ control, name: 'lines' });
  const [productSearch, setProductSearch] = useState('');
  const products = useProducts({
    ...(productSearch ? { q: productSearch } : {}),
    page_size: 20,
  });

  const totals = computeQuoteTotals(
    lines.map((line) => ({
      quantity: line.quantity,
      unit_price: line.unit_price,
      discount_percent: line.discount_percent || '0',
      vat_rate: line.vat_rate,
    })),
  );

  const appendProduct = (productId: string) => {
    const product = products.data?.items.find((item) => item.id === productId);
    if (!product) return;
    append({
      product_id: product.id,
      description: product.name,
      quantity: '1',
      unit_price: product.list_price,
      discount_percent: '0',
      vat_rate: '21',
    });
  };

  return (
    <fieldset className="flex flex-col gap-3">
      <legend className="text-sm font-medium">{t('quotes:lines.title')}</legend>
      {fields.map((field, index) => (
        <div key={field.id} className="flex flex-col gap-2 rounded-lg border p-3">
          <div className="flex items-start justify-between gap-2">
            <FormField
              control={control}
              name={`lines.${index}.description`}
              render={({ field: descriptionField }) => (
                <FormItem className="flex-1">
                  <FormLabel>{t('quotes:lines.description')}</FormLabel>
                  <FormControl>
                    <Input className="min-h-touch" {...descriptionField} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <Button
              type="button"
              variant="ghost"
              size="icon"
              className="mt-7 min-h-touch min-w-touch"
              aria-label={t('quotes:lines.remove')}
              onClick={() => {
                remove(index);
              }}
            >
              <Trash2 className="size-4" aria-hidden="true" />
            </Button>
          </div>
          <div className="grid gap-3 sm:grid-cols-4">
            <FormField
              control={control}
              name={`lines.${index}.quantity`}
              render={({ field: quantityField }) => (
                <FormItem>
                  <FormLabel>{t('quotes:lines.quantity')}</FormLabel>
                  <FormControl>
                    <Input className="min-h-touch" inputMode="decimal" {...quantityField} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={control}
              name={`lines.${index}.unit_price`}
              render={({ field: priceField }) => (
                <FormItem>
                  <FormLabel>{t('quotes:lines.unitPrice')}</FormLabel>
                  <FormControl>
                    <Input className="min-h-touch" inputMode="decimal" {...priceField} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={control}
              name={`lines.${index}.discount_percent`}
              render={({ field: discountField }) => (
                <FormItem>
                  <FormLabel>{t('quotes:lines.discount')}</FormLabel>
                  <FormControl>
                    <Input className="min-h-touch" inputMode="decimal" {...discountField} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={control}
              name={`lines.${index}.vat_rate`}
              render={({ field: vatField }) => (
                <FormItem>
                  <FormLabel>{t('quotes:lines.vat')}</FormLabel>
                  <FormControl>
                    <NativeSelect {...vatField}>
                      {VAT_RATES.map((rate) => (
                        <option key={rate} value={rate}>
                          {rate} %
                        </option>
                      ))}
                    </NativeSelect>
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
          </div>
          <p className="text-right text-sm font-medium tabular-nums">
            {t('quotes:lines.base')}
            {': '}
            {formatPrice(totals.lines[index]?.base ?? '0.00')}
          </p>
        </div>
      ))}
      <div className="flex flex-col gap-2 rounded-lg border border-dashed p-3">
        <label className="text-sm font-medium" htmlFor="quote-product-search">
          {t('quotes:lines.addProduct')}
        </label>
        <Input
          id="quote-product-search"
          type="search"
          className="min-h-touch"
          placeholder={t('quotes:lines.searchProduct')}
          value={productSearch}
          onChange={(event) => {
            setProductSearch(event.target.value);
          }}
        />
        <NativeSelect
          aria-label={t('quotes:lines.addProduct')}
          value=""
          onChange={(event) => {
            appendProduct(event.target.value);
          }}
        >
          <option value="">{t('quotes:lines.addProduct')}</option>
          {products.data?.items.map((product) => (
            <option key={product.id} value={product.id}>
              {product.name}
              {' · '}
              {product.sku}
            </option>
          ))}
        </NativeSelect>
        <Button
          type="button"
          variant="outline"
          className="min-h-touch"
          onClick={() => {
            append({
              product_id: '',
              description: '',
              quantity: '1',
              unit_price: '',
              discount_percent: '0',
              vat_rate: '21',
            });
          }}
        >
          <Plus className="size-4" aria-hidden="true" />
          {t('quotes:lines.addFreeLine')}
        </Button>
      </div>
    </fieldset>
  );
}
