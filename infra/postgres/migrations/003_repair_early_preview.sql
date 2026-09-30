-- Repair databases initialized by preview revisions before source tables and seed workspace existed.
ALTER TABLE companies ADD COLUMN IF NOT EXISTS description TEXT;
ALTER TABLE companies ADD COLUMN IF NOT EXISTS state TEXT;
ALTER TABLE companies ADD COLUMN IF NOT EXISTS postal_code TEXT;
ALTER TABLE companies ADD COLUMN IF NOT EXISTS latitude DOUBLE PRECISION;
ALTER TABLE companies ADD COLUMN IF NOT EXISTS longitude DOUBLE PRECISION;
ALTER TABLE companies ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ NOT NULL DEFAULT now();
CREATE TABLE IF NOT EXISTS company_sources (
  company_id TEXT NOT NULL REFERENCES companies(id), provider TEXT NOT NULL,
  provider_record_id TEXT NOT NULL, source_url TEXT, discovered_at TIMESTAMPTZ NOT NULL,
  PRIMARY KEY(provider, provider_record_id)
);
CREATE TABLE IF NOT EXISTS company_field_provenance (
  company_id TEXT NOT NULL REFERENCES companies(id), field_name TEXT NOT NULL,
  source_name TEXT NOT NULL, observed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY(company_id, field_name, source_name)
);
INSERT INTO workspaces(id, name) VALUES ('00000000-0000-0000-0000-000000000001', 'Default workspace') ON CONFLICT (id) DO NOTHING;
