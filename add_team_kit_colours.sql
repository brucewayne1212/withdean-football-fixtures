-- Add kit colours columns to teams table
ALTER TABLE teams
ADD COLUMN home_shirt VARCHAR(255),
ADD COLUMN home_shorts VARCHAR(255),
ADD COLUMN home_socks VARCHAR(255),
ADD COLUMN away_shirt VARCHAR(255),
ADD COLUMN away_shorts VARCHAR(255),
ADD COLUMN away_socks VARCHAR(255);
