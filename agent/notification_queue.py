from collections import deque
from typing import List, Tuple
from dataclasses import dataclass, field


@dataclass
class NotificationQueue:
    """Queue to store filtered notifications and timeline posts."""
    min_queue_size: int = 10
    items: deque = field(default_factory=lambda: deque(maxlen=100))  # Store up to 50 items
    processed_ids: set = field(default_factory=set)
    
    def add(self, filtered_notifications: list) -> None:
        """
        Add filtered notifications to the queue and log additions.

        Args:
            filtered_notifications: List of tuples containing (notification_content, tweet_id)
        """
        for notif, tweet_id in filtered_notifications:
            if tweet_id not in self.processed_ids:
                self.items.append((notif, tweet_id))
                self.processed_ids.add(tweet_id)
                print(f"Added to queue: {notif[:100]}... (Tweet ID: {tweet_id})")
    
    def is_ready(self) -> bool:
        """Check if queue has enough items to start processing."""
        return len(self.items) >= self.min_queue_size
    
    def get_all(self) -> List[Tuple[str, str]]:
        """Get all items from the queue and clear it."""
        items = list(self.items)
        return items
    

    def process_queue(self) -> tuple[List[Tuple[str, str]], List[str]]:
        """
        Process all items from the queue and prepare notifications for processing.
        
        Returns:
            tuple: (filtered_notifs_from_queue, notif_context)
                - filtered_notifs_from_queue: List of (content, tweet_id) tuples
                - notif_context: List of notification contents only
        """
        print("Queue ready for processing!")
        filtered_notifs_from_queue = self.get_all()
        notif_context = [context[0] for context in filtered_notifs_from_queue]
        
        print("New Notifications:")
        for content, tweet_id in filtered_notifs_from_queue:
            print(f"- {content}, tweet at https://x.com/user/status/{tweet_id}\n")
        
        return filtered_notifs_from_queue, notif_context

    def clear(self) -> None:
        """Clear the queue."""
        self.items.clear()
        self.processed_ids.clear()
    
    def __len__(self) -> int:
        return len(self.items)