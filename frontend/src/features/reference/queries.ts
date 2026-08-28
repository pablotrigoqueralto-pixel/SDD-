import { useQuery, type UseQueryResult } from '@tanstack/react-query';

import { referenceKeys } from '@/api/query-keys';

import {
  getReferenceData,
  type AccountType,
  type ActivityType,
  type Brand,
  type Division,
  type JobTitle,
  type LossReason,
  type Pipeline,
  type ReferenceData,
} from './api';

const REFERENCE_STALE_TIME = 5 * 60_000;
const REFERENCE_GC_TIME = 30 * 60_000;

/** One request per session for every master; consumers read slices through the selectors. */
export function useReferenceData<T = ReferenceData>(
  select?: (data: ReferenceData) => T,
): UseQueryResult<T> {
  return useQuery({
    queryKey: referenceKeys.bundle(),
    queryFn: getReferenceData,
    staleTime: REFERENCE_STALE_TIME,
    gcTime: REFERENCE_GC_TIME,
    ...(select ? { select } : {}),
  });
}

const selectAccountTypes = (data: ReferenceData): AccountType[] => data.account_types;
const selectActivityTypes = (data: ReferenceData): ActivityType[] => data.activity_types;
const selectDivisions = (data: ReferenceData): Division[] => data.divisions;
const selectBrands = (data: ReferenceData): Brand[] => data.brands;
const selectLossReasons = (data: ReferenceData): LossReason[] => data.loss_reasons;
const selectPipelines = (data: ReferenceData): Pipeline[] => data.pipelines;
const selectJobTitles = (data: ReferenceData): JobTitle[] => data.job_titles;

export const useAccountTypes = () => useReferenceData(selectAccountTypes);
export const useActivityTypes = () => useReferenceData(selectActivityTypes);
export const useDivisions = () => useReferenceData(selectDivisions);
export const useBrands = () => useReferenceData(selectBrands);
export const useLossReasons = () => useReferenceData(selectLossReasons);
export const usePipelines = () => useReferenceData(selectPipelines);
export const useJobTitles = () => useReferenceData(selectJobTitles);

interface Labelled {
  id: string;
}

/** Resolve a label by id from any master list; falls back to the id so nothing renders blank. */
export function labelOf<T extends Labelled>(
  items: T[] | undefined,
  id: string | null | undefined,
  pick: (item: T) => string,
): string {
  if (!id) return '';
  const item = items?.find((candidate) => candidate.id === id);
  return item ? pick(item) : id;
}
