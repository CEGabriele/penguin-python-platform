
from openai import AzureOpenAI
from django.conf import settings
from dashboard.models import HomeworkQuestion

def get_ai_review(code: str, question_id: int) -> str:

    question = HomeworkQuestion.objects.get(id=question_id).prompt
    ai_instructions = HomeworkQuestion.objects.get(id=question_id).extra_ai_instructions
    
    instructions = f"The student was excepted to respond to the following question in python: {question}.\n The teacher has provided the following additional information in how to access their work:\n{ai_instructions}\nThis is their code:\n{code}"
    
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
                "content": instructions
            }
        ],
            max_completion_tokens=2000,
            model = settings.AZURE_OPENAI_DEPLOYMENT_NAME

        
    )
    print("Full Response:", response)
    print("AI feedback", response.choices[0].message.content)

    return response.choices[0].message.content