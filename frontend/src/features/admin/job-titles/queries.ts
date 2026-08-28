import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { referenceKeys } from '@/api/query-keys';

import {
  createJobTitle,
  listJobTitles,
  updateJobTitle,
  type JobTitleCreate,
  type JobTitleUpdate,
} from './api';

export const jobTitleKeys = {
  all: ['job-titles'] as const,
  list: () => [...jobTitleKeys.all, 'list'] as const,
};

export function useJobTitleList() {
  return useQuery({ queryKey: jobTitleKeys.list(), queryFn: listJobTitles });
}

function useInvalidate() {
  const queryClient = useQueryClient();
  return async () => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: jobTitleKeys.all }),
      queryClient.invalidateQueries({ queryKey: referenceKeys.all }),
    ]);
  };
}

export function useCreateJobTitle() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: (payload: JobTitleCreate) => createJobTitle(payload),
    onSuccess: invalidate,
    meta: { silent: true },
  });
}

interface UpdateVariables {
  id: string;
  version: number;
  payload: JobTitleUpdate;
}

export function useUpdateJobTitle() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: ({ id, version, payload }: UpdateVariables) => updateJobTitle(id, version, payload),
    onSuccess: invalidate,
    meta: { silent: true },
  });
}
