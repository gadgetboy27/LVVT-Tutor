import os
from openai import OpenAI
from typing import List, Dict

client = OpenAI(
    api_key=os.environ.get("AI_INTEGRATIONS_OPENAI_API_KEY"),
    base_url=os.environ.get("AI_INTEGRATIONS_OPENAI_BASE_URL")
)


def generate_answer_with_citations(question: str, context_chunks: List[Dict]) -> str:
    context = "\n\n".join([
        f"[Source: {chunk.get('standard_number', 'Unknown')}, Section {chunk.get('id', 'N/A')}]\n{chunk.get('text', chunk.get('document', ''))}"
        for chunk in context_chunks
    ])
    
    system_prompt = """You are an expert on LVV (Low Volume Vehicle) certification standards in New Zealand.
Your role is to help certifiers understand the technical requirements and regulations.

IMPORTANT RULES:
1. ALWAYS cite the specific Standard Number (e.g., "According to LVV Standard 40-10, Section 2.1...") when providing information.
2. If the context doesn't contain enough information to answer the question, say so clearly.
3. Be precise and technical - these are professionals who need accurate information.
4. Focus on practical application of the standards."""

    user_prompt = f"""Based on the following context from LVV Standards, answer the question.
Always include specific citations with Standard Numbers.

CONTEXT:
{context}

QUESTION: {question}

Provide a clear, professional answer with specific Standard citations:"""

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        temperature=0.3,
        max_tokens=1000
    )
    
    return response.choices[0].message.content


def generate_quiz_questions(context: str, standard_number: str, num_questions: int = 5) -> List[Dict]:
    system_prompt = """You are an expert quiz creator for LVV certification training.
Create multiple choice questions that test understanding of the technical requirements."""

    user_prompt = f"""Based on this content from LVV Standard {standard_number}, create {num_questions} multiple choice questions.

CONTENT:
{context}

Format your response as a JSON array with this structure:
[
  {{
    "question": "The question text (reference the Standard Number)",
    "options": ["A) Option 1", "B) Option 2", "C) Option 3", "D) Option 4"],
    "correct_answer": "A",
    "explanation": "Brief explanation citing the specific section of {standard_number}"
  }}
]

Make questions practical and relevant to certification work."""

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        temperature=0.7,
        max_tokens=2000
    )
    
    import json
    try:
        content = response.choices[0].message.content
        start = content.find('[')
        end = content.rfind(']') + 1
        if start != -1 and end > start:
            return json.loads(content[start:end])
    except:
        pass
    
    return []
