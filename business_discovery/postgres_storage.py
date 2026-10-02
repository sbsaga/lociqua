"""PostgreSQL/PostGIS persistence adapter used when DATABASE_URL is configured."""
from __future__ import annotations

import json
import os
from uuid import UUID, uuid4

import psycopg
from psycopg.rows import dict_row

from .models import Company, Source
from .normalization import deduplicate, normalize_company
from .storage import CompanyStore
from .auth import hash_password, verify_password
from .duplicates import find_candidates
from .evidence import (CAPTURE_FIELDS, CONNECTOR_TYPES, EVIDENCE_STATUSES, POLICY_STATUSES,
                       TASK_STATUSES, canonical_domain, capture_url, content_fingerprint,
                       domain_matches, validate_fields)

DEFAULT_WORKSPACE = "00000000-0000-0000-0000-000000000001"


class PostgresCompanyStore(CompanyStore):
    """Same public operations as CompanyStore, isolated to one configured workspace."""
    def __init__(self, database_url: str, workspace_id: str | None = None):
        self.database_url = database_url
        self.workspace_id = workspace_id or os.environ.get("LOCIQUA_WORKSPACE_ID", DEFAULT_WORKSPACE)
        UUID(self.workspace_id)
        self.initialize()

    def connection(self):
        return psycopg.connect(self.database_url, row_factory=dict_row)

    def initialize(self) -> None:
        with self.connection() as db, db.cursor() as cur:
            cur.execute("SELECT 1 FROM workspaces WHERE id=%s", (self.workspace_id,))
            if not cur.fetchone():
                raise RuntimeError("configured LOCIQUA_WORKSPACE_ID does not exist; apply migrations and provision the workspace")
            email, password = os.environ.get("LOCIQUA_BOOTSTRAP_EMAIL"), os.environ.get("LOCIQUA_BOOTSTRAP_PASSWORD")
            if email and password:
                cur.execute("SELECT id FROM users WHERE email=%s", (email.lower(),))
                user = cur.fetchone()
                if not user:
                    user_id = str(uuid4())
                    cur.execute("INSERT INTO users(id,email,password_hash) VALUES(%s,%s,%s)", (user_id, email.lower(), hash_password(password)))
                    cur.execute("INSERT INTO workspace_memberships(workspace_id,user_id,role) VALUES(%s,%s,'owner')", (self.workspace_id, user_id))

    def register_source(self, name: str, source_type: str = "user_csv", permission_basis: str = "user_provided", license_note: str | None = None) -> None:
        if not name.strip() or len(name) > 160: raise ValueError("source name must contain 1-160 characters")
        with self.connection() as db, db.cursor() as cur:
            cur.execute("""INSERT INTO data_sources(id,workspace_id,name,source_type,permission_basis,license_note)
                VALUES(gen_random_uuid(),%s,%s,%s,%s,%s)
                ON CONFLICT(workspace_id,name) DO UPDATE SET source_type=EXCLUDED.source_type, permission_basis=EXCLUDED.permission_basis, license_note=COALESCE(EXCLUDED.license_note,data_sources.license_note)""", (self.workspace_id, name.strip(), source_type, permission_basis, license_note))

    def sources(self) -> list[dict[str, object]]:
        with self.connection() as db, db.cursor() as cur:
            cur.execute("SELECT id::text,name,source_type,permission_basis,license_note,created_at FROM data_sources WHERE workspace_id=%s ORDER BY created_at DESC", (self.workspace_id,))
            return list(cur.fetchall())

    def source_policies(self, domain: str | None = None, approved_capture_only: bool = False) -> list[dict[str, object]]:
        """Return only workspace-scoped policies; browser capture is default-deny."""
        normalized = canonical_domain(domain) if domain else None
        with self.connection() as db, db.cursor() as cur:
            sql = """SELECT id::text,name,domain,connector_type,permission_basis,license_note,attribution_text,
                       attribution_required,export_allowed,retention_days,allowed_fields,rate_limit_per_minute,status,
                       created_at,updated_at FROM source_policies WHERE workspace_id=%s"""
            params: list[object] = [self.workspace_id]
            if approved_capture_only:
                sql += " AND connector_type='browser_capture' AND status='approved'"
            if normalized:
                # A policy can approve its host and any of its subdomains, but never a sibling domain.
                sql += " AND (%s=domain OR %s LIKE ('%%.' || domain))"; params.extend([normalized, normalized])
            sql += " ORDER BY name"
            cur.execute(sql, params)
            return list(cur.fetchall())

    def save_source_policy(self, raw: dict[str, object], actor_id: str | None = None) -> dict[str, object]:
        name = str(raw.get("name", "")).strip()
        if not 1 <= len(name) <= 160: raise ValueError("policy name must contain 1-160 characters")
        connector_type = str(raw.get("connector_type", "")).strip()
        if connector_type not in CONNECTOR_TYPES: raise ValueError("invalid connector_type")
        status = str(raw.get("status", "draft")).strip()
        if status not in POLICY_STATUSES: raise ValueError("invalid policy status")
        domain = canonical_domain(str(raw.get("domain", "")))
        permission_basis = str(raw.get("permission_basis", "")).strip()
        if not permission_basis or len(permission_basis) > 500: raise ValueError("permission_basis is required and must not exceed 500 characters")
        allowed_fields = raw.get("allowed_fields", [])
        if not isinstance(allowed_fields, list) or not set(allowed_fields).issubset(CAPTURE_FIELDS):
            raise ValueError("allowed_fields must contain supported company fields only")
        retention_days = raw.get("retention_days")
        if retention_days is not None and (not isinstance(retention_days, int) or not 1 <= retention_days <= 3650): raise ValueError("retention_days must be 1-3650")
        rate_limit = raw.get("rate_limit_per_minute")
        if rate_limit is not None and (not isinstance(rate_limit, int) or not 1 <= rate_limit <= 10000): raise ValueError("rate_limit_per_minute must be 1-10000")
        policy_id = raw.get("id")
        with self.connection() as db, db.cursor() as cur:
            if policy_id:
                cur.execute("""UPDATE source_policies SET name=%s,domain=%s,connector_type=%s,permission_basis=%s,
                    license_note=%s,attribution_text=%s,attribution_required=%s,export_allowed=%s,retention_days=%s,
                    allowed_fields=%s::jsonb,rate_limit_per_minute=%s,status=%s,updated_by=%s,updated_at=now()
                    WHERE id=%s AND workspace_id=%s RETURNING id::text,name,domain,connector_type,permission_basis,
                    license_note,attribution_text,attribution_required,export_allowed,retention_days,allowed_fields,
                    rate_limit_per_minute,status,created_at,updated_at""", (name,domain,connector_type,permission_basis,
                    raw.get("license_note"),raw.get("attribution_text"),bool(raw.get("attribution_required",False)),
                    bool(raw.get("export_allowed",True)),retention_days,json.dumps(allowed_fields),rate_limit,status,actor_id,
                    policy_id,self.workspace_id))
            else:
                cur.execute("""INSERT INTO source_policies(workspace_id,name,domain,connector_type,permission_basis,
                    license_note,attribution_text,attribution_required,export_allowed,retention_days,allowed_fields,
                    rate_limit_per_minute,status,created_by,updated_by) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s,%s,%s,%s)
                    ON CONFLICT(workspace_id,domain,connector_type) DO UPDATE SET name=EXCLUDED.name,
                    permission_basis=EXCLUDED.permission_basis,license_note=EXCLUDED.license_note,
                    attribution_text=EXCLUDED.attribution_text,attribution_required=EXCLUDED.attribution_required,
                    export_allowed=EXCLUDED.export_allowed,retention_days=EXCLUDED.retention_days,
                    allowed_fields=EXCLUDED.allowed_fields,rate_limit_per_minute=EXCLUDED.rate_limit_per_minute,
                    status=EXCLUDED.status,updated_by=EXCLUDED.updated_by,updated_at=now()
                    RETURNING id::text,name,domain,connector_type,permission_basis,license_note,attribution_text,
                    attribution_required,export_allowed,retention_days,allowed_fields,rate_limit_per_minute,status,created_at,updated_at""",
                    (self.workspace_id,name,domain,connector_type,permission_basis,raw.get("license_note"),raw.get("attribution_text"),
                    bool(raw.get("attribution_required",False)),bool(raw.get("export_allowed",True)),retention_days,
                    json.dumps(allowed_fields),rate_limit,status,actor_id,actor_id))
            saved = cur.fetchone()
            if not saved: raise ValueError("source policy was not found")
            cur.execute("INSERT INTO audit_events(workspace_id,actor_id,action,entity_type,entity_id,details) VALUES(%s,%s,%s,'source_policy',%s,%s::jsonb)",
                (self.workspace_id,actor_id,"source_policy_updated" if policy_id else "source_policy_saved",saved["id"],json.dumps({"domain":domain,"status":status,"connector_type":connector_type})))
            return saved

    def create_research_session(self, raw: dict[str, object], actor_id: str | None = None) -> dict[str, object]:
        title, keyword = str(raw.get("title", "")).strip(), str(raw.get("keyword", "")).strip()
        locations = raw.get("target_locations", [])
        policy_ids = raw.get("source_policy_ids", [])
        if not title or not keyword or not isinstance(locations, list): raise ValueError("title, keyword, and target_locations are required")
        locations = list(dict.fromkeys(str(item).strip() for item in locations if str(item).strip()))
        if not 1 <= len(locations) <= 100: raise ValueError("target_locations must contain 1-100 locations")
        if not isinstance(policy_ids, list): raise ValueError("source_policy_ids must be a list")
        with self.connection() as db, db.cursor() as cur:
            if policy_ids:
                if not all(isinstance(item, str) for item in policy_ids): raise ValueError("source_policy_ids must contain policy identifiers")
                cur.execute("SELECT count(*) AS count FROM source_policies WHERE workspace_id=%s AND id::text = ANY(%s) AND status='approved'", (self.workspace_id,policy_ids))
                if cur.fetchone()["count"] != len(set(policy_ids)):
                    raise ValueError("research sessions may scope only approved workspace source policies")
            cur.execute("""INSERT INTO research_sessions(workspace_id,title,keyword,target_locations,source_policy_ids,owner_id,due_at,status)
                VALUES(%s,%s,%s,%s::jsonb,%s::jsonb,%s,%s,'not_started') RETURNING id::text,title,keyword,target_locations,source_policy_ids,owner_id::text,due_at,status,created_at""",
                (self.workspace_id,title,keyword,json.dumps(locations),json.dumps(policy_ids),actor_id,raw.get("due_at")))
            session = cur.fetchone()
            for location in locations:
                cur.execute("INSERT INTO research_tasks(workspace_id,session_id,location) VALUES(%s,%s,%s)", (self.workspace_id,session["id"],location))
            cur.execute("INSERT INTO audit_events(workspace_id,actor_id,action,entity_type,entity_id,details) VALUES(%s,%s,'research_session_created','research_session',%s,%s::jsonb)",
                (self.workspace_id,actor_id,session["id"],json.dumps({"locations":len(locations)})))
            return self.research_session(session["id"]) or session

    def research_sessions(self) -> list[dict[str, object]]:
        with self.connection() as db, db.cursor() as cur:
            cur.execute("SELECT id::text,title,keyword,target_locations,source_policy_ids,owner_id::text,due_at,status,created_at,updated_at FROM research_sessions WHERE workspace_id=%s ORDER BY created_at DESC", (self.workspace_id,))
            return [self.research_session(item["id"]) for item in cur.fetchall()]

    def research_session(self, session_id: str) -> dict[str, object] | None:
        with self.connection() as db, db.cursor() as cur:
            cur.execute("SELECT id::text,title,keyword,target_locations,source_policy_ids,owner_id::text,due_at,status,created_at,updated_at FROM research_sessions WHERE id=%s AND workspace_id=%s", (session_id,self.workspace_id)); session=cur.fetchone()
            if not session: return None
            cur.execute("SELECT id::text,location,status,notes,updated_at FROM research_tasks WHERE session_id=%s AND workspace_id=%s ORDER BY location", (session_id,self.workspace_id)); session["tasks"]=list(cur.fetchall())
            return session

    def update_research_task(self, task_id: str, status: str, notes: str | None, actor_id: str | None = None) -> bool:
        if status not in TASK_STATUSES: raise ValueError("invalid research task status")
        if notes is not None and len(notes) > 4000: raise ValueError("notes must not exceed 4000 characters")
        with self.connection() as db, db.cursor() as cur:
            cur.execute("UPDATE research_tasks SET status=%s,notes=%s,updated_at=now() WHERE id=%s AND workspace_id=%s", (status,notes,task_id,self.workspace_id)); changed=cur.rowcount == 1
            if changed: cur.execute("INSERT INTO audit_events(workspace_id,actor_id,action,entity_type,entity_id,details) VALUES(%s,%s,'research_task_updated','research_task',%s,%s::jsonb)", (self.workspace_id,actor_id,task_id,json.dumps({"status":status})))
            return changed

    def capture_evidence(self, raw: dict[str, object], actor_id: str | None = None) -> dict[str, object]:
        policy_id = str(raw.get("source_policy_id", "")); url, observed_domain = capture_url(str(raw.get("capture_url", "")))
        with self.connection() as db, db.cursor() as cur:
            cur.execute("SELECT id::text,name,domain,allowed_fields,retention_days,rate_limit_per_minute,status FROM source_policies WHERE id=%s AND workspace_id=%s AND connector_type='browser_capture'", (policy_id,self.workspace_id)); policy=cur.fetchone()
            if not policy or policy["status"] != "approved": raise ValueError("an approved browser_capture source policy is required")
            if not domain_matches(policy["domain"], observed_domain): raise ValueError("capture URL domain is not approved by this source policy")
            fields = validate_fields(raw.get("fields"), policy["allowed_fields"])
            if policy["rate_limit_per_minute"]:
                cur.execute("SELECT count(*) AS count FROM evidence_items WHERE workspace_id=%s AND source_policy_id=%s AND created_at > now() - interval '1 minute'", (self.workspace_id,policy_id))
                if cur.fetchone()["count"] >= policy["rate_limit_per_minute"]:
                    raise ValueError("source policy capture rate limit exceeded; wait before submitting more evidence")
            task_id = raw.get("research_task_id")
            if task_id:
                cur.execute("SELECT id FROM research_tasks WHERE id=%s AND workspace_id=%s", (task_id,self.workspace_id))
                if not cur.fetchone(): raise ValueError("research task was not found")
            company_id = raw.get("company_id")
            if company_id:
                cur.execute("SELECT id FROM companies WHERE id=%s AND workspace_id=%s", (company_id,self.workspace_id))
                if not cur.fetchone(): raise ValueError("company was not found")
            else:
                evidence_source = Source(provider=f"evidence:{policy['name']}", provider_record_id=content_fingerprint(url, fields)[:32], source_url=url)
                company = Company(id=f"evidence:{content_fingerprint(url, fields)[:24]}", name=str(fields["name"]), description=fields.get("description"), categories=fields.get("categories", []), website=fields.get("website"), phone=fields.get("phone"), email=fields.get("email"), address=fields.get("address"), locality=fields.get("locality"), city=fields.get("city"), state=fields.get("state"), country=fields.get("country"), postal_code=fields.get("postal_code"), sources=[evidence_source])
                # Preserve the same normalisation and immutable source record rules as a CSV import.
                self.upsert_many([company]); company_id = company.id
            fingerprint = content_fingerprint(url, fields)
            cur.execute("""INSERT INTO evidence_items(workspace_id,company_id,source_policy_id,research_task_id,capture_url,capture_domain,content_fingerprint,captured_fields,captured_by,expires_at)
                VALUES(%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s,CASE WHEN CAST(%s AS integer) IS NULL THEN NULL ELSE now() + (CAST(%s AS integer) * interval '1 day') END)
                ON CONFLICT(workspace_id,source_policy_id,content_fingerprint) DO UPDATE SET captured_by=EXCLUDED.captured_by,created_at=now()
                RETURNING id::text,company_id,source_policy_id,status,capture_url,capture_domain,captured_fields,expires_at,created_at""",
                (self.workspace_id,company_id,policy_id,task_id,url,observed_domain,fingerprint,json.dumps(fields),actor_id,policy["retention_days"],policy["retention_days"]))
            evidence=cur.fetchone()
            cur.execute("INSERT INTO audit_events(workspace_id,actor_id,action,entity_type,entity_id,details) VALUES(%s,%s,'evidence_captured','evidence',%s,%s::jsonb)", (self.workspace_id,actor_id,evidence["id"],json.dumps({"company_id":company_id,"policy":policy["name"],"domain":observed_domain})))
            return evidence

    def evidence_items(self, status: str | None = None, company_id: str | None = None) -> list[dict[str, object]]:
        if status is not None and status not in EVIDENCE_STATUSES: raise ValueError("invalid evidence status")
        with self.connection() as db, db.cursor() as cur:
            cur.execute("""SELECT e.id::text,e.company_id,e.source_policy_id::text,e.research_task_id::text,e.capture_url,e.capture_domain,e.captured_fields,e.status,e.expires_at,e.created_at,
                p.name AS policy_name,p.attribution_text,p.export_allowed,c.email AS captured_by_email,r.email AS reviewer_email
                FROM evidence_items e JOIN source_policies p ON p.id=e.source_policy_id LEFT JOIN users c ON c.id=e.captured_by LEFT JOIN users r ON r.id=e.reviewed_by
                WHERE e.workspace_id=%s AND (%s::text IS NULL OR e.status=%s) AND (%s::text IS NULL OR e.company_id=%s) ORDER BY e.created_at DESC LIMIT 500""", (self.workspace_id,status,status,company_id,company_id))
            return list(cur.fetchall())

    def review_evidence(self, evidence_id: str, status: str, reviewer_id: str | None = None) -> bool:
        if status not in EVIDENCE_STATUSES - {"pending"}: raise ValueError("invalid evidence review status")
        with self.connection() as db, db.cursor() as cur:
            cur.execute("UPDATE evidence_items SET status=%s,reviewed_by=%s,reviewed_at=now() WHERE id=%s AND workspace_id=%s AND status='pending'", (status,reviewer_id,evidence_id,self.workspace_id)); changed=cur.rowcount == 1
            if changed: cur.execute("INSERT INTO audit_events(workspace_id,actor_id,action,entity_type,entity_id,details) VALUES(%s,%s,%s,'evidence',%s,%s::jsonb)", (self.workspace_id,reviewer_id,f"evidence_{status}",evidence_id,json.dumps({"review_only":True})))
            return changed

    def purge_expired_evidence(self) -> int:
        """Enforce source-policy retention without deleting the company record itself."""
        with self.connection() as db, db.cursor() as cur:
            cur.execute("DELETE FROM evidence_items WHERE workspace_id=%s AND expires_at IS NOT NULL AND expires_at <= now() RETURNING id::text", (self.workspace_id,))
            removed = [row["id"] for row in cur.fetchall()]
            if removed:
                cur.execute("INSERT INTO audit_events(workspace_id,action,entity_type,entity_id,details) VALUES(%s,'evidence_retention_purged','evidence_retention','workspace',%s::jsonb)", (self.workspace_id,json.dumps({"count":len(removed)})))
            return len(removed)

    def ensure_export_allowed(self, companies: list[Company]) -> None:
        ids = [item.id for item in companies]
        if not ids: return
        with self.connection() as db, db.cursor() as cur:
            cur.execute("""SELECT DISTINCT p.name FROM evidence_items e JOIN source_policies p ON p.id=e.source_policy_id
                WHERE e.workspace_id=%s AND e.company_id = ANY(%s) AND p.export_allowed=false""", (self.workspace_id,ids))
            names=[row["name"] for row in cur.fetchall()]
            if names: raise ValueError("export is prohibited by source policy: " + ", ".join(names))

    def authenticate(self, email: str, password: str) -> dict[str, str] | None:
        with self.connection() as db, db.cursor() as cur:
            cur.execute("""SELECT u.id::text AS user_id, m.workspace_id::text AS workspace_id, m.role, u.password_hash
                FROM users u JOIN workspace_memberships m ON m.user_id=u.id WHERE u.email=%s AND m.workspace_id=%s""", (email.lower(), self.workspace_id))
            user = cur.fetchone()
            if user and verify_password(password, user["password_hash"]):
                return {"user_id": user["user_id"], "workspace_id": user["workspace_id"], "role": user["role"]}
            return None

    def upsert_many(self, companies: list[Company]) -> int:
        saved = 0
        for company in deduplicate(companies):
            company = normalize_company(company); company_id = company.id
            with self.connection() as db, db.cursor() as cur:
                known = None
                for source in company.sources:
                    cur.execute("SELECT company_id::text FROM company_sources WHERE provider=%s AND provider_record_id=%s", (source.provider, source.provider_record_id))
                    if known := cur.fetchone(): break
                company_id = known["company_id"] if known else company_id
                cur.execute("""INSERT INTO companies(id,workspace_id,name,description,categories,website,domain,phone,email,address,locality,city,state,country,postal_code,latitude,longitude,coordinates)
                VALUES(%s,%s,%s,%s,%s::jsonb,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,CASE WHEN CAST(%s AS double precision) IS NULL OR CAST(%s AS double precision) IS NULL THEN NULL ELSE ST_SetSRID(ST_MakePoint(CAST(%s AS double precision),CAST(%s AS double precision)),4326)::geography END)
                ON CONFLICT(id) DO UPDATE SET name=EXCLUDED.name,description=COALESCE(EXCLUDED.description,companies.description),categories=EXCLUDED.categories,website=COALESCE(EXCLUDED.website,companies.website),domain=COALESCE(EXCLUDED.domain,companies.domain),phone=COALESCE(EXCLUDED.phone,companies.phone),email=COALESCE(EXCLUDED.email,companies.email),address=COALESCE(EXCLUDED.address,companies.address),locality=COALESCE(EXCLUDED.locality,companies.locality),city=COALESCE(EXCLUDED.city,companies.city),state=COALESCE(EXCLUDED.state,companies.state),country=COALESCE(EXCLUDED.country,companies.country),postal_code=COALESCE(EXCLUDED.postal_code,companies.postal_code),latitude=COALESCE(EXCLUDED.latitude,companies.latitude),longitude=COALESCE(EXCLUDED.longitude,companies.longitude),updated_at=now()""", (company_id,self.workspace_id,company.name,company.description,json.dumps(company.categories),company.website,company.domain,company.phone,company.email,company.address,company.locality,company.city,company.state,company.country,company.postal_code,company.latitude,company.longitude,company.longitude,company.latitude,company.longitude,company.latitude))
                for source in company.sources:
                    self.register_source(source.provider, "provider" if source.provider != "user_csv" else "user_csv", "configured_or_user_provided")
                    cur.execute("INSERT INTO company_sources(company_id,provider,provider_record_id,source_url,discovered_at) VALUES(%s,%s,%s,%s,%s) ON CONFLICT(provider,provider_record_id) DO NOTHING", (company_id,source.provider,source.provider_record_id,source.source_url,source.discovered_at))
                cur.execute("INSERT INTO audit_events(workspace_id,action,entity_type,entity_id,details) VALUES(%s,'company_upserted','company',%s,%s::jsonb)", (self.workspace_id,company_id,json.dumps({"source_count":len(company.sources)})))
            saved += 1
        self.refresh_duplicate_candidates()
        return saved

    def refresh_duplicate_candidates(self) -> int:
        companies = self.search("", None, 10_000)
        candidates = find_candidates(companies)
        with self.connection() as db, db.cursor() as cur:
            for item in candidates:
                left, right = sorted((item.left_id, item.right_id))
                cur.execute("""INSERT INTO duplicate_reviews(workspace_id,left_company_id,right_company_id,score,reasons)
                    VALUES(%s,%s,%s,%s,%s::jsonb) ON CONFLICT(workspace_id,left_company_id,right_company_id)
                    DO UPDATE SET score=EXCLUDED.score,reasons=EXCLUDED.reasons WHERE duplicate_reviews.status='pending'""",
                    (self.workspace_id, left, right, item.score, json.dumps(item.reasons)))
        return len(candidates)

    def duplicate_reviews(self, status: str = "pending") -> list[dict[str, object]]:
        with self.connection() as db, db.cursor() as cur:
            if status not in {"pending", "approved", "rejected", "merged"}:
                raise ValueError("invalid duplicate review status")
            cur.execute("""SELECT d.id::text,d.left_company_id,d.right_company_id,d.score,d.reasons,d.status,
                d.created_at,d.reviewed_at,u.email AS reviewer_email,
                COALESCE((SELECT jsonb_agg(jsonb_build_object('action',a.action,'occurred_at',a.occurred_at,'details',a.details) ORDER BY a.occurred_at DESC)
                    FROM audit_events a WHERE a.workspace_id=d.workspace_id AND a.entity_type='duplicate_review' AND a.entity_id=d.id::text), '[]'::jsonb) AS audit_events,
                jsonb_build_object('id',l.id,'name',l.name,'website',l.website,'domain',l.domain,
                    'phone',l.phone,'address',l.address,'locality',l.locality,'city',l.city,'country',l.country) AS left_company,
                jsonb_build_object('id',r.id,'name',r.name,'website',r.website,'domain',r.domain,
                    'phone',r.phone,'address',r.address,'locality',r.locality,'city',r.city,'country',r.country) AS right_company
                FROM duplicate_reviews d
                JOIN companies l ON l.id=d.left_company_id AND l.workspace_id=d.workspace_id
                JOIN companies r ON r.id=d.right_company_id AND r.workspace_id=d.workspace_id
                LEFT JOIN users u ON u.id=d.reviewer_id
                WHERE d.workspace_id=%s AND d.status=%s ORDER BY d.score DESC,d.created_at""", (self.workspace_id, status))
            return list(cur.fetchall())

    def review_duplicate(self, review_id: str, status: str, reviewer_id: str | None = None) -> bool:
        # Decisions are review records only.  They deliberately never merge or delete companies.
        if status not in {"approved", "rejected"}: raise ValueError("status must be approved or rejected")
        with self.connection() as db, db.cursor() as cur:
            cur.execute("UPDATE duplicate_reviews SET status=%s,reviewer_id=%s,reviewed_at=now() WHERE id=%s AND workspace_id=%s AND status='pending'", (status, reviewer_id, review_id, self.workspace_id))
            changed = cur.rowcount == 1
            if changed:
                cur.execute("INSERT INTO audit_events(workspace_id,actor_id,action,entity_type,entity_id,details) VALUES(%s,%s,%s,'duplicate_review',%s,%s::jsonb)",
                    (self.workspace_id, reviewer_id, f"duplicate_{status}", review_id, json.dumps({"review_only": True})))
            return changed

    def members(self) -> list[dict[str, object]]:
        with self.connection() as db, db.cursor() as cur:
            cur.execute("SELECT u.id::text AS id,u.email,m.role,u.created_at FROM users u JOIN workspace_memberships m ON m.user_id=u.id WHERE m.workspace_id=%s ORDER BY u.email", (self.workspace_id,))
            return list(cur.fetchall())

    def add_member(self, email: str, password: str, role: str, actor_id: str | None = None) -> None:
        if role not in {"owner", "editor", "viewer"}: raise ValueError("invalid role")
        if not email or "@" not in email or len(email) > 254: raise ValueError("a valid email is required")
        if not password: raise ValueError("an initial password is required")
        with self.connection() as db, db.cursor() as cur:
            cur.execute("SELECT id::text FROM users WHERE email=%s", (email.lower(),)); row = cur.fetchone()
            user_id = row["id"] if row else str(uuid4())
            # Never reset an existing user's password through an invitation endpoint.
            if not row:
                cur.execute("INSERT INTO users(id,email,password_hash) VALUES(%s,%s,%s)", (user_id, email.lower(), hash_password(password)))
            cur.execute("INSERT INTO workspace_memberships(workspace_id,user_id,role) VALUES(%s,%s,%s) ON CONFLICT(workspace_id,user_id) DO UPDATE SET role=EXCLUDED.role", (self.workspace_id,user_id,role))
            cur.execute("INSERT INTO audit_events(workspace_id,actor_id,action,entity_type,entity_id,details) VALUES(%s,%s,'member_saved','member',%s,%s::jsonb)",
                (self.workspace_id, actor_id, user_id, json.dumps({"email": email.lower(), "role": role})))

    def set_member_role(self, user_id: str, role: str, actor_id: str | None = None) -> bool:
        if role not in {"owner", "editor", "viewer"}: raise ValueError("invalid role")
        with self.connection() as db, db.cursor() as cur:
            cur.execute("SELECT role FROM workspace_memberships WHERE workspace_id=%s AND user_id=%s", (self.workspace_id,user_id))
            current = cur.fetchone()
            if not current: return False
            if current["role"] == "owner" and role != "owner":
                cur.execute("SELECT count(*) AS count FROM workspace_memberships WHERE workspace_id=%s AND role='owner'", (self.workspace_id,))
                if cur.fetchone()["count"] < 2: raise ValueError("cannot demote the last owner")
            cur.execute("UPDATE workspace_memberships SET role=%s WHERE workspace_id=%s AND user_id=%s", (role,self.workspace_id,user_id))
            cur.execute("INSERT INTO audit_events(workspace_id,actor_id,action,entity_type,entity_id,details) VALUES(%s,%s,'member_role_changed','member',%s,%s::jsonb)",
                (self.workspace_id, actor_id, user_id, json.dumps({"role": role})))
            return True

    def remove_member(self, user_id: str, actor_id: str | None = None) -> bool:
        with self.connection() as db, db.cursor() as cur:
            cur.execute("SELECT role FROM workspace_memberships WHERE workspace_id=%s AND user_id=%s", (self.workspace_id,user_id))
            current = cur.fetchone()
            if not current: return False
            if current["role"] == "owner":
                cur.execute("SELECT count(*) AS count FROM workspace_memberships WHERE workspace_id=%s AND role='owner'", (self.workspace_id,))
                if cur.fetchone()["count"] < 2: raise ValueError("cannot remove the last owner")
            cur.execute("DELETE FROM workspace_memberships WHERE workspace_id=%s AND user_id=%s", (self.workspace_id,user_id))
            cur.execute("INSERT INTO audit_events(workspace_id,actor_id,action,entity_type,entity_id,details) VALUES(%s,%s,'member_removed','member',%s,'{}'::jsonb)",
                (self.workspace_id, actor_id, user_id))
            return True

    def company_detail(self, company_id: str) -> dict[str, object] | None:
        matches = self.search("", None, 10_000)
        company = next((item for item in matches if item.id == company_id), None)
        if not company: return None
        with self.connection() as db, db.cursor() as cur:
            cur.execute("SELECT field_name,source_name,observed_at FROM company_field_provenance WHERE company_id=%s ORDER BY field_name", (company_id,)); provenance=list(cur.fetchall())
            cur.execute("SELECT action,details,occurred_at FROM audit_events WHERE workspace_id=%s AND entity_type='company' AND entity_id=%s ORDER BY id DESC LIMIT 50", (self.workspace_id,company_id)); events=list(cur.fetchall())
            cur.execute("""SELECT e.id::text,e.capture_url,e.capture_domain,e.captured_fields,e.status,e.expires_at,e.created_at,
                p.name AS policy_name,p.attribution_text,u.email AS captured_by_email,r.email AS reviewer_email
                FROM evidence_items e JOIN source_policies p ON p.id=e.source_policy_id
                LEFT JOIN users u ON u.id=e.captured_by LEFT JOIN users r ON r.id=e.reviewed_by
                WHERE e.workspace_id=%s AND e.company_id=%s ORDER BY e.created_at DESC""", (self.workspace_id,company_id)); evidence=list(cur.fetchall())
        quality = self._quality(company)
        approved = sum(item["status"] == "approved" for item in evidence)
        stale = sum(item["status"] == "stale" for item in evidence)
        quality["approved_evidence"] = approved; quality["stale_evidence"] = stale
        quality["score"] = max(0, min(100, quality["score"] + min(10, approved * 5) - min(10, stale * 5)))
        return {"company": company.as_dict(), "quality": quality, "field_provenance": provenance, "evidence": evidence, "audit_events": events}

    def companies_with_quality(self, quality: str | None = None, limit: int = 100) -> list[dict[str, object]]:
        """Return a bounded list for the quality dashboard, scoped to this workspace."""
        if quality not in {None, "all", "low"}: raise ValueError("quality must be all or low")
        rows = []
        for company in self.search("", None, min(max(limit, 1), 500)):
            item = company.as_dict(); item["quality"] = self._quality(company)
            if quality != "low" or item["quality"]["score"] < 60: rows.append(item)
        return rows

    def search(self, keyword: str, location: str | None, limit: int) -> list[Company]:
        like = f"%{keyword.strip()}%"; location_like = f"%{location.strip()}%" if location else None
        with self.connection() as db, db.cursor() as cur:
            cur.execute("""SELECT * FROM companies WHERE workspace_id=%s AND (name ILIKE %s OR COALESCE(description,'') ILIKE %s OR categories::text ILIKE %s) AND (CAST(%s AS text) IS NULL OR COALESCE(locality,'') ILIKE %s OR COALESCE(city,'') ILIKE %s OR COALESCE(address,'') ILIKE %s) ORDER BY name LIMIT %s""", (self.workspace_id,like,like,like,location_like,location_like,location_like,location_like,limit))
            rows = cur.fetchall(); result=[]
            for row in rows:
                cur.execute("SELECT provider,provider_record_id,source_url,discovered_at::text FROM company_sources WHERE company_id=%s", (row["id"],))
                row["id"] = str(row["id"]); row["categories"] = row["categories"] or []; row["sources"] = [Source(**source) for source in cur.fetchall()]; row.pop("workspace_id",None); row.pop("coordinates",None); row.pop("created_at",None); row.pop("updated_at",None)
                result.append(Company(**row))
            return result
