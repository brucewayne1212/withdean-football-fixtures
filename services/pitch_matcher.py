from sqlalchemy import func
from models import Pitch, PitchAlias
import logging

logger = logging.getLogger(__name__)

class PitchMatcher:
    def __init__(self, session, organization_id):
        self.session = session
        self.organization_id = organization_id
        self._pitches = None
        self._aliases = None

    def _load_data(self):
        if self._pitches is None:
            self._pitches = self.session.query(Pitch).filter_by(organization_id=self.organization_id).all()
        
        # We don't preload aliases as we query them by name, but we could optimize later
        pass

    def match_pitch(self, pitch_name):
        """
        Match a pitch name to a database Pitch object.
        Returns: (Pitch object or None, match_type string, confidence score)
        match_type: 'alias', 'exact', 'partial', 'fuzzy', 'default', or None
        """
        if not pitch_name:
            return None, None, 0

        pitch_name = pitch_name.strip()
        pitch_lower = pitch_name.lower()

        # 1. Check for Alias Match
        alias_match = self.session.query(PitchAlias).filter(
            PitchAlias.organization_id == self.organization_id,
            func.lower(PitchAlias.alias) == pitch_lower
        ).first()
        
        if alias_match:
            pitch = self.session.query(Pitch).get(alias_match.pitch_id)
            if pitch:
                return pitch, 'alias', 100

        # Load pitches if not loaded
        self._load_data()

        exact_match = None
        partial_match = None
        fuzzy_matches = []

        for p in self._pitches:
            pitch_db_lower = p.name.lower().strip()

            # 2. Exact match
            if pitch_db_lower == pitch_lower:
                return p, 'exact', 100

            # 3. Partial match
            if pitch_db_lower in pitch_lower or pitch_lower in pitch_db_lower:
                partial_match = p
                continue

            # 4. Fuzzy matching
            p_words = set(pitch_db_lower.split())
            fixture_words = set(pitch_lower.split())
            word_intersect = p_words.intersection(fixture_words)

            if word_intersect and len(word_intersect) >= max(1, min(len(p_words), len(fixture_words)) * 0.5):
                fuzzy_matches.append((p, len(word_intersect)))

        # Special case: check for common abbreviations
        if not partial_match:
            # "3G" might be written as "3G", "3g", etc.
            if "3g" in pitch_lower:
                 for p in self._pitches:
                     if "3g" in p.name.lower():
                         partial_match = p
                         break
            
            # "College" might be written as "Coll", "Col", etc.
            if any(word in pitch_lower for word in ["college", "coll", "col"]):
                for p in self._pitches:
                    p_lower = p.name.lower()
                    if any(word in p_lower for word in ["college", "coll", "col"]):
                        partial_match = p
                        break

        # Select best match
        if partial_match:
            return partial_match, 'partial', 80
        
        if fuzzy_matches:
            # Sort by number of matching words (descending)
            fuzzy_matches.sort(key=lambda x: x[1], reverse=True)
            return fuzzy_matches[0][0], 'fuzzy', 60

        return None, None, 0

    def find_default_home_pitch(self):
        """Find a default pitch for home games (e.g. Withdean)"""
        default_pitches = ['3g', 'withdean', 'stanley deason', 'balfour', 'dorothy stringer', 'varndean']
        for dp in default_pitches:
            default_pitch = self.session.query(Pitch).filter(
                Pitch.organization_id == self.organization_id,
                Pitch.name.ilike(f'%{dp}%')
            ).first()
            if default_pitch:
                return default_pitch
        return None
