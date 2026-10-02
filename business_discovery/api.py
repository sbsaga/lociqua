"""Minimal standard-library HTTP API; place behind TLS/authentication in deployment."""
from __future__ import annotations

import asyncio
import json
import csv
import io
import os
import logging
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse
from dataclasses import asdict
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from .models import SearchQuery, SearchRequest
from .importers import import_csv, preview_csv
from .orchestrator import SearchOrchestrator
from .providers import LocalDatabaseProvider
from .storage import CompanyStore
from .dashboard import DASHBOARD_HTML
from .observability import Metrics, configure_logging
from .auth import TokenService
from .jobs import SearchJobQueue
from .alerts import AlertWebhook


def make_handler(service: SearchOrchestrator, metrics: Metrics):
    require_auth = os.environ.get("LOCIQUA_REQUIRE_AUTH", "false").lower() == "true"
    token_service = TokenService(os.environ["LOCIQUA_AUTH_SECRET"]) if require_auth else None
    alerts = AlertWebhook()
    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"
        def _reply(self, status: int, body: dict) -> None:
            payload = json.dumps(body, default=str).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers(); self.wfile.write(payload)
            if status >= 500:
                alerts.notify("http_server_error", {"path": urlparse(self.path).path, "status": status})

        def _identity(self) -> dict[str, object] | None:
            if not require_auth: return {"role": "owner"}
            header = self.headers.get("Authorization", "")
            return token_service.verify(header.removeprefix("Bearer ")) if header.startswith("Bearer ") else None

        def _authorized(self, write: bool = False) -> bool:
            identity = self._identity()
            if not identity:
                self._reply(401, {"error": {"code": "UNAUTHENTICATED", "message": "sign in is required", "retryable": False}}); return False
            configured_workspace = getattr(service.store, "workspace_id", None)
            if configured_workspace and identity.get("workspace_id") != configured_workspace:
                self._reply(403, {"error": {"code": "FORBIDDEN", "message": "workspace access is denied", "retryable": False}}); return False
            if write and identity.get("role") not in ("owner", "editor"):
                self._reply(403, {"error": {"code": "FORBIDDEN", "message": "editor or owner role is required", "retryable": False}}); return False
            return True

        def _owner(self) -> dict[str, object] | None:
            identity = self._identity()
            configured_workspace = getattr(service.store, "workspace_id", None)
            if not identity or identity.get("role") != "owner" or (configured_workspace and identity.get("workspace_id") != configured_workspace):
                self._reply(403, {"error": {"code": "FORBIDDEN", "message": "owner role is required", "retryable": False}}); return None
            return identity

        def end_headers(self) -> None:
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("X-Frame-Options", "DENY")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Security-Policy", "default-src 'self'; connect-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; script-src 'self' 'unsafe-inline'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'")
            super().end_headers()

        def do_GET(self) -> None:
            parsed = urlparse(self.path)
            if parsed.path == "/healthz": return self._reply(200, {"status": "ok"})
            if parsed.path == "/readyz":
                try:
                    service.store.sources(); return self._reply(200, {"status": "ready", "storage": "available"})
                except Exception: return self._reply(503, {"status": "not_ready", "storage": "unavailable"})
            if parsed.path == "/metrics":
                payload = metrics.prometheus(); self.send_response(200); self.send_header("Content-Type", "text/plain; version=0.0.4"); self.send_header("Content-Length", str(len(payload))); self.end_headers(); self.wfile.write(payload); return
            if self.path == "/":
                payload = DASHBOARD_HTML.encode()
                self.send_response(200); self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(payload))); self.end_headers(); self.wfile.write(payload); return
            if self.path == "/assets/logo":
                logo = Path(__file__).parent.parent / "assets" / "lociqua-mark.png"
                if logo.is_file():
                    payload = logo.read_bytes(); self.send_response(200); self.send_header("Content-Type", "image/png")
                    self.send_header("Content-Length", str(len(payload))); self.end_headers(); self.wfile.write(payload); return
            if not self._authorized(): return
            if parsed.path.startswith("/api/jobs/"):
                try: job = SearchJobQueue().get(parsed.path.rsplit("/", 1)[-1])
                except Exception: return self._reply(503, {"error": {"code": "QUEUE_UNAVAILABLE", "message": "background queue is unavailable", "retryable": True}})
                return self._reply(200, job) if job else self._reply(404, {"error": {"code": "NOT_FOUND", "message": "job not found", "retryable": False}})
            if parsed.path == "/api/companies/export":
                query = parse_qs(parsed.query)
                companies = service.store.search(query.get("keyword", [""])[0], query.get("location", [None])[0], 10_000)
                try:
                    if hasattr(service.store, "ensure_export_allowed"):
                        service.store.ensure_export_allowed(companies)
                except ValueError as error:
                    return self._reply(403, {"error": {"code": "EXPORT_PROHIBITED", "message": str(error), "retryable": False}})
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
            if parsed.path == "/api/sources":
                return self._reply(200, {"sources": service.store.sources()})
            if parsed.path == "/api/source-policies":
                if not hasattr(service.store, "source_policies"):
                    return self._reply(501, {"error": {"code": "POSTGRES_REQUIRED", "message": "source policies require PostgreSQL", "retryable": False}})
                try:
                    domain = parse_qs(parsed.query).get("domain", [None])[0]
                    return self._reply(200, {"source_policies": service.store.source_policies(domain, approved_capture_only=bool(domain))})
                except ValueError as error:
                    return self._reply(400, {"error": {"code": "INVALID_REQUEST", "message": str(error), "retryable": False}})
            if parsed.path == "/api/evidence":
                if not hasattr(service.store, "evidence_items"):
                    return self._reply(501, {"error": {"code": "POSTGRES_REQUIRED", "message": "evidence review requires PostgreSQL", "retryable": False}})
                try:
                    query = parse_qs(parsed.query)
                    return self._reply(200, {"evidence": service.store.evidence_items(query.get("status", [None])[0], query.get("company_id", [None])[0])})
                except ValueError as error:
                    return self._reply(400, {"error": {"code": "INVALID_REQUEST", "message": str(error), "retryable": False}})
            if parsed.path == "/api/research-sessions":
                if not hasattr(service.store, "research_sessions"):
                    return self._reply(501, {"error": {"code": "POSTGRES_REQUIRED", "message": "research sessions require PostgreSQL", "retryable": False}})
                return self._reply(200, {"research_sessions": service.store.research_sessions()})
            if parsed.path.startswith("/api/research-sessions/"):
                if not hasattr(service.store, "research_session"):
                    return self._reply(501, {"error": {"code": "POSTGRES_REQUIRED", "message": "research sessions require PostgreSQL", "retryable": False}})
                item = service.store.research_session(unquote(parsed.path.rsplit("/", 1)[-1]))
                return self._reply(200, item) if item else self._reply(404, {"error": {"code": "NOT_FOUND", "message": "research session not found", "retryable": False}})
            if parsed.path == "/api/duplicates":
                if not hasattr(service.store, "duplicate_reviews"):
                    return self._reply(501, {"error": {"code": "POSTGRES_REQUIRED", "message": "duplicate review requires PostgreSQL", "retryable": False}})
                try:
                    return self._reply(200, {"reviews": service.store.duplicate_reviews(parse_qs(parsed.query).get("status", ["pending"])[0])})
                except ValueError as error: return self._reply(400, {"error": {"code": "INVALID_REQUEST", "message": str(error), "retryable": False}})
            if parsed.path == "/api/members":
                if not self._owner(): return
                if not hasattr(service.store, "members"): return self._reply(501, {"error": {"code": "POSTGRES_REQUIRED", "message": "member administration requires PostgreSQL", "retryable": False}})
                return self._reply(200, {"members": service.store.members()})
            if parsed.path == "/api/companies":
                if not hasattr(service.store, "companies_with_quality"):
                    return self._reply(501, {"error": {"code": "POSTGRES_REQUIRED", "message": "quality dashboard requires PostgreSQL", "retryable": False}})
                try:
                    query = parse_qs(parsed.query)
                    return self._reply(200, {"companies": service.store.companies_with_quality(query.get("quality", ["all"])[0], int(query.get("limit", ["100"])[0]))})
                except (ValueError, TypeError) as error: return self._reply(400, {"error": {"code": "INVALID_REQUEST", "message": str(error), "retryable": False}})
            if parsed.path.startswith("/api/companies/"):
                detail = service.store.company_detail(unquote(parsed.path.removeprefix("/api/companies/")))
                return self._reply(200, detail) if detail else self._reply(404, {"error": {"code": "NOT_FOUND", "message": "company not found", "retryable": False}})
            if self.path == "/api/providers":
                self._reply(200, {"providers": [{"name": name, "capabilities": asdict(p.capabilities)} for name, p in service.providers.items()]})
            else:
                self._reply(404, {"error": {"code": "NOT_FOUND", "message": "route not found", "retryable": False}})

        def do_POST(self) -> None:
            if self.path == "/api/auth/login":
                if not require_auth: return self._reply(400, {"error": {"code": "AUTH_DISABLED", "message": "authentication is not enabled", "retryable": False}})
                try:
                    raw = json.loads(self.rfile.read(int(self.headers.get("Content-Length", "0"))))
                    identity = service.store.authenticate(raw["email"], raw["password"])
                    if not identity: return self._reply(401, {"error": {"code": "INVALID_CREDENTIALS", "message": "email or password is incorrect", "retryable": False}})
                    return self._reply(200, {"access_token": token_service.issue(identity["user_id"], identity["workspace_id"], identity["role"]), "token_type": "Bearer", "role": identity["role"]})
                except (ValueError, KeyError, json.JSONDecodeError): return self._reply(400, {"error": {"code": "INVALID_REQUEST", "message": "email and password are required", "retryable": False}})
            if not self._authorized(write=True): return
            if self.path == "/api/auth/extension-token":
                # The extension receives a deliberately short session credential, never a stored password.
                if not require_auth or not token_service: return self._reply(400, {"error": {"code": "AUTH_DISABLED", "message": "extension tokens require application authentication", "retryable": False}})
                identity = self._identity()
                return self._reply(201, {"access_token": token_service.issue(str(identity["sub"]), str(identity["workspace_id"]), str(identity["role"]), ttl_seconds=600), "expires_in_seconds": 600})
            if self.path == "/api/jobs/search":
                try:
                    raw = json.loads(self.rfile.read(int(self.headers.get("Content-Length", "0"))))
                    SearchOrchestrator.validate(service, SearchRequest(tuple(SearchQuery(**query) for query in raw["queries"])))
                    return self._reply(202, {"job_id": SearchJobQueue().enqueue(raw), "status": "queued"})
                except (ValueError, KeyError, json.JSONDecodeError) as error:
                    return self._reply(400, {"error": {"code": "INVALID_REQUEST", "message": str(error), "retryable": False}})
            if self.path.startswith("/api/duplicates/"):
                try:
                    raw = json.loads(self.rfile.read(int(self.headers.get("Content-Length", "0"))))
                    if not hasattr(service.store, "review_duplicate"): raise ValueError("duplicate review requires PostgreSQL")
                    identity = self._identity(); changed = service.store.review_duplicate(self.path.rsplit("/", 1)[-1], raw["status"], str(identity.get("sub")))
                    return self._reply(200, {"status": "updated", "review_only": True}) if changed else self._reply(404, {"error": {"code": "NOT_FOUND", "message": "pending review not found", "retryable": False}})
                except (ValueError, KeyError, json.JSONDecodeError) as error:
                    return self._reply(400, {"error": {"code": "INVALID_REQUEST", "message": str(error), "retryable": False}})
            if self.path == "/api/members":
                if not self._owner(): return
                try:
                    raw = json.loads(self.rfile.read(int(self.headers.get("Content-Length", "0"))))
                    if not hasattr(service.store, "add_member"): raise ValueError("member administration requires PostgreSQL")
                    service.store.add_member(raw["email"], raw["password"], raw["role"], str(self._identity().get("sub")))
                    return self._reply(201, {"status": "member_saved"})
                except (ValueError, KeyError, json.JSONDecodeError) as error: return self._reply(400, {"error": {"code": "INVALID_REQUEST", "message": str(error), "retryable": False}})
            if self.path.startswith("/api/members/"):
                if not self._owner(): return
                try:
                    user_id = self.path.rsplit("/", 1)[-1]; raw = json.loads(self.rfile.read(int(self.headers.get("Content-Length", "0"))))
                    if not hasattr(service.store, "set_member_role"): raise ValueError("member administration requires PostgreSQL")
                    actor = str(self._identity().get("sub"))
                    if raw.get("action") == "remove": changed = service.store.remove_member(user_id, actor)
                    else: changed = service.store.set_member_role(user_id, raw["role"], actor)
                    return self._reply(200, {"status": "member_updated"}) if changed else self._reply(404, {"error": {"code":"NOT_FOUND","message":"member not found","retryable":False}})
                except (ValueError, KeyError, json.JSONDecodeError) as error: return self._reply(400, {"error": {"code":"INVALID_REQUEST","message":str(error),"retryable":False}})
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
            if self.path == "/api/sources":
                length = int(self.headers.get("Content-Length", "0"))
                try:
                    raw = json.loads(self.rfile.read(length))
                    service.store.register_source(raw["name"], raw.get("source_type", "user_csv"),
                        raw.get("permission_basis", "user_provided"), raw.get("license_note"))
                    return self._reply(201, {"status": "registered"})
                except (ValueError, KeyError, json.JSONDecodeError) as error:
                    return self._reply(400, {"error": {"code": "INVALID_REQUEST", "message": str(error), "retryable": False}})
            if self.path == "/api/source-policies":
                if not self._owner(): return
                try:
                    raw = json.loads(self.rfile.read(int(self.headers.get("Content-Length", "0"))))
                    if not hasattr(service.store, "save_source_policy"): raise ValueError("source policies require PostgreSQL")
                    saved = service.store.save_source_policy(raw, str(self._identity().get("sub")))
                    return self._reply(201, {"source_policy": saved})
                except (ValueError, KeyError, json.JSONDecodeError) as error:
                    return self._reply(400, {"error": {"code": "INVALID_REQUEST", "message": str(error), "retryable": False}})
            if self.path == "/api/evidence/capture":
                try:
                    raw = json.loads(self.rfile.read(int(self.headers.get("Content-Length", "0"))))
                    if not hasattr(service.store, "capture_evidence"): raise ValueError("evidence capture requires PostgreSQL")
                    evidence = service.store.capture_evidence(raw, str(self._identity().get("sub")))
                    return self._reply(201, {"evidence_id": evidence["id"], "status": evidence["status"], "company_id": evidence["company_id"]})
                except (ValueError, KeyError, json.JSONDecodeError) as error:
                    return self._reply(400, {"error": {"code": "INVALID_REQUEST", "message": str(error), "retryable": False}})
            if self.path.startswith("/api/evidence/"):
                try:
                    raw = json.loads(self.rfile.read(int(self.headers.get("Content-Length", "0"))))
                    if not hasattr(service.store, "review_evidence"): raise ValueError("evidence review requires PostgreSQL")
                    changed = service.store.review_evidence(self.path.rsplit("/", 1)[-1], raw["status"], str(self._identity().get("sub")))
                    return self._reply(200, {"status": "updated"}) if changed else self._reply(404, {"error": {"code": "NOT_FOUND", "message": "pending evidence not found", "retryable": False}})
                except (ValueError, KeyError, json.JSONDecodeError) as error:
                    return self._reply(400, {"error": {"code": "INVALID_REQUEST", "message": str(error), "retryable": False}})
            if self.path == "/api/research-sessions":
                try:
                    raw = json.loads(self.rfile.read(int(self.headers.get("Content-Length", "0"))))
                    if not hasattr(service.store, "create_research_session"): raise ValueError("research sessions require PostgreSQL")
                    session = service.store.create_research_session(raw, str(self._identity().get("sub")))
                    return self._reply(201, {"research_session": session})
                except (ValueError, KeyError, json.JSONDecodeError) as error:
                    return self._reply(400, {"error": {"code": "INVALID_REQUEST", "message": str(error), "retryable": False}})
            if self.path.startswith("/api/research-tasks/"):
                try:
                    raw = json.loads(self.rfile.read(int(self.headers.get("Content-Length", "0"))))
                    if not hasattr(service.store, "update_research_task"): raise ValueError("research tasks require PostgreSQL")
                    changed = service.store.update_research_task(self.path.rsplit("/", 1)[-1], raw["status"], raw.get("notes"), str(self._identity().get("sub")))
                    return self._reply(200, {"status": "updated"}) if changed else self._reply(404, {"error": {"code": "NOT_FOUND", "message": "research task not found", "retryable": False}})
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
        def log_message(self, format: str, *args: object) -> None:
            status = int(args[1]) if len(args) > 1 and str(args[1]).isdigit() else 500
            metrics.record(urlparse(self.path).path, status)
            logging.getLogger("lociqua.http").info("request method=%s path=%s status=%s", self.command, self.path, status)
    return Handler


def build_service() -> SearchOrchestrator:
    database_url = os.environ.get("DATABASE_URL")
    if database_url:
        from .postgres_storage import PostgresCompanyStore
        store = PostgresCompanyStore(database_url)
    else:
        store = CompanyStore(os.environ.get("LOCIQUA_DATABASE_PATH", "business_discovery.db"))
    service = SearchOrchestrator([LocalDatabaseProvider(store)])
    service.store = store  # HTTP import handler shares the service-owned store.
    return service


def serve(host: str = "127.0.0.1", port: int = 8000) -> None:
    configure_logging(); service = build_service()
    logging.getLogger("lociqua").info("service_started host=%s port=%s", host, port)
    ThreadingHTTPServer((host, port), make_handler(service, Metrics())).serve_forever()
