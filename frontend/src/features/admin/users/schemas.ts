import { z } from 'zod';

import { ROLES } from '../types';

const roleSchema = z.enum(ROLES as [string, ...string[]]);

export const userCreateSchema = z.object({
  full_name: z.string().trim().min(1, 'auth:login.emailRequired').max(200),
  email: z.string().trim().min(1, 'auth:login.emailRequired').email('auth:login.emailInvalid'),
  role: roleSchema,
  password: z.string().min(12, 'auth:password.tooShort'),
  territory_ids: z.array(z.string()),
  division_ids: z.array(z.string()),
});

export const userUpdateSchema = userCreateSchema.omit({ password: true, email: true }).extend({
  is_active: z.boolean(),
  password: z.union([z.literal(''), z.string().min(12, 'auth:password.tooShort')]),
});

export type UserCreateInput = z.infer<typeof userCreateSchema>;
export type UserUpdateInput = z.infer<typeof userUpdateSchema>;
