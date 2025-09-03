"""Configuration loader for market analysis tool."""

import yaml
from pathlib import Path
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field


@dataclass
class Location:
    """Represents a single location to search."""
    name: str
    address: str
    zip_code: str
    market: str = ""
    region: str = ""


@dataclass
class Region:
    """Represents a region containing multiple locations."""
    name: str
    locations: List[Location] = field(default_factory=list)


@dataclass
class Market:
    """Represents a market containing multiple regions."""
    name: str
    regions: List[Region] = field(default_factory=list)
    
    @property
    def all_locations(self) -> List[Location]:
        """Get all locations in this market."""
        locations = []
        for region in self.regions:
            locations.extend(region.locations)
        return locations


@dataclass
class Config:
    """Complete configuration for market analysis."""
    job_title: str
    search_radius: int = 25
    results_per_location: int = 200
    batch_size: int = 5
    markets: List[Market] = field(default_factory=list)
    
    @property
    def all_locations(self) -> List[Location]:
        """Get all locations across all markets."""
        locations = []
        for market in self.markets:
            locations.extend(market.all_locations)
        return locations
    
    @property
    def total_locations(self) -> int:
        """Get total number of locations."""
        return len(self.all_locations)


def load_config(config_path: str) -> Config:
    """Load configuration from YAML file.
    
    Args:
        config_path: Path to YAML configuration file
        
    Returns:
        Config object with all settings and locations
        
    Raises:
        FileNotFoundError: If config file doesn't exist
        ValueError: If config file is invalid
    """
    path = Path(config_path)
    if not path.exists():
        raise FileNotFoundError(f"Configuration file not found: {config_path}")
    
    with open(path, 'r') as f:
        data = yaml.safe_load(f)
    
    if not data:
        raise ValueError("Configuration file is empty")
    
    # Validate required fields
    if 'job_title' not in data:
        raise ValueError("Configuration must include 'job_title'")
    
    if 'markets' not in data or not data['markets']:
        raise ValueError("Configuration must include at least one market")
    
    # Parse configuration
    config = Config(
        job_title=data['job_title'],
        search_radius=data.get('search_radius', 25),
        results_per_location=data.get('results_per_location', 200),
        batch_size=data.get('batch_size', 5)
    )
    
    # Parse markets, regions, and locations
    for market_data in data['markets']:
        if not isinstance(market_data, dict) or 'name' not in market_data:
            raise ValueError("Each market must have a 'name'")
        
        market = Market(name=market_data['name'])
        
        if 'regions' in market_data:
            for region_data in market_data['regions']:
                if not isinstance(region_data, dict) or 'name' not in region_data:
                    raise ValueError("Each region must have a 'name'")
                
                region = Region(name=region_data['name'])
                
                if 'locations' in region_data:
                    for loc_data in region_data['locations']:
                        if not isinstance(loc_data, dict):
                            raise ValueError("Each location must be a dictionary")
                        
                        # Validate required location fields
                        required_fields = ['name', 'address', 'zip_code']
                        for field in required_fields:
                            if field not in loc_data:
                                raise ValueError(f"Location missing required field: {field}")
                        
                        location = Location(
                            name=loc_data['name'],
                            address=loc_data['address'],
                            zip_code=str(loc_data['zip_code']),
                            market=market.name,
                            region=region.name
                        )
                        region.locations.append(location)
                
                market.regions.append(region)
        
        config.markets.append(market)
    
    # Validate we have at least one location
    if config.total_locations == 0:
        raise ValueError("Configuration must include at least one location")
    
    return config


def validate_config(config: Config) -> List[str]:
    """Validate configuration and return any warnings.
    
    Args:
        config: Configuration to validate
        
    Returns:
        List of warning messages (empty if no warnings)
    """
    warnings = []
    
    # Check for reasonable values
    if config.search_radius > 100:
        warnings.append(f"Large search radius ({config.search_radius} miles) may return too many results")
    
    if config.results_per_location > 500:
        warnings.append(f"Large results_per_location ({config.results_per_location}) may be slow")
    
    if config.batch_size > 10:
        warnings.append(f"Large batch_size ({config.batch_size}) may trigger rate limiting")
    
    # Check for duplicate locations
    zip_codes = [loc.zip_code for loc in config.all_locations]
    if len(zip_codes) != len(set(zip_codes)):
        warnings.append("Duplicate zip codes found in configuration")
    
    return warnings