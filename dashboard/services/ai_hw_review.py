
from openai import AzureOpenAI
from django.conf import settings
from dashboard.models import HomeworkQuestion, CompletedCurriculum, HomeworkTemplate

def get_ai_review(response, code: str, question_id: int) -> str:
    
    question = HomeworkQuestion.objects.get(id=question_id).prompt
    topic_instructions = generate_ai_knowledge_instructions(response)
    
    instructions = f"The student is responding to the following problem posted by their teacher: {question}.\n This is their code:\n{code}\n Provide feedback on errors in their code in a bulleted list, containing up to five items. The student has the ability to get more feedback if they ask for it, so do not give them more than five items at a time."
    
    client = AzureOpenAI(
        api_version = settings.AZURE_OPENAI_API_VERSION,
        azure_endpoint= settings.AZURE_OPENAI_ENDPOINT,
        api_key = settings.AZURE_OPENAI_API_KEY,
    )
    
    response = client.chat.completions.create(
        messages=[
            {
                "role": "system",
                "content": "You are an AI assistant that reviews student code in the language Python to help students improve their programming. Find errors and suggest improvements to their code. The student you are speaking to is in middle or elementary school, so use a supportive, simple, and clear tone. Do not give students full solutions; instead, explain what's wrong and what they might want to consider when fixing their code. If a student's code is correct, say so and do not ask the student to do anything further." + topic_instructions
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

def generate_ai_knowledge_instructions(response):
    student = response.user.student
    topics = get_known_topics(student)
    prompt = f"""The following topics have been covered in this student's classes so far and may be used in your explanation: {", ".join(topics)}. Some topics may not be relevant to this assignment."""
    return prompt


def split_topics(text):
    return [t.strip().lower() for t in text.split(',') if t.strip()]

def get_known_topics(student):
    completions = CompletedCurriculum.objects.filter(student=student)
    topics = set()
    for progress in completions:
        templates = HomeworkTemplate.objects.filter(curriculum=progress.curriculum, class_week__lte=progress.completed_weeks)

        for template in templates:
            topics.update(split_topics(template.new_material))
    return topics