from typing import Dict, Optional
import requests
from models import TweetPost
from twitter.account import Account

class PostSender:
    def __init__(self):
        pass

    def reply_post(self, account: Account, content: str, tweet_id) -> str:
        res = account.reply(content, tweet_id=tweet_id)
        return res

    def send_post_API(self, auth, content: str) -> str:
        """
        Posts a tweet on behalf of the user.
        Parameters:
        - content: The message to tweet.
        """
        url = 'https://api.twitter.com/2/tweets'

        # Prepare the payload
        payload = {
            'text': content
        }
        try:
            response = requests.post(url, json=payload, auth=auth)

            if response.status_code == 201:  # Twitter API returns 201 for successful tweet creation
                tweet_data = response.json()
                return tweet_data['data']['id']
            else:
                print(f'Error: {response.status_code} - {response.text}')
                return None
        except Exception as e:
            print(f'Failed to post tweet: {str(e)}')
            return None

    def send_post(self, account: Account, content: str) -> str:
        """
        Posts a tweet on behalf of the user.

        Parameters:
        - content: The message to tweet.
        """

        res = account.tweet(content)
        return res


    def verify_post_success(self, response: Dict) -> bool:
        """
        Verify that a post was successfully sent by checking the API response.
        Returns True if the post was successful, False otherwise.
        """
        try:
            # Check for the expected successful response structure
            tweet_result = (response.get('data', {})
                           .get('create_tweet', {})
                           .get('tweet_results', {})
                           .get('result', {}))

            if not tweet_result:
                print("Warning: Incomplete tweet response structure")
                return False

            # Get the tweet ID
            tweet_id = tweet_result.get('rest_id')
            if not tweet_id:
                print("Warning: No tweet ID in response")
                return False

            # Verify tweet text matches what we tried to send
            tweet_text = (tweet_result.get('legacy', {})
                         .get('full_text', ''))

            print(f"Tweet successfully posted with ID: {tweet_id}")
            print(f"Tweet URL: https://x.com/user/status/{tweet_id}")

            return True

        except Exception as e:
            print(f"Error verifying tweet post: {str(e)}")



    def _post_content(self, content: str) -> Optional[str]:
        """Attempt to post content using available methods."""
        # Try API method first
        tweet_id = self.send_post_API(self.config.auth, content)
        if tweet_id:
            return tweet_id
        # Fallback to account method
        response = self.send_post(self.config.account, content)
        return (response.get('data', {})
                .get('create_tweet', {})
                .get('tweet_results', {})
                .get('result', {})
                .get('rest_id'))
    

    def store_processed_tweets(self, db, notif_context_tuple) -> None:
        """
        Store processed tweet IDs in the database.

        Args:
            db: Database session
            notif_context_tuple: List of notification contexts containing tweet IDs
        """
        print("Storing processed tweet IDs")

        for context in notif_context_tuple:
            try:
                if isinstance(context, (list, tuple)) and len(context) >= 2:
                    tweet_id = context[1]
                    db.add(TweetPost(tweet_id=tweet_id))
            except Exception as e:
                print(f"Error processing tweet for storage: {e}")
                print(f"Problematic context: {context}")
                continue
            
        try:
            db.commit()
            print("Processed tweets stored")
        except Exception as e:
            print(f"Error committing to database: {e}")
            db.rollback()