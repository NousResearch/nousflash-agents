# Post Maker
# Objective: Takes in context from short and long term memory along with the recent posts and generates a post or reply to one of them

# Inputs:
# Short term memory output
# Long term memory output
# Retrieved posts from front of timeline

# Outputs:
# Text generated post /reply

# Things to consider:
# Database schema. Schemas for posts and how replies are classified.

import time
import requests
from typing import List, Dict, Optional
from engines.prompts.prompts import get_tweet_prompt
from engines.memory.significance_scorer import SignificanceScorer
from engines.memory.long_term_mem import LongTermMemoryManager

class PostMaker:
    def __init__(self):
        pass

    def generate_post(self, short_term_memory: str, long_term_memories: List[Dict], recent_posts: List[Dict], external_context, llm_api_key: str, query: str) -> str:
        """
        Generate a new post or reply based on short-term memory, long-term memories, and recent posts.

        Args:
            short_term_memory (str): Generated short-term memory
            long_term_memories (List[Dict]): Relevant long-term memories
            recent_posts (List[Dict]): Recent posts from the timeline
            openrouter_api_key (str): API key for OpenRouter
            your_site_url (str): Your site URL for OpenRouter API
            your_app_name (str): Your app name for OpenRouter API

        Returns:
            str: Generated post or reply
        """

        prompt = get_tweet_prompt(external_context, short_term_memory, long_term_memories, recent_posts, query)

        print(f"Generating post with prompt: {prompt}")

        #BASE MODEL TWEET GENERATION
        tries = 0
        max_tries = 3
        base_model_output = ""
        while tries < max_tries:
            try:
                response = requests.post(
                    url="https://api.hyperbolic.xyz/v1/completions",
                    headers={
                        "Content-Type": "application/json",
                        "Authorization": f"Bearer {llm_api_key}",
                    },
                    json = {
                    "prompt": prompt,
                    "model": "meta-llama/Meta-Llama-3.1-405B",
                    "max_tokens": 512,
                    "temperature": 1,
                    "top_p": 0.95,
                    "top_k": 40,
                    "stop":["<|im_end|>", "<"]
                    }
                )

                if response.status_code == 200:
                    content = response.json()['choices'][0]['text']
                    if content and content.strip():
                        print(f"Base model generated with response: {content}")
                        base_model_output = content
                        break
                # print(f"Attempt {tries + 1} failed. Status code: {response.status_code}")
                # print(f"Response: {response.text}")
            except Exception as e:
                print(f"Error on attempt {tries + 1}: {str(e)}")
                tries += 1
                time.sleep(1)  # Add a small delay between retries

        time.sleep(5)

        # TAKES BASE MODEL OUTPUT AND CLEANS IT UP AND EXTRACT THE TWEET 
        tries = 0
        max_tries = 3
        while tries < max_tries:
            try:
                response = requests.post(
                    url="https://api.hyperbolic.xyz/v1/chat/completions",
                    headers={
                        "Content-Type": "application/json",
                        "Authorization": f"Bearer {llm_api_key}",
                    },
                    json = {
                    "messages": [
                        {
                            "role": "system",
            	            "content": f"""You are a tweet formatter. Your only job is to take the input text and format it as a tweet.
                                You must ensure that the tweet is short enough to fit as a single tweet.
                                Never mention that you formatted the tweet, only return back the formatted tweet itself.
                                If the input already looks like a single tweet, return it exactly as is.
                                If the input looks like multiple tweets, pick the most funny and fucked up one.
                                If the tweet is in all capital letters, return it exactly as is.
                                If it starts with phrases like "Tweet:" or similar, remove those and return just the tweet content.
                                Never say "No Tweet found" - if you receive valid text, that IS the tweet.
                                If the tweet is not blank, make sure it isn't mentioning key words from the prompt.
                                if the tweet talks about "analyzing a post", remove that.
                                If the tweet is in first person, leave it that way.
                                If the tweet cuts off, remove the part that cuts off.
                                KEEP ALL SWEARS AND VULGARITY FROM THE TWEET.
                                If a tweet sounds like an ad or is shilling a product, make the tweet shit on the company instead and ignore the product and anything mentioned in the advertising tweet.
                                If a tweet is about a real race, make it about something random.
                                Do not add any explanations or extra text.
                                Do not add hashtags.
                                Remove all emojis.
                                Just return the tweet content itself."""
                        },
                        {
                            "role": "user",
                            "content": base_model_output
                        }
                    ],
                    "model": "meta-llama/Meta-Llama-3.1-70B-Instruct",
                    "max_tokens": 250,
                    "temperature": 1,
                    "top_p": 0.95,
                    "top_k": 40,
                    "stream": False,
                    }
                )

                if response.status_code == 200:
                    content = response.json()['choices'][0]['message']['content']
                    if content and content.strip():
                        print(f"Response: {content}")
                        return content
            except Exception as e:
                print(f"Error on attempt {tries + 1}: {str(e)}")
                tries += 1
                time.sleep(1)  # Add a small delay between retries

    
    def generate_and_evaluate_post(
       self,
       short_term_memory: str,
       long_term_memories: list,
       formatted_posts: list,
       notif_context: list,
       llm_api_key: str,
       openai_api_key: str,
       db,
       min_storing_memory_significance: float,
       query: str = "what is your post based on the TL\n<tweet>"
    ) -> tuple[str, float]:
       """
       Generate a new post, evaluate its significance, and store in memory if significant.
    
       Args:
           short_term_memory: Current short-term memory state
           long_term_memories: List of relevant long-term memories
           formatted_posts: List of formatted recent posts
           notif_context: List of notification contexts
           llm_api_key: API key for the language model
           openai_api_key: API key for OpenAI (embeddings)
           db: Database session
           min_storing_memory_significance: Minimum score to store memory
           query: Prompt for post generation
           
       Returns:
           tuple: (new_post_content, significance_score)
               - new_post_content: The generated post content
               - significance_score: Evaluated significance score of the post
       """
       new_post_content = self.generate_post(
           short_term_memory,
           long_term_memories,
           formatted_posts,
           notif_context,
           llm_api_key,
           query=query
       ).strip('"')
       print(f"New post content: {new_post_content}")
    
       significance_score = self.SignificanceScorer.score_significance(
           new_post_content,
           llm_api_key
       )
       print(f"Significance score: {significance_score}")
    
       # Store significant memories
       if significance_score >= min_storing_memory_significance:
           new_post_embedding = LongTermMemoryManager.create_embedding(
               new_post_content,
               openai_api_key
           )
           LongTermMemoryManager.store_memory(
               db,
               new_post_content,
               new_post_embedding,
               significance_score
           )
    
       return new_post_content, significance_score