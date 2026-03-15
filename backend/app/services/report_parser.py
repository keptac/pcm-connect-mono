import json
from pathlib import Path
import pandas as pd
from sqlalchemy.orm import Session
from ..models import UploadedReport, ParsedReportRow


class ReportParseResult:
    def __init__(self, total_rows: int, invalid_rows: int, errors: list[str]):
        self.total_rows = total_rows
        self.invalid_rows = invalid_rows
        self.errors = errors


def _normalize_columns(columns: list[str]) -> list[str]:
    return [c.strip().lower().replace(" ", "_") for c in columns]


def parse_report(db: Session, report: UploadedReport, template_columns: list[str]) -> ReportParseResult:
    path = Path(report.stored_path)
    if not path.exists():
        return ReportParseResult(0, 0, ["File not found"])

    if path.suffix.lower() == ".xlsx":
        df = pd.read_excel(path)
    else:
        df = pd.read_csv(path)

    df.columns = _normalize_columns(df.columns.tolist())
    required = _normalize_columns(template_columns)

    missing = [col for col in required if col not in df.columns]
    if missing:
        return ReportParseResult(0, 0, [f"Missing columns: {', '.join(missing)}"])

    invalid_rows = 0
    for idx, row in df.iterrows():
        data = row.to_dict()
        errors = []
        for col in required:
            if pd.isna(data.get(col)):
                errors.append(f"Missing {col}")
        is_valid = len(errors) == 0
        if not is_valid:
            invalid_rows += 1
        parsed = ParsedReportRow(
            uploaded_report_id=report.id,
            row_index=int(idx),
            data_json=json.dumps(data, default=str),
            is_valid=str(is_valid).lower(),
            validation_errors_json=json.dumps(errors) if errors else None,
        )
        db.add(parsed)
    db.commit()
    return ReportParseResult(len(df), invalid_rows, [])
