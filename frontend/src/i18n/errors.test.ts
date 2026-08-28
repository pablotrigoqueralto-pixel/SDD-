import { describe, expect, it } from 'vitest';

import { ERROR_CODES } from '@/lib/error-codes';
import { NETWORK_PROBLEM_CODE } from '@/lib/problem';

import errors from './es-ES/errors.json';

describe('errors translations', () => {
  it.each([...ERROR_CODES, NETWORK_PROBLEM_CODE])('has a Spanish message for %s', (code) => {
    const message = (errors as Record<string, string>)[code];
    expect(message).toBeTruthy();
  });

  it('contains no CRM jargon', () => {
    const text = Object.values(errors).join(' ').toLowerCase();
    for (const jargon of ['lead', 'mql', 'workflow', 'scoring']) {
      expect(text).not.toContain(jargon);
    }
  });
});
