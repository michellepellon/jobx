#!/usr/bin/env python3
"""
Monitor search success rates and detect when being blocked.
"""

import json
from pathlib import Path
from datetime import datetime
from collections import defaultdict

class SearchMonitor:
    def __init__(self, log_file="search_monitor.json"):
        self.log_file = Path(log_file)
        self.stats = self.load_stats()
    
    def load_stats(self):
        """Load existing stats or create new."""
        if self.log_file.exists():
            with open(self.log_file, 'r') as f:
                return json.load(f)
        return {
            "locations": defaultdict(dict),
            "failure_patterns": [],
            "last_success": None,
            "total_searches": 0,
            "total_failures": 0,
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
    
    def should_pause(self) -> tuple[bool, str]:
        """Check if we should pause based on failure patterns."""
        # Check recent failure rate
        recent_failures = [
            f for f in self.stats["failure_patterns"]
            if datetime.fromisoformat(f["time"]) > 
               datetime.now().replace(hour=datetime.now().hour-1)
        ]
        
        if len(recent_failures) > 5:
            return True, f"Too many recent failures ({len(recent_failures)} in last hour)"
        
        # Check consecutive failures
        if self.stats["failure_patterns"]:
            last_failures = self.stats["failure_patterns"][-3:]
            if len(last_failures) == 3:
                # 3 consecutive failures
                time_diffs = []
                for i in range(1, len(last_failures)):
                    t1 = datetime.fromisoformat(last_failures[i-1]["time"])
                    t2 = datetime.fromisoformat(last_failures[i]["time"]) 
                    time_diffs.append((t2 - t1).total_seconds())
                
                if all(diff < 300 for diff in time_diffs):  # All within 5 minutes
                    return True, "3 consecutive failures detected"
        
        # Check overall failure rate
        if self.stats["total_searches"] > 20:
            failure_rate = self.stats["total_failures"] / self.stats["total_searches"]
            if failure_rate > 0.3:  # More than 30% failures
                return True, f"High failure rate: {failure_rate:.1%}"
        
        return False, "OK"
    
    def get_summary(self):
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
- Recent failures: {len([f for f in self.stats['failure_patterns'] if datetime.fromisoformat(f['time']) > datetime.now().replace(hour=datetime.now().hour-1)])} in last hour
"""

# Example integration:
if __name__ == "__main__":
    monitor = SearchMonitor()
    
    # Simulate some searches
    monitor.record_search("Miami, FL", True, jobs_found=45)
    monitor.record_search("Orlando, FL", True, jobs_found=38)
    monitor.record_search("Tampa, FL", False, error="Rate limited")
    
    # Check if should pause
    should_pause, reason = monitor.should_pause()
    if should_pause:
        print(f"⚠️ PAUSE RECOMMENDED: {reason}")
    
    # Show summary
    print(monitor.get_summary())