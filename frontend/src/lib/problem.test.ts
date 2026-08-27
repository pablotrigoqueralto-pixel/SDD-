import { AxiosError, AxiosHeaders } from 'axios';
import { describe, expect, it } from 'vitest';

import { fieldErrorsOf, problemFromBody, toProblem } from './problem';

const validationBody = {
  type: 'https://crm.quermed.com/problems/validation-error',
  title: 'Validation error',
  status: 422,
  detail: 'One or more fields are invalid.',
  code: 'validation_error',
  trace_id: 'abc',
  errors: [{ field: 'email', message: 'Invalid email address', code: 'invalid_email' }],
};

function axiosErrorWith(status: number, data: unknown): AxiosError {
  return new AxiosError('Request failed', 'ERR_BAD_REQUEST', undefined, undefined, {
    status,
    statusText: '',
    headers: {},
    config: { headers: new AxiosHeaders() },
    data,
  });
}

describe('problemFromBody', () => {
  it('maps a problem+json body including field errors and trace id', () => {
    const problem = problemFromBody(422, validationBody);

    expect(problem.code).toBe('validation_error');
    expect(problem.traceId).toBe('abc');
    expect(problem.errors).toEqual(validationBody.errors);
  });

  it('falls back to internal_error for non-problem bodies', () => {
    const problem = problemFromBody(502, '<html>bad gateway</html>');

    expect(problem.code).toBe('internal_error');
    expect(problem.status).toBe(502);
    expect(problem.errors).toEqual([]);
  });
});

describe('toProblem', () => {
  it('extracts the problem from an axios response error', () => {
    const problem = toProblem(axiosErrorWith(409, { code: 'conflict', status: 409 }));

    expect(problem.status).toBe(409);
    expect(problem.code).toBe('conflict');
  });

  it('reports a network error when there is no response', () => {
    const problem = toProblem(new AxiosError('Network Error', 'ERR_NETWORK'));

    expect(problem.code).toBe('network_error');
    expect(problem.status).toBe(0);
  });

  it('wraps unknown errors', () => {
    expect(toProblem(new Error('boom')).detail).toBe('boom');
    expect(toProblem('weird').code).toBe('internal_error');
  });

  it('returns an existing problem untouched', () => {
    const problem = problemFromBody(404, { code: 'not_found' });

    expect(toProblem(problem)).toBe(problem);
  });
});

describe('fieldErrorsOf', () => {
  it('indexes field errors by field name and drops form-level ones', () => {
    const problem = problemFromBody(422, {
      ...validationBody,
      errors: [...validationBody.errors, { field: '', message: 'x', code: 'y' }],
    });

    expect(Object.keys(fieldErrorsOf(problem))).toEqual(['email']);
  });
});
