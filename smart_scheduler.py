#!/usr/bin/env python3
"""
Smart scheduler that runs searches during optimal times to blend in with normal traffic.
"""

import random
from datetime import datetime, time
import time as time_module

class SmartScheduler:
    """Schedule searches during business hours when traffic is highest."""
    
    # Optimal search windows (local time)
    PEAK_HOURS = [
        (time(9, 0), time(11, 30)),   # Morning job search peak
        (time(12, 30), time(14, 30)),  # Lunch break searches
        (time(16, 0), time(18, 0)),    # After work searches
        (time(19, 30), time(21, 30)),  # Evening searches
    ]
    
    # Days with different patterns
    WEEKDAY_MULTIPLIER = 1.0
    SATURDAY_MULTIPLIER = 0.7  # Less traffic
    SUNDAY_MULTIPLIER = 0.5     # Least traffic
    
    @classmethod
    def is_good_time_to_search(cls) -> tuple[bool, str]:
        """Check if current time is good for searching."""
        now = datetime.now()
        current_time = now.time()
        
        # Check day of week (0=Monday, 6=Sunday)
        day_of_week = now.weekday()
        
        # Avoid late night/early morning (2 AM - 6 AM)
        if time(2, 0) <= current_time <= time(6, 0):
            return False, "Too early - wait until business hours"
        
        # Check if in peak hours
        for start, end in cls.PEAK_HOURS:
            if start <= current_time <= end:
                return True, f"Peak hour window: {start.strftime('%H:%M')}-{end.strftime('%H:%M')}"
        
        # Off-peak but acceptable hours (6 AM - 10 PM)
        if time(6, 0) <= current_time <= time(22, 0):
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
    def wait_for_good_time(cls):
        """Wait until a good time to search."""
        while True:
            is_good, reason = cls.is_good_time_to_search()
            if is_good:
                print(f"✓ Good time to search: {reason}")
                break
            else:
                print(f"⏸ {reason}")
                # Check every 30 minutes
                wait_minutes = 30 + random.randint(-5, 5)
                print(f"  Waiting {wait_minutes} minutes...")
                time_module.sleep(wait_minutes * 60)
    
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

# Example usage:
if __name__ == "__main__":
    scheduler = SmartScheduler()
    
    # Check if good time
    is_good, reason = scheduler.is_good_time_to_search()
    print(f"Current time check: {reason}")
    
    if not is_good:
        scheduler.wait_for_good_time()
    
    # Get appropriate delay
    delay = scheduler.get_human_like_delay()
    print(f"Recommended delay: {delay:.1f} seconds")