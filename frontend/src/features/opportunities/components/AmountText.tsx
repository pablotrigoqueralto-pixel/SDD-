import { formatPrice } from '@/features/catalogue';

interface AmountTextProps {
  amount: string | number;
  className?: string;
}

/** "30000.00" → "30.000,00 €" with tabular numbers for column alignment. */
export function AmountText({ amount, className }: AmountTextProps) {
  return <span className={className ?? 'tabular-nums'}>{formatPrice(amount)}</span>;
}
