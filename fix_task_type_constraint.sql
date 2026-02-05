-- Migration to fix task_type constraint from 'away_forward' to 'away_email'

-- Drop the old constraint
ALTER TABLE tasks DROP CONSTRAINT check_task_type;

-- Add the correct constraint
ALTER TABLE tasks ADD CONSTRAINT check_task_type
    CHECK (task_type IN ('home_email', 'away_email'));

-- Update any existing 'away_forward' task_types to 'away_email'
UPDATE tasks SET task_type = 'away_email' WHERE task_type = 'away_forward';

COMMIT;
