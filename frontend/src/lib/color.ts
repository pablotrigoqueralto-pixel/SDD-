/** WCAG contrast helpers for the design-token test (no runtime usage). */

export interface Hsl {
  h: number;
  s: number;
  l: number;
}

/** Parse the `H S% L%` token format used in globals.css. */
export function parseHslToken(token: string): Hsl {
  const match = /^\s*([\d.]+)\s+([\d.]+)%\s+([\d.]+)%\s*$/.exec(token);
  if (!match) {
    throw new Error(`Not an HSL token: "${token}"`);
  }
  return { h: Number(match[1]), s: Number(match[2]) / 100, l: Number(match[3]) / 100 };
}

export function hslToRgb({ h, s, l }: Hsl): [number, number, number] {
  const c = (1 - Math.abs(2 * l - 1)) * s;
  const x = c * (1 - Math.abs(((h / 60) % 2) - 1));
  const m = l - c / 2;
  const sector = Math.floor(h / 60) % 6;
  const table: [number, number, number][] = [
    [c, x, 0],
    [x, c, 0],
    [0, c, x],
    [0, x, c],
    [x, 0, c],
    [c, 0, x],
  ];
  const [r, g, b] = table[sector] ?? [0, 0, 0];
  return [r + m, g + m, b + m];
}

function channelLuminance(channel: number): number {
  return channel <= 0.03928 ? channel / 12.92 : ((channel + 0.055) / 1.055) ** 2.4;
}

export function relativeLuminance(hsl: Hsl): number {
  const [r, g, b] = hslToRgb(hsl);
  return 0.2126 * channelLuminance(r) + 0.7152 * channelLuminance(g) + 0.0722 * channelLuminance(b);
}

export function contrastRatio(a: Hsl, b: Hsl): number {
  const la = relativeLuminance(a);
  const lb = relativeLuminance(b);
  const [light, dark] = la >= lb ? [la, lb] : [lb, la];
  return (light + 0.05) / (dark + 0.05);
}

/** Extract `--name: value` declarations from a CSS `:root` block. */
export function parseCssTokens(css: string): Record<string, string> {
  const tokens: Record<string, string> = {};
  for (const match of css.matchAll(/--([a-z0-9-]+):\s*([^;]+);/g)) {
    tokens[match[1] ?? ''] = (match[2] ?? '').trim();
  }
  return tokens;
}
