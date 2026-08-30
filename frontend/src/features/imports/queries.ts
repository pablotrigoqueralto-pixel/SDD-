import { useMutation, useQueryClient } from '@tanstack/react-query';

import { accountKeys, contactKeys, productKeys, quoteKeys, searchKeys } from '@/api/query-keys';

import { runImport, type ImportTarget } from './api';

export function useRunImport(target: ImportTarget) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ file, dryRun }: { file: File; dryRun: boolean }) =>
      runImport(target, file, dryRun),
    onSuccess: async (_data, { dryRun }) => {
      if (dryRun) return;
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: productKeys.all }),
        queryClient.invalidateQueries({ queryKey: accountKeys.all }),
        queryClient.invalidateQueries({ queryKey: contactKeys.all }),
        queryClient.invalidateQueries({ queryKey: quoteKeys.all }),
        queryClient.invalidateQueries({ queryKey: searchKeys.all }),
      ]);
    },
    meta: { silent: true },
  });
}
