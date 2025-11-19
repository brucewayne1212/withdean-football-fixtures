-- Add google_drive_map_url column to pitches table
ALTER TABLE pitches ADD COLUMN google_drive_map_url TEXT;

-- Add comment for clarity
COMMENT ON COLUMN pitches.google_drive_map_url IS 'URL to Google Drive walking/estate map image';