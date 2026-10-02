CREATE TABLE IF NOT EXISTS source_policies (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  workspace_id UUID NOT NULL REFERENCES workspaces(id),
  name TEXT NOT NULL,
  domain TEXT NOT NULL,
  connector_type TEXT NOT NULL CHECK(connector_type IN ('browser_capture','csv','official_api','licensed_feed','open_data','manual')),
  permission_basis TEXT NOT NULL,
  license_note TEXT,
  attribution_text TEXT,
  attribution_required BOOLEAN NOT NULL DEFAULT false,
  export_allowed BOOLEAN NOT NULL DEFAULT true,
  retention_days INTEGER CHECK(retention_days IS NULL OR retention_days BETWEEN 1 AND 3650),
  allowed_fields JSONB NOT NULL DEFAULT '[]',
  rate_limit_per_minute INTEGER CHECK(rate_limit_per_minute IS NULL OR rate_limit_per_minute BETWEEN 1 AND 10000),
  status TEXT NOT NULL DEFAULT 'draft' CHECK(status IN ('draft','approved','paused','blocked')),
  created_by UUID REFERENCES users(id),
  updated_by UUID REFERENCES users(id),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE(workspace_id,domain,connector_type)
);
CREATE INDEX IF NOT EXISTS source_policies_workspace_status_idx ON source_policies(workspace_id,status);

CREATE TABLE IF NOT EXISTS research_sessions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  workspace_id UUID NOT NULL REFERENCES workspaces(id),
  title TEXT NOT NULL,
  keyword TEXT NOT NULL,
  target_locations JSONB NOT NULL DEFAULT '[]',
  source_policy_ids JSONB NOT NULL DEFAULT '[]',
  owner_id UUID REFERENCES users(id),
  due_at TIMESTAMPTZ,
  status TEXT NOT NULL DEFAULT 'not_started' CHECK(status IN ('not_started','in_review','completed','blocked','needs_clarification')),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS research_tasks (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  workspace_id UUID NOT NULL REFERENCES workspaces(id),
  session_id UUID NOT NULL REFERENCES research_sessions(id) ON DELETE CASCADE,
  location TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'not_started' CHECK(status IN ('not_started','in_review','completed','blocked','needs_clarification')),
  notes TEXT,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE(session_id,location)
);
CREATE INDEX IF NOT EXISTS research_tasks_workspace_session_idx ON research_tasks(workspace_id,session_id,status);

CREATE TABLE IF NOT EXISTS evidence_items (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  workspace_id UUID NOT NULL REFERENCES workspaces(id),
  company_id TEXT REFERENCES companies(id),
  source_policy_id UUID NOT NULL REFERENCES source_policies(id),
  research_task_id UUID REFERENCES research_tasks(id),
  capture_url TEXT NOT NULL,
  capture_domain TEXT NOT NULL,
  content_fingerprint TEXT NOT NULL,
  captured_fields JSONB NOT NULL,
  status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending','approved','rejected','needs_correction','stale')),
  captured_by UUID REFERENCES users(id),
  reviewed_by UUID REFERENCES users(id),
  reviewed_at TIMESTAMPTZ,
  expires_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE(workspace_id,source_policy_id,content_fingerprint)
);
CREATE INDEX IF NOT EXISTS evidence_items_workspace_status_idx ON evidence_items(workspace_id,status,created_at DESC);
CREATE INDEX IF NOT EXISTS evidence_items_company_idx ON evidence_items(workspace_id,company_id,created_at DESC);
