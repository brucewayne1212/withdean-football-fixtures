# How to Download Google Sheets as CSV

Since your weekly fixtures come as a locked Google Sheet, here's the easiest way to get the data into the app:

## Method 1: Direct Download (Recommended)

1. **Open the Google Sheet** in your browser
2. **Go to File → Download → Comma Separated Values (.csv)**
3. **Save the file** to your computer (e.g., `fixtures_2024_week_1.csv`)
4. **Run the workflow app** and import this CSV file

## Method 2: Copy the Link

1. **Get the sharing link** from the Google Sheet
2. **Replace `/edit` with `/export?format=csv`** in the URL
3. **Open this modified URL** in your browser - it will automatically download the CSV

### Example:
- Original: `https://docs.google.com/spreadsheets/d/ABC123/edit#gid=0`
- Modified: `https://docs.google.com/spreadsheets/d/ABC123/export?format=csv`

## Weekly Workflow

1. **Monday/Tuesday**: Download the new fixtures CSV from Google Sheets
2. **Run the workflow app**: `python workflow_app.py`
3. **Import fixtures**: This creates your weekly tasks automatically
4. **Home games**: Generate and send emails to opposition
5. **Away games**: Wait for opposition emails, then forward to your teams
6. **Check off completed tasks** as you go

## File Naming Suggestion

Save your CSV files with consistent names like:
- `fixtures_2024_week_01.csv`
- `fixtures_2024_week_02.csv`
- etc.

This makes it easy to find the right file each week and keeps your downloads organized.