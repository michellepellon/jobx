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
    SalaryFilterConfig,
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


class TestConfigurableFields:
    """Tests for the new configurable fields (SearchConfig, SalaryFilterConfig, Role)."""

    def _write_config(self, data: dict) -> str:
        """Write config data to a temp YAML file and return its path."""
        f = tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False)
        yaml.dump(data, f)
        f.close()
        return f.name

    def _base_config_data(self, **overrides) -> dict:
        """Return a minimal valid config dict with optional overrides."""
        data = {
            "roles": [
                {
                    "id": "rbt",
                    "name": "RBT",
                    "pay_type": "hourly",
                    "default_unit": "USD/hour",
                }
            ],
            "search": {"radius_miles": 25},
            "regions": [
                {
                    "name": "Central",
                    "markets": [
                        {
                            "name": "Texas",
                            "paybands": {
                                "rbt": {"min": 15, "max": 22, "pay_type": "hourly"}
                            },
                            "centers": [
                                {
                                    "code": "HOU",
                                    "name": "Houston",
                                    "address_1": "123 Main",
                                    "city": "Houston",
                                    "state": "TX",
                                    "zip_code": "77001",
                                }
                            ],
                        }
                    ],
                }
            ],
        }
        for key, val in overrides.items():
            data[key] = val
        return data

    # ── SearchConfig defaults ──────────────────────────────────

    def test_search_config_defaults(self):
        """New SearchConfig fields have correct defaults when YAML omits them."""
        path = self._write_config(self._base_config_data())
        try:
            cfg = load_config(path)
            assert cfg.search.site_names == ["linkedin", "indeed"]
            assert cfg.search.country_indeed == "usa"
            assert cfg.search.min_search_terms == 4
            assert cfg.search.max_search_terms == 6
            assert cfg.search.inter_search_delay_min == 3.0
            assert cfg.search.inter_search_delay_max == 8.0
            assert cfg.search.delay_between_completions == 0.5
            assert cfg.search.delay_between_batches == 2.0
            assert cfg.search.max_retries == 3
            assert cfg.search.retry_backoff_base == 30.0
            assert cfg.search.min_sample_size == 100
        finally:
            Path(path).unlink()

    def test_search_config_custom(self):
        """SearchConfig fields can be set via YAML."""
        data = self._base_config_data()
        data["search"].update({
            "site_names": ["linkedin"],
            "country_indeed": "canada",
            "min_search_terms": 2,
            "max_search_terms": 4,
            "inter_search_delay_min": 1.0,
            "inter_search_delay_max": 5.0,
            "delay_between_completions": 1.0,
            "delay_between_batches": 5.0,
            "max_retries": 5,
            "retry_backoff_base": 60.0,
            "min_sample_size": 50,
        })
        path = self._write_config(data)
        try:
            cfg = load_config(path)
            assert cfg.search.site_names == ["linkedin"]
            assert cfg.search.country_indeed == "canada"
            assert cfg.search.min_search_terms == 2
            assert cfg.search.max_search_terms == 4
            assert cfg.search.max_retries == 5
            assert cfg.search.min_sample_size == 50
        finally:
            Path(path).unlink()

    # ── SalaryFilterConfig ─────────────────────────────────────

    def test_salary_filter_defaults(self):
        """SalaryFilterConfig defaults match prior hardcoded values."""
        path = self._write_config(self._base_config_data())
        try:
            cfg = load_config(path)
            sf = cfg.salary_filter
            assert sf.hourly_rate_threshold == 500.0
            assert sf.iqr_multiplier == 1.5
            assert sf.min_data_points_for_iqr == 4
            assert sf.hourly_salary_min == 31000.0
            assert sf.hourly_salary_max == 125000.0
            assert sf.salary_min == 40000.0
            assert sf.salary_max == 300000.0
            assert sf.default_salary_min == 20000.0
            assert sf.default_salary_max == 500000.0
        finally:
            Path(path).unlink()

    def test_salary_filter_custom(self):
        """SalaryFilterConfig can be overridden via YAML."""
        data = self._base_config_data()
        data["salary_filter"] = {
            "iqr_multiplier": 2.0,
            "salary_min": 50000.0,
            "salary_max": 250000.0,
        }
        path = self._write_config(data)
        try:
            cfg = load_config(path)
            assert cfg.salary_filter.iqr_multiplier == 2.0
            assert cfg.salary_filter.salary_min == 50000.0
            assert cfg.salary_filter.salary_max == 250000.0
            # Unspecified fields keep defaults
            assert cfg.salary_filter.hourly_rate_threshold == 500.0
        finally:
            Path(path).unlink()

    # ── Role excluded_title_keywords ───────────────────────────

    def test_excluded_title_keywords_from_yaml(self):
        """excluded_title_keywords is parsed from YAML."""
        data = self._base_config_data()
        data["roles"][0]["excluded_title_keywords"] = ["intern", "junior"]
        path = self._write_config(data)
        try:
            cfg = load_config(path)
            assert cfg.roles[0].excluded_title_keywords == ["intern", "junior"]
        finally:
            Path(path).unlink()

    def test_excluded_title_keywords_default_empty(self):
        """Non-BCBA roles get empty excluded_title_keywords by default."""
        path = self._write_config(self._base_config_data())
        try:
            cfg = load_config(path)
            # RBT role should have no excluded keywords
            assert cfg.roles[0].excluded_title_keywords == []
        finally:
            Path(path).unlink()

    def test_bcba_backward_compat_shim(self):
        """BCBA roles get auto-populated excluded_title_keywords when not specified."""
        data = self._base_config_data()
        data["roles"] = [
            {
                "id": "bcba",
                "name": "Board Certified Behavioral Analyst",
                "pay_type": "salary",
                "default_unit": "USD/year",
            }
        ]
        # Update payband to match role
        data["regions"][0]["markets"][0]["paybands"] = {
            "bcba": {"min": 70000, "max": 90000, "pay_type": "salary"}
        }
        path = self._write_config(data)
        try:
            cfg = load_config(path)
            assert len(cfg.roles[0].excluded_title_keywords) > 0
            assert "teacher" in cfg.roles[0].excluded_title_keywords
            assert "therapist" in cfg.roles[0].excluded_title_keywords
        finally:
            Path(path).unlink()

    def test_bcba_explicit_keywords_not_overridden(self):
        """Explicit excluded_title_keywords on BCBA are not overridden by shim."""
        data = self._base_config_data()
        data["roles"] = [
            {
                "id": "bcba",
                "name": "BCBA",
                "pay_type": "salary",
                "default_unit": "USD/year",
                "excluded_title_keywords": ["manager"],
            }
        ]
        data["regions"][0]["markets"][0]["paybands"] = {
            "bcba": {"min": 70000, "max": 90000, "pay_type": "salary"}
        }
        path = self._write_config(data)
        try:
            cfg = load_config(path)
            assert cfg.roles[0].excluded_title_keywords == ["manager"]
        finally:
            Path(path).unlink()

    # ── Validation ─────────────────────────────────────────────

    def test_validation_search_term_range(self):
        """Warns when min_search_terms > max_search_terms."""
        cfg = Config(
            meta=Meta(),
            roles=[Role(id="r", name="R", pay_type="salary", default_unit="USD/year")],
            search=SearchConfig(min_search_terms=8, max_search_terms=4),
            regions=[],
        )
        w = cfg.validate()
        assert any("min_search_terms" in x and "max_search_terms" in x for x in w)

    def test_validation_delay_range(self):
        """Warns when inter_search_delay_min > inter_search_delay_max."""
        cfg = Config(
            meta=Meta(),
            roles=[Role(id="r", name="R", pay_type="salary", default_unit="USD/year")],
            search=SearchConfig(inter_search_delay_min=10, inter_search_delay_max=2),
            regions=[],
        )
        w = cfg.validate()
        assert any("inter_search_delay_min" in x for x in w)

    def test_validation_salary_bounds(self):
        """Warns when salary_min >= salary_max or hourly bounds are inverted."""
        cfg = Config(
            meta=Meta(),
            roles=[Role(id="r", name="R", pay_type="salary", default_unit="USD/year")],
            search=SearchConfig(),
            regions=[],
            salary_filter=SalaryFilterConfig(salary_min=300000, salary_max=40000),
        )
        w = cfg.validate()
        assert any("salary_min" in x and "salary_max" in x for x in w)

    def test_valid_config_no_extra_warnings(self):
        """A well-formed config with all defaults produces no new warnings."""
        path = self._write_config(self._base_config_data())
        try:
            cfg = load_config(path)
            w = cfg.validate()
            # The only possible warning is missing payband for roles, not our new checks
            assert not any("min_search_terms" in x for x in w)
            assert not any("salary_min" in x for x in w)
        finally:
            Path(path).unlink()

    # ── Legacy config backward compat ──────────────────────────

    def test_legacy_config_gets_defaults(self):
        """Legacy configs get default values for all new fields."""
        data = {
            "job_title": "Tester",
            "markets": [
                {
                    "name": "M",
                    "locations": [
                        {"name": "L", "address": "A", "zip_code": "00000"}
                    ],
                }
            ],
        }
        path = self._write_config(data)
        try:
            with pytest.warns(DeprecationWarning):
                cfg = load_config(path)
            assert cfg.search.max_retries == 3
            assert cfg.search.min_sample_size == 100
            assert cfg.salary_filter.iqr_multiplier == 1.5
        finally:
            Path(path).unlink()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])