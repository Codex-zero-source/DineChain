import requests

url = "https://api.intelligence.io.solutions/api/v1/chat/completions"

headers = {
    "Content-Type": "application/json",
    "Authorization": "Bearer io-v2-eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.eyJvd25lciI6Ijg4ZDM2MzI4LTUxMjItNGRhMi1iMGJiLTlkNWM1MmU4NDUxOCIsImV4cCI6NDkwNjUxMjgxOH0.JJiEoCHrw-25arj7JKIQ1ZdPmEivj3aoI30vR3xOXRAA2QjO9-cWJ7lvgCOj_8gSYLgFpbH6xhdkP1-BNTPuQg"
}

data = {
    "model": "meta-llama/Llama-4-Maverick-17B-128E-Instruct-FP8",
    "messages": [
        {
            "role": "system",
            "content": "You are a helpful assistant."
        },
        {
            "role": "user",
            "content": "Hello!"
        }
    ]
}

response = requests.post(url, headers=headers, json=data)

print(response.json()) 
