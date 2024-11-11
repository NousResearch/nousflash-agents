import json
from datetime import datetime
from typing import Dict, Any

def parse_twitter_data(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Parse and format Twitter JSON data into a more readable structure.
    
    Args:
        data (Dict[str, Any]): Raw Twitter JSON data
        
    Returns:
        Dict[str, Any]: Formatted and cleaned data structure
    """
    parsed_data = {
        'users': [],
        'notifications': []
    }
    
    # Parse users
    if 'globalObjects' in data and 'users' in data['globalObjects']:
        users = data['globalObjects']['users']
        for user_id, user_info in users.items():
            cleaned_user = {
                'id': user_info['id'],
                'name': user_info['name'],
                'screen_name': user_info['screen_name'],
                'description': user_info['description'],
                'followers_count': user_info['followers_count'],
                'following_count': user_info['friends_count'],
                'tweet_count': user_info['statuses_count'],
                'location': user_info['location'],
                'created_at': user_info['created_at'],
                'verified': user_info['verified'],
                'is_blue_verified': user_info['ext_is_blue_verified']
            }
            parsed_data['users'].append(cleaned_user)
    
    # Parse notifications
    if 'notifications' in data:
        notifications = data['notifications']
        for notif_id, notif_info in notifications.items():
            # Convert timestamp to readable format
            timestamp = datetime.fromtimestamp(
                int(notif_info['timestampMs']) / 1000
            ).strftime('%Y-%m-%d %H:%M:%S')
            
            # Extract notification message and type
            message = notif_info['message']['text']
            notif_type = notif_info['icon']['id']
            
            cleaned_notification = {
                'id': notif_id,
                'timestamp': timestamp,
                'type': notif_type,
                'message': message
            }
            
            # Add user references if present
            if 'entities' in notif_info['message']:
                user_refs = []
                for entity in notif_info['message']['entities']:
                    if 'ref' in entity and 'user' in entity['ref']:
                        user_refs.append(entity['ref']['user']['id'])
                if user_refs:
                    cleaned_notification['referenced_users'] = user_refs
                    
            parsed_data['notifications'].append(cleaned_notification)
    
    return parsed_data

def format_output(parsed_data: Dict[str, Any]) -> str:
    """
    Format the parsed data into a readable string.
    
    Args:
        parsed_data (Dict[str, Any]): Parsed Twitter data
        
    Returns:
        str: Formatted string representation of the data
    """
    output = []
    
    # Format users section
    output.append("=== Users ===")
    for user in parsed_data['users']:
        output.append(f"\nUser: @{user['screen_name']}")
        output.append(f"Name: {user['name']}")
        output.append(f"Followers: {user['followers_count']:,}")
        output.append(f"Following: {user['following_count']:,}")
        output.append(f"Tweets: {user['tweet_count']:,}")
        if user['description']:
            output.append(f"Bio: {user['description']}")
        output.append(f"Verified: {'✓' if user['verified'] else '✗'}")
        output.append(f"Blue Verified: {'✓' if user['is_blue_verified'] else '✗'}")
        output.append("-" * 50)
    
    # Format notifications section
    output.append("\n=== Notifications ===")
    for notif in parsed_data['notifications']:
        output.append(f"\nTime: {notif['timestamp']}")
        output.append(f"Type: {notif['type']}")
        output.append(f"Message: {notif['message']}")
        if 'referenced_users' in notif:
            output.append(f"Referenced Users: {', '.join(notif['referenced_users'])}")
        output.append("-" * 50)
    
    return "\n".join(output)

def process_twitter_json(json_data) -> str:
    """
    Main function to process Twitter JSON data and return readable output.
    
    Args:
        json_data (str): Raw JSON string
        
    Returns:
        str: Formatted readable output
    """
    try:
        # Parse JSON string to dictionary
        data = json_data
        # Parse the data into a cleaner structure
        parsed_data = parse_twitter_data(data)
        # Format the parsed data into readable output
        return format_output(parsed_data)
    except json.JSONDecodeError:
        return "Error: Invalid JSON data"
    except Exception as e:
        return f"Error processing data: {str(e)}"
    

def is_spam(self, content: str) -> bool:
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
    return any(re.search(p, clean) for p in patterns)