import { zodResolver } from '@hookform/resolvers/zod';
import { useQueryClient } from '@tanstack/react-query';
import { ChevronDown } from 'lucide-react';
import { useState } from 'react';
import { useForm } from 'react-hook-form';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';

import { productKeys } from '@/api/query-keys';
import { routes } from '@/app/routes';
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
import { useBrands, useDivisions, useProductFamilies } from '@/features/reference';
import { toast } from '@/hooks/use-toast';
import { cn } from '@/lib/cn';
import { isKnownErrorCode } from '@/lib/error-codes';
import { toProblem } from '@/lib/problem';
import { useConflictStore } from '@/store/conflict.store';

import {
  PRODUCT_KINDS,
  type Product,
  type ProductCreate,
  type ProductKind,
  type ProductUpdate,
} from '../api';
import { useCanEditCatalogue, useCanViewCost } from '../hooks';
import { useCreateProduct, useSetProductActive, useUpdateProduct } from '../queries';
import { parsePrice, priceToInput, productSchema, type ProductInput } from '../schemas';
import { KindIcon } from './KindIcon';

interface ProductFormProps {
  product?: Product;
  onSaved: (product: Product) => void;
}

function toDefaults(product: Product | undefined): ProductInput {
  return {
    sku: product?.sku ?? '',
    name: product?.name ?? '',
    brand_id: product?.brand.id ?? '',
    family_id: product?.family.id ?? '',
    kind: product?.kind ?? '',
    list_price: priceToInput(product?.list_price),
    cost_price: priceToInput(product?.cost_price),
    unit: product?.unit ?? 'ud',
    description: product?.description ?? '',
    is_active: product?.is_active ?? true,
  };
}

function toCreate(values: ProductInput, canViewCost: boolean): ProductCreate {
  const payload: ProductCreate = {
    sku: values.sku,
    name: values.name,
    brand_id: values.brand_id,
    family_id: values.family_id,
    kind: values.kind as ProductKind,
    list_price: parsePrice(values.list_price) ?? '0.00',
  };
  if (values.unit && values.unit !== 'ud') payload.unit = values.unit;
  if (values.description) payload.description = values.description;
  const cost = canViewCost ? parsePrice(values.cost_price) : null;
  if (cost) payload.cost_price = cost;
  return payload;
}

/** Only fields whose value changed travel in the PATCH (null clears an optional one). */
function toUpdate(values: ProductInput, product: Product, canViewCost: boolean): ProductUpdate {
  const payload: ProductUpdate = {};
  if (values.sku.toUpperCase() !== product.sku) payload.sku = values.sku;
  if (values.name !== product.name) payload.name = values.name;
  if (values.brand_id !== product.brand.id) payload.brand_id = values.brand_id;
  if (values.family_id !== product.family.id) payload.family_id = values.family_id;
  if (values.kind !== product.kind) payload.kind = values.kind as ProductKind;
  const listPrice = parsePrice(values.list_price);
  if (listPrice && listPrice !== product.list_price) payload.list_price = listPrice;
  if (canViewCost) {
    const cost = parsePrice(values.cost_price);
    if (cost !== (product.cost_price ?? null)) payload.cost_price = cost;
  }
  const unit = values.unit || 'ud';
  if (unit !== product.unit) payload.unit = unit;
  const description = values.description || null;
  if (description !== product.description) payload.description = description;
  return payload;
}

export function ProductForm({ product, onSaved }: ProductFormProps) {
  const { t } = useTranslation();
  const canEdit = useCanEditCatalogue();
  const canViewCost = useCanViewCost();
  const brands = useBrands();
  const divisions = useDivisions();
  const families = useProductFamilies();
  const create = useCreateProduct();
  const update = useUpdateProduct();
  const setActive = useSetProductActive();
  const queryClient = useQueryClient();
  const [moreOpen, setMoreOpen] = useState(Boolean(product));
  const [formError, setFormError] = useState<string | null>(null);
  const [existingProductId, setExistingProductId] = useState<string | null>(null);
  const form = useForm<ProductInput>({
    resolver: zodResolver(productSchema),
    defaultValues: toDefaults(product),
    disabled: !canEdit,
  });
  const pending = create.isPending || update.isPending || setActive.isPending;

  const brandOptions = [...(brands.data ?? [])]
    .filter((brand) => brand.is_active || brand.id === product?.brand.id)
    .sort((a, b) => Number(b.is_own) - Number(a.is_own) || a.name.localeCompare(b.name));
  // A new family lands in the division of the family already chosen, which is what an
  // admin adding "Láser" next to the other vascular families means.
  const selectedFamilyId = form.watch('family_id');
  const divisionOfSelectedFamily = (families.data ?? []).find(
    (family) => family.id === selectedFamilyId,
  )?.division_id;
  const familyGroups = (divisions.data ?? [])
    .map((division) => ({
      division,
      families: (families.data ?? []).filter(
        (family) =>
          family.division_id === division.id &&
          (family.is_active || family.id === product?.family.id),
      ),
    }))
    .filter((group) => group.families.length > 0);

  const handleSubmit = form.handleSubmit(async (values) => {
    setFormError(null);
    setExistingProductId(null);
    try {
      let saved: Product;
      if (product) {
        const payload = toUpdate(values, product, canViewCost);
        saved =
          Object.keys(payload).length > 0
            ? await update.mutateAsync({ id: product.id, version: product.version, payload })
            : product;
        if (values.is_active !== product.is_active) {
          saved = await setActive.mutateAsync({
            id: product.id,
            version: saved.version,
            active: values.is_active,
          });
        }
        toast({ description: t('catalogue:updated') });
      } else {
        saved = await create.mutateAsync(toCreate(values, canViewCost));
        toast({ description: t('catalogue:created') });
      }
      onSaved(saved);
    } catch (error) {
      const problem = toProblem(error);
      if (problem.code === 'conflict' && product) {
        useConflictStore
          .getState()
          .show(() => queryClient.invalidateQueries({ queryKey: productKeys.detail(product.id) }));
        return;
      }
      if (problem.code === 'product_sku_exists') {
        setExistingProductId(problem.extensions.existing_product_id ?? null);
        form.setError('sku', { message: 'catalogue:form.skuExists' });
        return;
      }
      if (problem.code === 'product_sku_locked') {
        form.setError('sku', { message: 'catalogue:form.skuLocked' });
        return;
      }
      if (problem.code === 'price_invalid') {
        const field = problem.errors[0]?.field === 'cost_price' ? 'cost_price' : 'list_price';
        setMoreOpen(true);
        form.setError(field, { message: 'catalogue:form.priceInvalid' });
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
        {canEdit ? null : (
          <p className="text-sm text-muted-foreground" role="note">
            {t('catalogue:readOnly')}
          </p>
        )}
        <div className="grid gap-4 sm:grid-cols-2">
          <FormField
            control={form.control}
            name="sku"
            render={({ field }) => (
              <FormItem>
                <FormLabel>{t('catalogue:form.sku')}</FormLabel>
                <FormControl>
                  <Input className="min-h-touch uppercase" autoCapitalize="characters" {...field} />
                </FormControl>
                <FormMessage />
                {existingProductId ? (
                  <Link to={routes.product(existingProductId)} className="text-sm underline">
                    {t('catalogue:form.skuExistsLink')}
                  </Link>
                ) : null}
              </FormItem>
            )}
          />
          <FormField
            control={form.control}
            name="name"
            render={({ field }) => (
              <FormItem>
                <FormLabel>{t('catalogue:form.name')}</FormLabel>
                <FormControl>
                  <Input className="min-h-touch" {...field} />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />
        </div>
        <div className="grid gap-4 sm:grid-cols-2">
          <FormField
            control={form.control}
            name="brand_id"
            render={({ field }) => (
              <FormItem>
                <FormLabel>{t('catalogue:form.brand')}</FormLabel>
                <FormControl>
                  <NativeSelect {...field}>
                    <option value="">{t('catalogue:form.selectBrand')}</option>
                    {brandOptions.map((brand) => (
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
          <FormField
            control={form.control}
            name="family_id"
            render={({ field }) => (
              <FormItem>
                <FormLabel>{t('catalogue:form.family')}</FormLabel>
                <FormControl>
                  <NativeSelect {...field}>
                    <option value="">{t('catalogue:form.selectFamily')}</option>
                    {familyGroups.map((group) => (
                      <optgroup key={group.division.id} label={group.division.name_es}>
                        {group.families.map((family) => (
                          <option key={family.id} value={family.id}>
                            {family.name_es}
                          </option>
                        ))}
                      </optgroup>
                    ))}
                  </NativeSelect>
                </FormControl>
                <CreateOptionDialog
                  kind="product_family"
                  onCreated={field.onChange}
                  {...(divisionOfSelectedFamily ? { divisionId: divisionOfSelectedFamily } : {})}
                />
                <FormMessage />
              </FormItem>
            )}
          />
        </div>
        <FormField
          control={form.control}
          name="kind"
          render={({ field }) => (
            <FormItem>
              <fieldset disabled={!canEdit}>
                <legend className="text-sm font-medium">{t('catalogue:form.kind')}</legend>
                <div className="mt-1 grid grid-cols-3 gap-2">
                  {PRODUCT_KINDS.map((kind) => (
                    <label
                      key={kind}
                      className={cn(
                        'flex min-h-touch cursor-pointer flex-col items-center justify-center gap-1 rounded-md border px-2 py-2 text-xs',
                        field.value === kind
                          ? 'border-primary bg-accent font-semibold'
                          : 'hover:bg-muted',
                      )}
                    >
                      <input
                        type="radio"
                        name={field.name}
                        value={kind}
                        checked={field.value === kind}
                        onChange={() => {
                          field.onChange(kind);
                        }}
                        onBlur={field.onBlur}
                        className="sr-only"
                      />
                      <KindIcon kind={kind} labelled={false} />
                      <span>{t(`catalogue:kind.${kind}`)}</span>
                    </label>
                  ))}
                </div>
              </fieldset>
              <FormMessage />
            </FormItem>
          )}
        />
        <FormField
          control={form.control}
          name="list_price"
          render={({ field }) => (
            <FormItem>
              <FormLabel>{t('catalogue:form.listPrice')}</FormLabel>
              <FormControl>
                <Input
                  className="min-h-touch"
                  inputMode="decimal"
                  placeholder={t('catalogue:form.priceHint')}
                  {...field}
                />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />

        <button
          type="button"
          className="flex min-h-touch items-center justify-between rounded-md border px-3 text-sm font-medium"
          aria-expanded={moreOpen}
          aria-controls="product-more-data"
          onClick={() => {
            setMoreOpen((open) => !open);
          }}
        >
          <span>{t('catalogue:form.moreData')}</span>
          <ChevronDown
            className={cn('size-4 transition-transform', moreOpen && 'rotate-180')}
            aria-hidden="true"
          />
        </button>
        <div id="product-more-data" className="flex flex-col gap-4" hidden={!moreOpen}>
          <div className="grid gap-4 sm:grid-cols-2">
            <FormField
              control={form.control}
              name="unit"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>{t('catalogue:form.unit')}</FormLabel>
                  <FormControl>
                    <Input className="min-h-touch" {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            {canViewCost ? (
              <FormField
                control={form.control}
                name="cost_price"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>{t('catalogue:form.costPrice')}</FormLabel>
                    <FormControl>
                      <Input className="min-h-touch" inputMode="decimal" {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
            ) : null}
          </div>
          <FormField
            control={form.control}
            name="description"
            render={({ field }) => (
              <FormItem>
                <FormLabel>{t('catalogue:form.description')}</FormLabel>
                <FormControl>
                  <Input className="min-h-touch" {...field} />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />
          {product ? (
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
                      disabled={!canEdit}
                      onChange={(event) => {
                        field.onChange(event.target.checked);
                      }}
                    />
                    <span>{t('catalogue:form.active')}</span>
                  </label>
                </FormItem>
              )}
            />
          ) : null}
        </div>
        {formError ? (
          <p role="alert" className="text-sm font-medium text-destructive">
            {t(formError)}
          </p>
        ) : null}
        {canEdit ? (
          <Button type="submit" size="lg" className="min-h-touch" disabled={pending}>
            {pending ? t('states.saving') : t('actions.save')}
          </Button>
        ) : null}
      </form>
    </Form>
  );
}
