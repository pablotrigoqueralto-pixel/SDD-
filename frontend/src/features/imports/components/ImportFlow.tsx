import { Download, Upload } from 'lucide-react';
import { useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';

import { PageHeader } from '@/components/shared/PageHeader';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { isKnownErrorCode } from '@/lib/error-codes';
import { toProblem } from '@/lib/problem';

import type { ImportReportRead, ImportRowRead, ImportTarget } from '../api';
import { errorReportCsv } from '../api';
import { useRunImport } from '../queries';

const OUTCOME_VARIANTS: Record<
  ImportRowRead['outcome'],
  'default' | 'secondary' | 'outline' | 'destructive'
> = {
  created: 'default',
  updated: 'secondary',
  unchanged: 'outline',
  error: 'destructive',
};

function sortedRows(report: ImportReportRead): ImportRowRead[] {
  return [...report.rows].sort((a, b) => {
    if (a.outcome === 'error' && b.outcome !== 'error') return -1;
    if (b.outcome === 'error' && a.outcome !== 'error') return 1;
    return a.row - b.row;
  });
}

function RowTable({ report }: { report: ImportReportRead }) {
  const { t } = useTranslation();
  return (
    <div
      role="region"
      aria-label={t('imports:preview.title')}
      // eslint-disable-next-line jsx-a11y/no-noninteractive-tabindex -- axe requires scrollable regions to be keyboard reachable
      tabIndex={0}
      className="max-h-96 overflow-auto rounded-lg border"
    >
      <table className="w-full min-w-[480px] text-sm">
        <thead className="sticky top-0 bg-background">
          <tr className="border-b text-left text-muted-foreground">
            <th className="p-2 font-medium">{t('imports:preview.row')}</th>
            <th className="p-2 font-medium">{t('imports:preview.record')}</th>
            <th className="p-2 font-medium">{t('imports:preview.outcome')}</th>
            <th className="p-2 font-medium">{t('imports:preview.message')}</th>
          </tr>
        </thead>
        <tbody>
          {sortedRows(report).map((row) => (
            <tr key={row.row} className="border-b last:border-0">
              <td className="p-2 tabular-nums">{row.row}</td>
              <td className="p-2">{row.label}</td>
              <td className="p-2">
                <Badge variant={OUTCOME_VARIANTS[row.outcome]}>
                  {t(`imports:outcomes.${row.outcome}`)}
                </Badge>
              </td>
              <td className="p-2 text-muted-foreground">{row.message ?? ''}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function Totals({ report, applied }: { report: ImportReportRead; applied: boolean }) {
  const { t } = useTranslation();
  const entries = [
    [applied ? 'imports:result.created' : 'imports:preview.willCreate', report.created],
    [applied ? 'imports:result.updated' : 'imports:preview.willUpdate', report.updated],
    [applied ? 'imports:result.unchanged' : 'imports:preview.unchanged', report.unchanged],
    [applied ? 'imports:result.errors' : 'imports:preview.errors', report.errors],
  ] as const;
  return (
    <dl className="flex flex-wrap gap-x-6 gap-y-1 text-sm">
      {entries.map(([key, value]) => (
        <div key={key} className="flex gap-1">
          <dt className="text-muted-foreground">
            {t(key, { count: typeof value === 'number' ? value : 0 })}
            {applied ? '' : ':'}
          </dt>
          {applied ? null : <dd className="font-medium tabular-nums">{value}</dd>}
        </div>
      ))}
    </dl>
  );
}

interface ImportFlowProps {
  target: ImportTarget;
  title: string;
  columnsHelp: string;
}

/** Pick a file → automatic dry-run preview → confirm → summary + error report. */
export function ImportFlow({ target, title, columnsHelp }: ImportFlowProps) {
  const { t } = useTranslation();
  const runImport = useRunImport(target);
  const fileInput = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<ImportReportRead | null>(null);
  const [applied, setApplied] = useState<ImportReportRead | null>(null);
  const [error, setError] = useState<string | null>(null);

  const analyse = async (picked: File) => {
    setError(null);
    setApplied(null);
    setPreview(null);
    setFile(picked);
    try {
      setPreview(await runImport.mutateAsync({ file: picked, dryRun: true }));
    } catch (problemError) {
      const problem = toProblem(problemError);
      setError(
        isKnownErrorCode(problem.code)
          ? `errors:${problem.code}`
          : problem.detail || 'toasts.genericError',
      );
    }
  };

  const confirm = async () => {
    if (!file) return;
    setError(null);
    try {
      setApplied(await runImport.mutateAsync({ file, dryRun: false }));
      setPreview(null);
    } catch (problemError) {
      const problem = toProblem(problemError);
      setError(
        isKnownErrorCode(problem.code)
          ? `errors:${problem.code}`
          : problem.detail || 'toasts.genericError',
      );
    }
  };

  const downloadErrors = (report: ImportReportRead) => {
    const blob = new Blob([errorReportCsv(report)], { type: 'text/csv;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement('a');
    anchor.href = url;
    anchor.download = 'errores-importacion.csv';
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
    URL.revokeObjectURL(url);
  };

  const reset = () => {
    setFile(null);
    setPreview(null);
    setApplied(null);
    setError(null);
    if (fileInput.current) fileInput.current.value = '';
  };

  const pendingCount = preview ? preview.created + preview.updated : 0;

  return (
    <>
      <PageHeader title={title} />
      <section className="flex flex-col gap-4 py-4">
        <p className="text-sm text-muted-foreground">{columnsHelp}</p>
        <label className="flex flex-col gap-2 text-sm font-medium">
          {t('imports:picker.label')}
          <input
            ref={fileInput}
            type="file"
            accept=".csv,.xlsx"
            className="min-h-touch rounded-md border border-input bg-background px-3 py-2"
            onChange={(event) => {
              const picked = event.target.files?.[0];
              if (picked) void analyse(picked);
            }}
          />
        </label>
        {error ? (
          <p role="alert" className="text-sm font-medium text-destructive">
            {error.startsWith('errors:') || error.startsWith('toasts.') ? t(error) : error}
          </p>
        ) : null}
        {runImport.isPending ? <Skeleton className="h-10 w-full" /> : null}
        {preview ? (
          <div className="flex flex-col gap-3">
            <h2 className="text-base font-semibold">{t('imports:preview.title')}</h2>
            <Totals report={preview} applied={false} />
            <RowTable report={preview} />
            {pendingCount > 0 ? (
              <Button
                className="min-h-touch self-start"
                disabled={runImport.isPending}
                onClick={() => void confirm()}
              >
                <Upload className="size-4" aria-hidden="true" />
                {t('imports:preview.confirm', { count: pendingCount })}
              </Button>
            ) : (
              <p className="text-sm text-muted-foreground">
                {t('imports:preview.nothingToImport')}
              </p>
            )}
          </div>
        ) : null}
        {applied ? (
          <div className="flex flex-col gap-3">
            <h2 className="text-base font-semibold">{t('imports:result.title')}</h2>
            <Totals report={applied} applied />
            <RowTable report={applied} />
            <div className="flex flex-wrap gap-2">
              {applied.errors > 0 ? (
                <Button
                  variant="outline"
                  className="min-h-touch"
                  onClick={() => {
                    downloadErrors(applied);
                  }}
                >
                  <Download className="size-4" aria-hidden="true" />
                  {t('imports:result.downloadErrors')}
                </Button>
              ) : null}
              <Button variant="outline" className="min-h-touch" onClick={reset}>
                {t('imports:result.again')}
              </Button>
            </div>
          </div>
        ) : null}
      </section>
    </>
  );
}
