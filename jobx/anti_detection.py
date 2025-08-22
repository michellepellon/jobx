# Copyright (c) 2025 Michelle Pellon. MIT License

"""jobx.anti_detection

Advanced anti-scraping and detection avoidance utilities for web scraping.
This module provides user agent rotation, browser fingerprinting, request
randomization, and CAPTCHA detection capabilities.
"""

from __future__ import annotations

import random
import secrets
import time
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

import numpy as np
from bs4 import BeautifulSoup


class DeviceType(Enum):
    """Device types for user agent generation."""
    DESKTOP = "desktop"
    MOBILE = "mobile"
    TABLET = "tablet"


class BrowserType(Enum):
    """Browser types for user agent generation."""
    CHROME = "chrome"
    FIREFOX = "firefox"
    SAFARI = "safari"
    EDGE = "edge"


@dataclass
class BrowserProfile:
    """Represents a browser fingerprint profile."""
    user_agent: str
    accept_language: str
    accept_encoding: str
    accept: str
    sec_ch_ua: Optional[str] = None
    sec_ch_ua_mobile: Optional[str] = None
    sec_ch_ua_platform: Optional[str] = None
    viewport_width: Optional[int] = None
    viewport_height: Optional[int] = None
    screen_width: Optional[int] = None
    screen_height: Optional[int] = None
    timezone: Optional[str] = None
    plugins_count: Optional[int] = None
    do_not_track: Optional[str] = None


class UserAgentRotator:
    """Manages user agent rotation with realistic browser profiles."""
    
    # Real user agents collected from popular browsers (2024-2025)
    USER_AGENTS = {
        DeviceType.DESKTOP: {
            BrowserType.CHROME: [
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            ],
            BrowserType.FIREFOX: [
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:133.0) Gecko/20100101 Firefox/133.0",
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 14.5) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Firefox/133.0",
                "Mozilla/5.0 (X11; Linux x86_64; rv:133.0) Gecko/20100101 Firefox/133.0",
                "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:133.0) Gecko/20100101 Firefox/133.0",
            ],
            BrowserType.SAFARI: [
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Safari/605.1.15",
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_6_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Safari/605.1.15",
            ],
            BrowserType.EDGE: [
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36 Edg/131.0.0.0",
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36 Edg/130.0.0.0",
            ],
        },
        DeviceType.MOBILE: {
            BrowserType.CHROME: [
                "Mozilla/5.0 (iPhone; CPU iPhone OS 17_5_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) CriOS/131.0.6778.73 Mobile/15E148 Safari/604.1",
                "Mozilla/5.0 (Linux; Android 14; SM-S921B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.6778.39 Mobile Safari/537.36",
                "Mozilla/5.0 (Linux; Android 14; Pixel 8 Pro) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.6778.39 Mobile Safari/537.36",
            ],
            BrowserType.SAFARI: [
                "Mozilla/5.0 (iPhone; CPU iPhone OS 17_5_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1",
                "Mozilla/5.0 (iPad; CPU OS 17_5_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1",
            ],
            BrowserType.FIREFOX: [
                "Mozilla/5.0 (Android 14; Mobile; rv:125.0) Gecko/125.0 Firefox/125.0",
                "Mozilla/5.0 (iPhone; CPU iPhone OS 17_5_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) FxiOS/126.0 Mobile/15E148 Safari/605.1.15",
            ],
            BrowserType.EDGE: [
                "Mozilla/5.0 (Linux; Android 14; SM-S921B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.6778.39 Mobile Safari/537.36 EdgA/131.0.2903.52",
                "Mozilla/5.0 (iPhone; CPU iPhone OS 17_5_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 EdgiOS/131.2903.70 Mobile/15E148 Safari/604.1",
            ],
        },
    }
    
    def __init__(self, device_types: Optional[List[DeviceType]] = None):
        """Initialize user agent rotator with specified device types."""
        self.device_types = device_types or [DeviceType.DESKTOP]
        self.current_profile: Optional[BrowserProfile] = None
        self._used_agents: List[str] = []
        self._max_history = 10
    
    def get_random_user_agent(self) -> str:
        """Get a random user agent string."""
        device = random.choice(self.device_types)
        browser = random.choice(list(BrowserType))
        
        agents = self.USER_AGENTS.get(device, {}).get(browser, [])
        if not agents:
            # Fallback to Chrome desktop if no agents available
            agents = self.USER_AGENTS[DeviceType.DESKTOP][BrowserType.CHROME]
        
        # Try to avoid recently used agents
        available = [a for a in agents if a not in self._used_agents]
        if not available:
            available = agents
            self._used_agents = []
        
        agent = random.choice(available)
        self._used_agents.append(agent)
        if len(self._used_agents) > self._max_history:
            self._used_agents.pop(0)
        
        return agent
    
    def generate_browser_profile(self) -> BrowserProfile:
        """Generate a complete browser profile with fingerprinting data."""
        user_agent = self.get_random_user_agent()
        is_mobile = "Mobile" in user_agent or "Android" in user_agent
        
        # Language preferences (weighted towards English)
        languages = [
            "en-US,en;q=0.9",
            "en-GB,en;q=0.9",
            "en-US,en;q=0.9,es;q=0.8",
            "en-US,en;q=0.9,fr;q=0.8",
            "en-US,en;q=0.9,de;q=0.8",
            "en-US,en;q=0.9,zh-CN;q=0.8",
        ]
        
        # Screen resolutions
        desktop_resolutions = [
            (1920, 1080), (2560, 1440), (1366, 768), (1440, 900),
            (1536, 864), (1920, 1200), (3840, 2160), (1680, 1050)
        ]
        mobile_resolutions = [
            (390, 844), (412, 915), (360, 800), (414, 896),
            (375, 812), (393, 851), (428, 926)
        ]
        
        if is_mobile:
            screen_width, screen_height = random.choice(mobile_resolutions)
            viewport_width = screen_width
            viewport_height = screen_height - random.randint(50, 100)
        else:
            screen_width, screen_height = random.choice(desktop_resolutions)
            viewport_width = screen_width
            viewport_height = screen_height - random.randint(100, 150)
        
        # Generate Chrome Client Hints for Chrome/Edge
        sec_ch_ua = None
        sec_ch_ua_mobile = None
        sec_ch_ua_platform = None
        
        if "Chrome" in user_agent or "Edg" in user_agent:
            chrome_version = "131"
            if "Chrome/130" in user_agent:
                chrome_version = "130"
            
            sec_ch_ua = f'"Chromium";v="{chrome_version}", "Google Chrome";v="{chrome_version}", "Not?A_Brand";v="24"'
            sec_ch_ua_mobile = "?1" if is_mobile else "?0"
            
            if "Windows" in user_agent:
                sec_ch_ua_platform = '"Windows"'
            elif "Mac" in user_agent:
                sec_ch_ua_platform = '"macOS"'
            elif "Linux" in user_agent:
                sec_ch_ua_platform = '"Linux"'
            elif "Android" in user_agent:
                sec_ch_ua_platform = '"Android"'
            else:
                sec_ch_ua_platform = '"Unknown"'
        
        profile = BrowserProfile(
            user_agent=user_agent,
            accept_language=random.choice(languages),
            accept_encoding="gzip, deflate, br",
            accept="text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8",
            sec_ch_ua=sec_ch_ua,
            sec_ch_ua_mobile=sec_ch_ua_mobile,
            sec_ch_ua_platform=sec_ch_ua_platform,
            viewport_width=viewport_width,
            viewport_height=viewport_height,
            screen_width=screen_width,
            screen_height=screen_height,
            timezone=random.choice(["America/New_York", "America/Chicago", "America/Los_Angeles", "America/Denver"]),
            plugins_count=random.randint(0, 5) if not is_mobile else 0,
            do_not_track=random.choice(["1", None, None]),  # Most users don't set DNT
        )
        
        self.current_profile = profile
        return profile


class RequestRandomizer:
    """Randomizes request parameters to appear more human-like."""
    
    @staticmethod
    def randomize_headers(base_headers: Dict[str, str], profile: BrowserProfile) -> Dict[str, str]:
        """Randomize and enhance request headers."""
        headers = base_headers.copy()
        
        # Update with profile data
        headers["User-Agent"] = profile.user_agent
        headers["Accept-Language"] = profile.accept_language
        headers["Accept-Encoding"] = profile.accept_encoding
        headers["Accept"] = profile.accept
        
        # Add Chrome Client Hints if available
        if profile.sec_ch_ua:
            headers["Sec-CH-UA"] = profile.sec_ch_ua
            headers["Sec-CH-UA-Mobile"] = profile.sec_ch_ua_mobile
            headers["Sec-CH-UA-Platform"] = profile.sec_ch_ua_platform
        
        # Add other common headers with randomization
        if random.random() > 0.3:  # 70% chance
            headers["Sec-Fetch-Site"] = random.choice(["same-origin", "same-site", "cross-site", "none"])
            headers["Sec-Fetch-Mode"] = random.choice(["navigate", "cors", "no-cors", "same-origin"])
            headers["Sec-Fetch-User"] = "?1" if random.random() > 0.5 else None
            headers["Sec-Fetch-Dest"] = random.choice(["document", "empty", "script", "style"])
        
        # Randomly add DNT header
        if profile.do_not_track:
            headers["DNT"] = profile.do_not_track
        
        # Randomly order headers (some sites check header order)
        header_items = list(headers.items())
        random.shuffle(header_items)
        
        return dict(header_items)
    
    @staticmethod
    def random_delay(min_seconds: float = 0.5, max_seconds: float = 3.0) -> float:
        """Generate human-like random delay with realistic distribution."""
        # Use a beta distribution for more realistic delays (most are medium, few are very short or long)
        alpha, beta = 2, 2
        normalized = np.random.beta(alpha, beta)
        delay = min_seconds + (max_seconds - min_seconds) * normalized
        
        # Add small random jitter
        jitter = random.uniform(-0.1, 0.1)
        return max(min_seconds, delay + jitter)
    
    @staticmethod
    def random_mouse_movement_time() -> float:
        """Simulate time for mouse movement between actions."""
        return random.uniform(0.1, 0.5)


class CaptchaDetector:
    """Detects various types of CAPTCHA challenges."""
    
    CAPTCHA_INDICATORS = {
        "recaptcha": [
            "g-recaptcha",
            "grecaptcha",
            "recaptcha/api",
            "google.com/recaptcha",
        ],
        "hcaptcha": [
            "h-captcha",
            "hcaptcha.com",
            "hcaptcha-response",
        ],
        "cloudflare": [
            "cf-chl-bypass",
            "Checking your browser",
            "cf_clearance",
            "challenges.cloudflare.com",
            "_cf_bm",
        ],
        "datadome": [
            "datadome",
            "dd.min.js",
            "datadome-session-id",
        ],
        "perimetex": [
            "px-captcha",
            "perimeterx",
            "_px2",
            "_px3",
        ],
        "funcaptcha": [
            "funcaptcha",
            "arkoselabs",
            "fc-token",
        ],
    }
    
    CAPTCHA_TITLES = [
        "security check",
        "verify you're human",
        "robot verification",
        "captcha",
        "challenge",
        "access denied",
        "please verify",
    ]
    
    @classmethod
    def detect_captcha(cls, html_content: str, url: str = "") -> Tuple[bool, Optional[str]]:
        """Detect if page contains a CAPTCHA challenge."""
        if not html_content:
            return False, None
        
        html_lower = html_content.lower()
        
        # Check for CAPTCHA indicators in HTML
        for captcha_type, indicators in cls.CAPTCHA_INDICATORS.items():
            for indicator in indicators:
                if indicator.lower() in html_lower:
                    return True, captcha_type
        
        # Check page title
        soup = BeautifulSoup(html_content, 'html.parser')
        title = soup.find('title')
        if title:
            title_text = title.text.lower()
            for captcha_title in cls.CAPTCHA_TITLES:
                if captcha_title in title_text:
                    return True, "unknown"
        
        # Check for suspicious meta tags
        meta_robots = soup.find('meta', attrs={'name': 'robots'})
        if meta_robots and 'noindex' in meta_robots.get('content', '').lower():
            # Could be a challenge page
            if any(word in html_lower for word in ['challenge', 'verify', 'captcha']):
                return True, "unknown"
        
        # Check for common CAPTCHA form elements
        captcha_forms = soup.find_all('form', id=lambda x: x and 'captcha' in x.lower())
        if captcha_forms:
            return True, "form_captcha"
        
        # Check for iframe-based CAPTCHAs
        iframes = soup.find_all('iframe')
        for iframe in iframes:
            src = iframe.get('src', '')
            if any(indicator in src for indicator in ['recaptcha', 'hcaptcha', 'captcha']):
                return True, "iframe_captcha"
        
        return False, None
    
    @classmethod
    def detect_rate_limit(cls, response_code: int, html_content: str) -> bool:
        """Detect if response indicates rate limiting."""
        # HTTP status codes indicating rate limiting
        if response_code in [429, 503]:
            return True
        
        if response_code == 403:
            # Check if it's a rate limit 403 vs access denied
            rate_limit_phrases = [
                "rate limit",
                "too many requests",
                "slow down",
                "try again later",
                "temporarily blocked",
            ]
            html_lower = html_content.lower()
            return any(phrase in html_lower for phrase in rate_limit_phrases)
        
        return False


class IntelligentDelayManager:
    """Manages delays with adaptive patterns based on response times."""
    
    def __init__(self, base_delay: float = 1.0, max_delay: float = 10.0):
        """Initialize delay manager."""
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.recent_response_times: List[float] = []
        self.consecutive_fast_responses = 0
        self.consecutive_slow_responses = 0
        self.last_request_time = 0
        self.backoff_multiplier = 1.0
    
    def calculate_delay(self, last_response_time: Optional[float] = None) -> float:
        """Calculate next delay based on patterns."""
        if last_response_time is not None:
            self.recent_response_times.append(last_response_time)
            if len(self.recent_response_times) > 10:
                self.recent_response_times.pop(0)
            
            # Detect patterns
            if last_response_time < 0.5:  # Very fast response
                self.consecutive_fast_responses += 1
                self.consecutive_slow_responses = 0
            elif last_response_time > 2.0:  # Slow response
                self.consecutive_slow_responses += 1
                self.consecutive_fast_responses = 0
            else:
                self.consecutive_fast_responses = max(0, self.consecutive_fast_responses - 1)
                self.consecutive_slow_responses = max(0, self.consecutive_slow_responses - 1)
        
        # Adjust delay based on patterns
        if self.consecutive_fast_responses > 3:
            # Server is responding very quickly, might be getting suspicious
            self.backoff_multiplier = min(3.0, self.backoff_multiplier * 1.5)
        elif self.consecutive_slow_responses > 3:
            # Server is slow, we're likely rate limited
            self.backoff_multiplier = min(5.0, self.backoff_multiplier * 2.0)
        else:
            # Gradually reduce backoff
            self.backoff_multiplier = max(1.0, self.backoff_multiplier * 0.9)
        
        # Calculate delay with randomization
        delay = self.base_delay * self.backoff_multiplier
        delay = RequestRandomizer.random_delay(delay * 0.8, min(delay * 1.5, self.max_delay))
        
        # Add burst protection
        time_since_last = time.time() - self.last_request_time if self.last_request_time else float('inf')
        if time_since_last < 0.5:  # Requests too close together
            delay = max(delay, 1.0)
        
        self.last_request_time = time.time()
        return delay
    
    def reset(self):
        """Reset delay manager state."""
        self.recent_response_times = []
        self.consecutive_fast_responses = 0
        self.consecutive_slow_responses = 0
        self.backoff_multiplier = 1.0


class ProxyRotator:
    """Manages proxy rotation with health checking."""
    
    def __init__(self, proxies: List[str]):
        """Initialize proxy rotator with list of proxies."""
        self.proxies = proxies
        self.current_index = 0
        self.proxy_health: Dict[str, Dict[str, Any]] = {}
        self.initialize_health_tracking()
    
    def initialize_health_tracking(self):
        """Initialize health tracking for all proxies."""
        for proxy in self.proxies:
            self.proxy_health[proxy] = {
                "failures": 0,
                "successes": 0,
                "last_used": 0,
                "last_failure": 0,
                "response_times": [],
                "blacklisted": False,
            }
    
    def get_next_proxy(self) -> Optional[str]:
        """Get next healthy proxy from rotation."""
        attempts = 0
        while attempts < len(self.proxies):
            proxy = self.proxies[self.current_index]
            self.current_index = (self.current_index + 1) % len(self.proxies)
            
            health = self.proxy_health[proxy]
            
            # Skip blacklisted proxies
            if health["blacklisted"]:
                attempts += 1
                continue
            
            # Skip recently failed proxies (cooldown period)
            if health["last_failure"] > 0:
                cooldown = min(300, 30 * health["failures"])  # Exponential cooldown
                if time.time() - health["last_failure"] < cooldown:
                    attempts += 1
                    continue
            
            # Skip overused proxies (rate limiting)
            if health["last_used"] > 0:
                if time.time() - health["last_used"] < 1:  # Minimum 1 second between uses
                    attempts += 1
                    continue
            
            health["last_used"] = time.time()
            return proxy
        
        # All proxies are unhealthy
        return None
    
    def mark_success(self, proxy: str, response_time: float):
        """Mark a successful request for a proxy."""
        if proxy in self.proxy_health:
            health = self.proxy_health[proxy]
            health["successes"] += 1
            health["failures"] = max(0, health["failures"] - 1)  # Reduce failure count
            health["response_times"].append(response_time)
            if len(health["response_times"]) > 10:
                health["response_times"].pop(0)
    
    def mark_failure(self, proxy: str, error_type: str = "unknown"):
        """Mark a failed request for a proxy."""
        if proxy in self.proxy_health:
            health = self.proxy_health[proxy]
            health["failures"] += 1
            health["last_failure"] = time.time()
            
            # Blacklist after too many failures
            if health["failures"] >= 5:
                health["blacklisted"] = True
    
    def get_proxy_stats(self) -> Dict[str, Any]:
        """Get statistics about proxy health."""
        total = len(self.proxies)
        healthy = sum(1 for h in self.proxy_health.values() if not h["blacklisted"])
        
        avg_response_times = {}
        for proxy, health in self.proxy_health.items():
            if health["response_times"]:
                avg_response_times[proxy] = np.mean(health["response_times"])
        
        return {
            "total_proxies": total,
            "healthy_proxies": healthy,
            "blacklisted_proxies": total - healthy,
            "average_response_times": avg_response_times,
        }
    
    def reset_proxy(self, proxy: str):
        """Reset a proxy's health stats."""
        if proxy in self.proxy_health:
            self.proxy_health[proxy] = {
                "failures": 0,
                "successes": 0,
                "last_used": 0,
                "last_failure": 0,
                "response_times": [],
                "blacklisted": False,
            }


class StealthSession:
    """Enhanced session with anti-detection features."""
    
    def __init__(
        self,
        session: Any,
        user_agent_rotator: Optional[UserAgentRotator] = None,
        delay_manager: Optional[IntelligentDelayManager] = None,
        proxy_rotator: Optional[ProxyRotator] = None,
    ):
        """Initialize stealth session wrapper."""
        self.session = session
        self.user_agent_rotator = user_agent_rotator or UserAgentRotator()
        self.delay_manager = delay_manager or IntelligentDelayManager()
        self.proxy_rotator = proxy_rotator
        self.current_profile = self.user_agent_rotator.generate_browser_profile()
    
    def prepare_request(self, url: str, **kwargs) -> Dict[str, Any]:
        """Prepare request with anti-detection measures."""
        # Apply delay
        delay = self.delay_manager.calculate_delay()
        time.sleep(delay)
        
        # Rotate user agent periodically
        if random.random() < 0.1:  # 10% chance to rotate
            self.current_profile = self.user_agent_rotator.generate_browser_profile()
        
        # Randomize headers
        headers = kwargs.get("headers", {})
        headers = RequestRandomizer.randomize_headers(headers, self.current_profile)
        kwargs["headers"] = headers
        
        # Set proxy if available
        if self.proxy_rotator:
            proxy = self.proxy_rotator.get_next_proxy()
            if proxy:
                kwargs["proxies"] = {"http": proxy, "https": proxy}
        
        return kwargs
    
    def get(self, url: str, **kwargs) -> Any:
        """Make GET request with anti-detection."""
        kwargs = self.prepare_request(url, **kwargs)
        start_time = time.time()
        
        try:
            response = self.session.get(url, **kwargs)
            response_time = time.time() - start_time
            
            # Update delay manager with response time
            self.delay_manager.calculate_delay(response_time)
            
            # Mark proxy success if used
            if self.proxy_rotator and "proxies" in kwargs:
                proxy = kwargs["proxies"]["http"]
                self.proxy_rotator.mark_success(proxy, response_time)
            
            # Check for CAPTCHA
            is_captcha, captcha_type = CaptchaDetector.detect_captcha(
                response.text if hasattr(response, 'text') else "",
                url
            )
            if is_captcha:
                raise Exception(f"CAPTCHA detected: {captcha_type}")
            
            # Check for rate limiting
            if CaptchaDetector.detect_rate_limit(
                response.status_code,
                response.text if hasattr(response, 'text') else ""
            ):
                # Increase backoff
                self.delay_manager.backoff_multiplier *= 2
                raise Exception("Rate limit detected")
            
            return response
            
        except Exception as e:
            # Mark proxy failure if used
            if self.proxy_rotator and "proxies" in kwargs:
                proxy = kwargs["proxies"]["http"]
                self.proxy_rotator.mark_failure(proxy, str(e))
            raise
    
    def post(self, url: str, **kwargs) -> Any:
        """Make POST request with anti-detection."""
        kwargs = self.prepare_request(url, **kwargs)
        return self.session.post(url, **kwargs)