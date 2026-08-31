import { z } from 'zod';

import { phoneRowSchema } from '@/components/shared/PhoneListEditor';

export const contactSchema = z
  .object({
    first_name: z.string().trim().min(1, 'contacts:form.firstNameRequired').max(100),
    last_name: z.string().trim().min(1, 'contacts:form.lastNameRequired').max(150),
    job_title_id: z.string(),
    specialty_id: z.string(),
    email: z.string().trim().max(254),
    phones: z.array(phoneRowSchema),
    is_head_of_department: z.boolean(),
    preferred_channel: z.enum(['', 'email', 'phone']),
    notes: z.string().trim().max(4000),
    is_primary: z.boolean(),
    is_active: z.boolean(),
    consent_status: z.enum(['unknown', 'granted', 'denied']),
    consent_at: z.string(),
    consent_source: z.enum(['', 'verbal', 'email', 'form', 'imported']),
  })
  .superRefine((values, context) => {
    if (values.email && !/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(values.email)) {
      context.addIssue({
        code: z.ZodIssueCode.custom,
        path: ['email'],
        message: 'contacts:form.emailInvalid',
      });
    }
    if (values.consent_status !== 'unknown') {
      if (!values.consent_source) {
        context.addIssue({
          code: z.ZodIssueCode.custom,
          path: ['consent_source'],
          message: 'contacts:consent.sourceRequired',
        });
      }
      if (!values.consent_at) {
        context.addIssue({
          code: z.ZodIssueCode.custom,
          path: ['consent_at'],
          message: 'contacts:consent.dateRequired',
        });
      }
    }
  });

export type ContactInput = z.infer<typeof contactSchema>;

export function today(): string {
  return new Date().toISOString().slice(0, 10);
}
