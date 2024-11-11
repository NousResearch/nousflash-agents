import json
import requests
from typing import List, Dict
from sqlalchemy.orm import Session
from models import Post, TweetPost
from sqlalchemy.orm import class_mapper
from twitter.account import Account

class PostRetriever:
    def __init__(self):
        pass

    def sqlalchemy_obj_to_dict(self, obj):
        """Convert a SQLAlchemy object to a dictionary."""
        if obj is None:
            return None
        columns = [column.key for column in class_mapper(obj.__class__).columns]
        return {column: getattr(obj, column) for column in columns}


    def convert_posts_to_dict(self, posts):
        """Convert a list of SQLAlchemy Post objects to a list of dictionaries."""
        return [self.sqlalchemy_obj_to_dict(post) for post in posts]


    def retrieve_recent_posts(self, db: Session, limit: int = 10) -> List[Dict]:
        """
        Retrieve the most recent posts from the database.

        Args:
            db (Session): Database session
            limit (int): Number of posts to retrieve

        Returns:
            List[Dict]: List of recent posts as dictionaries
        """
        recent_posts = db.query(Post).order_by(Post.created_at.desc()).limit(limit).all()
        return [self.post_to_dict(post) for post in recent_posts]

    
    def get_existing_tweet_ids(self, db: Session) -> set:
        """
        Retrieve all existing tweet IDs from the database.
        
        Args:
            db: Database session
            
        Returns:
            set: Set of tweet IDs that have been processed
        """
        return {
            tweet.tweet_id for tweet in 
            db.query(TweetPost.tweet_id).all()
        }

    def post_to_dict(self, post: Post) -> Dict:
        """Convert a Post object to a dictionary."""
        return {
            "id": post.id,
            "content": post.content,
            "user_id": post.user_id,
            "created_at": post.created_at.isoformat() if post.created_at else None,
            "updated_at": post.updated_at.isoformat() if post.updated_at else None,
            "type": post.type,
            "comment_count": post.comment_count,
            "image_path": post.image_path,
            "tweet_id": post.tweet_id,
        }

    def format_post_list(self, posts) -> str:
        """
        Format posts into a readable string, handling both pre-formatted strings 
        and lists of post dictionaries.

        Args:
            posts: Either a string of posts or List[Dict] of post objects

        Returns:
            str: Formatted string of posts
        """
        # If it's already a string, return it
        if isinstance(posts, str):
            return posts

        # If it's None or empty
        if not posts:
            return "No recent posts"

        # If it's a list of dictionaries
        if isinstance(posts, list):
            formatted = []
            for post in posts:
                try:
                    # Handle dictionary format
                    if isinstance(post, dict):
                        content = post.get('content', '')
                        formatted.append(f"- {content}")
                    # Handle string format
                    elif isinstance(post, str):
                        formatted.append(f"- {post}")
                except Exception as e:
                    print(f"Error formatting post: {e}")
                    continue
                
            return "\n".join(formatted)

        # If we can't process it, return as string
        return str(posts)


    def fetch_external_context(self, api_key: str, query: str) -> List[str]:
        """
        Fetch external context from a news API or other source.

        Args:
            api_key (str): API key for the external service
            query (str): Search query

        Returns:
            List[str]: List of relevant news headlines or context
        """
        url = f"https://newsapi.org/v2/everything?q={query}&apiKey={api_key}"
        response = requests.get(url)
        if response.status_code == 200:
            news_items = response.json().get("articles", [])
            return [item["title"] for item in news_items[:5]]
        return []


    def parse_tweet_data(self, tweet_data):
        """Parse tweet data from the X API response."""
        try:
            all_tweets_info = []
            entries = tweet_data['data']['home']['home_timeline_urt']['instructions'][0]['entries']

            for entry in entries:
                entry_id = entry.get('entryId', '')
                tweet_id = entry_id.replace('tweet-', '') if entry_id.startswith('tweet-') else None

                if 'itemContent' not in entry.get('content', {}) or \
                   'tweet_results' not in entry.get('content', {}).get('itemContent', {}):
                    continue

                tweet_info = entry['content']['itemContent']['tweet_results'].get('result')
                if not tweet_info:
                    continue

                try:
                    user_info = tweet_info['core']['user_results']['result']['legacy']
                    tweet_details = tweet_info['legacy']

                    readable_format = {
                        "Tweet ID": tweet_id or tweet_details.get('id_str'),
                        "Entry ID": entry_id,
                        "Tweet Information": {
                            "text": tweet_details['full_text'],
                            "created_at": tweet_details['created_at'],
                            "likes": tweet_details['favorite_count'],
                            "retweets": tweet_details['retweet_count'],
                            "replies": tweet_details['reply_count'],
                            "language": tweet_details['lang'],
                            "tweet_id": tweet_details['id_str']
                        },
                        "Author Information": {
                            "name": user_info['name'],
                            "username": user_info['screen_name'],
                            "followers": user_info['followers_count'],
                            "following": user_info['friends_count'],
                            "account_created": user_info['created_at'],
                            "profile_image": user_info['profile_image_url_https']
                        },
                        "Tweet Metrics": {
                            "views": tweet_info.get('views', {}).get('count', '0'),
                            "bookmarks": tweet_details.get('bookmark_count', 0)
                        }
                    }
                    if tweet_details['favorite_count'] > 20 and user_info['followers_count'] > 300 and tweet_details['reply_count'] > 3:
                        all_tweets_info.append(readable_format)
                except KeyError:
                    continue

            return all_tweets_info

        except KeyError as e:
            return f"Error parsing data: {e}"


    def get_root_tweet_id(self, tweets, start_id):
        """Find the root tweet ID of a conversation."""
        current_id = start_id
        while True:
            tweet = tweets.get(str(current_id))
            if not tweet:
                return current_id
            parent_id = tweet.get('in_reply_to_status_id_str')
            if not parent_id or parent_id not in tweets:
                return current_id
            current_id = parent_id


    def format_conversation_for_llm(self, data, tweet_id):
        """Convert a conversation tree into LLM-friendly format."""
        tweets = data['globalObjects']['tweets']
        users = data['globalObjects']['users']

        def get_conversation_chain(current_id, processed_ids=None):
            if processed_ids is None:
                processed_ids = set()

            if not current_id or current_id in processed_ids:
                return []

            processed_ids.add(current_id)
            current_tweet = tweets.get(str(current_id))
            if not current_tweet:
                return []

            user = users.get(str(current_tweet['user_id']))
            username = f"@{user['screen_name']}" if user else "Unknown User"

            chain = [{
                'id': current_id,
                'username': username,
                'text': current_tweet['full_text'],
                'reply_to': current_tweet.get('in_reply_to_status_id_str')
            }]

            for potential_reply_id, potential_reply in tweets.items():
                if potential_reply.get('in_reply_to_status_id_str') == current_id:
                    chain.extend(get_conversation_chain(potential_reply_id, processed_ids))

            return chain

        root_id = self.get_root_tweet_id(tweets, tweet_id)
        conversation = get_conversation_chain(root_id)

        if not conversation:
            return "No conversation found."

        # Format the conversation for LLM
        output = ["New reply to my original conversation thread or a Mention from somebody:"]

        for i, tweet in enumerate(conversation, 1):
            reply_context = (f"[Replying to {next((t['username'] for t in conversation if t['id'] == tweet['reply_to']), 'unknown')}]"
                            if tweet['reply_to'] else "[Original tweet]")

            output.append(f"{i}. {tweet['username']} {reply_context}:")
            output.append(f"   \"{tweet['text']}\"")
            output.append("")

        return "\n".join(output)

    def find_all_conversations(self, data):
        """Find and format all conversations in the data."""
        if 'globalObjects' not in data or 'tweets' not in data['globalObjects']:
            return "no new replies or mentions"
        tweets = data['globalObjects']['tweets']
        processed_roots = set()
        conversations = []

        sorted_tweets = sorted(
            tweets.items(),
            key=lambda x: x[1]['created_at'],
            reverse=True
        )

        for tweet_id, _ in sorted_tweets:
            root_id = self.get_root_tweet_id(tweets, tweet_id)

            if root_id not in processed_roots:
                processed_roots.add(root_id)
                conversation = self.format_conversation_for_llm(data, tweet_id)
                if conversation != "No conversation found.":
                    conversations.append((conversation, tweet_id))

        if not conversations:
            return "No conversations found."

        return conversations


    def parse_tweet_data(self, data: dict) -> List[Dict]:
        """
        Parse tweet data with improved error handling and logging.
        Returns list of dicts containing parsed tweet information.
        """
        tweets_info = []

        try:
            # Check if we have the expected data structure
            if not isinstance(data, dict):
                print(f"Warning: Timeline data is not a dict. Type: {type(data)}")
                return tweets_info

            if 'data' not in data:
                print("Warning: No 'data' key in timeline response")
                return tweets_info

            tweet_details = data.get('data', {}).get('home', {}).get('home_timeline_urt', {}).get('instructions', [])

            if not tweet_details:
                print("Warning: No tweet details found in timeline")
                return tweets_info

            # Process each tweet entry
            for instruction in tweet_details:
                if instruction.get('type') != 'TimelineAddEntries':
                    continue

                for entry in instruction.get('entries', []):
                    try:
                        result = entry.get('content', {}).get('itemContent', {}).get('tweet_results', {}).get('result', {})
                        if not result:
                            continue

                        # Extract legacy data
                        legacy = result.get('legacy', {})
                        if not legacy:
                            continue

                        # Extract user data
                        user_data = result.get('core', {}).get('user_results', {}).get('result', {}).get('legacy', {})
                        if not user_data:
                            continue

                        tweet_info = {
                            "Tweet ID": legacy.get('id_str', ''),
                            "Tweet Information": {
                                "text": legacy.get('full_text', ''),
                                "created_at": legacy.get('created_at', ''),
                            },
                            "Author Information": {
                                "username": user_data.get('screen_name', ''),
                                "name": user_data.get('name', ''),
                            }
                        }

                        # Only add if we have the minimum required data
                        if tweet_info["Tweet ID"] and tweet_info["Tweet Information"]["text"] and tweet_info["Author Information"]["username"]:
                            tweets_info.append(tweet_info)

                    except Exception as e:
                        print(f"Error parsing individual tweet: {str(e)}")
                        continue

        except Exception as e:
            print(f"Error parsing timeline data: {str(e)}")
            if isinstance(data, dict):
                print(f"Available keys: {list(data.keys())}")
                if 'data' in data:
                    print(f"Data structure: {json.dumps(data['data'], indent=2)[:500]}...")

        return tweets_info

    def get_timeline(self, account: Account) -> List[tuple[str, str]]:
        """
        Get timeline using the Account-based approach with improved error handling.
        Returns list of tuples containing (tweet_text, tweet_id).
        """
        try:
            # Get timeline with error handling
            timeline = account.home_latest_timeline(20)
            if not timeline or not isinstance(timeline, list) or len(timeline) == 0:
                print(f"Warning: Invalid timeline response: {timeline}")
                return []

            # Check for errors in response
            if isinstance(timeline[0], dict) and 'errors' in timeline[0]:
                print(f"Timeline API errors: {timeline[0]['errors']}")
                return []

            # Parse tweets
            tweets_info = self.parse_tweet_data(timeline[0])
            filtered_timeline = []

            for tweet in tweets_info:
                try:
                    timeline_tweet_text = (
                        f'New post on my timeline from @{tweet["Author Information"]["username"]}: '
                        f'{tweet["Tweet Information"]["text"]}\n'
                    )
                    filtered_timeline.append((timeline_tweet_text, tweet["Tweet ID"]))
                except Exception as e:
                    print(f"Error formatting tweet: {str(e)}")
                    print(f"Problem tweet data: {tweet}")
                    continue

            if not filtered_timeline:
                print("Warning: No tweets were successfully parsed from timeline")

            return filtered_timeline

        except Exception as e:
            print(f"Error getting timeline: {str(e)}")
            print("Timeline response:", timeline if 'timeline' in locals() else 'No response')
            return []

    def fetch_notification_context(self, account: Account) -> str:
        """Fetch notification context using the new Account-based approach."""
        context = []

        # Get timeline posts
        print("getting timeline")
        timeline = self.get_timeline(account)
        print(timeline)
        context.extend(timeline)

        print("getting notifications")
        notifications = account.notifications()
        print(notifications)

        print(f"getting reply trees")
        context.extend(self.find_all_conversations(notifications))
        print(f"received reply trees")

        return context
    
    def filter_notifications(self, notif_context_tuple, existing_tweet_ids) -> list:
        """
        Filter notifications to only include unprocessed tweets.

        Args:
            notif_context_tuple: Tuple/List of notification contexts to filter
            existing_tweet_ids (set): Set of already processed tweet IDs

        Returns:
            list: Filtered notifications that haven't been processed
        """
        filtered_notifs = []

        for context in notif_context_tuple:
            try:
                if isinstance(context, (list, tuple)) and len(context) > 1:
                    if context[1] not in existing_tweet_ids:
                        filtered_notifs.append(context)
            except Exception as e:
                print(f"Error processing context {context}: {e}")

        print(f"Filtered notifs: {filtered_notifs}")
        return filtered_notifs