
import random
from datetime import datetime, timedelta, time as dt_time
from typing import Tuple

class HumanBehaviorSimulator:
    """Simulates high-volume but natural-looking social media behavior patterns."""
    
    # Extended active hours (24-hour format)
    WEEKDAY_ACTIVE_HOURS = {
        'start': dt_time(6, 0),    # 6 AM
        'peak1': dt_time(9, 0),    # 9 AM
        'peak2': dt_time(12, 0),   # 12 PM
        'peak3': dt_time(15, 0),   # 3 PM
        'peak4': dt_time(19, 0),   # 7 PM
        'peak5': dt_time(22, 0),   # 10 PM
        'end': dt_time(1, 0)       # 1 AM
    }
    
    WEEKEND_ACTIVE_HOURS = {
        'start': dt_time(8, 0),    # 8 AM
        'peak1': dt_time(11, 0),   # 11 AM
        'peak2': dt_time(14, 0),   # 2 PM
        'peak3': dt_time(17, 0),   # 5 PM
        'peak4': dt_time(20, 0),   # 8 PM
        'peak5': dt_time(23, 0),   # 11 PM
        'end': dt_time(2, 0)       # 2 AM
    }
    
    def __init__(self):
        self.last_post_time = None
        self.daily_post_count = 0
        self.max_daily_posts = random.randint(100, 150)  # Target ~150 posts/day
        self.burst_mode = False
        self.burst_count = 0
        self.max_burst = random.randint(3, 5)
        self.last_burst_time = None
        
    def is_active_hour(self) -> bool:
        """Determine if current time is within active hours."""
        current_time = datetime.now().time()
        current_day = datetime.now().weekday()
        hours = self.WEEKEND_ACTIVE_HOURS if current_day >= 5 else self.WEEKDAY_ACTIVE_HOURS
        
        # Handle day transition
        if hours['end'] < hours['start']:
            return current_time >= hours['start'] or current_time <= hours['end']
        return hours['start'] <= current_time <= hours['end']
    
    def get_post_probability(self) -> float:
        """Calculate probability of posting based on time and previous activity."""
        if not self.is_active_hour():
            return 0.2  # Still maintain some off-hours activity
        
        current_time = datetime.now().time()
        current_day = datetime.now().weekday()
        hours = self.WEEKEND_ACTIVE_HOURS if current_day >= 5 else self.WEEKDAY_ACTIVE_HOURS
        
        # Base probability higher to achieve volume
        prob = 0.7
        
        # Check if we're in burst mode
        if self.burst_mode:
            if self.burst_count >= self.max_burst:
                self.burst_mode = False
                self.burst_count = 0
                prob *= 0.3  # Cool down after burst
            else:
                prob = 0.9  # High probability during burst
                
        # Start new burst randomly
        elif (not self.last_burst_time or 
              (datetime.now() - self.last_burst_time).total_seconds() > 1800):  # 30 min
            if random.random() < 0.2:  # 20% chance to start burst
                self.burst_mode = True
                self.last_burst_time = datetime.now()
                prob = 0.9
        
        # Increase probability during peak hours
        for peak_hour in ['peak1', 'peak2', 'peak3', 'peak4', 'peak5']:
            peak_time = hours[peak_hour]
            time_diff = abs(current_time.hour - peak_time.hour)
            if time_diff <= 1:
                prob *= 1.3
                break
                
        # Minimum gap between regular posts (2-5 minutes)
        if self.last_post_time:
            minutes_since_last = (datetime.now() - self.last_post_time).total_seconds() / 60
            if minutes_since_last < 2:
                return 0
            elif minutes_since_last < 5:
                prob *= 0.5
                
        # Adjust for daily target
        hours_remaining = (24 - datetime.now().hour)
        target_remaining = self.max_daily_posts - self.daily_post_count
        if hours_remaining > 0:
            current_rate = target_remaining / hours_remaining
            if current_rate > 3:  # Need to post more frequently
                prob *= 1.2
            elif current_rate < 1:  # Can slow down
                prob *= 0.8
                
        return min(prob, 1.0)
    
    def should_post(self) -> bool:
        """Decide whether to post based on various factors."""
        # Reset daily count if it's a new day
        if self.last_post_time and self.last_post_time.date() != datetime.now().date():
            self.daily_post_count = 0
            self.max_daily_posts = random.randint(45, 60)
            self.burst_mode = False
            self.burst_count = 0
        
        prob = self.get_post_probability()
        should_post = random.random() < prob
        
        if should_post:
            self.last_post_time = datetime.now()
            self.daily_post_count += 1
            if self.burst_mode:
                self.burst_count += 1
            
        return should_post
    
    def get_timing_parameters(self) -> Tuple[datetime, timedelta]:
        """Calculate next activation time and duration."""
        if self.burst_mode:
            # Shorter cycles during burst mode
            delay_minutes = random.uniform(1, 3)
            duration_minutes = random.uniform(5, 10)
        else:
            # Regular timing
            if not self.is_active_hour():
                delay_minutes = random.uniform(10, 20)
                duration_minutes = random.uniform(5, 10)
            else:
                delay_minutes = random.uniform(3, 8)
                duration_minutes = random.uniform(8, 15)
        
        activation_time = datetime.now() + timedelta(minutes=delay_minutes)
        active_duration = timedelta(minutes=duration_minutes)
        return activation_time, active_duration

    def get_next_run_time(self) -> datetime:
        """Calculate next run time with variable delays."""
        if self.burst_mode:
            # Quick checks during bursts
            delay_seconds = random.uniform(30, 90)
        else:
            # Regular timing
            if self.is_active_hour():
                delay_seconds = random.uniform(60, 180)  # 1-3 minutes
            else:
                delay_seconds = random.uniform(180, 300)  # 3-5 minutes
                
        return datetime.now() + timedelta(seconds=delay_seconds)