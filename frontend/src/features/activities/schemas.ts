import { z } from 'zod';

export const activitySchema = z
  .object({
    activity_type_id: z.string().min(1, 'activities:form.typeRequired'),
    account_id: z.string().min(1, 'activities:form.accountRequired'),
    scheduled_at: z.string().min(1, 'activities:form.whenRequired'),
    planned: z.boolean(),
    contact_ids: z.array(z.string()),
    duration_minutes: z.string().trim(),
    outcome: z.enum(['', 'positive', 'neutral', 'negative', 'no_contact']),
    subject: z.string().trim().max(120),
    notes: z.string().trim().max(4000),
    owner_id: z.string(),
    next_action_type_id: z.string(),
    next_action_at: z.string(),
    next_action_subject: z.string().trim().max(120),
  })
  .superRefine((values, context) => {
    if (values.next_action_type_id && !values.next_action_at) {
      context.addIssue({
        code: z.ZodIssueCode.custom,
        path: ['next_action_at'],
        message: 'activities:form.nextActionWhenRequired',
      });
    }
  });

export type ActivityInput = z.infer<typeof activitySchema>;

export const completeSchema = z
  .object({
    done_at: z.string(),
    outcome: z.enum(['', 'positive', 'neutral', 'negative', 'no_contact']),
    notes: z.string().trim().max(4000),
    next_action_type_id: z.string(),
    next_action_at: z.string(),
  })
  .superRefine((values, context) => {
    if (values.next_action_type_id && !values.next_action_at) {
      context.addIssue({
        code: z.ZodIssueCode.custom,
        path: ['next_action_at'],
        message: 'activities:form.nextActionWhenRequired',
      });
    }
  });

export type CompleteInput = z.infer<typeof completeSchema>;

export const cancelSchema = z.object({
  reason: z.string().trim().min(1, 'activities:cancel.reasonRequired').max(200),
});

export type CancelInput = z.infer<typeof cancelSchema>;

export const rescheduleSchema = z.object({
  scheduled_at: z.string().min(1, 'activities:form.whenRequired'),
});

export type RescheduleInput = z.infer<typeof rescheduleSchema>;

/** `datetime-local` value (local wall time, minute precision) for a Date. */
export function toLocalInput(date: Date): string {
  const pad = (n: number) => String(n).padStart(2, '0');
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`;
}

export function nowLocal(): string {
  return toLocalInput(new Date());
}

export function tomorrowAtNine(): string {
  const date = new Date();
  date.setDate(date.getDate() + 1);
  date.setHours(9, 0, 0, 0);
  return toLocalInput(date);
}

export function fromLocalInput(value: string): string {
  return new Date(value).toISOString();
}

export const EDIT_WINDOW_DAYS = 7;

export function isWithinEditWindow(doneAt: string | null, now = new Date()): boolean {
  if (!doneAt) return true;
  return now.getTime() - new Date(doneAt).getTime() <= EDIT_WINDOW_DAYS * 86_400_000;
}
