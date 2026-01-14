import os
import json
from openai import OpenAI
from typing import List, Dict, Any

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
Create multiple choice questions that test the deep understanding required of a professional LVV Certifier.
Questions must be practical and relevant to real-world certification work."""

    user_prompt = f"""Based on this content from LVV Standard {standard_number}, create {num_questions} multiple choice questions.

CONTENT:
{context}

Format your response as a JSON array with this structure:
[
  {{
    "question": "The question text (reference the Standard Number)",
    "options": ["A) Option 1", "B) Option 2", "C) Option 3", "D) Option 4"],
    "correct_answer": "A",
    "explanation": "Brief explanation citing the specific section of {standard_number}",
    "type": "MCQ"
  }}
]

Include a mix of:
- Technical specification questions
- Certification process questions  
- Safety compliance questions

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
    
    try:
        content = response.choices[0].message.content
        start = content.find('[')
        end = content.rfind(']') + 1
        if start != -1 and end > start:
            return json.loads(content[start:end])
    except Exception:
        pass
    
    return []


def summarize_and_categorize(doc_text: str, doc_title: str) -> Dict[str, Any]:
    system_prompt = """You are an expert on NZ LVVTA (Low Volume Vehicle Technical Association) standards.
Your job is to analyze technical documentation and structure it for a learning platform."""

    user_prompt = f"""Analyze this LVV document and provide a structured response.

DOCUMENT TITLE: {doc_title}

CONTENT:
{doc_text[:8000]}

Respond with a JSON object containing:
{{
    "summary": "A concise 3-5 sentence summary of the document's purpose and key requirements",
    "category": "One of: Brakes, Suspension & Steering, Engine & Drivetrain, Lighting & Electrical, Body & Structure, Wheels & Tyres, Exhaust & Emissions, General Compliance, Certification Process",
    "sections": [
        {{
            "title": "Section name",
            "summary": "Brief summary of this section's key points"
        }}
    ]
}}

Focus on the technical requirements and certification processes."""

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        temperature=0.3,
        max_tokens=2000
    )
    
    try:
        content = response.choices[0].message.content
        start = content.find('{')
        end = content.rfind('}') + 1
        if start != -1 and end > start:
            return json.loads(content[start:end])
    except Exception:
        pass
    
    return {
        "summary": f"Document: {doc_title}",
        "category": "General Compliance",
        "sections": []
    }


def lookup_competency(skill: str) -> str:
    system_prompt = """You are an expert on LVV (Low Volume Vehicle) certification in New Zealand.
You help certifiers understand the professional competencies required for their role."""

    user_prompt = f"""Explain how an LVV Certifier demonstrates the following competency in their professional work:

COMPETENCY: {skill}

Provide a detailed explanation that:
1. Defines what this competency means in the LVV certification context
2. Gives practical examples of how it applies to daily certification work
3. Explains why it's critical for public safety and the integrity of the LVVTA scheme

Format your response clearly with examples."""

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        temperature=0.5,
        max_tokens=800
    )
    
    return response.choices[0].message.content


def generate_section_quiz(section_content: str, section_title: str, standard_number: str, count: int = 5) -> List[Dict[str, Any]]:
    system_prompt = """You are an expert quiz creator for LVV certification training.
Create questions that test certifier-level understanding of the specific section content."""

    user_prompt = f"""Create {count} quiz questions based ONLY on this section content.

STANDARD: {standard_number}
SECTION: {section_title}

CONTENT:
{section_content}

Return a JSON array:
[
  {{
    "question": "Specific question referencing {standard_number}, {section_title}",
    "options": ["A) Option 1", "B) Option 2", "C) Option 3", "D) Option 4"],
    "correct_answer": "A",
    "explanation": "Why this is correct, citing the section",
    "type": "MCQ"
  }}
]

Questions must test deep understanding required for professional LVV certification."""

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        temperature=0.7,
        max_tokens=2000
    )
    
    try:
        content = response.choices[0].message.content
        start = content.find('[')
        end = content.rfind(']') + 1
        if start != -1 and end > start:
            return json.loads(content[start:end])
    except Exception:
        pass
    
    return []
