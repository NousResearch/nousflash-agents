from models import User
from sqlalchemy.orm import Session

class UserManager:
    def __init__(self):
        pass

    def _get_or_create_ai_user(self, db: Session, bot_username: str, bot_email: str) -> User:
        """Get or create the AI user in the database."""
        ai_user = (db.query(User)
                  .filter(User.username == bot_username)
                  .first())
        
        if not ai_user:
            ai_user = User(
                username=bot_username,
                email=bot_email
            )
            db.add(ai_user)
            db.commit()
        return ai_user