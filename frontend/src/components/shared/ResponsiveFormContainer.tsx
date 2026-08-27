import type { ReactNode } from 'react';

import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from '@/components/ui/sheet';
import { useIsDesktop } from '@/hooks/useMediaQuery';

interface ResponsiveFormContainerProps {
  open: boolean;
  title: string;
  description?: string;
  onClose: () => void;
  children: ReactNode;
}

/** Forms are written once: bottom sheet on mobile, dialog on desktop. */
export function ResponsiveFormContainer({
  open,
  title,
  description,
  onClose,
  children,
}: ResponsiveFormContainerProps) {
  const isDesktop = useIsDesktop();
  const handleOpenChange = (next: boolean) => {
    if (!next) onClose();
  };

  if (isDesktop) {
    return (
      <Dialog open={open} onOpenChange={handleOpenChange}>
        <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-lg">
          <DialogHeader>
            <DialogTitle>{title}</DialogTitle>
            <DialogDescription>{description ?? ''}</DialogDescription>
          </DialogHeader>
          {children}
        </DialogContent>
      </Dialog>
    );
  }

  return (
    <Sheet open={open} onOpenChange={handleOpenChange}>
      <SheetContent side="bottom" className="max-h-[92dvh] overflow-y-auto rounded-t-xl">
        <SheetHeader className="text-left">
          <SheetTitle>{title}</SheetTitle>
          <SheetDescription>{description ?? ''}</SheetDescription>
        </SheetHeader>
        <div className="pt-4">{children}</div>
      </SheetContent>
    </Sheet>
  );
}
