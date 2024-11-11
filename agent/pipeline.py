from dataclasses import dataclass, field
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

from engines.twitter.post_retriever import PostRetriever
from engines.memory.short_term_mem import ShortTermMemoryManager
from engines.memory.long_term_mem import LongTermMemoryManager, LongTermMemory
from engines.twitter.post_maker import PostMaker
from engines.memory.significance_scorer import SignificanceScorer
from engines.twitter.post_sender import PostSender
from engines.wallet.wallet_send import WalletManager
from engines.twitter.follow_user import FollowManager
from engines.twitter.reply_manager import ReplyManager
from engines.twitter.create_user import UserManager
from notification_queue import NotificationQueue
from config import Config

class PostingPipeline:
    def __init__(self, config: Config):
        self.config = config
        self.post_retriever = PostRetriever()
        self.short_term_mem = ShortTermMemoryManager()
        self.long_term_mem = LongTermMemoryManager()
        self.post_maker = PostMaker()
        self.significance_scorer = SignificanceScorer()
        self.post_sender = PostSender()
        self.wallet_manager = WalletManager()
        self.follow_manager = FollowManager(self.config)
        self.notification_queue = NotificationQueue()
        self.user_manager = UserManager()
        self.ai_user = self.user_manager._get_or_create_ai_user(self.config.db, 
                                                                self.config.bot_username, 
                                                                self.config.bot_email)
        self.reply_manager = ReplyManager(self.config, self.ai_user)

    def run(self) -> None:
        """Execute the main pipeline."""
        # Retrieve and format recent posts
        recent_posts = self.post_retriever.retrieve_recent_posts(self.config.db)
        formatted_posts = self.post_retriever.format_post_list(recent_posts)
        print(f"Recent posts: {formatted_posts}")

        # Process notifications
        notif_context_tuple = self.post_retriever.fetch_notification_context(self.config.account)
        print(f"Notification context: {notif_context_tuple}")

        existing_tweet_ids = self.post_retriever.get_existing_tweet_ids(self.config.db)
        print(f"Existing tweet ids: {existing_tweet_ids}")

        filtered_notifs = self.post_retriever.filter_notifications(notif_context_tuple, existing_tweet_ids)
        

        self.notification_queue.add(filtered_notifications=filtered_notifs)

         # If queue isn't ready, just store the tweet IDs and exit early
        if not self.notification_queue.is_ready():
            print(f"Queue not ready. Current size: {len(self.notification_queue)}")
            return

        # Store processed tweet IDs
        self.post_sender.store_processed_tweets(self.config.db, notif_context_tuple)
        
        # Let agent go through tweets now
        filtered_notifs_from_queue, notif_context = self.notification_queue.process_queue()

        if notif_context:
            try:
                self.reply_manager._handle_replies(filtered_notifs_from_queue)
                time.sleep(5)
            except Exception as e:
                print(f"Error handling replies: {e}")
            
            try:
                self.wallet_manager._handle_wallet_transactions(notif_context, self.config)
                time.sleep(5)
            except Exception as e:
                print(f"Error handling wallet transactions: {e}")
            
            try:
                self.follow_manager._handle_follows(notif_context)
                time.sleep(5)
            except Exception as e: 
                print(f"Error handling follows: {e}")
    
        # Generate and process memories
        short_term_memory = self.short_term_mem.generate_short_term_memory(
            recent_posts,
            notif_context,
            self.config.llm_api_key
        )
        print(f"Short-term memory: {short_term_memory}")

        
        # Get relevant long term memories
        long_term_memories = self.long_term_mem.retrieve_relevant_memories(
            db=self.config.db,
            query=short_term_memory,
            openai_api_key=self.config.openai_api_key
        )
        print(f"Long-term memories: {long_term_memories}")

        # Generate and evaluate new post
        new_post_content, significance_score = self.post_maker.generate_and_evaluate_post(
           short_term_memory,
           long_term_memories,
           formatted_posts,
           notif_context,
           self.config.llm_api_key,
           self.config.openai_api_key,
           self.config.db,
           self.config.min_storing_memory_significance
        )

        # Post if significant enough
        if significance_score >= self.config.min_posting_significance_score:
            tweet_id = self.post_maker._post_content(new_post_content)
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
        
        # Remove processed tweet IDs from the queue
        self.notification_queue.clear()