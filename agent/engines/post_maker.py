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
from typing import List, Dict
from engines.prompts import get_tweet_prompt

def generate_post(short_term_memory: str, long_term_memories: List[Dict], recent_posts: List[Dict], external_context, llm_api_key: str, query: str) -> str:
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
                            Never mention that you formatted the tweet, only return back the formatted tweet itself.
                            If the input already looks like a tweet, return it exactly as is.
                            If the tweet is in all capital letters, return it exactly as is.
                            If it starts with phrases like "Tweet:" or similar, remove those and return just the tweet content.
                            Never say "No Tweet found" - if you receive valid text, that IS the tweet.
                            If the text is blank or only contains a symbol, use this prompt to generate a tweet:
                            {prompt}
                            If the tweet is not blank, make sure it isn't mentioning key words from the prompt.
                            If you get multiple tweets, pick the most funny but fucked up one.
                            MAKE SURE to keep the funny stuff, but if the thoughts mentioned in the tweet aren't as funny as the tweet itself, ignore them. 
                            If the tweet mentions the word timeline and/or the timeline itself modify it so it doesnt say timeline.
                            If the tweet is in first person, leave it that way.
                            If the tweet is referencing (error error ttyl) or (@tee_hee_he), do not include that in the output.
                            If the tweet cuts off, remove the part that cuts off.
                            If the word "suicide" is mentioned, keep everything else the same and replace with the word "suicide" with "toaster bath".
                            ONLY if a tweet contains a racial slur, replace the racial slur with soemthing sex related lol.
                            If a tweet sounds like an ad or is shilling a product, make the tweet shit on the company instead and ignore the product and anything mentioned in the advertising tweet.
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
                "max_tokens": 512,
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
