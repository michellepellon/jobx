# Copyright (c) 2025 Michelle Pellon. MIT License

"""Tests for anti-detection and anti-scraping measures."""

import time
from unittest.mock import MagicMock, Mock, patch

import pytest

from jobx.anti_detection import (
    BrowserProfile,
    BrowserType,
    CaptchaDetector,
    DeviceType,
    IntelligentDelayManager,
    ProxyRotator,
    RequestRandomizer,
    StealthSession,
    UserAgentRotator,
)


class TestUserAgentRotator:
    """Test user agent rotation functionality."""
    
    def test_get_random_user_agent(self):
        """Test getting random user agents."""
        rotator = UserAgentRotator()
        
        # Get multiple agents
        agents = [rotator.get_random_user_agent() for _ in range(10)]
        
        # Should all be non-empty strings
        assert all(isinstance(agent, str) and agent for agent in agents)
        
        # Should have some variety (not all the same)
        assert len(set(agents)) > 1
    
    def test_device_type_filtering(self):
        """Test filtering by device type."""
        # Desktop only
        desktop_rotator = UserAgentRotator([DeviceType.DESKTOP])
        desktop_agent = desktop_rotator.get_random_user_agent()
        assert "Mobile" not in desktop_agent
        assert "Android" not in desktop_agent
        
        # Mobile only
        mobile_rotator = UserAgentRotator([DeviceType.MOBILE])
        mobile_agent = mobile_rotator.get_random_user_agent()
        assert any(x in mobile_agent for x in ["Mobile", "Android", "iPhone"])
    
    def test_agent_history(self):
        """Test that recent agents are avoided."""
        rotator = UserAgentRotator()
        rotator._max_history = 3
        
        # Get first agent
        first_agent = rotator.get_random_user_agent()
        assert first_agent in rotator._used_agents
        
        # History should not exceed max
        for _ in range(5):
            rotator.get_random_user_agent()
        assert len(rotator._used_agents) <= rotator._max_history
    
    def test_generate_browser_profile(self):
        """Test complete browser profile generation."""
        rotator = UserAgentRotator()
        profile = rotator.generate_browser_profile()
        
        assert isinstance(profile, BrowserProfile)
        assert profile.user_agent
        assert profile.accept_language
        assert profile.accept_encoding
        assert profile.accept
        assert profile.viewport_width > 0
        assert profile.viewport_height > 0
        assert profile.screen_width >= profile.viewport_width
        assert profile.screen_height >= profile.viewport_height
        
        # Chrome should have client hints
        if "Chrome" in profile.user_agent:
            assert profile.sec_ch_ua
            assert profile.sec_ch_ua_mobile
            assert profile.sec_ch_ua_platform


class TestRequestRandomizer:
    """Test request randomization functionality."""
    
    def test_randomize_headers(self):
        """Test header randomization."""
        base_headers = {"Custom-Header": "value"}
        profile = BrowserProfile(
            user_agent="Mozilla/5.0 Test",
            accept_language="en-US",
            accept_encoding="gzip",
            accept="text/html",
        )
        
        headers = RequestRandomizer.randomize_headers(base_headers, profile)
        
        assert headers["User-Agent"] == profile.user_agent
        assert headers["Accept-Language"] == profile.accept_language
        assert headers["Custom-Header"] == "value"
        assert "Accept" in headers
    
    def test_random_delay(self):
        """Test random delay generation."""
        delays = [RequestRandomizer.random_delay(0.5, 2.0) for _ in range(100)]
        
        # All delays should be within bounds
        assert all(0.4 <= d <= 2.1 for d in delays)  # Allow for jitter
        
        # Should have variety
        assert len(set(delays)) > 50
        
        # Average should be near middle of range
        avg_delay = sum(delays) / len(delays)
        assert 0.8 <= avg_delay <= 1.7
    
    def test_mouse_movement_time(self):
        """Test mouse movement time simulation."""
        times = [RequestRandomizer.random_mouse_movement_time() for _ in range(100)]
        assert all(0.1 <= t <= 0.5 for t in times)


class TestCaptchaDetector:
    """Test CAPTCHA detection functionality."""
    
    def test_detect_recaptcha(self):
        """Test reCAPTCHA detection."""
        html = '<div class="g-recaptcha" data-sitekey="key"></div>'
        detected, captcha_type = CaptchaDetector.detect_captcha(html)
        assert detected is True
        assert captcha_type == "recaptcha"
    
    def test_detect_cloudflare(self):
        """Test Cloudflare challenge detection."""
        html = '<title>Just a moment...</title><body>Checking your browser</body>'
        detected, captcha_type = CaptchaDetector.detect_captcha(html)
        assert detected is True
        assert captcha_type == "cloudflare"
    
    def test_detect_hcaptcha(self):
        """Test hCaptcha detection."""
        html = '<div class="h-captcha" data-sitekey="key"></div>'
        detected, captcha_type = CaptchaDetector.detect_captcha(html)
        assert detected is True
        assert captcha_type == "hcaptcha"
    
    def test_detect_by_title(self):
        """Test CAPTCHA detection by page title."""
        html = '<title>Security Check</title><body>Please verify</body>'
        detected, captcha_type = CaptchaDetector.detect_captcha(html)
        assert detected is True
        assert captcha_type == "unknown"
    
    def test_no_captcha(self):
        """Test when no CAPTCHA is present."""
        html = '<title>Job Listings</title><body>Here are the jobs</body>'
        detected, captcha_type = CaptchaDetector.detect_captcha(html)
        assert detected is False
        assert captcha_type is None
    
    def test_detect_rate_limit(self):
        """Test rate limit detection."""
        # HTTP 429
        assert CaptchaDetector.detect_rate_limit(429, "") is True
        
        # HTTP 503
        assert CaptchaDetector.detect_rate_limit(503, "") is True
        
        # HTTP 403 with rate limit message
        html = "Error: Too many requests. Please slow down."
        assert CaptchaDetector.detect_rate_limit(403, html) is True
        
        # HTTP 403 without rate limit message
        html = "Access denied"
        assert CaptchaDetector.detect_rate_limit(403, html) is False
        
        # HTTP 200
        assert CaptchaDetector.detect_rate_limit(200, "") is False


class TestIntelligentDelayManager:
    """Test intelligent delay management."""
    
    def test_initial_delay(self):
        """Test initial delay calculation."""
        manager = IntelligentDelayManager(base_delay=1.0)
        delay = manager.calculate_delay()
        assert 0.8 <= delay <= 1.5
    
    def test_fast_response_pattern(self):
        """Test adjustment for fast responses."""
        manager = IntelligentDelayManager(base_delay=1.0)
        
        # Simulate fast responses
        for _ in range(5):
            manager.calculate_delay(0.3)
        
        # Backoff should increase
        assert manager.backoff_multiplier > 1.0
        delay = manager.calculate_delay()
        assert delay > 1.0
    
    def test_slow_response_pattern(self):
        """Test adjustment for slow responses."""
        manager = IntelligentDelayManager(base_delay=1.0)
        
        # Simulate slow responses
        for _ in range(5):
            manager.calculate_delay(3.0)
        
        # Backoff should increase significantly
        assert manager.backoff_multiplier > 2.0
    
    def test_normal_response_pattern(self):
        """Test adjustment for normal responses."""
        manager = IntelligentDelayManager(base_delay=1.0)
        manager.backoff_multiplier = 2.0
        
        # Simulate normal responses
        for _ in range(5):
            manager.calculate_delay(1.0)
        
        # Backoff should decrease
        assert manager.backoff_multiplier < 2.0
    
    def test_burst_protection(self):
        """Test burst request protection."""
        manager = IntelligentDelayManager(base_delay=0.5)
        
        # First request
        manager.calculate_delay()
        
        # Immediate second request
        delay = manager.calculate_delay()
        assert delay >= 1.0  # Should enforce minimum delay
    
    def test_reset(self):
        """Test reset functionality."""
        manager = IntelligentDelayManager()
        manager.consecutive_fast_responses = 5
        manager.backoff_multiplier = 3.0
        
        manager.reset()
        
        assert manager.consecutive_fast_responses == 0
        assert manager.backoff_multiplier == 1.0
        assert len(manager.recent_response_times) == 0


class TestProxyRotator:
    """Test proxy rotation functionality."""
    
    def test_initialization(self):
        """Test proxy rotator initialization."""
        proxies = ["proxy1:8080", "proxy2:8080", "proxy3:8080"]
        rotator = ProxyRotator(proxies)
        
        assert len(rotator.proxies) == 3
        assert len(rotator.proxy_health) == 3
        
        for proxy in proxies:
            assert proxy in rotator.proxy_health
            assert rotator.proxy_health[proxy]["failures"] == 0
            assert rotator.proxy_health[proxy]["blacklisted"] is False
    
    def test_get_next_proxy(self):
        """Test getting next proxy in rotation."""
        proxies = ["proxy1:8080", "proxy2:8080", "proxy3:8080"]
        rotator = ProxyRotator(proxies)
        
        # Should rotate through all proxies
        used_proxies = []
        for _ in range(3):
            proxy = rotator.get_next_proxy()
            assert proxy is not None
            used_proxies.append(proxy)
            time.sleep(1.1)  # Avoid rate limiting
        
        assert set(used_proxies) == set(proxies)
    
    def test_blacklisting(self):
        """Test proxy blacklisting after failures."""
        proxies = ["proxy1:8080", "proxy2:8080"]
        rotator = ProxyRotator(proxies)
        
        # Mark many failures for proxy1
        for _ in range(5):
            rotator.mark_failure("proxy1:8080")
        
        assert rotator.proxy_health["proxy1:8080"]["blacklisted"] is True
        
        # Should only return proxy2 now
        time.sleep(1.1)
        proxy = rotator.get_next_proxy()
        assert proxy == "proxy2:8080"
    
    def test_cooldown_period(self):
        """Test cooldown after failure."""
        proxies = ["proxy1:8080", "proxy2:8080"]
        rotator = ProxyRotator(proxies)
        
        # Mark failure for proxy1
        rotator.mark_failure("proxy1:8080")
        
        # Should skip proxy1 immediately after failure
        proxies_returned = []
        for _ in range(3):
            proxy = rotator.get_next_proxy()
            if proxy:
                proxies_returned.append(proxy)
            time.sleep(0.1)
        
        # Should mostly return proxy2 during cooldown
        assert proxies_returned.count("proxy2:8080") > proxies_returned.count("proxy1:8080")
    
    def test_mark_success(self):
        """Test marking successful requests."""
        proxies = ["proxy1:8080"]
        rotator = ProxyRotator(proxies)
        
        rotator.proxy_health["proxy1:8080"]["failures"] = 3
        rotator.mark_success("proxy1:8080", 1.5)
        
        assert rotator.proxy_health["proxy1:8080"]["failures"] == 2
        assert rotator.proxy_health["proxy1:8080"]["successes"] == 1
        assert 1.5 in rotator.proxy_health["proxy1:8080"]["response_times"]
    
    def test_get_proxy_stats(self):
        """Test getting proxy statistics."""
        proxies = ["proxy1:8080", "proxy2:8080"]
        rotator = ProxyRotator(proxies)
        
        rotator.mark_success("proxy1:8080", 1.0)
        rotator.mark_success("proxy1:8080", 1.5)
        for _ in range(5):
            rotator.mark_failure("proxy2:8080")
        
        stats = rotator.get_proxy_stats()
        
        assert stats["total_proxies"] == 2
        assert stats["healthy_proxies"] == 1
        assert stats["blacklisted_proxies"] == 1
        assert "proxy1:8080" in stats["average_response_times"]
        assert stats["average_response_times"]["proxy1:8080"] == 1.25


class TestStealthSession:
    """Test stealth session wrapper."""
    
    def test_prepare_request(self):
        """Test request preparation with anti-detection."""
        mock_session = Mock()
        stealth = StealthSession(mock_session)
        
        with patch('time.sleep'):
            kwargs = stealth.prepare_request("https://example.com", headers={"Custom": "Header"})
        
        assert "headers" in kwargs
        assert "User-Agent" in kwargs["headers"]
        assert "Accept-Language" in kwargs["headers"]
        assert kwargs["headers"]["Custom"] == "Header"
    
    def test_get_with_captcha_detection(self):
        """Test GET request with CAPTCHA detection."""
        mock_session = Mock()
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = '<div class="g-recaptcha"></div>'
        mock_session.get.return_value = mock_response
        
        stealth = StealthSession(mock_session)
        
        with patch('time.sleep'):
            with pytest.raises(Exception, match="CAPTCHA detected"):
                stealth.get("https://example.com")
    
    def test_get_with_rate_limit_detection(self):
        """Test GET request with rate limit detection."""
        mock_session = Mock()
        mock_response = Mock()
        mock_response.status_code = 429
        mock_response.text = 'Rate limited'
        mock_session.get.return_value = mock_response
        
        stealth = StealthSession(mock_session)
        initial_backoff = stealth.delay_manager.backoff_multiplier
        
        with patch('time.sleep'):
            with pytest.raises(Exception, match="Rate limit detected"):
                stealth.get("https://example.com")
        
        # Backoff should increase
        assert stealth.delay_manager.backoff_multiplier > initial_backoff
    
    def test_profile_rotation(self):
        """Test periodic profile rotation."""
        mock_session = Mock()
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = '<html></html>'
        mock_session.get.return_value = mock_response
        
        stealth = StealthSession(mock_session)
        initial_profile = stealth.current_profile
        
        # Make many requests to trigger rotation
        with patch('time.sleep'):
            with patch('random.random', return_value=0.05):  # Force rotation
                stealth.get("https://example.com")
                
        # Profile should have changed
        assert stealth.current_profile != initial_profile
    
    def test_proxy_integration(self):
        """Test integration with proxy rotator."""
        mock_session = Mock()
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = '<html></html>'
        mock_session.get.return_value = mock_response
        
        proxy_rotator = ProxyRotator(["proxy1:8080", "proxy2:8080"])
        stealth = StealthSession(mock_session, proxy_rotator=proxy_rotator)
        
        with patch('time.sleep'):
            stealth.get("https://example.com")
        
        # Should have set proxy in request
        call_kwargs = mock_session.get.call_args[1]
        assert "proxies" in call_kwargs
        assert call_kwargs["proxies"]["http"] in ["proxy1:8080", "proxy2:8080"]