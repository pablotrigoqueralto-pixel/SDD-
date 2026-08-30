import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { accountKeys, activityKeys, opportunityKeys, quoteKeys } from '@/api/query-keys';

import {
  acceptQuote,
  createQuote,
  deleteQuote,
  getQuote,
  getQuoteSettings,
  listOpportunityQuotes,
  listQuotes,
  rejectQuote,
  retryQuoteEmail,
  reviseQuote,
  sendQuote,
  updateQuote,
  updateQuoteSettings,
  type QuoteListFilters,
  type QuoteSendPayload,
  type QuoteSettingsUpdate,
  type QuoteUpdatePayload,
} from './api';

export const QUOTE_PAGE_SIZE = 25;

export function useQuotes(filters: QuoteListFilters) {
  return useQuery({
    queryKey: quoteKeys.list(filters as Record<string, unknown>),
    queryFn: () => listQuotes({ page_size: QUOTE_PAGE_SIZE, ...filters }),
    placeholderData: (previous) => previous,
  });
}

export function useOpportunityQuotes(opportunityId: string | undefined) {
  return useQuery({
    queryKey: quoteKeys.byOpportunity(opportunityId ?? ''),
    queryFn: () => listOpportunityQuotes(opportunityId ?? ''),
    enabled: Boolean(opportunityId),
  });
}

export function useQuote(id: string | undefined) {
  return useQuery({
    queryKey: quoteKeys.detail(id ?? ''),
    queryFn: () => getQuote(id ?? ''),
    enabled: Boolean(id),
  });
}

export function useQuoteSettings(enabled = true) {
  return useQuery({
    queryKey: quoteKeys.settings(),
    queryFn: getQuoteSettings,
    enabled,
  });
}

/** Quote changes move the lists, the opportunity/account sections, "Hoy" and timelines. */
function useInvalidateQuotes() {
  const queryClient = useQueryClient();
  return async (context: {
    accountId?: string | undefined;
    opportunityId?: string | undefined;
    quoteId?: string | undefined;
  }) => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: quoteKeys.lists() }),
      queryClient.invalidateQueries({ queryKey: activityKeys.todays() }),
      context.opportunityId
        ? queryClient.invalidateQueries({
            queryKey: quoteKeys.byOpportunity(context.opportunityId),
          })
        : Promise.resolve(),
      context.opportunityId
        ? queryClient.invalidateQueries({
            queryKey: opportunityKeys.detail(context.opportunityId),
          })
        : Promise.resolve(),
      queryClient.invalidateQueries({ queryKey: opportunityKeys.lists() }),
      queryClient.invalidateQueries({ queryKey: opportunityKeys.boards() }),
      context.accountId
        ? queryClient.invalidateQueries({ queryKey: accountKeys.detail(context.accountId) })
        : Promise.resolve(),
      context.accountId
        ? queryClient.invalidateQueries({ queryKey: activityKeys.timelines(context.accountId) })
        : Promise.resolve(),
      context.quoteId
        ? queryClient.invalidateQueries({ queryKey: quoteKeys.detail(context.quoteId) })
        : Promise.resolve(),
    ]);
  };
}

interface QuoteContext {
  accountId?: string | undefined;
  opportunityId?: string | undefined;
}

export function useCreateQuote() {
  const invalidate = useInvalidateQuotes();
  return useMutation({
    mutationFn: (payload: { opportunity_id: string; contact_id?: string }) => createQuote(payload),
    onSuccess: (data) =>
      invalidate({
        accountId: data.account_id,
        opportunityId: data.opportunity_id,
        quoteId: data.id,
      }),
    meta: { silent: true },
  });
}

export function useUpdateQuote() {
  const invalidate = useInvalidateQuotes();
  return useMutation({
    mutationFn: ({
      id,
      version,
      payload,
    }: QuoteContext & { id: string; version: number; payload: QuoteUpdatePayload }) =>
      updateQuote(id, version, payload),
    onSuccess: (_data, { accountId, opportunityId, id }) =>
      invalidate({ accountId, opportunityId, quoteId: id }),
    meta: { silent: true },
  });
}

export function useDeleteQuote() {
  const invalidate = useInvalidateQuotes();
  return useMutation({
    mutationFn: ({ id }: QuoteContext & { id: string }) => deleteQuote(id),
    onSuccess: (_data, { accountId, opportunityId }) => invalidate({ accountId, opportunityId }),
    meta: { silent: true },
  });
}

export function useSendQuote() {
  const invalidate = useInvalidateQuotes();
  return useMutation({
    mutationFn: ({
      id,
      version,
      payload,
    }: QuoteContext & { id: string; version: number; payload: QuoteSendPayload }) =>
      sendQuote(id, version, payload),
    onSuccess: (_data, { accountId, opportunityId, id }) =>
      invalidate({ accountId, opportunityId, quoteId: id }),
    meta: { silent: true },
  });
}

export function useAcceptQuote() {
  const invalidate = useInvalidateQuotes();
  return useMutation({
    mutationFn: ({
      id,
      version,
      occurredOn,
    }: QuoteContext & { id: string; version: number; occurredOn?: string }) =>
      acceptQuote(id, version, occurredOn ? { occurred_on: occurredOn } : {}),
    onSuccess: (_data, { accountId, opportunityId, id }) =>
      invalidate({ accountId, opportunityId, quoteId: id }),
    meta: { silent: true },
  });
}

export function useRejectQuote() {
  const invalidate = useInvalidateQuotes();
  return useMutation({
    mutationFn: ({
      id,
      version,
      note,
    }: QuoteContext & { id: string; version: number; note?: string }) =>
      rejectQuote(id, version, note ? { note } : {}),
    onSuccess: (_data, { accountId, opportunityId, id }) =>
      invalidate({ accountId, opportunityId, quoteId: id }),
    meta: { silent: true },
  });
}

export function useReviseQuote() {
  const invalidate = useInvalidateQuotes();
  return useMutation({
    mutationFn: ({ id, version }: QuoteContext & { id: string; version: number }) =>
      reviseQuote(id, version),
    onSuccess: (data, { accountId, opportunityId, id }) =>
      invalidate({ accountId, opportunityId, quoteId: id }).then(() =>
        invalidate({ quoteId: data.id }),
      ),
    meta: { silent: true },
  });
}

export function useRetryQuoteEmail() {
  const invalidate = useInvalidateQuotes();
  return useMutation({
    mutationFn: ({ id }: QuoteContext & { id: string }) => retryQuoteEmail(id),
    onSuccess: (_data, { accountId, opportunityId, id }) =>
      invalidate({ accountId, opportunityId, quoteId: id }),
    meta: { silent: true },
  });
}

export function useUpdateQuoteSettings() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: QuoteSettingsUpdate) => updateQuoteSettings(payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: quoteKeys.settings() }),
    meta: { silent: true },
  });
}
