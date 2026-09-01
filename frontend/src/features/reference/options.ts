import { useMutation, useQueryClient } from '@tanstack/react-query';

import { apiClient } from '@/api/client';
import { referenceKeys } from '@/api/query-keys';
import type { components } from '@/api/schema';

/** The five catalogues an administrator can add to straight from a dropdown. */
export type CatalogueKind =
  'job_title' | 'specialty' | 'account_type' | 'loss_reason' | 'product_family';

export type CatalogueOutcome = components['schemas']['CatalogueOutcome'];

/** What every one of the five endpoints answers, reduced to what the dialog needs. */
export interface CreatedOption {
  id: string;
  name_es: string;
  outcome: CatalogueOutcome;
}

export interface CreateOptionInput {
  kind: CatalogueKind;
  name: string;
  /** Account types only: the flag that turns on the tender fields. */
  buysViaTender?: boolean;
  /** Product families only: a family belongs to exactly one division. */
  divisionId?: string;
}

const PATHS: Record<CatalogueKind, string> = {
  job_title: '/job-titles',
  specialty: '/specialties',
  account_type: '/account-types',
  loss_reason: '/loss-reasons',
  product_family: '/product-families',
};

/** Query keys of the per-catalogue admin lists, invalidated alongside the bundle. */
const LIST_KEYS: Record<CatalogueKind, readonly string[]> = {
  job_title: ['job-titles'],
  specialty: ['specialties'],
  account_type: ['account-types'],
  loss_reason: ['loss-reasons'],
  product_family: ['product-families'],
};

export async function createOption(input: CreateOptionInput): Promise<CreatedOption> {
  const body: Record<string, unknown> = { name: input.name };
  if (input.kind === 'account_type') body.buys_via_tender = input.buysViaTender ?? false;
  if (input.kind === 'product_family') body.division_id = input.divisionId;
  const { data } = await apiClient.post<CreatedOption>(PATHS[input.kind], body);
  return data;
}

/**
 * One mutation for every "+ Añadir": the new entry must show up in the form that created
 * it AND in every other screen, so the reference bundle is invalidated with the list.
 */
export function useCreateOption() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: createOption,
    onSuccess: async (_data, variables) => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: referenceKeys.all }),
        queryClient.invalidateQueries({ queryKey: LIST_KEYS[variables.kind] }),
      ]);
    },
    meta: { silent: true },
  });
}
