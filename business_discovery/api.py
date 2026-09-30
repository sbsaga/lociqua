"""Minimal standard-library HTTP API; place behind TLS/authentication in deployment."""
from __future__ import annotations

import asyncio
import json
import csv
import io
import os
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from dataclasses import asdict
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from .models import SearchQuery, SearchRequest
from .importers import import_csv, preview_csv
from .orchestrator import SearchOrchestrator
from .providers import LocalDatabaseProvider
from .storage import CompanyStore
from .dashboard import DASHBOARD_HTML


def make_handler(service: SearchOrchestrator):
    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"
        def _reply(self, status: int, body: dict) -> None:
            payload = json.dumps(body).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers(); self.wfile.write(payload)

        def do_GET(self) -> None:
            parsed = urlparse(self.path)
            if self.path == "/":
                payload = DASHBOARD_HTML.encode()
                self.send_response(200); self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(payload))); self.end_headers(); self.wfile.write(payload); return
            if self.path == "/assets/logo":
                logo = Path(__file__).parent.parent / "assets" / "lociqua-mark.png"
                if logo.is_file():
                    payload = logo.read_bytes(); self.send_response(200); self.send_header("Content-Type", "image/png")
                    self.send_header("Content-Length", str(len(payload))); self.end_headers(); self.wfile.write(payload); return
            if parsed.path == "/api/companies/export":
                query = parse_qs(parsed.query)
                companies = service.store.search(query.get("keyword", [""])[0], query.get("location", [None])[0], 10_000)
                output = io.StringIO(); writer = csv.writer(output)
                writer.writerow(["name", "categories", "website", "phone", "email", "address", "locality", "city", "country", "sources"])
                for company in companies:
                    writer.writerow([company.name, "; ".join(company.categories), company.website or "", company.phone or "", company.email or "",
                        company.address or "", company.locality or "", company.city or "", company.country or "",
                        "; ".join(f"{source.provider}:{source.provider_record_id}" for source in company.sources)])
                payload = output.getvalue().encode("utf-8-sig")
                self.send_response(200); self.send_header("Content-Type", "text/csv; charset=utf-8")
                self.send_header("Content-Disposition", "attachment; filename=lociqua-export.csv")
                self.send_header("Content-Length", str(len(payload))); self.end_headers(); self.wfile.write(payload); return
            if parsed.path == "/api/saved-searches":
                return self._reply(200, {"saved_searches": service.store.saved_searches()})
            if self.path == "/api/providers":
                self._reply(200, {"providers": [{"name": name, "capabilities": asdict(p.capabilities)} for name, p in service.providers.items()]})
            else:
                self._reply(404, {"error": {"code": "NOT_FOUND", "message": "route not found", "retryable": False}})

        def do_POST(self) -> None:
            if self.path == "/api/import/csv/preview":
                length = int(self.headers.get("Content-Length", "0"))
                if length < 1 or length > 25 * 1024 * 1024:
                    return self._reply(413, {"error": {"code": "PAYLOAD_TOO_LARGE", "message": "CSV must be 1-25 MB", "retryable": False}})
                try:
                    preview = preview_csv(self.rfile.read(length))
                    return self._reply(200, {"columns": preview.columns, "sample_rows": preview.sample_rows,
                        "valid": preview.valid, "message": preview.message})
                except (ValueError, UnicodeDecodeError) as error:
                    return self._reply(400, {"error": {"code": "INVALID_CSV", "message": str(error), "retryable": False}})
            if self.path == "/api/saved-searches":
                length = int(self.headers.get("Content-Length", "0"))
                try:
                    raw = json.loads(self.rfile.read(length))
                    name, keyword = raw["name"].strip(), raw["keyword"].strip()
                    if not name or not keyword: raise ValueError("name and keyword are required")
                    service.store.save_search(name, keyword, raw.get("location"), int(raw.get("max_results", 25)))
                    return self._reply(201, {"status": "saved"})
                except (ValueError, KeyError, json.JSONDecodeError) as error:
                    return self._reply(400, {"error": {"code": "INVALID_REQUEST", "message": str(error), "retryable": False}})
            if self.path == "/api/import/csv":
                length = int(self.headers.get("Content-Length", "0"))
                if length < 1 or length > 25 * 1024 * 1024:
                    return self._reply(413, {"error": {"code": "PAYLOAD_TOO_LARGE", "message": "CSV must be 1–25 MB", "retryable": False}})
                try:
                    report = import_csv(self.rfile.read(length), service.store, self.headers.get("X-Source-Name", "user_csv"))
                    return self._reply(201, {"accepted": report.accepted, "rejected": report.rejected, "errors": report.errors})
                except (ValueError, UnicodeDecodeError) as error:
                    return self._reply(400, {"error": {"code": "INVALID_CSV", "message": str(error), "retryable": False}})
            if self.path != "/api/search":
                return self._reply(404, {"error": {"code": "NOT_FOUND", "message": "route not found", "retryable": False}})
            length = int(self.headers.get("Content-Length", "0"))
            if length < 1 or length > 1_000_000:
                return self._reply(413, {"error": {"code": "PAYLOAD_TOO_LARGE", "message": "invalid request size", "retryable": False}})
            try:
                raw = json.loads(self.rfile.read(length))
                queries = tuple(SearchQuery(keyword=q["keyword"], location=q.get("location"), latitude=q.get("latitude"),
                    longitude=q.get("longitude"), radius_m=q.get("radius_m"), max_results=q.get("max_results", 25),
                    provider_preference=tuple(q.get("provider_preference", ()))) for q in raw["queries"])
                self._reply(200, asyncio.run(service.search(SearchRequest(queries, enrichment=bool(raw.get("enrichment"))))))
            except (ValueError, KeyError, json.JSONDecodeError) as error:
                self._reply(400, {"error": {"code": "INVALID_REQUEST", "message": str(error), "retryable": False}})
        def log_message(self, *_: object) -> None: pass
    return Handler


def serve(host: str = "127.0.0.1", port: int = 8000) -> None:
    store = CompanyStore(os.environ.get("LOCIQUA_DATABASE_PATH", "business_discovery.db"))
    service = SearchOrchestrator([LocalDatabaseProvider(store)])
    service.store = store  # HTTP import handler shares the service-owned store.
    ThreadingHTTPServer((host, port), make_handler(service)).serve_forever()
