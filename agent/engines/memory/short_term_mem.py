# Short Term Memory Engine
# Objective: Ephemeral memory. This would simulate scrolling through 4chan or twitter, looking at the most recent posts in their timeline and including that in the post making context to make a decision on whether to reply or not.

# Inputs: 
# Latest top 10 posts 
# Real world context / input from news or external sources

# Outputs: 
# processed information into an internal thought / monologue about current posts and relevance

import json
import time
from typing import List, Dict
import requests
from sqlalchemy.orm import class_mapper
from engines.prompts.prompts import get_short_term_memory_prompt


class ShortTermMemoryManager:
    def __init__(self):
        pass
    # Can modify the type depending on the format that twitter api returns for posts
    # external_context in case you want to include information from other sources 
    def generate_short_term_memory(self, posts: List[Dict], external_context: List[str], llm_api_key: str) -> str:
        """
        Generate short-term memory based on recent posts and external context.

        Args:
            posts (List[Dict]): List of recent posts
            external_context (List[str]): List of external context items
            openrouter_api_key (str): API key for OpenRouter

        Returns:
            str: Generated short-term memory
        """

        prompt = get_short_term_memory_prompt(posts, external_context)

        tries = 0
        max_tries = 3
        while tries < max_tries:
            try:
                url = "https://api.hyperbolic.xyz/v1/chat/completions"

                headers = {
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {llm_api_key}"
                }

                data = {
                    "messages": [
                        {
                            "role": "system",
            	            "content": prompt
                        },
                        {
                            "role": "user",
                            "content": "Respond only with your internal monologue based on the given context."
                        }
                    ],
                    "model": "meta-llama/Meta-Llama-3.1-70B-Instruct",
                    "max_tokens": 512,
                    "temperature": 1,
                    "top_p": 0.95,
                    "top_k": 40,
                    "stream": False,
                }

                response = requests.post(url, headers=headers, json=data)

                if response.status_code == 200:
                    content = response.json()['choices'][0]['message']['content']
                    print(f"Short-term memory generated with response: {content}")
                    if content and content.strip():
                        return content

                print(f"Attempt {tries + 1} failed for short-term memory generation. Status code: {response.status_code}")
                print(f"Response: {response.text}")
                time.sleep(5)

            except Exception as e:
                print(f"Error on attempt {tries + 1}: {str(e)}")
                tries += 1
                time.sleep(5)  # Add a small delay between retries