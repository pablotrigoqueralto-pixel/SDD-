import { MutationCache, QueryCache, QueryClient, QueryClientProvider } from '@tanstack/react-query';
import type { ReactNode } from 'react';
import { I18nextProvider } from 'react-i18next';

import { ConflictDialog } from '@/components/shared/ConflictDialog';
import { Toaster } from '@/components/ui/toaster';
import { toast } from '@/hooks/use-toast';
import { i18n } from '@/i18n';
import { isKnownErrorCode } from '@/lib/error-codes';
import { toProblem } from '@/lib/problem';
import { useConflictStore } from '@/store/conflict.store';

interface MutationMeta {
  /** The caller handles errors itself (field errors, inline messages). */
  silent?: boolean;
  /** Query keys to refetch when the user chooses "Recargar" on a conflict. */
  conflictKeys?: readonly (readonly unknown[])[];
}

function handleMutationError(queryClient: QueryClient, error: unknown, meta: MutationMeta): void {
  const problem = toProblem(error);
  if (meta.silent) return; // the caller maps errors (field errors, conflicts) itself
  if (problem.code === 'conflict') {
    useConflictStore.getState().show(async () => {
      await Promise.all(
        (meta.conflictKeys ?? []).map((key) => queryClient.invalidateQueries({ queryKey: key })),
      );
    });
    return;
  }
  if (problem.errors.length > 0) return;
  toast({
    variant: 'destructive',
    description: isKnownErrorCode(problem.code)
      ? i18n.t(`errors:${problem.code}`)
      : i18n.t('toasts.genericError'),
  });
}

export function createQueryClient(): QueryClient {
  const queryClient: QueryClient = new QueryClient({
    defaultOptions: {
      queries: {
        staleTime: 30_000,
        retry: (failureCount, error) => {
          const problem = toProblem(error);
          // Retry only network failures (poor coverage), never 4xx/5xx application errors.
          return problem.status === 0 && failureCount < 3;
        },
        networkMode: 'offlineFirst',
        refetchOnWindowFocus: false,
      },
      mutations: { networkMode: 'offlineFirst', retry: 0 },
    },
    queryCache: new QueryCache(),
    mutationCache: new MutationCache({
      onError: (error, _variables, _context, mutation) => {
        handleMutationError(queryClient, error, mutation.meta ?? {});
      },
    }),
  });
  return queryClient;
}

interface ProvidersProps {
  queryClient: QueryClient;
  children: ReactNode;
}

export function Providers({ queryClient, children }: ProvidersProps) {
  return (
    <QueryClientProvider client={queryClient}>
      <I18nextProvider i18n={i18n}>
        {children}
        <ConflictDialog />
        <Toaster />
      </I18nextProvider>
    </QueryClientProvider>
  );
}
