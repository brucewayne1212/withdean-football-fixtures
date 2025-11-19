-- Add fa_fixtures_url column to teams table
ALTER TABLE teams ADD COLUMN IF NOT EXISTS fa_fixtures_url TEXT;

