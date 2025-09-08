"""Tests for the configuration loader with role-based paybands."""

import tempfile
from pathlib import Path

import pytest
import yaml

from jobx.market_analysis.config_loader import (
    Center,
    Config,
    Location,
    Market,
    Meta,
    Payband,
    PayType,
    Region,
    Role,
    SearchConfig,
    load_config,
    migrate_config,
    validate_config,
)


class TestDataModels:
    """Test data model classes."""
    
    def test_role_creation(self):
        """Test Role creation and validation."""
        role = Role(
            id="test",
            name="Test Role",
            pay_type="hourly",
            default_unit="USD/hour"
        )
        assert role.id == "test"
        assert role.name == "Test Role"
        assert role.pay_type == PayType.HOURLY
        assert role.default_unit == "USD/hour"
    
    def test_payband_creation(self):
        """Test Payband creation and auto-unit setting."""
        # Hourly payband
        hourly = Payband(min=15.0, max=25.0, pay_type=PayType.HOURLY)
        assert hourly.unit == "USD/hour"
        assert hourly.currency == "USD"
        
        # Salary payband
        salary = Payband(min=50000, max=80000, pay_type=PayType.SALARY)
        assert salary.unit == "USD/year"
        
        # Custom unit
        custom = Payband(min=20, max=30, unit="EUR/hour", currency="EUR", pay_type="hourly")
        assert custom.unit == "EUR/hour"
        assert custom.currency == "EUR"
    
    def test_payband_validation(self):
        """Test Payband validation."""
        # Valid payband
        valid = Payband(min=20, max=30, pay_type="hourly")
        errors = valid.validate()
        assert len(errors) == 0
        
        # Invalid: negative min
        invalid_neg = Payband(min=-10, max=30, pay_type="hourly")
        errors = invalid_neg.validate()
        assert len(errors) == 1
        assert "negative" in errors[0].lower()
        
        # Invalid: max < min
        invalid_range = Payband(min=40, max=30, pay_type="hourly")
        errors = invalid_range.validate()
        assert len(errors) == 1
        assert "less than minimum" in errors[0]
    
    def test_center_creation(self):
        """Test Center creation and address formatting."""
        center = Center(
            code="TEST-001",
            name="Test Center",
            address_1="123 Main St",
            address_2="Suite 100",
            city="Houston",
            state="TX",
            zip_code="77001"
        )
        
        assert center.code == "TEST-001"
        assert center.search_location == "77001"
        assert "Suite 100" in center.full_address
        assert "Houston, TX 77001" in center.full_address
    
    def test_market_payband_operations(self):
        """Test Market payband operations."""
        market = Market(name="Test Market")
        
        # Add paybands
        market.paybands["rbt"] = Payband(min=15, max=22, pay_type="hourly")
        market.paybands["bcba"] = Payband(min=70000, max=90000, pay_type="salary")
        
        # Get payband
        rbt_band = market.get_payband("rbt")
        assert rbt_band is not None
        assert rbt_band.min == 15
        
        # Non-existent payband
        assert market.get_payband("nonexistent") is None
    
    def test_market_payband_validation(self):
        """Test Market payband validation against roles."""
        roles = [
            Role(id="rbt", name="RBT", pay_type="hourly", default_unit="USD/hour"),
            Role(id="bcba", name="BCBA", pay_type="salary", default_unit="USD/year")
        ]
        
        market = Market(name="Test")
        market.paybands["rbt"] = Payband(min=15, max=22, pay_type="hourly")
        market.paybands["unknown"] = Payband(min=20, max=30, pay_type="hourly")
        
        warnings = market.validate_paybands(roles)
        
        # Should warn about undefined role "unknown"
        assert any("undefined role: unknown" in w for w in warnings)
        # Should warn about missing payband for "bcba"
        assert any("missing payband for role: bcba" in w for w in warnings)
    
    def test_backward_compatibility_location(self):
        """Test Location backward compatibility."""
        center = Center(
            code="TEST",
            name="Test Center",
            address_1="123 Main St",
            city="Houston",
            state="TX",
            zip_code="77001"
        )
        
        location = Location.from_center(center, "Test Market", "Test Region")
        assert location.name == "Test Center"
        assert location.zip_code == "77001"
        assert location.market == "Test Market"
        assert location.region == "Test Region"


class TestConfigLoading:
    """Test configuration loading."""
    
    def test_load_new_format(self):
        """Test loading configuration in new format."""
        config_data = {
            "meta": {
                "version": 1,
                "currency_default": "USD",
                "unit_defaults": {
                    "hourly": "USD/hour",
                    "salary": "USD/year"
                }
            },
            "roles": [
                {
                    "id": "rbt",
                    "name": "RBT",
                    "pay_type": "hourly",
                    "default_unit": "USD/hour"
                }
            ],
            "search": {
                "radius_miles": 25,
                "results_per_location": 200,
                "batch_size": 5
            },
            "regions": [
                {
                    "name": "Central",
                    "markets": [
                        {
                            "name": "Texas",
                            "paybands": {
                                "rbt": {
                                    "min": 15,
                                    "max": 22.50,
                                    "currency": "USD",
                                    "unit": "USD/hour",
                                    "pay_type": "hourly"
                                }
                            },
                            "centers": [
                                {
                                    "code": "HOU-001",
                                    "name": "Houston Center",
                                    "address_1": "123 Main St",
                                    "city": "Houston",
                                    "state": "TX",
                                    "zip_code": "77001"
                                }
                            ]
                        }
                    ]
                }
            ]
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(config_data, f)
            config_path = f.name
        
        try:
            config = load_config(config_path)
            
            assert config.meta.version == 1
            assert len(config.roles) == 1
            assert config.roles[0].id == "rbt"
            assert config.search.radius_miles == 25
            assert len(config.regions) == 1
            assert len(config.all_markets) == 1
            assert len(config.all_centers) == 1
            assert config.total_locations == 1
            
            # Check payband
            market = config.all_markets[0]
            payband = market.get_payband("rbt")
            assert payband is not None
            assert payband.min == 15
            assert payband.max == 22.50
            
        finally:
            Path(config_path).unlink()
    
    def test_load_legacy_format(self):
        """Test loading configuration in legacy format."""
        config_data = {
            "job_title": "Software Engineer",
            "search_radius": 30,
            "results_per_location": 150,
            "batch_size": 3,
            "markets": [
                {
                    "name": "West Coast",
                    "regions": [
                        {
                            "name": "California",
                            "locations": [
                                {
                                    "name": "San Francisco",
                                    "address": "123 Market St",
                                    "zip_code": "94105"
                                }
                            ]
                        }
                    ]
                }
            ]
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(config_data, f)
            config_path = f.name
        
        try:
            with pytest.warns(DeprecationWarning):
                config = load_config(config_path)
            
            # Should create synthetic role
            assert len(config.roles) == 1
            assert config.roles[0].id == "default"
            assert config.roles[0].name == "Software Engineer"
            
            # Should preserve search parameters
            assert config.search.radius_miles == 30
            assert config.search.results_per_location == 150
            
            # Should have backward compat fields
            assert config.job_title == "Software Engineer"
            assert config.search_radius == 30
            
            # Should convert locations to centers
            assert config.total_locations == 1
            center = config.all_centers[0]
            assert center.zip_code == "94105"
            
        finally:
            Path(config_path).unlink()
    
    def test_validation_warnings(self):
        """Test configuration validation warnings."""
        config = Config(
            meta=Meta(),
            roles=[Role(id="test", name="Test", pay_type="salary", default_unit="USD/year")],
            search=SearchConfig(
                radius_miles=150,  # Too large
                results_per_location=600,  # Too large
                batch_size=15  # Too large
            ),
            regions=[]
        )
        
        warnings = config.validate()
        
        assert any("radius" in w for w in warnings)
        assert any("results_per_location" in w for w in warnings)
        assert any("batch_size" in w for w in warnings)
    
    def test_duplicate_detection(self):
        """Test duplicate center code and zip code detection."""
        region = Region(name="Test")
        market = Market(name="Test Market")
        
        # Add duplicate center codes
        market.centers.append(Center(
            code="DUP",
            name="Center 1",
            address_1="123 St",
            city="City",
            state="ST",
            zip_code="12345"
        ))
        market.centers.append(Center(
            code="DUP",  # Duplicate code
            name="Center 2",
            address_1="456 St",
            city="City",
            state="ST",
            zip_code="67890"
        ))
        
        region.markets.append(market)
        
        config = Config(
            meta=Meta(),
            roles=[],
            search=SearchConfig(),
            regions=[region]
        )
        
        warnings = config.validate()
        assert any("Duplicate center codes" in w for w in warnings)
    
    def test_config_migration(self):
        """Test configuration migration from old to new format."""
        # Create old format config
        old_data = {
            "job_title": "Test Engineer",
            "search_radius": 25,
            "markets": [
                {
                    "name": "Test Market",
                    "regions": [
                        {
                            "name": "Test Region",
                            "locations": [
                                {
                                    "name": "Test Location",
                                    "address": "123 Test St",
                                    "zip_code": "12345"
                                }
                            ]
                        }
                    ]
                }
            ]
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as old_file:
            yaml.dump(old_data, old_file)
            old_path = old_file.name
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as new_file:
            new_path = new_file.name
        
        try:
            # Migrate
            migrate_config(old_path, new_path)
            
            # Load migrated config
            config = load_config(new_path)
            
            # Verify structure
            assert config.meta.version == 1
            assert len(config.roles) == 1
            assert config.roles[0].name == "Test Engineer"
            assert config.search.radius_miles == 25
            assert config.total_locations == 1
            
            # Should not have legacy fields in new config
            assert config.job_title is None
            
        finally:
            Path(old_path).unlink()
            Path(new_path).unlink()


class TestConfigIntegration:
    """Integration tests for configuration usage."""
    
    def test_full_config_workflow(self):
        """Test complete configuration workflow."""
        # Create comprehensive config
        meta = Meta(version=2, currency_default="USD")
        
        roles = [
            Role(id="junior", name="Junior Dev", pay_type="salary", default_unit="USD/year"),
            Role(id="senior", name="Senior Dev", pay_type="salary", default_unit="USD/year")
        ]
        
        search = SearchConfig(radius_miles=50, results_per_location=100)
        
        region = Region(name="West")
        market = Market(name="California")
        
        # Add paybands for both roles
        market.paybands["junior"] = Payband(min=60000, max=80000, pay_type="salary")
        market.paybands["senior"] = Payband(min=120000, max=180000, pay_type="salary")
        
        # Add centers
        market.centers.append(Center(
            code="SF-001",
            name="San Francisco",
            address_1="123 Market St",
            city="San Francisco",
            state="CA",
            zip_code="94105"
        ))
        
        region.markets.append(market)
        
        config = Config(
            meta=meta,
            roles=roles,
            search=search,
            regions=[region]
        )
        
        # Test config properties
        assert config.total_locations == 1
        assert len(config.all_markets) == 1
        
        # Test role lookup
        junior = config.get_role("junior")
        assert junior is not None
        assert junior.name == "Junior Dev"
        
        # Test market operations
        ca_market = config.all_markets[0]
        junior_band = ca_market.get_payband("junior")
        assert junior_band is not None
        assert junior_band.min == 60000
        
        # Validate
        warnings = config.validate()
        # Should have no warnings for this valid config
        assert len(warnings) == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])