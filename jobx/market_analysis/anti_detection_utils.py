"""
Advanced anti-detection utilities for market analysis.
Provides scheduling, monitoring, and safety features.
"""

import json
import random
import time
from pathlib import Path
from datetime import datetime, time as datetime_time, timedelta
from typing import Dict, List, Optional, Tuple
from collections import defaultdict
import yaml


class SmartScheduler:
    """Schedule searches during optimal times to blend in with normal traffic."""
    
    # Optimal search windows (local time)
    PEAK_HOURS = [
        (datetime_time(9, 0), datetime_time(11, 30)),   # Morning job search peak
        (datetime_time(12, 30), datetime_time(14, 30)),  # Lunch break searches
        (datetime_time(16, 0), datetime_time(18, 0)),    # After work searches
        (datetime_time(19, 30), datetime_time(21, 30)),  # Evening searches
    ]
    
    # Days with different patterns
    WEEKDAY_MULTIPLIER = 1.0
    SATURDAY_MULTIPLIER = 0.7  # Less traffic
    SUNDAY_MULTIPLIER = 0.5     # Least traffic
    
    @classmethod
    def is_good_time_to_search(cls) -> Tuple[bool, str]:
        """Check if current time is good for searching."""
        now = datetime.now()
        current_time = now.time()
        
        # Check day of week (0=Monday, 6=Sunday)
        day_of_week = now.weekday()
        
        # Avoid late night/early morning (2 AM - 6 AM)
        if datetime_time(2, 0) <= current_time <= datetime_time(6, 0):
            return False, "Too early - wait until business hours"
        
        # Check if in peak hours
        for start, end in cls.PEAK_HOURS:
            if start <= current_time <= end:
                return True, f"Peak hour window: {start.strftime('%H:%M')}-{end.strftime('%H:%M')}"
        
        # Off-peak but acceptable hours (6 AM - 10 PM)
        if datetime_time(6, 0) <= current_time <= datetime_time(22, 0):
            if day_of_week < 5:  # Weekday
                return True, "Weekday off-peak (acceptable)"
            else:  # Weekend
                return True, "Weekend hours (lower traffic expected)"
        
        return False, "Outside optimal search hours"
    
    @classmethod
    def get_delay_multiplier(cls) -> float:
        """Get delay multiplier based on time and day."""
        now = datetime.now()
        day_of_week = now.weekday()
        
        if day_of_week < 5:  # Weekday
            return cls.WEEKDAY_MULTIPLIER
        elif day_of_week == 5:  # Saturday
            return cls.SATURDAY_MULTIPLIER
        else:  # Sunday
            return cls.SUNDAY_MULTIPLIER
    
    @classmethod
    def wait_for_good_time(cls, logger=None):
        """Wait until a good time to search."""
        while True:
            is_good, reason = cls.is_good_time_to_search()
            if is_good:
                if logger:
                    logger.info(f"Good time to search: {reason}")
                else:
                    print(f"✓ Good time to search: {reason}")
                break
            else:
                if logger:
                    logger.info(f"Waiting: {reason}")
                else:
                    print(f"⏸ {reason}")
                # Check every 30 minutes
                wait_minutes = 30 + random.randint(-5, 5)
                if logger:
                    logger.info(f"Waiting {wait_minutes} minutes...")
                else:
                    print(f"  Waiting {wait_minutes} minutes...")
                time.sleep(wait_minutes * 60)
    
    @classmethod
    def get_human_like_delay(cls, base_delay: float = 5.0) -> float:
        """Get a human-like delay with time-of-day variation."""
        multiplier = cls.get_delay_multiplier()
        
        # Add "typing time" - humans don't search instantly
        typing_delay = random.uniform(0.5, 2.0)
        
        # Add "reading time" - humans read results
        reading_delay = random.uniform(2.0, 5.0)
        
        # Total delay with variation
        total = (base_delay * multiplier) + typing_delay + reading_delay
        
        # Add random "distraction" delays occasionally (checking email, etc)
        if random.random() < 0.1:  # 10% chance
            distraction = random.uniform(10, 30)
            total += distraction
        
        return total


class SearchMonitor:
    """Monitor search success rates and detect when being blocked."""
    
    def __init__(self, output_dir: str = "."):
        self.log_file = Path(output_dir) / "search_monitor.json"
        self.stats = self.load_stats()
    
    def load_stats(self) -> Dict:
        """Load existing stats or create new."""
        if self.log_file.exists():
            with open(self.log_file, 'r') as f:
                return json.load(f)
        return {
            "locations": {},
            "failure_patterns": [],
            "last_success": None,
            "total_searches": 0,
            "total_failures": 0,
            "session_start": datetime.now().isoformat()
        }
    
    def save_stats(self):
        """Save stats to file."""
        with open(self.log_file, 'w') as f:
            json.dump(self.stats, f, indent=2, default=str)
    
    def record_search(self, location: str, success: bool, jobs_found: int = 0, error: str = None):
        """Record a search attempt."""
        self.stats["total_searches"] += 1
        
        if not success:
            self.stats["total_failures"] += 1
            self.stats["failure_patterns"].append({
                "time": datetime.now().isoformat(),
                "location": location,
                "error": error
            })
            # Keep only last 100 failures to avoid memory issues
            if len(self.stats["failure_patterns"]) > 100:
                self.stats["failure_patterns"] = self.stats["failure_patterns"][-100:]
        else:
            self.stats["last_success"] = datetime.now().isoformat()
        
        # Track per-location stats
        if location not in self.stats["locations"]:
            self.stats["locations"][location] = {
                "attempts": 0,
                "successes": 0,
                "failures": 0,
                "jobs_found": 0
            }
        
        loc_stats = self.stats["locations"][location]
        loc_stats["attempts"] += 1
        if success:
            loc_stats["successes"] += 1
            loc_stats["jobs_found"] += jobs_found
        else:
            loc_stats["failures"] += 1
        
        self.save_stats()
    
    def should_pause(self) -> Tuple[bool, str]:
        """Check if we should pause based on failure patterns."""
        # Check recent failure rate
        recent_failures = []
        one_hour_ago = datetime.now() - timedelta(hours=1)
        
        for f in self.stats["failure_patterns"]:
            try:
                failure_time = datetime.fromisoformat(f["time"])
                if failure_time > one_hour_ago:
                    recent_failures.append(f)
            except:
                continue
        
        if len(recent_failures) > 5:
            return True, f"Too many recent failures ({len(recent_failures)} in last hour)"
        
        # Check consecutive failures
        if len(self.stats["failure_patterns"]) >= 3:
            last_failures = self.stats["failure_patterns"][-3:]
            # Check if all within 5 minutes
            try:
                times = [datetime.fromisoformat(f["time"]) for f in last_failures]
                if (times[-1] - times[0]).total_seconds() < 300:
                    return True, "3 consecutive failures within 5 minutes"
            except:
                pass
        
        # Check overall failure rate
        if self.stats["total_searches"] > 20:
            failure_rate = self.stats["total_failures"] / self.stats["total_searches"]
            if failure_rate > 0.3:  # More than 30% failures
                return True, f"High failure rate: {failure_rate:.1%}"
        
        return False, "OK"
    
    def get_summary(self) -> str:
        """Get summary statistics."""
        total = self.stats["total_searches"]
        if total == 0:
            return "No searches recorded yet"
        
        success_rate = (total - self.stats["total_failures"]) / total * 100
        
        return f"""
Search Statistics:
- Total searches: {total}
- Success rate: {success_rate:.1f}%
- Last success: {self.stats.get('last_success', 'Never')}
- Unique locations: {len(self.stats['locations'])}
- Session start: {self.stats.get('session_start', 'Unknown')}
"""


class SafetyManager:
    """Manages safety features like breaks, region rotation, and progress tracking."""
    
    def __init__(self, output_dir: str = "."):
        self.output_dir = Path(output_dir)
        self.progress_file = self.output_dir / "search_progress.yaml"
        self.load_progress()
    
    def load_progress(self):
        """Load search progress."""
        if self.progress_file.exists():
            with open(self.progress_file, 'r') as f:
                self.progress = yaml.safe_load(f) or {}
        else:
            self.progress = {
                "completed_regions": [],
                "completed_centers": [],
                "last_search_time": None,
                "total_runtime_minutes": 0
            }
    
    def save_progress(self):
        """Save search progress."""
        with open(self.progress_file, 'w') as f:
            yaml.dump(self.progress, f, default_flow_style=False)
    
    def mark_region_complete(self, region_name: str):
        """Mark a region as complete."""
        if region_name not in self.progress["completed_regions"]:
            self.progress["completed_regions"].append(region_name)
        self.progress["last_search_time"] = datetime.now().isoformat()
        self.save_progress()
    
    def mark_center_complete(self, center_code: str):
        """Mark a center as complete."""
        if center_code not in self.progress["completed_centers"]:
            self.progress["completed_centers"].append(center_code)
        self.save_progress()
    
    def is_region_complete(self, region_name: str) -> bool:
        """Check if region is already complete."""
        return region_name in self.progress.get("completed_regions", [])
    
    def is_center_complete(self, center_code: str) -> bool:
        """Check if center is already complete."""
        return center_code in self.progress.get("completed_centers", [])
    
    def should_take_break(self) -> Tuple[bool, float]:
        """Check if we should take a break."""
        if not self.progress.get("last_search_time"):
            return False, 0
        
        try:
            last_search = datetime.fromisoformat(self.progress["last_search_time"])
            time_since = (datetime.now() - last_search).total_seconds()
            
            # If we've been running for more than 30 minutes, suggest a break
            if time_since < 1800:  # Less than 30 minutes
                return False, 0
            
            # Random break between 5-15 minutes
            break_minutes = random.uniform(5, 15)
            return True, break_minutes
        except:
            return False, 0
    
    def get_randomized_centers(self, centers: List) -> List:
        """Get randomized list of centers, excluding completed ones."""
        # Filter out completed centers
        remaining = [c for c in centers 
                    if not self.is_center_complete(getattr(c, 'code', str(c)))]
        
        # Randomize order
        random.shuffle(remaining)
        return remaining
    
    def reset_progress(self):
        """Reset all progress tracking."""
        self.progress = {
            "completed_regions": [],
            "completed_centers": [],
            "last_search_time": None,
            "total_runtime_minutes": 0
        }
        self.save_progress()