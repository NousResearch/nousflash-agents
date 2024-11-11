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
from behavior import HumanBehaviorSimulator
from eth_keys import keys
from dotenv import load_dotenv
from twitter.account import Account
from engines.twitter.post_sender import PostSender
from pipeline import PostingPipeline, Config
from config import Config, ConfigMaker
from db.db_setup import create_database, get_db
from engines.wallet.wallet_send import WalletManager

class PipelineRunner:
    def __init__(self):
        self.config_maker = ConfigMaker()
        self.config_maker.setup_environment()
        self.db = next(get_db())
        self.make_new_wallet = False
        self.wallet_manager = WalletManager()
        self.config = self.create_config()
        self.post_sender = PostSender()
        self.pipeline = PostingPipeline(self.config)
        self.behavior_simulator = HumanBehaviorSimulator()  # Initialize the simulator
                
    def create_config(self) -> Config:
        """Create pipeline configuration."""
        api_keys = self.config_maker.get_api_keys()
        twitter_auth, twitter_account = self.config_maker.get_twitter_config()
        
        if self.make_new_wallet:
            private_key_hex, eth_address = self.wallet_manager.generate_eth_account()
            print(f"Generated agent exclusively-owned wallet: {eth_address}")
            tweet_id = self.post_sender.send_post_API(twitter_auth, f'My wallet is {eth_address}')
            print(f"Wallet announcement tweet: https://x.com/user/status/{tweet_id}")
        else:
            private_key_hex, eth_address = self.wallet_manager.get_wallet_information()
    
        return Config(
            db=self.db,
            account=twitter_account,
            auth=twitter_auth,
            private_key_hex=private_key_hex,
            eth_mainnet_rpc_url=os.getenv("ETH_MAINNET_RPC_URL"),
            **api_keys
        )

    def run_pipeline_cycle(self) -> None:
        """Run a single pipeline cycle."""
        activation_time, active_duration = self.behavior_simulator.get_timing_parameters()
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

                next_run = self.behavior_simulator.get_next_run_time()
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