import { z } from 'zod';

export const loginSchema = z.object({
  email: z.string().trim().min(1, 'auth:login.emailRequired').email('auth:login.emailInvalid'),
  password: z.string().min(1, 'auth:login.passwordRequired'),
});

export type LoginInput = z.infer<typeof loginSchema>;

export const changePasswordSchema = z
  .object({
    current_password: z.string().min(1, 'auth:login.passwordRequired'),
    new_password: z.string().min(12, 'auth:password.tooShort'),
    confirm_password: z.string(),
  })
  .refine((values) => values.new_password === values.confirm_password, {
    path: ['confirm_password'],
    message: 'auth:password.mismatch',
  });

export type ChangePasswordInput = z.infer<typeof changePasswordSchema>;
