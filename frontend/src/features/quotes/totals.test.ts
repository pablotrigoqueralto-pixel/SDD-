import { describe, expect, it } from 'vitest';

import vectors from './__fixtures__/quote-totals-vectors.json';
import { computeQuoteTotals, toHundredths } from './totals';

interface VectorLine {
  quantity: string;
  unit_price: string;
  discount_percent: string;
  vat_rate: string;
}

interface VectorCase {
  name: string;
  lines: VectorLine[];
  line_bases: string[];
  line_vats: string[];
  total_base: string;
  total_vat: string;
  total: string;
}

// Mirror of backend/tests/fixtures/quote_totals_vectors.json — both suites must
// assert identical values; update the two copies together.
describe('computeQuoteTotals matches the backend vectors exactly', () => {
  for (const vector of (vectors as { cases: VectorCase[] }).cases) {
    it(vector.name, () => {
      const totals = computeQuoteTotals(vector.lines);

      expect(totals.lines.map((line) => line.base)).toEqual(vector.line_bases);
      expect(totals.lines.map((line) => line.vat)).toEqual(vector.line_vats);
      expect(totals.totalBase).toBe(vector.total_base);
      expect(totals.totalVat).toBe(vector.total_vat);
      expect(totals.total).toBe(vector.total);
    });
  }
});

describe('toHundredths', () => {
  it('accepts Spanish decimal commas and rounds extra decimals half up', () => {
    expect(toHundredths('33,33')).toBe(3333n);
    expect(toHundredths('2.675')).toBe(268n);
    expect(toHundredths('1.999')).toBe(200n);
    expect(toHundredths('abc')).toBeNull();
  });
});
