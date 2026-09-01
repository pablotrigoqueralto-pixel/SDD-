import { useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';

import { NativeSelect } from '@/components/shared/NativeSelect';
import { ResponsiveFormContainer } from '@/components/shared/ResponsiveFormContainer';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { useSessionStore } from '@/features/auth';
import { useCreateOption, useDivisions, type CatalogueKind } from '@/features/reference';
import { toProblem } from '@/lib/problem';

interface CreateOptionDialogProps {
  kind: CatalogueKind;
  /** Called with the id of the entry that was created, reused or reactivated. */
  onCreated: (id: string) => void;
  /** Product families only: the division the new family belongs to. */
  divisionId?: string;
}

/**
 * "+ Añadir" next to a business dropdown, for administrators only.
 *
 * The button sits BESIDE the select rather than being an option inside it: an `<option>`
 * that is not a value is a trap for screen readers and breaks the native select on mobile.
 * The created entry is handed back so the form that opened this dialog can select it and
 * carry on — a missing option must never cost a half-filled form.
 */
export function CreateOptionDialog({ kind, onCreated, divisionId }: CreateOptionDialogProps) {
  const { t } = useTranslation();
  const isAdmin = useSessionStore((state) => state.user?.role === 'admin');
  const createOption = useCreateOption();
  const divisions = useDivisions();
  const triggerRef = useRef<HTMLButtonElement>(null);
  const [open, setOpen] = useState(false);
  const [name, setName] = useState('');
  const [buysViaTender, setBuysViaTender] = useState(false);
  // A family belongs to exactly one division, so the dialog always shows which one it
  // will land in — pre-filled with the division of the family already selected.
  const [division, setDivision] = useState(divisionId ?? '');
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  if (!isAdmin) return null;

  const catalogue = t(`admin:options.catalogues.${kind}`);

  const close = () => {
    setOpen(false);
    setName('');
    setBuysViaTender(false);
    setDivision(divisionId ?? '');
    setError(null);
    // After the dialog's own focus management has run, so the caret lands back on the
    // button that opened it rather than on the page body.
    window.setTimeout(() => triggerRef.current?.focus(), 0);
  };

  const submit = async () => {
    setError(null);
    if (!name.trim()) {
      setError(t('admin:options.nameRequired'));
      return;
    }
    if (kind === 'product_family' && !division) {
      setError(t('admin:options.divisionRequired'));
      return;
    }
    try {
      const created = await createOption.mutateAsync({
        kind,
        name: name.trim(),
        ...(kind === 'account_type' ? { buysViaTender } : {}),
        ...(kind === 'product_family' ? { divisionId: division } : {}),
      });
      // Reuse and reactivation are not failures, but the administrator must know that
      // what they got back is an entry that was already there.
      setNotice(
        created.outcome === 'created'
          ? null
          : t(`admin:options.${created.outcome}`, { name: created.name_es }),
      );
      onCreated(created.id);
      close();
    } catch (caught) {
      setError(toProblem(caught).detail || t('errors.unexpected'));
    }
  };

  return (
    <>
      <Button
        ref={triggerRef}
        type="button"
        variant="outline"
        size="sm"
        className="min-h-touch self-end"
        onClick={() => {
          setNotice(null);
          // Read the division at opening time: the form may have chosen a family since
          // this component mounted.
          setDivision(divisionId ?? '');
          setOpen(true);
        }}
      >
        {t('admin:options.add')}
      </Button>
      {notice ? (
        <p className="text-sm text-muted-foreground" role="status">
          {notice}
        </p>
      ) : null}
      <ResponsiveFormContainer
        open={open}
        title={t('admin:options.addTitle', { catalogue })}
        onClose={close}
      >
        <div className="flex flex-col gap-4">
          <label className="flex flex-col gap-1 text-sm">
            {t('admin:options.name')}
            {/* The dialog moves focus into itself on open; autoFocus would fight it. */}
            <Input
              value={name}
              onChange={(event) => {
                setName(event.target.value);
              }}
            />
          </label>
          {kind === 'product_family' ? (
            <label className="flex flex-col gap-1 text-sm">
              {t('admin:options.division')}
              <NativeSelect
                value={division}
                onChange={(event) => {
                  setDivision(event.target.value);
                }}
              >
                <option value="">{t('admin:options.division')}</option>
                {divisions.data?.map((entry) => (
                  <option key={entry.id} value={entry.id}>
                    {entry.name_es}
                  </option>
                ))}
              </NativeSelect>
            </label>
          ) : null}
          {kind === 'account_type' ? (
            <div className="flex flex-col gap-1">
              {/* The hint is a description, not part of the checkbox's name. */}
              <label className="flex items-center gap-3 text-sm">
                <input
                  type="checkbox"
                  className="size-5 accent-primary"
                  checked={buysViaTender}
                  aria-describedby="buys-via-tender-hint"
                  onChange={(event) => {
                    setBuysViaTender(event.target.checked);
                  }}
                />
                {t('admin:options.buysViaTender')}
              </label>
              <p id="buys-via-tender-hint" className="text-xs text-muted-foreground">
                {t('admin:options.buysViaTenderHint')}
              </p>
            </div>
          ) : null}
          {error ? (
            <p role="alert" className="text-sm font-medium text-destructive">
              {error}
            </p>
          ) : null}
          <Button
            type="button"
            size="lg"
            className="min-h-touch"
            disabled={createOption.isPending}
            onClick={() => void submit()}
          >
            {createOption.isPending ? t('states.saving') : t('actions.save')}
          </Button>
        </div>
      </ResponsiveFormContainer>
    </>
  );
}
