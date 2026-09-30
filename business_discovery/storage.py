"""Durable local-data store. SQLite is the single-server default; PostgreSQL is a deployment adapter."""
from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from .models import Company, Source
from .normalization import deduplicate, normalize_company


class CompanyStore:
    def __init__(self, database_path: str | Path = "business_discovery.db"):
        self.database_path = str(database_path)
        self.initialize()

    @contextmanager
    def connection(self) -> Iterator[sqlite3.Connection]:
        db = sqlite3.connect(self.database_path)
        db.row_factory = sqlite3.Row
        try:
            yield db
            db.commit()
        finally:
            db.close()

    def initialize(self) -> None:
        with self.connection() as db:
            db.executescript("""
            CREATE TABLE IF NOT EXISTS companies (
              id TEXT PRIMARY KEY, name TEXT NOT NULL, description TEXT, categories TEXT NOT NULL,
              website TEXT, domain TEXT, phone TEXT, email TEXT, address TEXT, locality TEXT, city TEXT,
              state TEXT, country TEXT, postal_code TEXT, latitude REAL, longitude REAL
            );
            CREATE TABLE IF NOT EXISTS company_sources (
              company_id TEXT NOT NULL, provider TEXT NOT NULL, provider_record_id TEXT NOT NULL,
              source_url TEXT, discovered_at TEXT NOT NULL,
              UNIQUE(provider, provider_record_id), FOREIGN KEY(company_id) REFERENCES companies(id)
            );
            CREATE INDEX IF NOT EXISTS idx_companies_name ON companies(name);
            CREATE INDEX IF NOT EXISTS idx_companies_location ON companies(city, locality);
            CREATE INDEX IF NOT EXISTS idx_companies_domain ON companies(domain);
            CREATE INDEX IF NOT EXISTS idx_companies_phone ON companies(phone);
            CREATE TABLE IF NOT EXISTS saved_searches (
              id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL UNIQUE,
              keyword TEXT NOT NULL, location TEXT, max_results INTEGER NOT NULL,
              created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS data_sources (
              id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL UNIQUE,
              source_type TEXT NOT NULL, permission_basis TEXT NOT NULL,
              license_note TEXT, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS company_field_provenance (
              company_id TEXT NOT NULL, field_name TEXT NOT NULL, source_name TEXT NOT NULL,
              observed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
              PRIMARY KEY(company_id, field_name, source_name),
              FOREIGN KEY(company_id) REFERENCES companies(id),
              FOREIGN KEY(source_name) REFERENCES data_sources(name)
            );
            CREATE TABLE IF NOT EXISTS audit_events (
              id INTEGER PRIMARY KEY AUTOINCREMENT, action TEXT NOT NULL, entity_type TEXT NOT NULL,
              entity_id TEXT NOT NULL, details TEXT NOT NULL, occurred_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            """)

    def register_source(self, name: str, source_type: str = "user_csv", permission_basis: str = "user_provided",
                        license_note: str | None = None) -> None:
        if not name.strip() or len(name) > 160:
            raise ValueError("source name must contain 1-160 characters")
        with self.connection() as db:
            db.execute("""INSERT INTO data_sources(name,source_type,permission_basis,license_note) VALUES(?,?,?,?)
                ON CONFLICT(name) DO UPDATE SET source_type=excluded.source_type,
                permission_basis=excluded.permission_basis, license_note=COALESCE(excluded.license_note,data_sources.license_note)""",
                (name.strip(), source_type, permission_basis, license_note))

    def sources(self) -> list[dict[str, object]]:
        with self.connection() as db:
            return [dict(row) for row in db.execute("SELECT * FROM data_sources ORDER BY created_at DESC, id DESC")]

    @staticmethod
    def _quality(company: Company) -> dict[str, object]:
        fields = ("website", "phone", "email", "address", "locality", "city", "country")
        complete = sum(bool(getattr(company, field)) for field in fields)
        validity = 100
        if company.email and "@" not in company.email: validity -= 25
        if company.website and not company.website.startswith(("http://", "https://")): validity -= 25
        score = round((complete / len(fields) * 70) + (validity * .30))
        return {"score": score, "completeness": round(complete / len(fields) * 100), "validity": validity,
                "missing_fields": [field for field in fields if not getattr(company, field)]}

    @staticmethod
    def _audit(db: sqlite3.Connection, action: str, entity_type: str, entity_id: str, details: dict[str, object]) -> None:
        db.execute("INSERT INTO audit_events(action,entity_type,entity_id,details) VALUES(?,?,?,?)",
                   (action, entity_type, entity_id, json.dumps(details, sort_keys=True)))

    def upsert_many(self, companies: list[Company]) -> int:
        saved = 0
        for company in deduplicate(companies):
            company = normalize_company(company)
            with self.connection() as db:
                known = None
                for source in company.sources:
                    known = db.execute("SELECT company_id FROM company_sources WHERE provider=? AND provider_record_id=?",
                        (source.provider, source.provider_record_id)).fetchone()
                    if known: break
                company_id = known["company_id"] if known else company.id
                db.execute("""INSERT INTO companies VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                    ON CONFLICT(id) DO UPDATE SET name=excluded.name, description=COALESCE(excluded.description,companies.description),
                    categories=excluded.categories, website=COALESCE(excluded.website,companies.website), domain=COALESCE(excluded.domain,companies.domain),
                    phone=COALESCE(excluded.phone,companies.phone), email=COALESCE(excluded.email,companies.email),
                    address=COALESCE(excluded.address,companies.address), locality=COALESCE(excluded.locality,companies.locality),
                    city=COALESCE(excluded.city,companies.city), state=COALESCE(excluded.state,companies.state), country=COALESCE(excluded.country,companies.country),
                    postal_code=COALESCE(excluded.postal_code,companies.postal_code), latitude=COALESCE(excluded.latitude,companies.latitude), longitude=COALESCE(excluded.longitude,companies.longitude)""",
                    (company_id, company.name, company.description, json.dumps(company.categories), company.website, company.domain,
                     company.phone, company.email, company.address, company.locality, company.city, company.state,
                     company.country, company.postal_code, company.latitude, company.longitude))
                for source in company.sources:
                    db.execute("""INSERT OR IGNORE INTO data_sources(name,source_type,permission_basis) VALUES(?,?,?)""",
                        (source.provider, "provider" if source.provider != "user_csv" else "user_csv", "configured_or_user_provided"))
                    db.execute("INSERT OR IGNORE INTO company_sources VALUES(?,?,?,?,?)", (company_id, source.provider,
                        source.provider_record_id, source.source_url, source.discovered_at))
                    for field, value in company.as_dict().items():
                        if field != "sources" and value not in (None, "", [], {}):
                            db.execute("INSERT OR IGNORE INTO company_field_provenance(company_id,field_name,source_name) VALUES(?,?,?)",
                                (company_id, field, source.provider))
                self._audit(db, "company_upserted", "company", company_id,
                            {"source_count": len(company.sources), "quality": self._quality(company)["score"]})
            saved += 1
        return saved

    def search(self, keyword: str, location: str | None, limit: int) -> list[Company]:
        terms = f"%{keyword.strip()}%"
        location_term = f"%{location.strip()}%" if location else None
        with self.connection() as db:
            rows = db.execute("""SELECT * FROM companies WHERE (name LIKE ? OR description LIKE ? OR categories LIKE ?)
              AND (? IS NULL OR locality LIKE ? OR city LIKE ? OR address LIKE ?) ORDER BY name LIMIT ?""",
              (terms, terms, terms, location_term, location_term, location_term, location_term, limit)).fetchall()
            output = []
            for row in rows:
                sources = [Source(**dict(source)) for source in db.execute("SELECT provider, provider_record_id, source_url, discovered_at FROM company_sources WHERE company_id=?", (row["id"],))]
                data = dict(row); data["categories"] = json.loads(data["categories"]); data["sources"] = sources
                output.append(Company(**data))
            return output

    def company_detail(self, company_id: str) -> dict[str, object] | None:
        with self.connection() as db:
            row = db.execute("SELECT * FROM companies WHERE id=?", (company_id,)).fetchone()
            if not row: return None
            company = self._company_from_row(db, row)
            provenance = [dict(item) for item in db.execute("SELECT field_name,source_name,observed_at FROM company_field_provenance WHERE company_id=? ORDER BY field_name", (company_id,))]
            events = [dict(item) for item in db.execute("SELECT action,details,occurred_at FROM audit_events WHERE entity_type='company' AND entity_id=? ORDER BY id DESC LIMIT 50", (company_id,))]
            return {"company": company.as_dict(), "quality": self._quality(company), "field_provenance": provenance, "audit_events": events}

    @staticmethod
    def _company_from_row(db: sqlite3.Connection, row: sqlite3.Row) -> Company:
        sources = [Source(**dict(source)) for source in db.execute("SELECT provider, provider_record_id, source_url, discovered_at FROM company_sources WHERE company_id=?", (row["id"],))]
        data = dict(row); data["categories"] = json.loads(data["categories"]); data["sources"] = sources
        return Company(**data)

    def save_search(self, name: str, keyword: str, location: str | None, max_results: int) -> None:
        with self.connection() as db:
            db.execute("""INSERT INTO saved_searches(name,keyword,location,max_results) VALUES(?,?,?,?)
                ON CONFLICT(name) DO UPDATE SET keyword=excluded.keyword, location=excluded.location,
                max_results=excluded.max_results""", (name.strip(), keyword.strip(), location, max_results))

    def saved_searches(self) -> list[dict[str, object]]:
        with self.connection() as db:
            return [dict(row) for row in db.execute("SELECT * FROM saved_searches ORDER BY created_at DESC, id DESC")]
