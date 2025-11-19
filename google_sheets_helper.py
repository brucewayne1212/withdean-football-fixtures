"""
Google Sheets Helper Module
Handles fetching data from Google Sheets using the Sheets API or CSV export
"""

import re
import pandas as pd
import requests
from typing import Optional, Dict, List
from urllib.parse import urlparse, parse_qs

class GoogleSheetsImporter:
    """Helper class to import data from Google Sheets"""

    def __init__(self):
        pass

    def extract_sheet_id(self, url: str) -> Optional[str]:
        """Extract Google Sheets ID from URL"""
        # Match various Google Sheets URL formats
        patterns = [
            r'/spreadsheets/d/([a-zA-Z0-9-_]+)',
            r'key=([a-zA-Z0-9-_]+)',
            r'id=([a-zA-Z0-9-_]+)'
        ]

        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)

        return None

    def extract_gid(self, url: str) -> Optional[str]:
        """Extract sheet GID (sheet tab ID) from URL"""
        # Look for gid parameter in URL
        try:
            parsed = urlparse(url)
            if parsed.fragment:
                # Handle fragment-based gid (e.g., #gid=123456)
                if 'gid=' in parsed.fragment:
                    gid = parsed.fragment.split('gid=')[1].split('&')[0]
                    return gid

            if parsed.query:
                # Handle query-based gid
                query_params = parse_qs(parsed.query)
                if 'gid' in query_params:
                    return query_params['gid'][0]
        except:
            pass

        return '0'  # Default to first sheet

    def fetch_sheet_as_csv(self, sheet_url: str) -> Optional[pd.DataFrame]:
        """
        Fetch Google Sheets data as CSV
        Works for public sheets or sheets shared with 'Anyone with the link'
        """
        try:
            sheet_id = self.extract_sheet_id(sheet_url)
            if not sheet_id:
                raise ValueError("Could not extract sheet ID from URL")

            gid = self.extract_gid(sheet_url)

            # Construct CSV export URL
            csv_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv&gid={gid}"

            # Fetch the CSV data
            response = requests.get(csv_url, timeout=30)
            response.raise_for_status()

            # Check if we got actual CSV data or an error page
            if 'text/csv' not in response.headers.get('content-type', ''):
                # Might be a permission error or private sheet
                if 'sign in' in response.text.lower() or 'private' in response.text.lower():
                    raise ValueError("Sheet appears to be private. Please ensure it's shared with 'Anyone with the link' can view.")
                else:
                    raise ValueError("Failed to fetch CSV data from sheet")

            # Parse CSV into DataFrame
            from io import StringIO
            csv_data = StringIO(response.text)
            df = pd.read_csv(csv_data)

            return df

        except requests.exceptions.RequestException as e:
            raise ValueError(f"Network error fetching sheet: {str(e)}")
        except pd.errors.EmptyDataError:
            raise ValueError("Sheet appears to be empty")
        except Exception as e:
            raise ValueError(f"Error processing sheet: {str(e)}")

    def convert_to_fixture_format(self, df: pd.DataFrame) -> str:
        """
        Convert DataFrame to the expected fixture text format
        This should match the format expected by the existing text_fixture_parser
        """
        try:
            # Clean the DataFrame
            df = df.dropna(how='all')  # Remove completely empty rows
            df = df.fillna('')  # Fill NaN values with empty strings

            # Convert back to CSV string format for the text parser
            from io import StringIO
            output = StringIO()
            df.to_csv(output, index=False, lineterminator='\n')
            csv_string = output.getvalue()

            return csv_string.strip()

        except Exception as e:
            raise ValueError(f"Error converting sheet data: {str(e)}")

    def validate_sheet_format(self, df: pd.DataFrame) -> Dict[str, any]:
        """
        Validate that the sheet has the expected columns for fixtures
        Returns validation results and suggestions
        """
        if df.empty:
            return {
                'valid': False,
                'error': 'Sheet is empty',
                'suggestions': []
            }

        # Get column names (case-insensitive matching)
        columns = [col.lower().strip() for col in df.columns]

        # Common fixture-related column patterns
        expected_patterns = {
            'team': ['team', 'our team', 'home team', 'club'],
            'opposition': ['opposition', 'away team', 'opponent', 'vs'],
            'date': ['date', 'kick off', 'kickoff', 'time'],
            'venue': ['venue', 'pitch', 'ground', 'location'],
            'home_away': ['home/away', 'h/a', 'venue type']
        }

        found_columns = {}
        suggestions = []

        for category, patterns in expected_patterns.items():
            found = False
            for pattern in patterns:
                for col in columns:
                    if pattern in col:
                        found_columns[category] = col
                        found = True
                        break
                if found:
                    break

            if not found:
                suggestions.append(f"Consider adding a column for {category} (e.g., {patterns[0]})")

        return {
            'valid': len(found_columns) >= 2,  # At least team and opposition or date
            'found_columns': found_columns,
            'suggestions': suggestions,
            'total_rows': len(df),
            'sample_data': df.head(3).to_dict('records') if len(df) > 0 else []
        }

def test_google_sheets_url(url: str) -> Dict[str, any]:
    """
    Test function to validate a Google Sheets URL and return info about it
    """
    importer = GoogleSheetsImporter()

    try:
        # Extract sheet ID
        sheet_id = importer.extract_sheet_id(url)
        if not sheet_id:
            return {
                'success': False,
                'error': 'Invalid Google Sheets URL format'
            }

        # Try to fetch the data
        df = importer.fetch_sheet_as_csv(url)
        validation = importer.validate_sheet_format(df)

        return {
            'success': True,
            'sheet_id': sheet_id,
            'validation': validation
        }

    except Exception as e:
        return {
            'success': False,
            'error': str(e)
        }