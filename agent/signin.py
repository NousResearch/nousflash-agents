from twitter.account import Account
import json
import os
import dotenv

dotenv.load_dotenv()

cookies = os.environ.get("X_AUTH_TOKENS")
auth_tokens = json.loads(cookies)

account = Account(cookies=auth_tokens)
timeline = account.home_latest_timeline(10)
print(timeline)
