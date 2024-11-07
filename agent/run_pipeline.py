import os
import time
import random
import json
import secrets
import hashlib
from datetime import datetime, timedelta, time as dt_time
from typing import Tuple, Dict
from pathlib import Path
from requests_oauthlib import OAuth1
from eth_keys import keys
from dotenv import load_dotenv

from db.db_setup import create_database, get_db
from db.db_seed import seed_database
from twitter.account import Account
from engines.post_sender import send_post_API
from pipeline import PostingPipeline, Config

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


class PipelineRunner:
    def __init__(self):
        self.setup_environment()
        self.db = next(get_db())
        self.make_new_wallet = False
        self.config = self.create_config()
        self.pipeline = PostingPipeline(self.config)
        self.behavior_simulator = HumanBehaviorSimulator()  # Initialize the simulator
                
    def setup_environment(self) -> None:
        """Initialize environment and database."""
        load_dotenv()
        
        db_path = Path("./data/agents.db")
        if not db_path.exists():
            print("Creating database...")
            db_path.parent.mkdir(parents=True, exist_ok=True)
            create_database()
            print("Seeding database...")
            seed_database()
        else:
            print("Database already exists. Skipping creation and seeding.")

    def generate_eth_account(self) -> Tuple[str, str]:
        """Generate a new Ethereum account with private key and address."""
        random_seed = secrets.token_bytes(32)
        hashed_output = hashlib.sha256(random_seed).digest()
        private_key = keys.PrivateKey(hashed_output)
        private_key_hex = private_key.to_hex()
        eth_address = private_key.public_key.to_checksum_address()
        return private_key_hex, eth_address
    
    def get_wallet_information(self) -> Tuple[str, str]:
        """Retrieve wallet information from environment variables."""
        private_key_hex = os.getenv("AGENT_WALLET_PRIVATE_KEY")
        eth_address = os.getenv("AGENT_WALLET_ADDRESS")
        return private_key_hex, eth_address

    def get_api_keys(self) -> Dict[str, str]:
        """Retrieve API keys from environment variables."""
        return {
            "llm_api_key": os.getenv("HYPERBOLIC_API_KEY"),
            "openai_api_key": os.getenv("OPENAI_API_KEY"),
            "openrouter_api_key": os.getenv("OPENROUTER_API_KEY"),
        }

    def get_twitter_config(self) -> Tuple[OAuth1, Account]:
        """Set up Twitter authentication and account."""
        auth = OAuth1(
            os.getenv("X_CONSUMER_KEY"),
            os.getenv("X_CONSUMER_SECRET"),
            os.getenv("X_ACCESS_TOKEN"),
            os.getenv("X_ACCESS_TOKEN_SECRET")
        )
        
        auth_tokens = json.loads(os.getenv("X_AUTH_TOKENS"))
        account = Account(cookies=auth_tokens)
        
        return auth, account

    def create_config(self) -> Config:
        """Create pipeline configuration."""
        api_keys = self.get_api_keys()
        auth, account = self.get_twitter_config()
        
        if self.make_new_wallet:
            private_key_hex, eth_address = self.generate_eth_account()
        else:
            private_key_hex, eth_address = self.get_wallet_information()
        
        print(f"Generated agent exclusively-owned wallet: {eth_address}")
        tweet_id = send_post_API(auth, f'My wallet is {eth_address}')
        print(f"Wallet announcement tweet: https://x.com/user/status/{tweet_id}")
        
        return Config(
            db=self.db,
            account=account,
            auth=auth,
            private_key_hex=private_key_hex,
            eth_mainnet_rpc_url=os.getenv("ETH_MAINNET_RPC_URL"),
            **api_keys
        )

    def get_timing_parameters(self) -> Tuple[datetime, timedelta]:
        """Calculate next activation time and duration."""
        if self.behavior_simulator.burst_mode:
            # Shorter cycles during burst mode
            delay_minutes = random.uniform(1, 3)
            duration_minutes = random.uniform(5, 10)
        else:
            # Regular timing
            if not self.behavior_simulator.is_active_hour():
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
        if self.behavior_simulator.burst_mode:
            # Quick checks during bursts
            delay_seconds = random.uniform(30, 90)
        else:
            # Regular timing
            if self.behavior_simulator.is_active_hour():
                delay_seconds = random.uniform(60, 180)  # 1-3 minutes
            else:
                delay_seconds = random.uniform(180, 300)  # 3-5 minutes
                
        return datetime.now() + timedelta(seconds=delay_seconds)

    def run_pipeline_cycle(self) -> None:
        """Run a single pipeline cycle."""
        activation_time, active_duration = self.get_timing_parameters()
        deactivation_time = activation_time + active_duration

        print(f"\nNext cycle:")
        print(f"Activation time: {activation_time.strftime('%I:%M:%S %p')}")
        print(f"Deactivation time: {deactivation_time.strftime('%I:%M:%S %p')}")
        print(f"Duration: {active_duration.total_seconds() / 60:.1f} minutes")
        print(f"Daily post cycles so far: {self.behavior_simulator.daily_post_count}")
        print(f"Burst mode: {'Yes' if self.behavior_simulator.burst_mode else 'No'}")

        # Wait for activation time
        while datetime.now() < activation_time:
            time.sleep(60)

        print(f"\nPipeline activated at: {datetime.now().strftime('%H:%M:%S')}")
        next_run = self.get_next_run_time()

        while datetime.now() < deactivation_time:
            if datetime.now() >= next_run:
                if self.behavior_simulator.should_post():
                    print(f"Running pipeline at: {datetime.now().strftime('%H:%M:%S')}")
                    try:
                        self.pipeline.run()
                    except Exception as e:
                        print(f"Error running pipeline: {e}")
                else:
                    print("Skipping post based on behavior pattern...")

                next_run = self.get_next_run_time()
                print(
                    f"Next run scheduled for: {next_run.strftime('%H:%M:%S')} "
                    f"({(next_run - datetime.now()).total_seconds():.1f} seconds from now)"
                )

            time.sleep(1)

        print(f"Pipeline deactivated at: {datetime.now().strftime('%H:%M:%S')}")

    def run(self) -> None:
        """Main execution loop."""
        print("\nPerforming initial pipeline run...")
        try:
            self.pipeline.run()
            print("Initial run completed successfully.")
        except Exception as e:
            print(f"Error during initial run: {e}")

        print("Starting continuous pipeline process...")
        while True:
            try:
                self.run_pipeline_cycle()
            except Exception as e:
                print(f"Error in pipeline cycle: {e}")
                continue

def main():
    try:
        runner = PipelineRunner()
        runner.run()
    except KeyboardInterrupt:
        print("\nProcess terminated by user")

if __name__ == "__main__":
    main()