import { apiClient, ifMatch } from '@/api/client';
import type { components } from '@/api/schema';

export type JobTitleRead = components['schemas']['JobTitleRead'];
export type JobTitleCreate = components['schemas']['JobTitleCreate'];
export type JobTitleUpdate = components['schemas']['JobTitleUpdate'];

export async function listJobTitles(): Promise<JobTitleRead[]> {
  const { data } = await apiClient.get<JobTitleRead[]>('/job-titles');
  return data;
}

export async function createJobTitle(payload: JobTitleCreate): Promise<JobTitleRead> {
  const { data } = await apiClient.post<JobTitleRead>('/job-titles', payload);
  return data;
}

export async function updateJobTitle(
  id: string,
  version: number,
  payload: JobTitleUpdate,
): Promise<JobTitleRead> {
  const { data } = await apiClient.patch<JobTitleRead>(`/job-titles/${id}`, payload, {
    headers: ifMatch(version),
  });
  return data;
}
