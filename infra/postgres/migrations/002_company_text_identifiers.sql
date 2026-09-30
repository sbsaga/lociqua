-- Imported records use stable provider text identifiers (for example import:<hash>).
-- This migration upgrades databases initialized with the first UUID-only draft.
ALTER TABLE IF EXISTS company_sources DROP CONSTRAINT IF EXISTS company_sources_company_id_fkey;
ALTER TABLE IF EXISTS company_field_provenance DROP CONSTRAINT IF EXISTS company_field_provenance_company_id_fkey;
ALTER TABLE IF EXISTS companies ALTER COLUMN id TYPE TEXT USING id::text;
ALTER TABLE IF EXISTS company_sources ALTER COLUMN company_id TYPE TEXT USING company_id::text;
ALTER TABLE IF EXISTS company_field_provenance ALTER COLUMN company_id TYPE TEXT USING company_id::text;
ALTER TABLE IF EXISTS audit_events ALTER COLUMN entity_id TYPE TEXT USING entity_id::text;
ALTER TABLE IF EXISTS company_sources ADD CONSTRAINT company_sources_company_id_fkey FOREIGN KEY(company_id) REFERENCES companies(id);
ALTER TABLE IF EXISTS company_field_provenance ADD CONSTRAINT company_field_provenance_company_id_fkey FOREIGN KEY(company_id) REFERENCES companies(id);
