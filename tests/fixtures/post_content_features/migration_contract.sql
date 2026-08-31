\set ON_ERROR_STOP on

-- Executed after the migration by the T4A database verification harness.
-- The GREEN implementation must make all named checks succeed.
SELECT 'wrong dimension' AS pending_check;
SELECT 'unsupported encoder' AS pending_check;
SELECT 'invalid content hash' AS pending_check;
SELECT 'non-normalized topics' AS pending_check;
SELECT 'duplicate feature' AS pending_check;
SELECT 'immutable feature' AS pending_check;
SELECT 'multiple encoder versions' AS pending_check;
SELECT 'existing post without features' AS pending_check;
