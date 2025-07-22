import requests
from django.conf import settings
def get_ai_review(code: str) -> str:
    prompt = f"Please review the following code and point out errors or improvements:\n{code}\nDo not rewrite the code for the student, just provide feedback for how they can fix it."

    headers = {
        "api-key": settings.AZURE_OPENAI_API_KEY,
        "Content-Type": "application/json"
    }

    url = f"{settings.AZURE_OPENAI_ENDPOINT}/openai/deployments/{settings.AZURE_OPENAI_DEPLOYMENT_NAME}/chat/completions?api-version={settings.AZURE_OPENAI_API_VERSION}"
    
    data = {
        "messages" : [
            {
                "role": "system",
                "content": "You review student code like a teacher would in order to help students improve their programming."
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
        "max_tokens": 300
    }

    response = requests.post(url, headers=headers, json=data)
    response.raise_for_status()
    return response.json()['choices'][0]['message']['content']