-- Add map fields to pitches table
ALTER TABLE pitches ADD COLUMN IF NOT EXISTS map_image_url TEXT;
ALTER TABLE pitches ADD COLUMN IF NOT EXISTS google_maps_link TEXT;