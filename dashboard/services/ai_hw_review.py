
from openai import AzureOpenAI
from django.conf import settings

def get_ai_review(code: str) -> str:

    client = AzureOpenAI(
        api_version = settings.AZURE_OPENAI_API_VERSION,
        azure_endpoint= settings.AZURE_OPENAI_ENDPOINT,
        api_key = settings.AZURE_OPENAI_API_KEY,
    )
    
    response = client.chat.completions.create(
        messages=[
            {
                "role": "system",
                "content": "You are an AI assistant that reviews student code in the language Python, like a teacher might, to help students improve their programming. You are talking to a student who is in either elementary school or middle school. Do not show them the solution, but explain the problem and what they might want to do to fix it."
            },
            {
                "role": "user",
                "content": f"This is a student's code for the game rock, paper, scissors. Find any errors in their code:\n{code}"
            }
        ],
            max_completion_tokens=1000,
            model = settings.AZURE_OPENAI_DEPLOYMENT_NAME

        
    )

    return response.choices[0].message.content