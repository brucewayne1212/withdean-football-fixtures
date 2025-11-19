-- Add parking map fields to pitches table
ALTER TABLE pitches ADD COLUMN IF NOT EXISTS parking_map_image_url TEXT;
ALTER TABLE pitches ADD COLUMN IF NOT EXISTS parking_google_maps_link TEXT;