"""Configuration loader for market analysis tool with role-based paybands.

This module provides strongly-typed configuration models and validation for the
market analysis tool, supporting role-based compensation bands across multiple
geographic markets and centers.
"""

import warnings
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import yaml


class PayType(str, Enum):
    """Payment type enumeration."""
    HOURLY = "hourly"
    SALARY = "salary"


@dataclass
class Meta:
    """Configuration metadata."""
    version: int = 1
    currency_default: str = "USD"
    unit_defaults: Dict[str, str] = field(default_factory=lambda: {
        "hourly": "USD/hour",
        "salary": "USD/year"
    })


@dataclass
class Role:
    """Job role definition."""
    id: str
    name: str
    pay_type: PayType
    default_unit: str
    
    def __post_init__(self):
        """Validate and convert pay_type to enum."""
        if isinstance(self.pay_type, str):
            self.pay_type = PayType(self.pay_type)


@dataclass
class Payband:
    """Compensation range for a specific role."""
    min: float
    max: float
    currency: str = "USD"
    unit: str = ""
    pay_type: PayType = PayType.HOURLY
    
    def __post_init__(self):
        """Validate and convert pay_type to enum."""
        if isinstance(self.pay_type, str):
            self.pay_type = PayType(self.pay_type)
        
        # Auto-set unit based on pay_type if not provided
        if not self.unit:
            if self.pay_type == PayType.HOURLY:
                self.unit = f"{self.currency}/hour"
            else:
                self.unit = f"{self.currency}/year"
    
    def validate(self) -> List[str]:
        """Validate payband constraints.
        
        Returns:
            List of validation error messages (empty if valid)
        """
        errors = []
        if self.min < 0:
            errors.append(f"Minimum pay cannot be negative: {self.min}")
        if self.max < self.min:
            errors.append(f"Maximum pay ({self.max}) cannot be less than minimum ({self.min})")
        return errors


@dataclass
class Center:
    """Physical location/center definition."""
    code: str
    name: str
    address_1: str
    city: str
    state: str
    zip_code: str
    address_2: Optional[str] = None
    
    @property
    def full_address(self) -> str:
        """Get complete formatted address."""
        parts = [self.address_1]
        if self.address_2:
            parts.append(self.address_2)
        parts.append(f"{self.city}, {self.state} {self.zip_code}")
        return ", ".join(parts)
    
    @property
    def search_location(self) -> str:
        """Get location string for job searches."""
        return self.zip_code


@dataclass
class Market:
    """Market with paybands and centers."""
    name: str
    paybands: Dict[str, Payband] = field(default_factory=dict)
    centers: List[Center] = field(default_factory=list)
    
    def get_payband(self, role_id: str) -> Optional[Payband]:
        """Get payband for a specific role.
        
        Args:
            role_id: Role identifier
            
        Returns:
            Payband if exists, None otherwise
        """
        return self.paybands.get(role_id)
    
    def validate_paybands(self, roles: List[Role]) -> List[str]:
        """Validate paybands match defined roles.
        
        Args:
            roles: List of defined roles
            
        Returns:
            List of validation warnings
        """
        warnings = []
        role_ids = {role.id for role in roles}
        
        for role_id in self.paybands:
            if role_id not in role_ids:
                warnings.append(f"Market '{self.name}' has payband for undefined role: {role_id}")
        
        for role in roles:
            if role.id not in self.paybands:
                warnings.append(f"Market '{self.name}' missing payband for role: {role.id}")
        
        return warnings


@dataclass
class Region:
    """Geographic region containing markets."""
    name: str
    markets: List[Market] = field(default_factory=list)
    
    @property
    def all_centers(self) -> List[Center]:
        """Get all centers across all markets in this region."""
        centers = []
        for market in self.markets:
            centers.extend(market.centers)
        return centers


@dataclass
class SearchConfig:
    """Search configuration parameters."""
    radius_miles: int = 25
    results_per_location: int = 200
    batch_size: int = 5


@dataclass
class Config:
    """Complete configuration for market analysis."""
    meta: Meta
    roles: List[Role]
    search: SearchConfig
    regions: List[Region]
    
    # Backward compatibility fields (deprecated)
    job_title: Optional[str] = None  # Deprecated: use roles instead
    search_radius: Optional[int] = None  # Deprecated: use search.radius_miles
    results_per_location: Optional[int] = None  # Deprecated: use search.results_per_location
    batch_size: Optional[int] = None  # Deprecated: use search.batch_size
    
    def __post_init__(self):
        """Handle backward compatibility."""
        # Map deprecated fields to new structure
        if self.search_radius is not None:
            warnings.warn(
                "Field 'search_radius' is deprecated. Use 'search.radius_miles' instead.",
                DeprecationWarning,
                stacklevel=2
            )
            self.search.radius_miles = self.search_radius
        
        if self.results_per_location is not None:
            warnings.warn(
                "Field 'results_per_location' is deprecated. Use 'search.results_per_location' instead.",
                DeprecationWarning,
                stacklevel=2
            )
            self.search.results_per_location = self.results_per_location
        
        if self.batch_size is not None:
            warnings.warn(
                "Field 'batch_size' is deprecated. Use 'search.batch_size' instead.",
                DeprecationWarning,
                stacklevel=2
            )
            self.search.batch_size = self.batch_size
    
    @property
    def all_centers(self) -> List[Center]:
        """Get all centers across all regions and markets."""
        centers = []
        for region in self.regions:
            centers.extend(region.all_centers)
        return centers
    
    @property
    def all_markets(self) -> List[Market]:
        """Get all markets across all regions."""
        markets = []
        for region in self.regions:
            markets.extend(region.markets)
        return markets
    
    @property
    def total_locations(self) -> int:
        """Get total number of centers/locations."""
        return len(self.all_centers)
    
    def get_role(self, role_id: str) -> Optional[Role]:
        """Get role definition by ID.
        
        Args:
            role_id: Role identifier
            
        Returns:
            Role if exists, None otherwise
        """
        for role in self.roles:
            if role.id == role_id:
                return role
        return None
    
    def validate(self) -> List[str]:
        """Validate entire configuration.
        
        Returns:
            List of validation warnings (empty if fully valid)
        """
        warnings = []
        
        # Validate search config
        if self.search.radius_miles > 100:
            warnings.append(f"Large search radius ({self.search.radius_miles} miles) may return too many results")
        
        if self.search.results_per_location > 500:
            warnings.append(f"Large results_per_location ({self.search.results_per_location}) may be slow")
        
        if self.search.batch_size > 10:
            warnings.append(f"Large batch_size ({self.search.batch_size}) may trigger rate limiting")
        
        # Check for duplicate center codes
        center_codes = [center.code for center in self.all_centers]
        if len(center_codes) != len(set(center_codes)):
            warnings.append("Duplicate center codes found in configuration")
        
        # Check for duplicate zip codes
        zip_codes = [center.zip_code for center in self.all_centers]
        if len(zip_codes) != len(set(zip_codes)):
            warnings.append("Duplicate zip codes found in configuration")
        
        # Validate paybands
        for market in self.all_markets:
            market_warnings = market.validate_paybands(self.roles)
            warnings.extend(market_warnings)
            
            for role_id, payband in market.paybands.items():
                payband_errors = payband.validate()
                if payband_errors:
                    for error in payband_errors:
                        warnings.append(f"Market '{market.name}', role '{role_id}': {error}")
        
        return warnings


# Backward compatibility types
@dataclass
class Location:
    """Legacy location type for backward compatibility.
    
    Deprecated: Use Center instead.
    """
    name: str
    address: str
    zip_code: str
    market: str = ""
    region: str = ""
    
    @classmethod
    def from_center(cls, center: Center, market_name: str, region_name: str) -> 'Location':
        """Create Location from Center for backward compatibility.
        
        Args:
            center: Center object
            market_name: Market name
            region_name: Region name
            
        Returns:
            Location object
        """
        return cls(
            name=center.name,
            address=center.full_address,
            zip_code=center.zip_code,
            market=market_name,
            region=region_name
        )


def load_config(config_path: str) -> Config:
    """Load configuration from YAML file.
    
    Supports both new schema (with roles and paybands) and legacy schema
    (with job_title) for backward compatibility.
    
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
    
    # Check if this is legacy format (has job_title at root)
    if 'job_title' in data and 'roles' not in data:
        return _load_legacy_config(data)
    
    # Load new format
    return _load_new_config(data)


def _load_new_config(data: Dict[str, Any]) -> Config:
    """Load configuration in new schema format.
    
    Args:
        data: Parsed YAML data
        
    Returns:
        Config object
        
    Raises:
        ValueError: If required fields are missing
    """
    # Parse metadata
    meta_data = data.get('meta', {})
    meta = Meta(
        version=meta_data.get('version', 1),
        currency_default=meta_data.get('currency_default', 'USD'),
        unit_defaults=meta_data.get('unit_defaults', {
            'hourly': 'USD/hour',
            'salary': 'USD/year'
        })
    )
    
    # Parse roles
    if 'roles' not in data:
        raise ValueError("Configuration must include 'roles'")
    
    roles = []
    for role_data in data['roles']:
        role = Role(
            id=role_data['id'],
            name=role_data['name'],
            pay_type=role_data['pay_type'],
            default_unit=role_data.get('default_unit', '')
        )
        roles.append(role)
    
    if not roles:
        raise ValueError("Configuration must define at least one role")
    
    # Parse search config
    search_data = data.get('search', {})
    search = SearchConfig(
        radius_miles=search_data.get('radius_miles', 25),
        results_per_location=search_data.get('results_per_location', 200),
        batch_size=search_data.get('batch_size', 5)
    )
    
    # Parse regions
    if 'regions' not in data:
        raise ValueError("Configuration must include 'regions'")
    
    regions = []
    for region_data in data['regions']:
        region = Region(name=region_data['name'])
        
        # Parse markets in region
        for market_data in region_data.get('markets', []):
            market = Market(name=market_data['name'])
            
            # Parse paybands
            paybands_data = market_data.get('paybands', {})
            for role_id, payband_data in paybands_data.items():
                payband = Payband(
                    min=payband_data['min'],
                    max=payband_data['max'],
                    currency=payband_data.get('currency', meta.currency_default),
                    unit=payband_data.get('unit', ''),
                    pay_type=payband_data.get('pay_type', 'hourly')
                )
                market.paybands[role_id] = payband
            
            # Parse centers
            for center_data in market_data.get('centers', []):
                center = Center(
                    code=center_data['code'],
                    name=center_data['name'],
                    address_1=center_data['address_1'],
                    address_2=center_data.get('address_2'),
                    city=center_data['city'],
                    state=center_data['state'],
                    zip_code=str(center_data['zip_code'])
                )
                market.centers.append(center)
            
            region.markets.append(market)
        
        regions.append(region)
    
    # Create config
    config = Config(
        meta=meta,
        roles=roles,
        search=search,
        regions=regions
    )
    
    # Validate
    if config.total_locations == 0:
        raise ValueError("Configuration must include at least one center/location")
    
    return config


def _load_legacy_config(data: Dict[str, Any]) -> Config:
    """Load configuration in legacy format for backward compatibility.
    
    Args:
        data: Parsed YAML data in legacy format
        
    Returns:
        Config object converted from legacy format
        
    Raises:
        ValueError: If required fields are missing
    """
    warnings.warn(
        "Loading configuration in legacy format. Please migrate to new schema with roles and paybands.",
        DeprecationWarning,
        stacklevel=3
    )
    
    # Validate required legacy fields
    if 'job_title' not in data:
        raise ValueError("Legacy configuration must include 'job_title'")
    
    if 'markets' not in data or not data['markets']:
        raise ValueError("Configuration must include at least one market")
    
    # Create a synthetic role from job_title
    job_title = data['job_title']
    synthetic_role = Role(
        id='default',
        name=job_title,
        pay_type=PayType.SALARY,  # Default assumption
        default_unit='USD/year'
    )
    
    # Create search config
    search = SearchConfig(
        radius_miles=data.get('search_radius', 25),
        results_per_location=data.get('results_per_location', 200),
        batch_size=data.get('batch_size', 5)
    )
    
    # Parse legacy markets/regions/locations structure
    regions = []
    
    for market_data in data['markets']:
        # In legacy format, markets might have regions or direct locations
        if 'regions' in market_data:
            # Market contains regions
            region = Region(name=market_data['name'])
            
            for region_data in market_data['regions']:
                market = Market(name=region_data['name'])
                
                # Convert locations to centers
                for loc_data in region_data.get('locations', []):
                    center = Center(
                        code=f"{market.name}_{loc_data['name']}".replace(' ', '_'),
                        name=loc_data['name'],
                        address_1=loc_data['address'],
                        address_2=None,
                        city=loc_data.get('city', ''),
                        state=loc_data.get('state', ''),
                        zip_code=str(loc_data['zip_code'])
                    )
                    market.centers.append(center)
                
                region.markets.append(market)
            
            regions.append(region)
        else:
            # Direct locations under market (treat market as region)
            region = Region(name=market_data['name'])
            market = Market(name=market_data['name'])
            
            # Convert locations to centers
            for loc_data in market_data.get('locations', []):
                center = Center(
                    code=f"{market.name}_{loc_data['name']}".replace(' ', '_'),
                    name=loc_data['name'],
                    address_1=loc_data.get('address', ''),
                    address_2=None,
                    city=loc_data.get('city', ''),
                    state=loc_data.get('state', ''),
                    zip_code=str(loc_data['zip_code'])
                )
                market.centers.append(center)
            
            region.markets.append(market)
            regions.append(region)
    
    # Create config with backward compatibility fields
    config = Config(
        meta=Meta(),
        roles=[synthetic_role],
        search=search,
        regions=regions,
        job_title=job_title,  # Keep for backward compatibility
        search_radius=search.radius_miles,
        results_per_location=search.results_per_location,
        batch_size=search.batch_size
    )
    
    # Validate
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
    return config.validate()


def migrate_config(old_config_path: str, new_config_path: str) -> None:
    """Migrate configuration from old format to new format.
    
    Args:
        old_config_path: Path to old format config file
        new_config_path: Path where new format config will be saved
    """
    # Load old config
    config = load_config(old_config_path)
    
    # Convert to new format dict
    new_data = {
        'meta': {
            'version': config.meta.version,
            'currency_default': config.meta.currency_default,
            'unit_defaults': config.meta.unit_defaults
        },
        'roles': [
            {
                'id': role.id,
                'name': role.name,
                'pay_type': role.pay_type.value,
                'default_unit': role.default_unit
            }
            for role in config.roles
        ],
        'search': {
            'radius_miles': config.search.radius_miles,
            'results_per_location': config.search.results_per_location,
            'batch_size': config.search.batch_size
        },
        'regions': []
    }
    
    # Convert regions
    for region in config.regions:
        region_data = {
            'name': region.name,
            'markets': []
        }
        
        for market in region.markets:
            market_data = {
                'name': market.name,
                'paybands': {},
                'centers': []
            }
            
            # Add paybands
            for role_id, payband in market.paybands.items():
                market_data['paybands'][role_id] = {
                    'min': payband.min,
                    'max': payband.max,
                    'currency': payband.currency,
                    'unit': payband.unit,
                    'pay_type': payband.pay_type.value
                }
            
            # Add centers
            for center in market.centers:
                center_data = {
                    'code': center.code,
                    'name': center.name,
                    'address_1': center.address_1,
                    'city': center.city,
                    'state': center.state,
                    'zip_code': center.zip_code
                }
                if center.address_2:
                    center_data['address_2'] = center.address_2
                
                market_data['centers'].append(center_data)
            
            region_data['markets'].append(market_data)
        
        new_data['regions'].append(region_data)
    
    # Save new format
    with open(new_config_path, 'w') as f:
        yaml.dump(new_data, f, default_flow_style=False, sort_keys=False)
    
    print(f"Configuration migrated successfully to: {new_config_path}")