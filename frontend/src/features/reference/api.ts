import { apiClient } from '@/api/client';
import type { components } from '@/api/schema';

export type ReferenceData = components['schemas']['ReferenceDataRead'];
export type AccountType = components['schemas']['AccountTypeRead'];
export type ActivityType = components['schemas']['ActivityTypeRead'];
export type Division = components['schemas']['DivisionRead'];
export type Brand = components['schemas']['BrandRead'];
export type LossReason = components['schemas']['LossReasonRead'];
export type Pipeline = components['schemas']['PipelineRead'];
export type PipelineStage = components['schemas']['PipelineStageRead'];
export type JobTitle = components['schemas']['JobTitleRead'];
export type Specialty = components['schemas']['SpecialtyRead'];
export type ProductFamily = components['schemas']['ProductFamilyRead'];

export async function getReferenceData(): Promise<ReferenceData> {
  const { data } = await apiClient.get<ReferenceData>('/reference-data');
  return data;
}
