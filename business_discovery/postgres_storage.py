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
        return {"company": company.as_dict(), "quality": self._quality(company), "field_provenance": provenance, "audit_events": events}

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
