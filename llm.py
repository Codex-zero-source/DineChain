import os
import httpx
from dotenv import load_dotenv

load_dotenv()

LLM_BASE_URL = os.getenv("LLM_BASE_URL")
IOINTELLIGENCE_API_KEY = os.getenv("LLM_API_KEY")

if not LLM_BASE_URL or not IOINTELLIGENCE_API_KEY:
    raise ValueError("LLM_BASE_URL and LLM_API_KEY must be set in the environment.")

async def get_llm_response(history):
    url = f"{LLM_BASE_URL}/chat/completions"
    headers = {
        "Authorization": f"Bearer {IOINTELLIGENCE_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": "jollof-bot-4o",
        "messages": history,
    }
    async with httpx.AsyncClient() as client:
        response = await client.post(url, headers=headers, json=payload, timeout=30.0)
        response.raise_for_status()
        return response.json() 
