import os
import httpx
import logging

logging.basicConfig(level=logging.INFO)

async def get_llm_response(history):
    """Calls the IO Intelligence API to get a response."""
    LLM_BASE_URL = os.getenv("BASE_URL")
    IOINTELLIGENCE_API_KEY = os.getenv("LLM_API_KEY")

    if not LLM_BASE_URL or not IOINTELLIGENCE_API_KEY:
        logging.error("LLM_BASE_URL and/or IOINTELLIGENCE_API_KEY are not set.")
        return None # Return None instead of raising an exception
        
    url = f"{LLM_BASE_URL}/chat/completions"
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {IOINTELLIGENCE_API_KEY}"
    }
    data = {
        "model": "meta-llama/Llama-4-Maverick-17B-128E-Instruct-FP8",
        "messages": [{"role": msg["role"], "content": msg["content"]} for msg in history],
        "temperature": 0.7,
        "max_tokens": 400
    }

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(url, headers=headers, json=data, timeout=30.0)
            response.raise_for_status() # Raise an exception for bad status codes
            return response.json()
    except httpx.RequestError as e:
        logging.error(f"Error requesting LLM: {e}")
        return None
    except httpx.HTTPStatusError as e:
        logging.error(f"LLM request failed with status {e.response.status_code}: {e.response.text}")
        return None
    except Exception as e:
        logging.error(f"An unexpected error occurred in get_llm_response: {e}")
        return None 
