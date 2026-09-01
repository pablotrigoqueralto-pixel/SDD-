export interface CheckboxOption {
  value: string;
  label: string;
  disabled?: boolean | undefined;
  hint?: string | undefined;
}

interface CheckboxListProps {
  name: string;
  options: CheckboxOption[];
  value: string[];
  onChange: (value: string[]) => void;
  emptyLabel?: string;
  /** Accessible name of the group — needed when a form holds more than one list. */
  label?: string;
}

/** Touch-friendly multi-select as a list of native checkboxes. */
export function CheckboxList({
  name,
  options,
  value,
  onChange,
  emptyLabel,
  label,
}: CheckboxListProps) {
  if (options.length === 0) {
    return emptyLabel ? <p className="text-sm text-muted-foreground">{emptyLabel}</p> : null;
  }
  const toggle = (option: string, checked: boolean) => {
    onChange(checked ? [...value, option] : value.filter((item) => item !== option));
  };
  return (
    <ul className="flex flex-col gap-1" role="group" aria-label={label}>
      {options.map((option) => (
        <li key={option.value}>
          <label
            className={`flex min-h-touch cursor-pointer items-center gap-3 rounded-md px-2 text-sm hover:bg-muted ${option.disabled ? 'cursor-not-allowed opacity-60' : ''}`}
          >
            <input
              type="checkbox"
              name={name}
              value={option.value}
              checked={value.includes(option.value)}
              disabled={option.disabled}
              onChange={(event) => {
                toggle(option.value, event.target.checked);
              }}
              className="size-5 accent-primary"
            />
            <span className="flex-1">{option.label}</span>
            {option.hint ? (
              <span className="text-xs text-muted-foreground">{option.hint}</span>
            ) : null}
          </label>
        </li>
      ))}
    </ul>
  );
}
