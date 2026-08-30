/** Centralised query key factories: invalidate by prefix, never build keys inline. */

export const authKeys = {
  all: ['auth'] as const,
  me: () => [...authKeys.all, 'me'] as const,
};

export const userKeys = {
  all: ['users'] as const,
  lists: () => [...userKeys.all, 'list'] as const,
  list: (filters: Record<string, unknown>) => [...userKeys.lists(), filters] as const,
  details: () => [...userKeys.all, 'detail'] as const,
  detail: (id: string) => [...userKeys.details(), id] as const,
};

export const territoryKeys = {
  all: ['territories'] as const,
  lists: () => [...territoryKeys.all, 'list'] as const,
  list: (filters: Record<string, unknown>) => [...territoryKeys.lists(), filters] as const,
  details: () => [...territoryKeys.all, 'detail'] as const,
  detail: (id: string) => [...territoryKeys.details(), id] as const,
};

export const referenceKeys = {
  all: ['reference'] as const,
  bundle: () => [...referenceKeys.all, 'bundle'] as const,
};

export const accountKeys = {
  all: ['accounts'] as const,
  lists: () => [...accountKeys.all, 'list'] as const,
  list: (filters: Record<string, unknown>) => [...accountKeys.lists(), filters] as const,
  details: () => [...accountKeys.all, 'detail'] as const,
  detail: (id: string) => [...accountKeys.details(), id] as const,
};

export const contactKeys = {
  all: ['contacts'] as const,
  byAccount: (accountId: string) => [...contactKeys.all, 'account', accountId] as const,
  details: () => [...contactKeys.all, 'detail'] as const,
  detail: (id: string) => [...contactKeys.details(), id] as const,
};

export const productKeys = {
  all: ['products'] as const,
  lists: () => [...productKeys.all, 'list'] as const,
  list: (filters: Record<string, unknown>) => [...productKeys.lists(), filters] as const,
  details: () => [...productKeys.all, 'detail'] as const,
  detail: (id: string) => [...productKeys.details(), id] as const,
};

export const opportunityKeys = {
  all: ['opportunities'] as const,
  lists: () => [...opportunityKeys.all, 'list'] as const,
  list: (filters: Record<string, unknown>) => [...opportunityKeys.lists(), filters] as const,
  boards: () => [...opportunityKeys.all, 'board'] as const,
  board: (filters: Record<string, unknown>) => [...opportunityKeys.boards(), filters] as const,
  byAccount: (accountId: string) => [...opportunityKeys.all, 'account', accountId] as const,
  details: () => [...opportunityKeys.all, 'detail'] as const,
  detail: (id: string) => [...opportunityKeys.details(), id] as const,
};

export const searchKeys = {
  all: ['search'] as const,
  query: (q: string) => [...searchKeys.all, q] as const,
};

export const quoteKeys = {
  all: ['quotes'] as const,
  lists: () => [...quoteKeys.all, 'list'] as const,
  list: (filters: Record<string, unknown>) => [...quoteKeys.lists(), filters] as const,
  byOpportunity: (opportunityId: string) =>
    [...quoteKeys.all, 'opportunity', opportunityId] as const,
  details: () => [...quoteKeys.all, 'detail'] as const,
  detail: (id: string) => [...quoteKeys.details(), id] as const,
  settings: () => [...quoteKeys.all, 'settings'] as const,
};

export const activityKeys = {
  all: ['activities'] as const,
  todays: () => [...activityKeys.all, 'today'] as const,
  today: (userId: string) => [...activityKeys.todays(), userId] as const,
  timelines: (accountId: string) => [...activityKeys.all, 'timeline', accountId] as const,
  timeline: (accountId: string, filters: Record<string, unknown>) =>
    [...activityKeys.timelines(accountId), filters] as const,
  details: () => [...activityKeys.all, 'detail'] as const,
  detail: (id: string) => [...activityKeys.details(), id] as const,
};
