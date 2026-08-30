"""Import API schemas: the per-row report both importers return."""

from pydantic import BaseModel

from app.application.imports.report import ImportReport, RowOutcome


class ImportRowRead(BaseModel):
    row: int
    outcome: RowOutcome
    label: str
    message: str | None


class ImportReportRead(BaseModel):
    dry_run: bool
    created: int
    updated: int
    unchanged: int
    errors: int
    rows: list[ImportRowRead]

    @classmethod
    def build(cls, report: ImportReport, *, dry_run: bool) -> "ImportReportRead":
        return cls(
            dry_run=dry_run,
            created=report.created,
            updated=report.updated,
            unchanged=report.unchanged,
            errors=report.errors,
            rows=[
                ImportRowRead(
                    row=row.row, outcome=row.outcome, label=row.label, message=row.message
                )
                for row in report.rows
            ],
        )
