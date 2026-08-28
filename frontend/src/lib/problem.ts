import { isAxiosError } from 'axios';

/** RFC 7807 problem details as emitted by the backend. */
export interface FieldError {
  field: string;
  message: string;
  code: string;
}

export interface Problem {
  status: number;
  code: string;
  title: string;
  detail: string;
  traceId: string | null;
  errors: FieldError[];
  /** Extra RFC 7807 members (e.g. `existing_account_id`). */
  extensions: Record<string, string>;
}

export const NETWORK_PROBLEM_CODE = 'network_error';
export const UNKNOWN_PROBLEM_CODE = 'internal_error';

/** Throwable Problem so it flows through promise rejections and query error handling. */
export class ProblemError extends Error implements Problem {
  readonly status: number;
  readonly code: string;
  readonly title: string;
  readonly detail: string;
  readonly traceId: string | null;
  readonly errors: FieldError[];
  readonly extensions: Record<string, string>;

  constructor(problem: Problem) {
    super(problem.detail || problem.title || problem.code);
    this.name = 'ProblemError';
    this.status = problem.status;
    this.code = problem.code;
    this.title = problem.title;
    this.detail = problem.detail;
    this.traceId = problem.traceId;
    this.errors = problem.errors;
    this.extensions = problem.extensions;
  }
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null;
}

function asString(value: unknown, fallback: string): string {
  return typeof value === 'string' ? value : fallback;
}

/** Build a Problem from a raw response body, tolerating non-problem payloads. */
export function problemFromBody(status: number, body: unknown): ProblemError {
  const record = isRecord(body) ? body : {};
  const rawErrors = Array.isArray(record.errors) ? record.errors : [];
  const errors: FieldError[] = rawErrors.filter(isRecord).map((error) => ({
    field: asString(error.field, ''),
    message: asString(error.message, ''),
    code: asString(error.code, 'invalid'),
  }));
  const known = new Set(['type', 'title', 'status', 'detail', 'code', 'trace_id', 'errors']);
  const extensions: Record<string, string> = {};
  for (const [key, value] of Object.entries(record)) {
    if (!known.has(key) && typeof value === 'string') extensions[key] = value;
  }
  return new ProblemError({
    status,
    code: asString(record.code, UNKNOWN_PROBLEM_CODE),
    title: asString(record.title, ''),
    detail: asString(record.detail, ''),
    traceId: typeof record.trace_id === 'string' ? record.trace_id : null,
    errors,
    extensions,
  });
}

/** Normalise anything thrown by the API client into a Problem. */
export function toProblem(error: unknown): ProblemError {
  if (isProblem(error)) {
    return error;
  }
  if (isAxiosError(error)) {
    if (error.response) {
      return problemFromBody(error.response.status, error.response.data);
    }
    return new ProblemError({
      status: 0,
      code: NETWORK_PROBLEM_CODE,
      title: 'Network error',
      detail: error.message,
      traceId: null,
      errors: [],
      extensions: {},
    });
  }
  return new ProblemError({
    status: 0,
    code: UNKNOWN_PROBLEM_CODE,
    title: 'Unexpected error',
    detail: error instanceof Error ? error.message : String(error),
    traceId: null,
    errors: [],
    extensions: {},
  });
}

export function isProblem(value: unknown): value is ProblemError {
  return value instanceof ProblemError;
}

/** Field errors keyed by field name, ready for react-hook-form's setError. */
export function fieldErrorsOf(problem: Problem): Record<string, FieldError> {
  return Object.fromEntries(problem.errors.filter((e) => e.field).map((e) => [e.field, e]));
}
