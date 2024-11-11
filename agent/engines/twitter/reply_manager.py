import json
import random
import re
import time
from typing import List, Tuple

from engines.memory.significance_scorer import SignificanceScorer
from engines.twitter.post_maker import PostMaker
from engines.twitter.post_sender import PostSender
from models import Post


class ReplyManager:
    def __init__(self, config, ai_user):
        self.config = config
        self.ai_user = ai_user
        self.post_maker = PostMaker()
        self.post_sender = PostSender()
        self.significance_scorer = SignificanceScorer()
        pass

    def _should_reply(self, content: str, user_id: str) -> bool:
            """Determine if we should reply to a post."""
            if user_id.lower() == self.config.bot_username:
                return False

            if random.random() > self.config.max_reply_rate:
                return False

            reply_significance_score = self.significance_scorer.score_reply_significance(
                content,
                self.config.llm_api_key
            )
            print(f"Reply significance score: {reply_significance_score}")

            if self.is_spam(content):
                reply_significance_score -= 3

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
            # dont reply to yourself
            if user_match.group(1) == self.config.bot_username:  # Changed comparison
                continue
            user_id = user_match.group(1)
            
            if self._should_reply(content, user_id) == False:
                continue
            try:
                reply_content = self.post_maker.generate_post(
                    short_term_memory="",
                    long_term_memories=[],
                    recent_posts=[],
                    external_context=content,
                    llm_api_key=self.config.llm_api_key,
                    query="what are you thinking of replying now\n<tweet>"
                )
                response = self.config.account.reply(reply_content, tweet_id=tweet_id)
                # Verify the post was successful
                if self.post_sender.verify_post_success(response):
                    print(f"VERIFIED Replied to {user_id} with: {reply_content}")
                else:
                    print("Warning: Post may not have been sent successfully")
                    print(f"Response received: {json.dumps(response, indent=2)}")

                # print(f"Reply API call response: {response}")
                # print(f"Replied to {user_id} with: {reply_content}")
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

            time.sleep(30)

    def is_spam(self, content: str) -> bool:
        """Check if content appears to be spam."""
        import re
        from unicodedata import normalize

        # Normalize more aggressively: remove all whitespace, symbols, zero-width chars
        clean = re.sub(r'[\s\.\-_\|\\/\(\)\[\]\u200b-\u200f\u2060\ufeff]+', '', 
                       normalize('NFKC', content.lower()))

        patterns = [
            r'[\$\€\¢\£\¥]|(?:usd[t]?|usdc|busd)',  
            r'(?:ca|с[aа]|market.?cap)[:\|/]?(?:\d|soon)',
            r't[i1І]ck[e3Е]r|symb[o0]l|(?:trading|list).?pairs?',
            r'p[uüūи][mм]p|рuмр|ⓟⓤⓜⓟ|accumulate',
            r'(?:buy|sel[l1]|gr[a4]b|hurry|last.?chance|dont.?miss|act.?fast|limited|exclusive)[^.]{0,15}(?:now|fast|quick|soon|today)',
            r'(?:\d+x|\d+[k%]|\d+x?(?:gains?|profit|roi|apy|returns?))',
            r'(?:moon|rocket|profit|lambo|wealth|rich).{0,15}(?:soon|guaranteed|incoming|imminent)',
            r'[🚀💎🌙⬆️📈💰💵💸🤑🔥⭐️🌟✨]+',
            r'(?:diamond|gem|moon).?(?:hands?|hold|hodl)|hold?.?strong',
            r'(?:to|2|two|II).?(?:the|da|d[4a]).?(?:moon|m[o0]n|m[о0]{2}n)',
            r'\b(?:hodl|dyor|fomo|fud|wagmi|gm|ngmi|ath|altcoin|shitcoin|memecoin)\b',
            r'(?:1000|k|thousand).?x',
            r'(?:presale|private.?sale|ico|ido)',
            r'(?:whitel[i1]st|guaranteed.?spots?)',
            r'(?:low|small).?(?:cap|market.?cap)',
            r'(?:nft|mint).?(?:drop|launch|sale)',
            r'(?:early|earlybird|early.?access)',
            r'(?:t\.me|discord\.gg|dex\.tools)',
        ]
