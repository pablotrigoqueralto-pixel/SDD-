import type { components } from '@/api/schema';

import { ANA_ID, TAMBRE_ID } from './accounts-fixtures';
import { REP_ID } from './fixtures';

export type ActivityRead = components['schemas']['ActivityRead'];
export type TimelineEntryRead = components['schemas']['TimelineEntryRead'];
export type TodayRead = components['schemas']['TodayRead'];

export const VISIT_TYPE_ID = '019000000-0000-7000-8000-0000000000y1';
export const CALL_TYPE_ID = '019000000-0000-7000-8000-0000000000y2';
export const NOTE_TYPE_ID = '019000000-0000-7000-8000-0000000000y6';
export const VISIT_DONE_ID = '019000000-0000-7000-8000-0000000000v1';
export const CALL_PLANNED_ID = '019000000-0000-7000-8000-0000000000v2';
export const OVERDUE_ID = '019000000-0000-7000-8000-0000000000v3';

const stamp = { created_at: '2026-08-27T09:00:00Z', updated_at: '2026-08-27T09:00:00Z' };

export function todayAt(hour: number, minute = 0): string {
  const date = new Date();
  date.setHours(hour, minute, 0, 0);
  return date.toISOString();
}

export function daysFromNow(days: number, hour = 10): string {
  const date = new Date();
  date.setDate(date.getDate() + days);
  date.setHours(hour, 0, 0, 0);
  return date.toISOString();
}

export const visitDone: ActivityRead = {
  id: VISIT_DONE_ID,
  account_id: TAMBRE_ID,
  account_name: 'Clínica Tambre',
  activity_type_id: VISIT_TYPE_ID,
  activity_type_name: 'Visita',
  owner_id: REP_ID,
  owner_name: 'Ana García',
  status: 'done',
  scheduled_at: daysFromNow(-1),
  done_at: daysFromNow(-1),
  duration_minutes: 45,
  outcome: 'positive',
  subject: 'Demo Hadeco',
  notes: 'Interés en el ecógrafo',
  cancel_reason: null,
  opportunity_id: null,
  opportunity_name: null,
  contact_ids: [ANA_ID],
  contacts: [{ id: ANA_ID, name: 'Ana Pérez' }],
  next_activity_id: CALL_PLANNED_ID,
  version: 1,
  ...stamp,
};

export const callPlanned: ActivityRead = {
  ...visitDone,
  id: CALL_PLANNED_ID,
  activity_type_id: CALL_TYPE_ID,
  activity_type_name: 'Llamada',
  status: 'planned',
  scheduled_at: todayAt(11, 30),
  done_at: null,
  duration_minutes: null,
  outcome: null,
  subject: 'Seguimiento demo',
  notes: null,
  next_activity_id: null,
};

export const overdueVisit: ActivityRead = {
  ...callPlanned,
  id: OVERDUE_ID,
  activity_type_id: VISIT_TYPE_ID,
  activity_type_name: 'Visita',
  scheduled_at: daysFromNow(-3),
  subject: null,
  contact_ids: [],
  contacts: [],
};

export const activities: ActivityRead[] = [visitDone, callPlanned, overdueVisit];

export function entryOf(activity: ActivityRead): TimelineEntryRead {
  return {
    id: activity.id,
    kind: 'activity',
    occurred_at: activity.done_at ?? activity.scheduled_at,
    title: activity.subject ?? activity.activity_type_name,
    activity,
  };
}

export const timeline: TimelineEntryRead[] = [callPlanned, visitDone, overdueVisit].map(entryOf);

export const today: TodayRead = {
  date: new Date().toISOString().slice(0, 10),
  today: [callPlanned],
  overdue: [overdueVisit],
  week: { done_by_type: { [VISIT_TYPE_ID]: 3, [CALL_TYPE_ID]: 2 }, planned_remaining: 4 },
};
