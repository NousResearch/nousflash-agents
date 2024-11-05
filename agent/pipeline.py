from dataclasses import dataclass
from typing import List, Tuple, Optional
import json
import os
import time
import re
from random import random
from sqlalchemy.orm import Session

from db.db_setup import get_db
from models import Post, User, TweetPost
from twitter.account import Account

from engines.post_retriever import (
    retrieve_recent_posts,
    fetch_external_context,
    fetch_notification_context,
    format_post_list
)
from engines.short_term_mem import generate_short_term_memory
from engines.long_term_mem import create_embedding, retrieve_relevant_memories, store_memory
from engines.post_maker import generate_post
from engines.significance_scorer import score_significance, score_reply_significance
from engines.post_sender import send_post, send_post_API
from engines.wallet_send import transfer_eth, wallet_address_in_post, get_wallet_balance
from engines.follow_user import follow_by_username, decide_to_follow_users

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
    min_storing_memory_significance: float = 7.0
    min_reply_worthiness_score: float = 3.0
    min_follow_score: float = 0.75
    min_eth_balance: float = 0.3
    bot_username: str = "tee_hee_he"
    bot_email: str = "tee_hee_he@example.com"

class PostingPipeline:
    def __init__(self, config: Config):
        self.config = config
        self.ai_user = self._get_or_create_ai_user()

    def _get_or_create_ai_user(self) -> User:
        """Get or create the AI user in the database."""
        ai_user = (self.config.db.query(User)
                  .filter(User.username == self.config.bot_username)
                  .first())
        
        if not ai_user:
            ai_user = User(
                username=self.config.bot_username,
                email=self.config.bot_email
            )
            self.config.db.add(ai_user)
            self.config.db.commit()
        
        return ai_user

    def _handle_wallet_transactions(self, notif_context: List[str]) -> None:
        """Process and execute wallet transactions if conditions are met."""
        balance_ether = get_wallet_balance(
            self.config.private_key_hex,
            self.config.eth_mainnet_rpc_url
        )
        print(f"Agent wallet balance is {balance_ether} ETH now.\n")

        if balance_ether <= self.config.min_eth_balance:
            return

        for _ in range(2):  # Max 2 attempts
            try:
                wallet_data = wallet_address_in_post(
                    notif_context,
                    self.config.private_key_hex,
                    self.config.eth_mainnet_rpc_url,
                    self.config.llm_api_key
                )
                wallets = json.loads(wallet_data)
                
                if not wallets:
                    print("No wallet addresses or amounts to send ETH to.")
                    break

                for wallet in wallets:
                    transfer_eth(
                        self.config.private_key_hex,
                        self.config.eth_mainnet_rpc_url,
                        wallet["address"],
                        wallet["amount"]
                    )
                break
            except (json.JSONDecodeError, KeyError) as e:
                print(f"Error processing wallet data: {e}")
                continue

    def _handle_follows(self, notif_context: List[str]) -> None:
        """Process and execute follow decisions."""
        for _ in range(2):  # Max 2 attempts
            try:
                decision_data = decide_to_follow_users(
                    self.config.db,
                    notif_context,
                    self.config.openrouter_api_key
                )
                decisions = json.loads(decision_data)
                
                if not decisions:
                    print("No users to follow.")
                    break

                for decision in decisions:
                    username = decision["username"]
                    score = decision["score"]
                    
                    if score > self.config.min_follow_score:
                        follow_by_username(self.config.account, username)
                        print(f"user {username} has a high rizz of {score}, now following.")
                    else:
                        print(f"Score {score} for user {username} is too low. Not following.")
                break
            except Exception as e:
                print(f"Error processing follow decisions: {e}")
                continue

    def _should_reply(self, content: str, user_id: str) -> bool:
        """Determine if we should reply to a post."""
        if user_id.lower() == self.config.bot_username:
            return False
        
        if random() > self.config.max_reply_rate:
            return False

        reply_significance_score = score_reply_significance(
            content,
            self.config.llm_api_key
        )
        print(f"Reply significance score: {reply_significance_score}")

        if reply_significance_score >=self.config.min_reply_worthiness_score:
            return True
        else:
            return False

    def _handle_replies(self, external_context: List[Tuple[str, str]]) -> None:
        """Handle replies to mentions and interactions."""
        for content, tweet_id in external_context:
            user_match = re.search(r'@(\w+)', content)
            if not user_match:
                continue

            user_id = user_match.group(1)
            if self._should_reply(content, user_id) == False:
                continue

            try:
                reply_content = generate_post(
                    short_term_memory="",
                    long_term_memories=[],
                    recent_posts=[],
                    external_context=content,
                    llm_api_key=self.config.llm_api_key
                )

                response = self.config.account.reply(reply_content, tweet_id=tweet_id)
                print(f"Replied to {user_id} with: {reply_content}")

                new_reply = Post(
                    content=reply_content,
                    user_id=self.ai_user.id,
                    username=self.ai_user.username,
                    type="reply",
                    tweet_id=response.get('data', {}).get('id')
                )
                self.config.db.add(new_reply)
                self.config.db.commit()

            except Exception as e:
                print(f"Error handling reply: {e}")

    def _post_content(self, content: str) -> Optional[str]:
        """Attempt to post content using available methods."""
        # Try API method first
        tweet_id = send_post_API(self.config.auth, content)
        if tweet_id:
            return tweet_id

        # Fallback to account method
        response = send_post(self.config.account, content)
        return (response.get('data', {})
                .get('create_tweet', {})
                .get('tweet_results', {})
                .get('result', {})
                .get('rest_id'))

    def run(self) -> None:
        """Execute the main pipeline."""
        # Retrieve and format recent posts
        recent_posts = retrieve_recent_posts(self.config.db)
        formatted_posts = format_post_list(recent_posts)
        print(f"Recent posts: {formatted_posts}")

        # Process notifications
        notif_context_tuple = fetch_notification_context(self.config.account)
        existing_tweet_ids = {
            tweet.tweet_id for tweet in 
            self.config.db.query(TweetPost.tweet_id).all()
        }
        
        # Filter new notifications
        filtered_notifs = [
            context for context in notif_context_tuple 
            if context[1] not in existing_tweet_ids
        ]

        # Store processed tweet IDs
        for _, tweet_id in notif_context_tuple:
            self.config.db.add(TweetPost(tweet_id=tweet_id))
        self.config.db.commit()

        notif_context = [context[0] for context in filtered_notifs]
        print("New Notifications:")
        for content, tweet_id in filtered_notifs:
            print(f"- {content}, tweet at https://x.com/user/status/{tweet_id}\n")

        if notif_context:
            self._handle_replies(filtered_notifs)
            time.sleep(5)
            
            self._handle_wallet_transactions(notif_context)
            time.sleep(5)
            
            self._handle_follows(notif_context)
            time.sleep(5)

        # Generate and process memories
        short_term_memory = generate_short_term_memory(
            recent_posts,
            notif_context,
            self.config.llm_api_key
        )
        print(f"Short-term memory: {short_term_memory}")

        short_term_embedding = create_embedding(
            short_term_memory,
            self.config.openai_api_key
        )
        
        long_term_memories = retrieve_relevant_memories(
            self.config.db,
            short_term_embedding
        )
        print(f"Long-term memories: {long_term_memories}")

        # Generate and evaluate new post
        new_post_content = generate_post(
            short_term_memory,
            long_term_memories,
            formatted_posts,
            notif_context,
            self.config.llm_api_key
        ).strip('"')
        print(f"New post content: {new_post_content}")

        significance_score = score_significance(
            new_post_content,
            self.config.llm_api_key
        )
        print(f"Significance score: {significance_score}")

        # Store significant memories
        if significance_score >= self.config.min_storing_memory_significance:
            new_post_embedding = create_embedding(
                new_post_content,
                self.config.openai_api_key
            )
            store_memory(
                self.config.db,
                new_post_content,
                new_post_embedding,
                significance_score
            )

        # Post if significant enough
        if significance_score >= self.config.min_posting_significance_score:
            tweet_id = self._post_content(new_post_content)
            if tweet_id:
                new_post = Post(
                    content=new_post_content,
                    user_id=self.ai_user.id,
                    username=self.ai_user.username,
                    type="text",
                    tweet_id=tweet_id
                )
                self.config.db.add(new_post)
                self.config.db.commit()
                print(f"Posted with tweet_id: {tweet_id}")