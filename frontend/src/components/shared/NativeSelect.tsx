import { ChevronDown } from 'lucide-react';
import { forwardRef, type SelectHTMLAttributes } from 'react';

import { cn } from '@/lib/cn';

/** Native <select>: the best mobile picker, keyboard accessible, no Radix pointer requirements. */
export const NativeSelect = forwardRef<HTMLSelectElement, SelectHTMLAttributes<HTMLSelectElement>>(
  ({ className, children, ...props }, ref) => (
    <div className="relative">
      <select
        ref={ref}
        className={cn(
          'min-h-touch w-full appearance-none rounded-md border border-input bg-background px-3 py-2 pr-9 text-base',
          'disabled:cursor-not-allowed disabled:opacity-50',
          className,
        )}
        {...props}
      >
        {children}
      </select>
      <ChevronDown
        className="pointer-events-none absolute right-3 top-1/2 size-4 -translate-y-1/2 opacity-60"
        aria-hidden="true"
      />
    </div>
  ),
);
NativeSelect.displayName = 'NativeSelect';
