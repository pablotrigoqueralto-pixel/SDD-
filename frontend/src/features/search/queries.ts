import { useQuery } from '@tanstack/react-query';

import { searchKeys } from '@/api/query-keys';

import { SEARCH_MIN_LENGTH, globalSearch } from './api';

export function useGlobalSearch(q: string) {
  return useQuery({
    queryKey: searchKeys.query(q),
    queryFn: () => globalSearch(q),
    enabled: q.trim().length >= SEARCH_MIN_LENGTH,
    placeholderData: (previous) => previous,
  });
}
