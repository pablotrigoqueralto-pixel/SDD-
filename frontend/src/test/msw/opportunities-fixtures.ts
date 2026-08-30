import type { components } from '@/api/schema';

import { TAMBRE_ID } from './accounts-fixtures';
import { REP_ID, VASCULAR_ID } from './fixtures';
import { EQUIPMENT_ID, pipelines } from './reference-fixtures';

export type OpportunityRead = components['schemas']['OpportunityRead'];
export type OpportunitySummaryRead = components['schemas']['OpportunitySummaryRead'];
export type BoardRead = components['schemas']['BoardRead'];

export const OPP_ID = '019000000-0000-7000-8000-0000000000o1';
export const OPP_TENDER_ID = '019000000-0000-7000-8000-0000000000o2';
export const OPP_WON_ID = '019000000-0000-7000-8000-0000000000o3';

const equipment = pipelines[0]!;
export const CONTACT_STAGE = equipment.stages[0]!;
export const DEMO_STAGE = equipment.stages[1]!;
export const QUOTE_STAGE = equipment.stages[2]!;
export const WON_STAGE = equipment.stages[3]!;
export const LOST_STAGE = equipment.stages[4]!;

const stamp = { created_at: '2026-08-27T09:00:00Z', updated_at: '2026-08-27T09:00:00Z' };

export const doppler: OpportunityRead = {
  id: OPP_ID,
  account_id: TAMBRE_ID,
  account_name: 'Clínica Tambre',
  pipeline_id: EQUIPMENT_ID,
  pipeline_name: 'Equipos',
  stage_id: DEMO_STAGE.id,
  stage_name: 'Demo',
  division_id: VASCULAR_ID,
  owner_id: REP_ID,
  owner_name: 'Ana García',
  name: 'Clínica Tambre · Vascular · agosto 2026',
  description: null,
  status: 'open',
  estimated_amount: '30000.00',
  amount: '30000.00',
  expected_close_date: '2026-11-26',
  won_amount: null,
  won_at: null,
  lost_at: null,
  loss_reason_id: null,
  competitor_brand_id: null,
  loss_note: null,
  is_tender: false,
  tender_reference: null,
  tender_deadline: null,
  estimated_award_date: null,
  is_at_risk: false,
  at_risk_since: null,
  at_risk_source: null,
  stage_entered_at: '2026-08-22T09:00:00Z',
  days_in_stage: 6,
  lines: [],
  quotes_count: 0,
  stage_history: [
    {
      from_stage_id: CONTACT_STAGE.id,
      to_stage_id: DEMO_STAGE.id,
      actor_id: REP_ID,
      occurred_at: '2026-08-22T09:00:00Z',
      seconds_in_previous_stage: 86400,
    },
    {
      from_stage_id: null,
      to_stage_id: CONTACT_STAGE.id,
      actor_id: REP_ID,
      occurred_at: '2026-08-21T09:00:00Z',
      seconds_in_previous_stage: null,
    },
  ],
  version: 2,
  ...stamp,
};

export const tenderOpportunity: OpportunityRead = {
  ...doppler,
  id: OPP_TENDER_ID,
  name: 'H. La Paz · Vascular · agosto 2026',
  account_name: 'Hospital La Paz',
  stage_id: QUOTE_STAGE.id,
  stage_name: 'Presupuesto',
  amount: '60000.00',
  estimated_amount: '60000.00',
  is_tender: true,
  tender_reference: 'EXP-2026/44',
  tender_deadline: '2026-09-02',
  days_in_stage: 12,
  stage_history: [],
  version: 1,
};

export const wonOpportunity: OpportunityRead = {
  ...doppler,
  id: OPP_WON_ID,
  name: 'Clínica Tambre · Vascular · julio 2026',
  status: 'won',
  stage_id: WON_STAGE.id,
  stage_name: 'Ganada',
  won_amount: '24000.00',
  won_at: '2026-08-20T09:00:00Z',
  stage_history: [],
  version: 3,
};

export function summaryOf(opportunity: OpportunityRead): OpportunitySummaryRead {
  return {
    id: opportunity.id,
    account_id: opportunity.account_id,
    account_name: opportunity.account_name,
    name: opportunity.name,
    pipeline_id: opportunity.pipeline_id,
    stage_id: opportunity.stage_id,
    stage_name: opportunity.stage_name,
    division_id: opportunity.division_id,
    owner_id: opportunity.owner_id,
    owner_name: opportunity.owner_name,
    status: opportunity.status,
    amount: opportunity.amount,
    expected_close_date: opportunity.expected_close_date,
    is_tender: opportunity.is_tender,
    tender_deadline: opportunity.tender_deadline,
    is_at_risk: opportunity.is_at_risk,
    stage_entered_at: opportunity.stage_entered_at,
    days_in_stage: opportunity.days_in_stage,
    version: opportunity.version,
    updated_at: opportunity.updated_at,
  };
}

export const opportunities: OpportunityRead[] = [doppler, tenderOpportunity, wonOpportunity];

export const board: BoardRead = {
  pipeline: equipment,
  columns: [
    {
      stage: CONTACT_STAGE,
      count: 0,
      total_amount: '0.00',
      items: [],
      has_more: false,
    },
    {
      stage: DEMO_STAGE,
      count: 1,
      total_amount: '30000.00',
      items: [summaryOf(doppler)],
      has_more: false,
    },
    {
      stage: QUOTE_STAGE,
      count: 1,
      total_amount: '60000.00',
      items: [summaryOf(tenderOpportunity)],
      has_more: false,
    },
  ],
  closed_this_month: { won_count: 1, won_amount: '24000.00', lost_count: 0 },
};
