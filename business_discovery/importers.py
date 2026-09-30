from __future__ import annotations

import csv
import hashlib
import io
from dataclasses import dataclass

from .models import Company, Source
from .storage import CompanyStore

_FIELDS = {"name", "description", "website", "phone", "email", "address", "locality", "city", "state", "country", "postal_code", "latitude", "longitude"}

@dataclass(frozen=True)
class ImportReport:
    accepted: int
    rejected: int
    errors: list[str]

@dataclass(frozen=True)
class CsvPreview:
    columns: list[str]
    sample_rows: list[dict[str, str]]
    valid: bool
    message: str | None = None

def preview_csv(payload: bytes, sample_size: int = 5) -> CsvPreview:
    """Inspect a bounded CSV before importing; does not persist any customer data."""
    if len(payload) > 25 * 1024 * 1024:
        raise ValueError("CSV exceeds the 25 MB upload limit")
    reader = csv.DictReader(io.StringIO(payload.decode("utf-8-sig")))
    columns = [(field or "").strip() for field in (reader.fieldnames or [])]
    valid = "name" in {column.lower() for column in columns}
    return CsvPreview(columns, [{(key or "").strip(): (value or "") for key, value in row.items()}
        for _, row in zip(range(sample_size), reader)], valid,
        None if valid else "CSV must include a name column")

def import_csv(payload: bytes, store: CompanyStore, source_name: str = "user_csv", max_rows: int = 100_000) -> ImportReport:
    if len(payload) > 25 * 1024 * 1024: raise ValueError("CSV exceeds the 25 MB upload limit")
    text = payload.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames or "name" not in {key.strip().lower() for key in reader.fieldnames}:
        raise ValueError("CSV must include a name column")
    store.register_source(source_name)
    accepted, errors, records = 0, [], []
    for number, raw in enumerate(reader, start=2):
        if number > max_rows + 1: raise ValueError(f"CSV exceeds {max_rows} row limit")
        row = {(key or "").strip().lower(): (value or "").strip() for key, value in raw.items()}
        if not row.get("name"):
            errors.append(f"row {number}: missing name"); continue
        values = {key: row.get(key) or None for key in _FIELDS}
        values["categories"] = [item.strip() for item in row.get("categories", "").split(",") if item.strip()]
        for key in ("latitude", "longitude"):
            if values[key] is not None:
                try: values[key] = float(values[key])
                except ValueError: errors.append(f"row {number}: invalid {key}"); values[key] = None
        digest = hashlib.sha256(f"{source_name}|{number}|{row['name']}|{row.get('website','')}".encode()).hexdigest()[:24]
        records.append(Company(id=f"import:{digest}", sources=[Source(source_name, digest)], **values)); accepted += 1
    store.upsert_many(records)
    return ImportReport(accepted, len(errors), errors[:100])
