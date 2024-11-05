import os
import random
from datetime import datetime, timedelta
from time import sleep
import requests
from sqlalchemy.orm import Session
from models import User, Post, Comment, Like, LongTermMemory
from db.db_setup import SessionLocal, engine
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

def load_example_content(filename="examples.txt"):
    """Load and parse example content from a text file."""
    # Get the directory where the current script is located
    current_dir = os.path.dirname(os.path.abspath(__file__))
    file_path = os.path.join(current_dir, filename)
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read().strip()
            # Split on double newlines to separate different examples
            examples = [x.strip() for x in content.split('\n\n') if x.strip()]
            print(f"Successfully loaded {len(examples)} examples from {file_path}")
            return examples
    except FileNotFoundError:
        print(f"Could not find file at {file_path}")
        print("Current working directory:", os.getcwd())
        print("Looking for file in:", current_dir)
        raise

def create_embedding(text):
    """Create embedding using OpenAI API."""
    client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
    response = client.embeddings.create(
        input=text,
        model="text-embedding-3-small"
    )
    return response.data[0].embedding

def seed_database():
    db = SessionLocal()

    # Load example content
    examples = load_example_content()
    
    # Create users if they don't exist
    existing_users = db.query(User).all()
    print(f"Existing users: {existing_users}")
    if not existing_users:
        users = [
            User(username=f"tee_hee_he", email=f"tee_hee_he@example.com")
        ]
        db.add_all(users)
        db.commit()
    
    users = db.query(User).all()

    # Create posts using some of the examples
    num_posts = min(5, len(examples))  # Use up to 5 examples for posts
    post_examples = random.sample(examples, num_posts)
    
    for content in post_examples:
        post = Post(
            content=content,
            user_id=random.choice(users).id,
            type="text",
            created_at=datetime.now() - timedelta(days=random.randint(0, 30))
        )
        db.add(post)
    db.commit()

    # Create comments using different examples
    posts = db.query(Post).all()
    remaining_examples = [ex for ex in examples if ex not in post_examples]
    
    for post in posts:
        if remaining_examples:
            num_comments = random.randint(0, 2)
            for _ in range(num_comments):
                if remaining_examples:
                    content = remaining_examples.pop(0)
                    random_user = random.choice(users)
                    comment = Comment(
                        content=content,
                        user_id=random_user.id,
                        username=random_user.username,
                        post_id=post.id,
                        created_at=post.created_at + timedelta(hours=random.randint(1, 24))
                    )
                    db.add(comment)
    db.commit()
    
    # Create likes
    for post in posts:
        for user in random.sample(users, k=random.randint(0, len(users))):
            like = Like(user_id=user.id, post_id=post.id, is_like=True)
            db.add(like)
    db.commit()

    # Create long-term memories using remaining examples
    if remaining_examples:
        num_memories = min(3, len(remaining_examples))
        memory_examples = random.sample(remaining_examples, num_memories)
        
        for content in memory_examples:
            embedding = create_embedding(content)
            memory = LongTermMemory(
                content=content,
                embedding=str(embedding),
                significance_score=random.uniform(7.0, 10.0)
            )
            db.add(memory)
    db.commit()

    db.close()

if __name__ == "__main__":
    seed_database()
    print("Database seeded successfully.")