from dataclasses import dataclass
import json
import os
from pathlib import Path
from typing import Dict, Tuple
from sqlalchemy.orm import Session
from twitter.account import Account
from dotenv import load_dotenv
from requests_oauthlib import OAuth1

from db.db_setup import create_database, get_db
from db.db_seed import seed_database


@dataclass
class Config:
    """Configuration for the pipeline."""
    db: Session
    account: Account
    auth: dict
    private_key_hex: str
    eth_mainnet_rpc_url: str
    llm_api_key: str
    openrouter_api_key: str
    openai_api_key: str
    max_reply_rate: float = 1.0  # 100% for testing
    min_posting_significance_score: float = 3.0
    min_storing_memory_significance: float = 6.0
    min_reply_worthiness_score: float = 3.0
    min_follow_score: float = 0.9
    min_eth_balance: float = 0.3
    bot_username: str = "tee_hee_he"
    bot_email: str = "tee_hee_he@example.com"


class ConfigMaker:
    def __init__(self):
        pass
    
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
