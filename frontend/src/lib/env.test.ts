import { describe, expect, it } from 'vitest';

import { parseEnv } from './env';

describe('parseEnv', () => {
  it('accepts a base URL and strips trailing slashes', () => {
    expect(parseEnv({ VITE_API_URL: 'http://localhost:8000/' })).toEqual({
      VITE_API_URL: 'http://localhost:8000',
    });
  });

  it('throws when VITE_API_URL is missing', () => {
    expect(() => parseEnv({})).toThrow(/VITE_API_URL/);
  });

  it('throws when VITE_API_URL is not a URL', () => {
    expect(() => parseEnv({ VITE_API_URL: 'localhost' })).toThrow(/Invalid environment/);
  });

  it('rejects a URL that already contains the /api/v1 prefix', () => {
    expect(() => parseEnv({ VITE_API_URL: 'http://localhost:8000/api/v1' })).toThrow(
      /without the \/api\/v1 prefix/,
    );
  });
});
