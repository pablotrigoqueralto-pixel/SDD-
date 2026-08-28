import { ChevronDown } from 'lucide-react';
import { useId, useState, type ReactNode } from 'react';

import { cn } from '@/lib/cn';

const STORAGE_KEY = 'account-sections';

function readState(): Record<string, boolean> {
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    return raw ? (JSON.parse(raw) as Record<string, boolean>) : {};
  } catch {
    return {};
  }
}

function writeState(key: string, open: boolean): void {
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify({ ...readState(), [key]: open }));
  } catch {
    /* storage unavailable: the section simply does not persist */
  }
}

interface AccountSectionProps {
  sectionKey: string;
  title: string;
  count?: number | undefined;
  defaultOpen?: boolean;
  action?: ReactNode;
  children: ReactNode;
}

/** Collapsible block of the 360º page; the open/closed state is remembered per section. */
export function AccountSection({
  sectionKey,
  title,
  count,
  defaultOpen = true,
  action,
  children,
}: AccountSectionProps) {
  const contentId = useId();
  const [open, setOpen] = useState<boolean>(() => readState()[sectionKey] ?? defaultOpen);
  const toggle = () => {
    setOpen((current) => {
      writeState(sectionKey, !current);
      return !current;
    });
  };
  return (
    <section className="rounded-lg border bg-card" aria-labelledby={`${contentId}-title`}>
      <div className="flex items-center gap-2 pr-2">
        <button
          type="button"
          className="flex min-h-touch flex-1 items-center gap-2 px-3 text-left font-semibold"
          aria-expanded={open}
          aria-controls={contentId}
          onClick={toggle}
        >
          <ChevronDown
            className={cn('size-4 shrink-0 transition-transform', !open && '-rotate-90')}
            aria-hidden="true"
          />
          <span id={`${contentId}-title`}>
            {title}
            {count !== undefined ? ` (${count})` : ''}
          </span>
        </button>
        {action}
      </div>
      <div id={contentId} className="px-3 pb-3" hidden={!open}>
        {children}
      </div>
    </section>
  );
}
