"""
Location-based post-filtering for job search results.

This module provides functionality to filter job search results to only include
jobs physically located within a specified radius of a search center, excluding
remote positions from distant locations.
"""

import re
from typing import Dict, List, Optional, Tuple
import pandas as pd
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)

@dataclass
class LocationFilter:
    """Configuration for location-based filtering"""
    center_city: str
    center_state: str
    center_zip: str
    radius_miles: float = 50.0
    
    # Known cities within radius (populated dynamically based on state)
    valid_cities: Optional[List[str]] = None
    
    def __post_init__(self):
        """Initialize valid cities based on center location"""
        if self.valid_cities is None:
            self.valid_cities = self._get_nearby_cities()
    
    def _get_nearby_cities(self) -> List[str]:
        """Get list of cities within radius based on center location"""
        # This is a simplified version - in production, we'd use a proper
        # geographic database or API
        nearby_cities_by_region = {
            ('greenville', 'sc'): [
                # South Carolina cities
                'greenville', 'spartanburg', 'anderson', 'clemson', 'easley',
                'greer', 'mauldin', 'simpsonville', 'fountain inn', 'travelers rest',
                'pickens', 'liberty', 'belton', 'marietta', 'duncan', 'laurens',
                'clinton', 'union', 'woodruff', 'inman', 'boiling springs',
                'campobello', 'chesnee', 'cowpens', 'gaffney', 'landrum', 'lyman',
                'moore', 'pacolet', 'roebuck', 'wellford', 'mayo', 'reidville',
                'taylors', 'piedmont', 'pelzer', 'williamston', 'honea path',
                'ware shoals', 'donalds', 'due west', 'iva', 'starr', 'abbeville',
                'calhoun falls', 'central', 'norris', 'six mile', 'seneca',
                'walhalla', 'westminster', 'salem', 'tamassee', 'fair play',
                'townville', 'sandy springs', 'pendleton', 'greenwood', 'conestee'
            ],
            ('columbia', 'sc'): [
                'columbia', 'lexington', 'west columbia', 'cayce', 'forest acres',
                'irmo', 'chapin', 'blythewood', 'elgin', 'hopkins', 'eastover',
                'gadsden', 'swansea', 'gaston', 'pelion', 'gilbert', 'leesville',
                'batesburg', 'ridge spring', 'monetta', 'wagener', 'salley',
                'springdale', 'oak grove', 'red bank', 'dentsville', 'arcadia lakes',
                'winnsboro', 'ridgeway', 'blair', 'jenkinsville', 'pomaria',
                'little mountain', 'prosperity', 'newberry', 'whitmire', 'peak'
            ],
            ('charlotte', 'nc'): [
                'charlotte', 'concord', 'gastonia', 'rock hill', 'huntersville',
                'kannapolis', 'monroe', 'matthews', 'mint hill', 'indian trail',
                'fort mill', 'tega cay', 'pineville', 'belmont', 'mount holly',
                'cornelius', 'davidson', 'mooresville', 'lincolnton', 'shelby',
                'kings mountain', 'cherryville', 'stanley', 'cramerton', 'lowell',
                'mcadenville', 'ranlo', 'dallas', 'bessemer city', 'clover',
                'york', 'chester', 'lancaster', 'waxhaw', 'weddington', 'wesley chapel',
                'unionville', 'marshville', 'wingate', 'locust', 'midland', 'harrisburg'
            ],
            ('atlanta', 'ga'): [
                'atlanta', 'marietta', 'roswell', 'alpharetta', 'sandy springs',
                'johns creek', 'dunwoody', 'peachtree corners', 'lawrenceville',
                'duluth', 'suwanee', 'norcross', 'tucker', 'stone mountain',
                'decatur', 'avondale estates', 'east point', 'college park',
                'forest park', 'riverdale', 'jonesboro', 'mcdonough', 'stockbridge',
                'conyers', 'covington', 'lithonia', 'redan', 'clarkston',
                'chamblee', 'doraville', 'brookhaven', 'smyrna', 'vinings',
                'mableton', 'austell', 'powder springs', 'kennesaw', 'acworth',
                'woodstock', 'canton', 'holly springs', 'cumming', 'buford'
            ]
        }
        
        # Look up based on center city and state
        key = (self.center_city.lower(), self.center_state.lower())
        
        # First try exact match
        if key in nearby_cities_by_region:
            cities = nearby_cities_by_region[key]
        else:
            # Try to find a close match
            for region_key, cities_list in nearby_cities_by_region.items():
                if region_key[1] == key[1]:  # Same state
                    cities = cities_list
                    break
            else:
                # Default to empty list if no match found
                cities = []
                logger.warning(f"No predefined city list for {self.center_city}, {self.center_state}")
        
        # Also add nearby cities from neighboring states
        nearby_states = self._get_nearby_states()
        return cities + nearby_states
    
    def _get_nearby_states(self) -> List[str]:
        """Get cities from nearby states that might be within radius"""
        nearby_by_state = {
            'sc': {
                'nc': ['hendersonville', 'brevard', 'flat rock', 'saluda', 'columbus',
                       'tryon', 'mill spring', 'zirconia', 'tuxedo', 'edneyville',
                       'dana', 'fletcher', 'mountain home', 'etowah', 'horse shoe',
                       'mills river', 'penrose', 'pisgah forest', 'rosman',
                       'cedar mountain', 'lake toxaway'],
                'ga': ['toccoa', 'lavonia', 'carnesville', 'franklin springs',
                       'canon', 'royston', 'martin', 'hartwell', 'bowersville',
                       'bowman', 'comer', 'commerce', 'jefferson', 'athens']
            },
            'nc': {
                'sc': ['rock hill', 'fort mill', 'tega cay', 'clover', 'york',
                       'chester', 'lancaster', 'pageland', 'chesterfield'],
                'va': ['danville', 'martinsville', 'south boston'],
                'tn': ['johnson city', 'kingsport', 'bristol']
            },
            'ga': {
                'sc': ['aiken', 'north augusta', 'edgefield', 'johnston', 'trenton',
                       'mccormick', 'anderson', 'abbeville', 'greenwood'],
                'fl': ['jacksonville', 'fernandina beach', 'yulee'],
                'al': ['phenix city', 'columbus', 'valley', 'lanett'],
                'tn': ['chattanooga', 'east ridge', 'red bank', 'signal mountain']
            }
        }
        
        nearby = []
        state = self.center_state.lower()
        if state in nearby_by_state:
            for neighbor_state, cities in nearby_by_state[state].items():
                nearby.extend(cities)
        
        return nearby


def filter_jobs_by_location(
    df: pd.DataFrame,
    location_filter: LocationFilter,
    location_column: str = 'location'
) -> Tuple[pd.DataFrame, pd.DataFrame, Dict[str, any]]:
    """
    Filter job DataFrame to only include jobs within specified radius.
    
    Args:
        df: DataFrame with job data
        location_filter: Configuration for location filtering
        location_column: Name of column containing location data
        
    Returns:
        Tuple of (filtered_df, excluded_df, stats_dict)
    """
    if location_column not in df.columns:
        logger.warning(f"Location column '{location_column}' not found in DataFrame")
        return df, pd.DataFrame(), {'error': 'No location column'}
    
    # Create patterns for valid locations
    valid_patterns = []
    
    # Add patterns for each valid city
    for city in location_filter.valid_cities:
        # Match "City, ST" or "City ST" patterns
        valid_patterns.append(rf'\b{re.escape(city)}\b.*\b{location_filter.center_state}\b')
    
    # Add pattern for generic state matches (but exclude far cities)
    far_cities_by_state = {
        'sc': ['columbia', 'charleston', 'myrtle beach', 'florence', 'sumter',
               'rock hill', 'hilton head', 'beaufort', 'georgetown', 'orangeburg',
               'aiken', 'summerville', 'mount pleasant', 'north charleston'],
        'nc': ['raleigh', 'durham', 'greensboro', 'winston-salem', 'wilmington',
               'asheville', 'fayetteville', 'cary', 'high point', 'greenville',
               'jacksonville', 'new bern', 'rocky mount', 'wilson', 'goldsboro'],
        'ga': ['savannah', 'augusta', 'columbus', 'macon', 'albany', 'valdosta',
               'warner robins', 'rome', 'brunswick', 'dublin', 'hinesville',
               'statesboro', 'newnan', 'douglasville', 'lagrange', 'griffin']
    }
    
    def is_valid_location(location: str) -> bool:
        """Check if location is within valid area"""
        if pd.isna(location):
            return False
        
        location_str = str(location).lower()
        
        # Check against valid city patterns
        for pattern in valid_patterns:
            if re.search(pattern, location_str, re.IGNORECASE):
                # Make sure it's not a far city
                state = location_filter.center_state.lower()
                if state in far_cities_by_state:
                    for far_city in far_cities_by_state[state]:
                        if far_city in location_str:
                            return False
                return True
        
        # Check for generic state location (e.g., "South Carolina, United States")
        if location_filter.center_state.lower() in location_str:
            # Make sure it's not in a far city
            state = location_filter.center_state.lower()
            if state in far_cities_by_state:
                for far_city in far_cities_by_state[state]:
                    if far_city in location_str:
                        return False
            # Check if it's a generic state-wide posting
            if re.search(rf'\b{location_filter.center_state}\b.*united states', location_str, re.IGNORECASE):
                return False  # Skip generic state-wide postings
            return True
        
        return False
    
    # Apply filter
    logger.info(f"Filtering {len(df)} jobs by location...")
    df['is_local'] = df[location_column].apply(is_valid_location)
    
    # Split data
    df_local = df[df['is_local']].copy()
    df_excluded = df[~df['is_local']].copy()
    
    # Remove temporary column
    df_local = df_local.drop('is_local', axis=1)
    df_excluded = df_excluded.drop('is_local', axis=1)
    
    # Calculate statistics
    stats = {
        'total_jobs': len(df),
        'local_jobs': len(df_local),
        'excluded_jobs': len(df_excluded),
        'local_percentage': len(df_local) / len(df) * 100 if len(df) > 0 else 0,
        'excluded_percentage': len(df_excluded) / len(df) * 100 if len(df) > 0 else 0,
    }
    
    # Add salary statistics
    if 'min_amount' in df.columns:
        stats['total_with_salary'] = df['min_amount'].notna().sum()
        stats['local_with_salary'] = df_local['min_amount'].notna().sum()
        stats['excluded_with_salary'] = df_excluded['min_amount'].notna().sum()
        
        if len(df_local) > 0:
            local_salary_data = df_local[df_local['min_amount'].notna()]
            if len(local_salary_data) > 0:
                stats['local_median_salary'] = local_salary_data['min_amount'].median()
                stats['local_mean_salary'] = local_salary_data['min_amount'].mean()
    
    logger.info(f"Location filter: kept {stats['local_jobs']}/{stats['total_jobs']} jobs "
                f"({stats['local_percentage']:.1f}% local)")
    
    return df_local, df_excluded, stats