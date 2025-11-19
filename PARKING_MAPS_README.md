# Parking Maps Feature

This feature adds support for separate parking locations with dedicated map images and links for emails.

## Features

### Current (Post-Migration)
- **Dual-marker maps**: Shows both pitch (⚽) and parking (🅿️) locations on the same map when addresses differ
- **Separate parking maps**: Individual map images and Google Maps links for parking locations
- **Smart address detection**: Automatically generates separate parking maps only when parking address differs from pitch address
- **Enhanced preview**: Shows both main map and parking-only map in the pitch configuration modal

### Current (Pre-Migration)
- ✅ Parking address field added to pitch forms
- ✅ Dual-marker map generation (pitch + parking on same map)
- ✅ Enhanced preview UI with parking address support
- ❌ Separate parking map images (requires database migration)
- ❌ Separate parking Google Maps links (requires database migration)

## Files Modified

### Database Schema
- `models.py`: Added `parking_map_image_url` and `parking_google_maps_link` fields (commented out until migration)
- `add_parking_map_fields.sql`: Migration script to add new database columns
- `migrate_parking_maps.py`: Python migration script with instructions

### Backend Logic
- `app.py`:
  - Updated pitch saving to generate parking-specific maps
  - Enhanced preview API to return parking map data
  - Modified get_pitch_config to include parking map fields

### Frontend
- `templates/settings.html`:
  - Added parking address input field
  - Enhanced map preview with dual-column layout (main + parking maps)
  - Updated JavaScript to handle parking address in preview and edit functions

## How It Works

1. **Address Input**: User enters both pitch address and parking address (optional)

2. **Map Generation Logic**:
   - If parking address is empty or same as pitch address: Generate single map with pitch marker
   - If parking address differs: Generate dual-marker map + separate parking map

3. **Email Integration**:
   - Main map shows where to play (with parking info if different)
   - Separate parking map shows exactly where to park

## Migration Steps

### Step 1: Run Database Migration
```bash
# Set DATABASE_URL environment variable first
export DATABASE_URL="your_database_connection_string"

# Run migration
python migrate_parking_maps.py
```

### Step 2: Uncomment Code
After successful migration:

1. **models.py** (lines 133-134):
```python
# Uncomment these lines:
parking_map_image_url = Column(Text)  # URL to parking map image for emails
parking_google_maps_link = Column(Text)  # Link to parking location on Google Maps
```

2. **app.py** - Search for "TODO: Uncomment after running database migration" and uncomment:
   - Pitch saving logic (lines ~1666-1667, ~1684-1685)
   - API response fields (lines ~1732-1733)
   - Preview API parking map generation (lines ~1970-1980)

### Step 3: Restart Application
```bash
# Restart Flask application to pick up model changes
```

## Testing

After migration:

1. **Add New Pitch**:
   - Enter pitch address: "123 Football Ground, City"
   - Enter parking address: "456 Parking Lot, City"
   - Click "Preview Map"
   - Should see both main map (dual markers) and parking map (single marker)

2. **Edit Existing Pitch**:
   - Edit a pitch configuration
   - Add different parking address
   - Verify both parking fields populate correctly

3. **Email Generation**:
   - Generate fixture emails
   - Should include both map images when parking differs from pitch

## Troubleshooting

### Migration Issues
- Ensure DATABASE_URL is set correctly
- Check database permissions
- Verify PostgreSQL is accessible

### Map Preview Issues
- Check Google Maps API key configuration
- Verify network connectivity
- Check browser console for JavaScript errors

### Field Not Saving
- Ensure migration completed successfully
- Verify all TODO comments are uncommented
- Check server logs for database errors

## Technical Details

### Database Schema Changes
```sql
ALTER TABLE pitches ADD COLUMN IF NOT EXISTS parking_map_image_url TEXT;
ALTER TABLE pitches ADD COLUMN IF NOT EXISTS parking_google_maps_link TEXT;
```

### Map Generation Logic
```python
# Main map: includes both locations if different
map_image_url = generate_google_maps_url(address, api_key, parking_address)

# Parking-only map: single parking location
if parking_address != address:
    parking_map_image_url = generate_google_maps_url(parking_address, api_key)
```

This feature enhances the user experience by providing clear, separate information about where to play and where to park, reducing confusion for teams and families attending matches.