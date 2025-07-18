import os
import httpx

async def get_llm_response(history):
    """Calls the IO Intelligence API to get a response."""
    LLM_BASE_URL = "https://api.intelligence.io.solutions/api/v1"
    IOINTELLIGENCE_API_KEY = os.getenv("LLM_API_KEY")

    if not LLM_BASE_URL or not IOINTELLIGENCE_API_KEY:
        raise ValueError("BASE_URL and LLM_API_KEY must be set in the environment.")
        
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

    async with httpx.AsyncClient() as client:
        response = await client.post(url, headers=headers, json=data, timeout=30.0)
        response.raise_for_status()
        return response.json() 
