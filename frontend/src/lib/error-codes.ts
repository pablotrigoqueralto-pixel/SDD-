/** Stable machine-readable error codes emitted by the backend (design D6). */
export const ERROR_CODES = [
  'invalid_credentials',
  'account_locked',
  'rate_limited',
  'unauthenticated',
  'forbidden',
  'not_found',
  'conflict',
  'precondition_required',
  'validation_error',
  'invalid_sort_field',
  'email_already_exists',
  'unknown_reference',
  'cannot_demote_self',
  'invalid_current_password',
  'password_too_short',
  'invalid_email',
  'province_already_assigned',
  'invalid_province',
  'territory_in_use',
  'territory_name_already_exists',
  'internal_error',
] as const;

export type ErrorCode = (typeof ERROR_CODES)[number];

export function isKnownErrorCode(code: string): code is ErrorCode {
  return (ERROR_CODES as readonly string[]).includes(code);
}
