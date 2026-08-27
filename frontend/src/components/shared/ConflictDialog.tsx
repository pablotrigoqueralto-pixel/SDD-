import { useTranslation } from 'react-i18next';

import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { useConflictStore } from '@/store/conflict.store';

export function ConflictDialog() {
  const { t } = useTranslation();
  const { open, onReload, dismiss } = useConflictStore();

  const handleReload = async () => {
    await onReload?.();
    dismiss();
  };

  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        if (!next) dismiss();
      }}
    >
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{t('conflict.title')}</DialogTitle>
          <DialogDescription>{t('conflict.detail')}</DialogDescription>
        </DialogHeader>
        <DialogFooter>
          <Button variant="outline" onClick={dismiss} className="min-h-touch">
            {t('actions.close')}
          </Button>
          <Button onClick={handleReload} className="min-h-touch">
            {t('actions.reload')}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
