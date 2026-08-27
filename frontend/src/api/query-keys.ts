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

export const divisionKeys = {
  all: ['divisions'] as const,
  list: () => [...divisionKeys.all, 'list'] as const,
};
