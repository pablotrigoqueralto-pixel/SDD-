import { describe, expect, it } from 'vitest';

import { formatPrice, parsePrice, priceToInput, productSchema } from './schemas';

describe('parsePrice', () => {
  it.each([
    ['1.250,50', '1250.50'],
    ['1250.50', '1250.50'],
    ['1250,5', '1250.50'],
    ['1,250.50', '1250.50'],
    ['18', '18.00'],
    ['0', '0.00'],
    ['13.000', '13000.00'],
    ['1.250.000', '1250000.00'],
    [' 12500 ', '12500.00'],
  ])('parses %s as %s', (raw, expected) => {
    expect(parsePrice(raw)).toBe(expected);
  });

  it.each(['', 'abc', '-5', '1.2.3', '10,555'])('rejects %s', (raw) => {
    expect(parsePrice(raw)).toBeNull();
  });
});

describe('formatPrice and priceToInput', () => {
  it('formats in Spanish euros and maps API prices back to the input', () => {
    expect(formatPrice('12500.00').replace(/[\u00a0\u202f]/g, ' ')).toBe('12.500,00 €');
    expect(formatPrice(18.5).replace(/[\u00a0\u202f]/g, ' ')).toBe('18,50 €');
    expect(priceToInput('12500.00')).toBe('12500,00');
    expect(priceToInput(null)).toBe('');
  });
});

describe('productSchema', () => {
  const valid = {
    sku: 'had-1000',
    name: 'Doppler',
    brand_id: 'b',
    family_id: 'f',
    kind: 'equipment',
    list_price: '1.250,50',
    cost_price: '',
    unit: 'ud',
    description: '',
    is_active: true,
  };

  it('accepts a minimal product and reports i18n keys for missing fields', () => {
    expect(productSchema.safeParse(valid).success).toBe(true);

    const result = productSchema.safeParse({
      ...valid,
      sku: ' ',
      kind: '',
      list_price: 'abc',
      cost_price: '-1',
    });
    expect(result.success).toBe(false);
    const messages = result.success ? [] : result.error.issues.map((issue) => issue.message);
    expect(messages).toEqual(
      expect.arrayContaining([
        'catalogue:form.skuRequired',
        'catalogue:form.kindRequired',
        'catalogue:form.priceInvalid',
      ]),
    );
  });
});
