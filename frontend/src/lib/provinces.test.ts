import { describe, expect, it } from 'vitest';

import { PROVINCES, provinceName, provincesByCommunity } from './provinces';

describe('provinces', () => {
  it('lists the 52 INE provinces with sequential codes', () => {
    expect(PROVINCES).toHaveLength(52);
    expect(PROVINCES.map((p) => p.code)).toEqual(
      Array.from({ length: 52 }, (_, i) => String(i + 1).padStart(2, '0')),
    );
  });

  it('groups by community alphabetically', () => {
    const groups = provincesByCommunity();
    expect(groups[0]?.community).toBe('Andalucía');
    expect(groups.find((g) => g.community === 'Castilla y León')?.provinces).toHaveLength(9);
    expect(groups.reduce((sum, g) => sum + g.provinces.length, 0)).toBe(52);
  });

  it('resolves names and falls back to the code', () => {
    expect(provinceName('28')).toBe('Madrid');
    expect(provinceName('99')).toBe('99');
  });
});
