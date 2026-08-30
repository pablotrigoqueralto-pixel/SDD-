/**
 * Quote money math, mirroring the backend exactly (round HALF UP per line, two
 * decimals, totals as sums of the printed line values). Integer arithmetic via
 * BigInt so 3 × 33.33 × 0.9 rounds to 89.99 like `Decimal`, never like floats.
 */

export interface QuoteLineAmounts {
  quantity: string;
  unit_price: string;
  discount_percent: string;
  vat_rate: string;
}

export interface ComputedLine {
  base: string;
  vat: string;
}

export interface VatBucket {
  rate: string;
  base: string;
  vat: string;
}

export interface QuoteTotals {
  lines: ComputedLine[];
  totalBase: string;
  totalVat: string;
  total: string;
  breakdown: VatBucket[];
}

function divideHalfUp(numerator: bigint, divisor: bigint): bigint {
  const quotient = numerator / divisor;
  const remainder = numerator % divisor;
  return remainder * 2n >= divisor ? quotient + 1n : quotient;
}

/** "33.33" | "33,33" | "33" → hundredths as BigInt (3333n); extra decimals round
 * half up, matching the backend's input normalisation. Null when not a number. */
export function toHundredths(raw: string): bigint | null {
  const text = raw.trim().replace(',', '.');
  if (!/^\d+(\.\d+)?$/.test(text)) return null;
  const [whole = '0', decimals = ''] = text.split('.');
  let cents = BigInt(whole) * 100n;
  if (decimals.length <= 2) {
    cents += BigInt((decimals + '00').slice(0, 2));
  } else {
    cents += divideHalfUp(BigInt(decimals), 10n ** BigInt(decimals.length - 2));
  }
  return cents;
}

function centsToString(cents: bigint): string {
  const whole = cents / 100n;
  const rest = (cents % 100n).toString().padStart(2, '0');
  return `${whole.toString()}.${rest}`;
}

function lineCents(line: QuoteLineAmounts): { base: bigint; vat: bigint; rate: bigint } | null {
  const quantity = toHundredths(line.quantity);
  const price = toHundredths(line.unit_price);
  const discount = toHundredths(line.discount_percent) ?? 0n;
  const rate = toHundredths(line.vat_rate) ?? 2100n;
  if (quantity === null || price === null) return null;
  // base = qty × price × (1 − d/100); everything scaled ×100 → divide by 1e6 to land on cents.
  const numerator = quantity * price * (10000n - discount);
  const base = divideHalfUp(numerator, 1_000_000n);
  const vat = divideHalfUp(base * rate, 10_000n);
  return { base, vat, rate };
}

/** Live totals for the form; ignores lines that are not parseable yet. */
export function computeQuoteTotals(lines: QuoteLineAmounts[]): QuoteTotals {
  const computed: ComputedLine[] = [];
  const buckets = new Map<string, { rate: bigint; base: bigint; vat: bigint }>();
  let totalBase = 0n;
  let totalVat = 0n;
  for (const line of lines) {
    const cents = lineCents(line);
    if (cents === null) {
      computed.push({ base: '0.00', vat: '0.00' });
      continue;
    }
    computed.push({ base: centsToString(cents.base), vat: centsToString(cents.vat) });
    totalBase += cents.base;
    totalVat += cents.vat;
    const key = cents.rate.toString();
    const bucket = buckets.get(key) ?? { rate: cents.rate, base: 0n, vat: 0n };
    bucket.base += cents.base;
    bucket.vat += cents.vat;
    buckets.set(key, bucket);
  }
  const breakdown = [...buckets.values()]
    .sort((a, b) => (b.rate > a.rate ? 1 : b.rate < a.rate ? -1 : 0))
    .map((bucket) => ({
      rate: centsToString(bucket.rate),
      base: centsToString(bucket.base),
      vat: centsToString(bucket.vat),
    }));
  return {
    lines: computed,
    totalBase: centsToString(totalBase),
    totalVat: centsToString(totalVat),
    total: centsToString(totalBase + totalVat),
    breakdown,
  };
}
