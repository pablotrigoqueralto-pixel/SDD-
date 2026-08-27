import { z } from 'zod';

const envSchema = z.object({
  VITE_API_URL: z
    .string()
    .url()
    .refine((value) => !value.replace(/\/+$/, '').endsWith('/api/v1'), {
      message: 'VITE_API_URL must be the backend base URL without the /api/v1 prefix',
    }),
});

export type Env = z.infer<typeof envSchema>;

/** Validate the Vite environment once; throws a readable error at startup when misconfigured. */
export function parseEnv(raw: Record<string, unknown>): Env {
  const result = envSchema.safeParse(raw);
  if (!result.success) {
    const issues = result.error.issues.map((issue) => `${issue.path.join('.')}: ${issue.message}`);
    throw new Error(`Invalid environment configuration:\n${issues.join('\n')}`);
  }
  return {
    VITE_API_URL: result.data.VITE_API_URL.replace(/\/+$/, ''),
  };
}

export const env: Env = parseEnv(import.meta.env);
