import '@testing-library/jest-dom/vitest';
import { cleanup } from '@testing-library/react';
import { afterAll, afterEach, beforeAll } from 'vitest';

import '@/i18n';
import { server } from './msw/server';

beforeAll(() => {
  server.listen({ onUnhandledRequest: 'error' });
});

afterEach(() => {
  server.resetHandlers();
  cleanup();
  window.localStorage.clear();
});

afterAll(() => {
  server.close();
});

// jsdom lacks matchMedia and ResizeObserver, which Radix and our layout hooks use.
Object.defineProperty(window, 'matchMedia', {
  writable: true,
  value: (query: string): MediaQueryList => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: () => {
      /* legacy API, unused */
    },
    removeListener: () => {
      /* legacy API, unused */
    },
    addEventListener: () => {
      /* no-op in tests */
    },
    removeEventListener: () => {
      /* no-op in tests */
    },
    dispatchEvent: () => false,
  }),
});

class ResizeObserverStub {
  observe(): void {
    /* no-op in tests */
  }
  unobserve(): void {
    /* no-op in tests */
  }
  disconnect(): void {
    /* no-op in tests */
  }
}

Object.defineProperty(window, 'ResizeObserver', { writable: true, value: ResizeObserverStub });

Object.defineProperty(Element.prototype, 'scrollIntoView', {
  writable: true,
  value: () => {
    /* no-op in tests */
  },
});
