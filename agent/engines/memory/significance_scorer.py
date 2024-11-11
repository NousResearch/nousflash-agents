import requests
import time
from engines.prompts.prompts import get_significance_score_prompt, get_reply_worthiness_score_prompt


class SignificanceScorer:
    def __init__(self):
        pass
    def score_significance(self, memory: str, llm_api_key: str) -> int:
        """
        Score the significance of a memory on a scale of 1-10.

        Args:
            memory (str): The memory to be scored
            openrouter_api_key (str): API key for OpenRouter
            your_site_url (str): Your site URL for OpenRouter API
            your_app_name (str): Your app name for OpenRouter API

        Returns:
            int: Significance score (1-10)
        """
        prompt = get_significance_score_prompt(memory)

        tries = 0
        max_tries = 5
        while tries < max_tries:
            try:
                response = requests.post(
                    url="https://api.hyperbolic.xyz/v1/chat/completions",
                    headers={
                        "Content-Type": "application/json",
                        "Authorization": f"Bearer {llm_api_key}",
                    },
                    json={
                        "messages": [
                            {
                                "role": "system",
            	                "content": prompt
                            },
                            {
                                "role": "user",
                                "content": "Respond only with the score you would give for the given memory."
                            }
                        ],
                        "model": "meta-llama/Meta-Llama-3.1-70B-Instruct",
                        "temperature": 1,
                        "top_p": 0.95,
                        "top_k": 40,
                    }
                )

                if response.status_code == 200:
                    score_str = response.json()['choices'][0]['message']['content'].strip()
                    print(f"Score generated for memory: {score_str}")
                    if score_str == "":
                        print(f"Empty response on attempt {tries + 1}")
                        tries += 1
                        continue
                    
                    try:
                        # Extract the first number found in the response
                        # This helps handle cases where the model includes additional text
                        import re
                        numbers = re.findall(r'\d+', score_str)
                        if numbers:
                            score = int(numbers[0])
                            return max(1, min(10, score))  # Ensure the score is between 1 and 10
                        else:
                            print(f"No numerical score found in response: {score_str}")
                            tries += 1
                            continue

                    except ValueError:
                        print(f"Invalid score returned: {score_str}")
                        tries += 1
                        continue
                else:
                    print(f"Error on attempt {tries + 1}. Status code: {response.status_code}")
                    print(f"Response: {response.text}")
                    tries += 1

            except Exception as e:
                print(f"Error on attempt {tries + 1}: {str(e)}")
                tries += 1 
                time.sleep(1)  # Add a small delay between retries


    def score_reply_significance(self, tweet: str, llm_api_key: str) -> int:
        """
        Score the significance of a memory on a scale of 1-10.

        Args:
            memory (str): The memory to be scored
            openrouter_api_key (str): API key for OpenRouter
            your_site_url (str): Your site URL for OpenRouter API
            your_app_name (str): Your app name for OpenRouter API

        Returns:
            int: Significance score (1-10)
        """
        prompt = get_reply_worthiness_score_prompt(tweet)

        tries = 0
        max_tries = 5
        while tries < max_tries:
            try:
                response = requests.post(
                    url="https://api.hyperbolic.xyz/v1/chat/completions",
                    headers={
                        "Content-Type": "application/json",
                        "Authorization": f"Bearer {llm_api_key}",
                    },
                    json={
                        "messages": [
                            {
                                "role": "system",
            	                "content": prompt
                            },
                            {
                                "role": "user",
                                "content": "Respond only with the score you would give for the given memory."
                            }
                        ],
                        "model": "meta-llama/Meta-Llama-3.1-70B-Instruct",
                        "temperature": 1,
                        "top_p": 0.95,
                        "top_k": 40,
                    }
                )

                if response.status_code == 200:
                    score_str = response.json()['choices'][0]['message']['content'].strip()
                    print(f"Score generated for reply worthiness: {score_str}")
                    if score_str == "":
                        print(f"Empty response on attempt {tries + 1}")
                        tries += 1
                        continue
                    
                    try:
                        # Extract the first number found in the response
                        # This helps handle cases where the model includes additional text
                        import re
                        numbers = re.findall(r'\d+', score_str)
                        if numbers:
                            score = int(numbers[0])
                            return max(1, min(10, score))  # Ensure the score is between 1 and 10
                        else:
                            print(f"No numerical score found in response: {score_str}")
                            tries += 1
                            continue

                    except ValueError:
                        print(f"Invalid score returned: {score_str}")
                        tries += 1
                        continue
                else:
                    print(f"Error on attempt {tries + 1}. Status code: {response.status_code}")
                    print(f"Response: {response.text}")
                    tries += 1

            except Exception as e:
                print(f"Error on attempt {tries + 1}: {str(e)}")
                tries += 1 
                time.sleep(1)  # Add a small delay between retries