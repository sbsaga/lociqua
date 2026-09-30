CREATE TABLE IF NOT EXISTS duplicate_reviews (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  workspace_id UUID NOT NULL REFERENCES workspaces(id),
  left_company_id TEXT NOT NULL REFERENCES companies(id),
  right_company_id TEXT NOT NULL REFERENCES companies(id),
  score SMALLINT NOT NULL CHECK(score BETWEEN 0 AND 100),
  reasons JSONB NOT NULL DEFAULT '[]',
  status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending','approved','rejected','merged')),
  reviewer_id UUID REFERENCES users(id),
  reviewed_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE(workspace_id,left_company_id,right_company_id)
);
CREATE INDEX IF NOT EXISTS duplicate_reviews_pending_idx ON duplicate_reviews(workspace_id,status,score DESC);
