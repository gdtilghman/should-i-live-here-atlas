-- One-off cleanup. Not a migration; run it by hand once, after review:
--   npx wrangler d1 execute silh-mcp-requests --remote --file sql/cleanup-fixture-terms.sql
-- Check first what it will delete:
--   npx wrangler d1 execute silh-mcp-requests --remote --command "SELECT * FROM missing_requests WHERE term LIKE '%fixture%' OR (day = '2026-11-02' AND term = 'schools')"

-- Junk test terms such as "audit-fixture".
DELETE FROM missing_requests WHERE term LIKE '%fixture%';

-- The "schools" row from the go-live test on 2026-11-02 (count 1). Not a
-- real user request. Only that day, so later real requests stay.
DELETE FROM missing_requests WHERE day = '2026-11-02' AND term = 'schools';
