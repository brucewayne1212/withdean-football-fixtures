import pandas as pd
from typing import List, Dict, Optional
import os

class FixtureParser:
    def __init__(self):
        self.column_mapping = {
            0: 'Team',  # First column without header
            1: 'League/Division',
            2: 'Home Manager',
            3: 'Fixtures Sec',
            4: 'Opposition',
            5: 'Home/Away',
            6: 'Pitch',
            7: 'KO&Finish time',
            8: 'Further Instructions for Withdean Management',
            9: 'Format',
            10: 'Each Way',
            11: 'Fixture Length',
            12: 'Referee?',
            13: 'Home Manager Mobile',
            14: 'Home Team Contact 1',
            15: 'Home Team Contact 2',
            16: 'Home Team Contact 3',
            17: 'Home Team Contact 5',
            18: 'Home Team Contact 6',
            19: 'Home Team Contact 7'
        }
    
    def read_spreadsheet(self, file_path: str) -> pd.DataFrame:
        """Read spreadsheet and apply proper column names"""
        try:
            if file_path.endswith('.csv'):
                df = pd.read_csv(file_path, header=None)
            else:
                df = pd.read_excel(file_path, header=None)
            
            # Rename columns using our mapping
            df = df.rename(columns=self.column_mapping)
            
            # Remove any completely empty rows
            df = df.dropna(how='all')
            
            return df
        except Exception as e:
            print(f"Error reading file: {e}")
            return pd.DataFrame()
    
    def filter_teams(self, df: pd.DataFrame, managed_teams: List[str], manager_name: str = None) -> pd.DataFrame:
        """Filter dataframe for only managed teams or teams managed by specific person"""
        if df.empty:
            return df
        
        # Method 1: Filter by team names
        managed_teams_lower = [team.lower().strip() for team in managed_teams]
        # Handle NaN values in Team column safely
        team_names_safe = df['Team'].fillna('').astype(str)
        team_name_mask = team_names_safe.str.lower().str.strip().isin(managed_teams_lower)
        
        # Method 2: Filter by manager name in Fixtures Sec column (if provided)
        if manager_name:
            # Handle NaN values safely
            fixtures_sec_safe = df['Fixtures Sec'].fillna('').astype(str)
            manager_mask = fixtures_sec_safe.str.contains(manager_name, case=False, na=False)
            # Combine both filters with OR logic
            combined_mask = team_name_mask | manager_mask
        else:
            combined_mask = team_name_mask
        
        return df[combined_mask].copy()
    
    def get_fixture_data(self, df: pd.DataFrame) -> List[Dict]:
        """Convert filtered dataframe to list of fixture dictionaries"""
        fixtures = []
        
        for _, row in df.iterrows():
            # Clean and process the data
            fixture = {
                'team': self._clean_value(row['Team']),
                'league': self._clean_value(row['League/Division']),
                'home_manager': self._clean_value(row['Home Manager']),
                'fixtures_sec': self._clean_value(row['Fixtures Sec']),
                'opposition': self._clean_value(row['Opposition']),
                'home_away': self._clean_value(row['Home/Away']),
                'pitch': self._clean_value(row['Pitch']),
                'kickoff_time': self._clean_value(row['KO&Finish time']),
                'instructions': self._clean_value(row['Further Instructions for Withdean Management']),
                'format': self._clean_value(row['Format']),
                'each_way': self._clean_value(row['Each Way']),
                'fixture_length': self._clean_value(row['Fixture Length']),
                'referee': self._clean_value(row['Referee?']),
                'manager_mobile': self._clean_value(row['Home Manager Mobile']),
                'contact_1': self._clean_value(row['Home Team Contact 1']),
                'contact_2': self._clean_value(row['Home Team Contact 2']),
                'contact_3': self._clean_value(row['Home Team Contact 3']),
                'contact_5': self._clean_value(row['Home Team Contact 5']),
                'contact_6': self._clean_value(row['Home Team Contact 6']),
                'contact_7': self._clean_value(row['Home Team Contact 7'])
            }
            fixtures.append(fixture)
        
        return fixtures
    
    def _clean_value(self, value):
        """Clean and standardize a value from the spreadsheet"""
        if value is None or str(value).lower().strip() in ['nan', 'none', '']:
            return None
        return str(value).strip()

if __name__ == "__main__":
    parser = FixtureParser()
    
    # Example usage (will be updated based on user requirements)
    managed_teams = []  # To be filled with actual team names
    
    print("Fixture Parser initialized successfully!")
    print("Ready to process spreadsheet files.")