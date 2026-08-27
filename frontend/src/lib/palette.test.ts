import { readFileSync } from 'node:fs';
import path from 'node:path';

import { describe, expect, it } from 'vitest';

import { contrastRatio, parseCssTokens, parseHslToken } from './color';

const css = readFileSync(path.resolve(__dirname, '../styles/globals.css'), 'utf8');
const tokens = parseCssTokens(css);

function ratio(foreground: string, background: string): number {
  const fg = tokens[foreground];
  const bg = tokens[background];
  if (!fg || !bg) {
    throw new Error(`Missing token: ${foreground} / ${background}`);
  }
  return contrastRatio(parseHslToken(fg), parseHslToken(bg));
}

const TEXT_PAIRS: [string, string][] = [
  ['foreground', 'background'],
  ['primary-foreground', 'primary'],
  ['secondary-foreground', 'secondary'],
  ['muted-foreground', 'background'],
  ['muted-foreground', 'muted'],
  ['accent-foreground', 'accent'],
  ['destructive-foreground', 'destructive'],
  ['success-foreground', 'success'],
  ['warning-foreground', 'warning'],
  ['card-foreground', 'card'],
  ['popover-foreground', 'popover'],
];

const UI_PAIRS: [string, string][] = [
  ['primary', 'background'],
  ['destructive', 'background'],
  ['ring', 'background'],
  ['success', 'background'],
  ['warning', 'background'],
];

describe('design tokens', () => {
  it.each(TEXT_PAIRS)('text pair %s on %s reaches 4.5:1', (fg, bg) => {
    expect(ratio(fg, bg)).toBeGreaterThanOrEqual(4.5);
  });

  it.each(UI_PAIRS)('UI colour %s on %s reaches 3:1', (fg, bg) => {
    expect(ratio(fg, bg)).toBeGreaterThanOrEqual(3);
  });

  it('border is visible against the background', () => {
    expect(ratio('border', 'background')).toBeGreaterThanOrEqual(1.3);
  });
});
