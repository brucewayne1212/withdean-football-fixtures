"""
Smart Contact Parser - Extract contact information from various data formats
Handles text, CSV, Excel files with flexible parsing for name, email, and phone
"""

import re
import pandas as pd
from typing import List, Dict, Optional, Any
import io
from dataclasses import dataclass


@dataclass
class ContactInfo:
    """Represents a parsed contact"""
    team_name: str = ""
    contact_name: str = ""
    email: str = ""
    phone: str = ""
    notes: str = ""
    original_text: str = ""
    contact_type: str = "contact"  # "contact" or "coach"
    role: str = ""  # For coaches: Coach, Manager, Assistant Coach, etc.


class ContactParser:
    """Smart parser for extracting contact information from various formats"""
    
    def __init__(self):
        # Email regex pattern
        self.email_pattern = re.compile(
            r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
            re.IGNORECASE
        )
        
        # Phone number patterns (various formats)
        self.phone_patterns = [
            # UK mobile numbers: 07xxx xxxxxx
            re.compile(r'\b(?:\+44\s?)?(?:0)?7\d{3}\s?\d{6}\b'),
            # UK mobile with spaces: 07885 376628
            re.compile(r'\b(?:\+44\s?)?(?:0)?7\d{3}\s?\d{3}\s?\d{3}\b'),
            # UK landline: 01273 123456  
            re.compile(r'\b(?:\+44\s?)?(?:0)?1\d{3}\s?\d{6}\b'),
            # International format: +44 7890 123456
            re.compile(r'\b\+44\s?7\d{3}\s?\d{3}\s?\d{3}\b'),
            # General UK format
            re.compile(r'\b(?:\+44\s?)?(?:0\s?)?(?:1\d{2,4}|2\d|3\d|5\d|6\d|7\d|8\d|9\d)\s?\d{3,4}\s?\d{3,4}\b'),
            # US/Canada format
            re.compile(r'\b(?:\+1\s?)?(?:\(\d{3}\)\s?|\d{3}[-.\s]?)\d{3}[-.\s]?\d{4}\b'),
            # Simple consecutive digits (10-11 digits)
            re.compile(r'\b\d{10,11}\b'),
            # Common separated formats
            re.compile(r'\b\d{3}[-.\s]\d{3}[-.\s]\d{4}\b'),
            re.compile(r'\b\(\d{3}\)\s?\d{3}[-.\s]\d{4}\b'),
        ]
        
        # Common team name patterns
        self.team_patterns = [
            # Standard club formats: "Name FC", "Name United", etc.
            re.compile(r'\b\w+(?:\s+\w+)?\s+(?:FC|United|City|Town|Athletic|Rovers|Wanderers|Albion)\b', re.IGNORECASE),
            # AFC formats: "AFC Name"
            re.compile(r'\b(?:AFC|FC)\s+\w+(?:\s+\w+)?\b', re.IGNORECASE),
            # Age group formats: "U14 Name", "Under 16 Name"
            re.compile(r'\b(?:U\d+|Under\s+\d+)\s+\w+(?:\s+\w+)?\b', re.IGNORECASE),
            # Youth/Junior formats with FC
            re.compile(r'\b\w+(?:\s+\w+)?\s+(?:Youth|Junior|Senior)\s+FC\b', re.IGNORECASE),
            # Animal names (common in youth football)
            re.compile(r'\b\w+(?:\s+\w+)?\s+(?:Hawks?|Eagles?|Lions?|Tigers?|Bears?|Wolves?)\b', re.IGNORECASE),
            # Simple team names that start with typical football words
            re.compile(r'\b(?:AFC|FC|United|Athletic|City|Town|Rovers|Wanderers|Albion)\s+\w+(?:\s+\w+)?\b', re.IGNORECASE),
        ]
    
    def parse_text(self, text: str) -> List[ContactInfo]:
        """Parse contact information from free-form text"""
        contacts = []
        
        print(f"Parsing text of length: {len(text)}")  # Debug
        
        # Split text into potential contact blocks
        # Try different delimiters
        potential_contacts = self._split_text_into_contacts(text)
        print(f"Split into {len(potential_contacts)} potential contact blocks")  # Debug
        
        for contact_text in potential_contacts:
            contact = self._parse_single_contact(contact_text.strip())
            if contact and (contact.email or contact.phone or contact.contact_name or contact.team_name):
                contacts.append(contact)
            else:
                print(f"Rejected contact: {contact_text[:100] if contact_text else 'None'}")  # Debug
        
        return contacts
    
    def parse_csv_file(self, file_content: bytes) -> List[ContactInfo]:
        """Parse contacts from CSV file content"""
        try:
            # Try different encodings
            for encoding in ['utf-8', 'latin-1', 'cp1252']:
                try:
                    text_content = file_content.decode(encoding)
                    break
                except UnicodeDecodeError:
                    continue
            else:
                raise ValueError("Could not decode file with any supported encoding")
            
            # Try to read as CSV
            df = pd.read_csv(io.StringIO(text_content))
            return self._parse_dataframe(df)
            
        except Exception as e:
            # If CSV parsing fails, treat as plain text
            try:
                text_content = file_content.decode('utf-8', errors='ignore')
                return self.parse_text(text_content)
            except:
                raise ValueError(f"Could not parse file: {str(e)}")
    
    def parse_excel_file(self, file_content: bytes) -> List[ContactInfo]:
        """Parse contacts from Excel file content"""
        try:
            # Read Excel file
            df = pd.read_excel(io.BytesIO(file_content))
            return self._parse_dataframe(df)
            
        except Exception as e:
            raise ValueError(f"Could not parse Excel file: {str(e)}")
    
    def _split_text_into_contacts(self, text: str) -> List[str]:
        """Split text into potential contact blocks"""
        # Try different splitting strategies
        
        # Strategy 1: Split by double newlines (paragraph separation)
        if '\n\n' in text:
            blocks = text.split('\n\n')
            if len(blocks) > 1:
                return blocks
        
        # Strategy 2: Split by single newlines if each line might be a contact
        lines = text.split('\n')
        if len(lines) > 1:
            # Check if lines look like individual contacts (contain email or phone)
            contact_lines = []
            for line in lines:
                if line.strip() and (self.email_pattern.search(line) or self._find_phone(line)):
                    contact_lines.append(line)
            
            if contact_lines:
                return contact_lines
        
        # Strategy 3: Split by common separators
        for separator in [';', '|', '\t\t', '---', '===']:
            if separator in text:
                blocks = text.split(separator)
                if len(blocks) > 1:
                    return blocks
        
        # Strategy 4: Return as single block
        return [text]
    
    def _parse_single_contact(self, text: str) -> Optional[ContactInfo]:
        """Parse a single contact from text"""
        if not text.strip():
            return None
        
        contact = ContactInfo(original_text=text)
        
        # Extract email
        email_match = self.email_pattern.search(text)
        if email_match:
            contact.email = email_match.group()
            print(f"Found email: {contact.email}")  # Debug
        
        # Extract phone
        phone = self._find_phone(text)
        if phone:
            contact.phone = phone
            print(f"Found phone: {contact.phone}")  # Debug
        
        # Extract team name
        team_name = self._find_team_name(text)
        if team_name:
            contact.team_name = team_name
            print(f"Found team: {contact.team_name}")  # Debug
        
        # Extract contact name (more complex logic)
        contact_name = self._find_contact_name(text, contact.email)
        if contact_name:
            contact.contact_name = contact_name
            print(f"Found contact name: {contact.contact_name}")  # Debug
        
        # Extract role and determine contact type
        role = self._find_role(text)
        if role:
            contact.role = role
            contact.contact_type = "coach"
            print(f"Found role: {contact.role}")  # Debug
        
        # If no team name found, try to infer from context
        if not contact.team_name and contact.contact_name:
            # Look for team-like words near the contact name
            words = text.split()
            for i, word in enumerate(words):
                if contact.contact_name in ' '.join(words[max(0, i-3):i+4]):
                    # Look for team indicators around this area
                    context = ' '.join(words[max(0, i-5):i+6])
                    team = self._find_team_name(context)
                    if team:
                        contact.team_name = team
                        break
        
        # If we still have no team name but have other info, create a generic team name
        if not contact.team_name and (contact.email or contact.phone or contact.contact_name):
            if contact.contact_name:
                # Try to extract organization from email domain
                if contact.email and '@' in contact.email:
                    domain = contact.email.split('@')[1].split('.')[0]
                    contact.team_name = f"{domain.title()} FC"
                else:
                    contact.team_name = f"{contact.contact_name.split()[0]}'s Team"
            else:
                contact.team_name = "Unknown Team"
        
        return contact
    
    def _find_phone(self, text: str) -> Optional[str]:
        """Find phone number in text"""
        for pattern in self.phone_patterns:
            match = pattern.search(text)
            if match:
                # Clean up the phone number
                phone = re.sub(r'[^\d+]', '', match.group())
                if len(phone) >= 10:  # Minimum reasonable phone number length
                    return match.group().strip()
        return None
    
    def _find_team_name(self, text: str) -> Optional[str]:
        """Find team name in text"""
        # Clean up text first - remove extra whitespace
        text = ' '.join(text.split())
        
        for pattern in self.team_patterns:
            match = pattern.search(text)
            if match:
                team_name = match.group().strip()
                # Clean up team name to avoid including person names
                words = team_name.split()
                
                # For AFC/FC patterns that might capture too much, be more precise
                if len(words) >= 3 and words[0].upper() in ['AFC', 'FC']:
                    # AFC LANGNEY Gavin -> AFC LANGNEY
                    remaining_text = text[match.end():].strip()
                    if remaining_text and self._looks_like_person_name(remaining_text.split()[0] if remaining_text.split() else ""):
                        team_name = ' '.join(words[:2])  # Take just AFC + next word
                
                return team_name
        
        # Look for other team indicators with better word boundary detection
        team_keywords = ['fc', 'football club', 'youth', 'junior', 'senior', 'academy', 'hawks', 'eagles', 'united', 'city', 'afc']
        words = text.lower().split()
        
        for i, word in enumerate(words):
            if word in team_keywords:
                if word == 'afc' and i + 1 < len(words):
                    # AFC usually comes first: "AFC Langney"
                    team_name = f"AFC {words[i + 1].title()}"
                    return team_name
                elif word in ['fc', 'united', 'city', 'hawks', 'eagles'] and i > 0:
                    # These usually come after: "Brighton Hawks"
                    start = max(0, i - 1)
                    potential_team = ' '.join(words[start:i + 1])
                    potential_team = potential_team.title()
                    if len(potential_team) > 3 and len(potential_team) < 50:
                        return potential_team
        
        return None
    
    def _looks_like_person_name(self, word: str) -> bool:
        """Check if a word looks like a person's first name"""
        # Simple heuristic: capitalized word that's not a common team word
        team_words = ['fc', 'united', 'city', 'town', 'athletic', 'rovers', 'wanderers', 'albion', 'hawks', 'eagles', 'lions', 'tigers']
        return word and word[0].isupper() and word.lower() not in team_words
    
    def _find_role(self, text: str) -> Optional[str]:
        """Find role/position in text"""
        role_patterns = [
            # Direct role mentions
            re.compile(r'\b(coach|manager|assistant coach|head coach|team manager|secretary|trainer)\b', re.IGNORECASE),
            # Prefixed role mentions
            re.compile(r'(?:role|position|title):\s*([a-z\s]+)', re.IGNORECASE),
            # Common coaching phrases
            re.compile(r'\b(coaching|managing|training)\s+([a-z\s]+)', re.IGNORECASE),
        ]
        
        for pattern in role_patterns:
            match = pattern.search(text)
            if match:
                role = match.group(1).strip().title()
                # Normalize common roles
                role_mapping = {
                    'Manager': 'Manager',
                    'Coach': 'Coach', 
                    'Assistant Coach': 'Assistant Coach',
                    'Head Coach': 'Head Coach',
                    'Team Manager': 'Team Manager',
                    'Secretary': 'Secretary',
                    'Trainer': 'Coach'
                }
                return role_mapping.get(role, role)
        
        return None
    
    def _find_contact_name(self, text: str, email: str = "") -> Optional[str]:
        """Find contact person name in text"""
        # Remove email and phone to focus on names
        clean_text = text
        if email:
            clean_text = clean_text.replace(email, "")
        
        phone = self._find_phone(text)
        if phone:
            clean_text = clean_text.replace(phone, "")
        
        # Look for name patterns
        name_patterns = [
            re.compile(r'\b[A-Z][a-z]+\s+[A-Z][a-z]+\b'),  # First Last
            re.compile(r'\b[A-Z][a-z]+\s+[A-Z]\.\s+[A-Z][a-z]+\b'),  # First M. Last
            re.compile(r'\b[A-Z]\.\s+[A-Z][a-z]+\b'),  # F. Last
        ]
        
        for pattern in name_patterns:
            matches = pattern.findall(clean_text)
            for match in matches:
                # Validate that it's not a team name or other non-name text
                if not any(keyword in match.lower() for keyword in ['fc', 'football', 'united', 'city', 'youth']):
                    return match.strip()
        
        # Look for "Contact:" or "Manager:" prefixed names
        contact_prefix_pattern = re.compile(r'(?:contact|manager|secretary|coach):\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)', re.IGNORECASE)
        match = contact_prefix_pattern.search(clean_text)
        if match:
            return match.group(1).strip()
        
        return None
    
    def _parse_dataframe(self, df: pd.DataFrame) -> List[ContactInfo]:
        """Parse contacts from a pandas DataFrame (CSV/Excel)"""
        contacts = []
        
        # Normalize column names for easier matching
        df.columns = [str(col).lower().strip() for col in df.columns]
        
        # Create column mappings
        col_mappings = {
            'team': self._find_column(df.columns, ['team', 'club', 'team name', 'club name', 'organisation']),
            'name': self._find_column(df.columns, ['name', 'contact', 'contact name', 'manager', 'person']),
            'email': self._find_column(df.columns, ['email', 'e-mail', 'email address', 'mail']),
            'phone': self._find_column(df.columns, ['phone', 'telephone', 'mobile', 'cell', 'number', 'phone number']),
            'notes': self._find_column(df.columns, ['notes', 'comments', 'remarks', 'additional info'])
        }
        
        for index, row in df.iterrows():
            contact = ContactInfo()
            
            # Extract data from mapped columns
            if col_mappings['team']:
                contact.team_name = str(row[col_mappings['team']]) if pd.notna(row[col_mappings['team']]) else ""
            
            if col_mappings['name']:
                contact.contact_name = str(row[col_mappings['name']]) if pd.notna(row[col_mappings['name']]) else ""
            
            if col_mappings['email']:
                contact.email = str(row[col_mappings['email']]) if pd.notna(row[col_mappings['email']]) else ""
            
            if col_mappings['phone']:
                contact.phone = str(row[col_mappings['phone']]) if pd.notna(row[col_mappings['phone']]) else ""
            
            if col_mappings['notes']:
                contact.notes = str(row[col_mappings['notes']]) if pd.notna(row[col_mappings['notes']]) else ""
            
            # If no clear column mapping, try to extract from all text in the row
            if not any([contact.team_name, contact.contact_name, contact.email, contact.phone]):
                row_text = ' '.join([str(val) for val in row.values if pd.notna(val)])
                parsed_contact = self._parse_single_contact(row_text)
                if parsed_contact:
                    contact = parsed_contact
            
            # Validate email format
            if contact.email and not self.email_pattern.match(contact.email):
                # Try to extract email from the text
                email_match = self.email_pattern.search(contact.email)
                if email_match:
                    contact.email = email_match.group()
                else:
                    contact.email = ""
            
            # Clean up phone number
            if contact.phone:
                contact.phone = re.sub(r'[^\d+()-.\s]', '', str(contact.phone))
            
            # Only add if we have at least some useful information
            if contact.team_name or contact.contact_name or contact.email or contact.phone:
                contacts.append(contact)
        
        return contacts
    
    def _find_column(self, columns: List[str], keywords: List[str]) -> Optional[str]:
        """Find the best matching column for given keywords"""
        for keyword in keywords:
            for col in columns:
                if keyword in col:
                    return col
        return None