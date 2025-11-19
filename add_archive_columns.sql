-- Add archiving columns to existing tables
-- Run this script to add the is_archived and archived_at columns

-- Add columns to fixtures table
ALTER TABLE fixtures 
ADD COLUMN is_archived BOOLEAN DEFAULT FALSE,
ADD COLUMN archived_at TIMESTAMP WITH TIME ZONE;

-- Add columns to tasks table  
ALTER TABLE tasks
ADD COLUMN is_archived BOOLEAN DEFAULT FALSE,
ADD COLUMN archived_at TIMESTAMP WITH TIME ZONE;

-- Set existing records to not archived
UPDATE fixtures SET is_archived = FALSE WHERE is_archived IS NULL;
UPDATE tasks SET is_archived = FALSE WHERE is_archived IS NULL;