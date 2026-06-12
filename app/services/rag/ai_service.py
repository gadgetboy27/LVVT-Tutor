import os
import json
import re
from typing import List, Dict, Any

import anthropic
from openai import OpenAI

from app.core.config import settings

# --------------------------------------------------------------------------- #
# LLM provider layer: primary = Anthropic (Claude Fable 5), fallback = OpenAI.
# All clients are built lazily so the app imports without any key, and every
# AI-using endpoint additionally has a deterministic non-AI fallback on top.
# --------------------------------------------------------------------------- #
_anthropic_client = None
_openai_client = None


def _anthropic_ready() -> bool:
    return bool(settings.ANTHROPIC_API_KEY)


def _get_anthropic() -> anthropic.Anthropic:
    global _anthropic_client
    if _anthropic_client is None:
        _anthropic_client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
    return _anthropic_client


def _openai_ready() -> bool:
    return bool(settings.OPENAI_API_KEY)


def _get_openai() -> OpenAI:
    global _openai_client
    if _openai_client is None:
        _openai_client = OpenAI(
            api_key=settings.OPENAI_API_KEY or None,
            base_url=settings.OPENAI_BASE_URL or None,
        )
    return _openai_client


def _anthropic_chat(system: str, user: str, max_tokens: int) -> str:
    # Fable 5: adaptive thinking only and no sampling params; omit both. The
    # system prompt is a top-level field, not a message.
    resp = _get_anthropic().messages.create(
        model=settings.ANTHROPIC_MODEL,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    return "".join(b.text for b in resp.content if getattr(b, "type", None) == "text")


def _openai_chat(system: str, user: str, max_tokens: int) -> str:
    resp = _get_openai().chat.completions.create(
        model=settings.OPENAI_MODEL,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        max_tokens=max_tokens,
    )
    return resp.choices[0].message.content or ""


def _provider_order() -> List[str]:
    pref = (settings.LLM_PROVIDER or "auto").lower()
    if pref == "anthropic":
        return ["anthropic"]
    if pref == "openai":
        return ["openai"]
    return ["anthropic", "openai"]  # auto: Fable first, OpenAI as fallback


def _llm_chat(system: str, user: str, max_tokens: int = 1024) -> str:
    """One chat completion with provider fallback (Anthropic -> OpenAI).

    Raises RuntimeError if no provider is configured or all fail. Callers that
    need graceful degradation wrap this in try/except and fall back to
    deterministic, non-AI logic (quiz + teach-back already do)."""
    last_error = None
    for provider in _provider_order():
        try:
            if provider == "anthropic" and _anthropic_ready():
                return _anthropic_chat(system, user, max_tokens)
            if provider == "openai" and _openai_ready():
                return _openai_chat(system, user, max_tokens)
        except Exception as e:  # noqa: BLE001 — try the next provider
            last_error = e
            print(f"LLM provider '{provider}' failed: {e}")
    raise RuntimeError(
        f"No LLM provider available (set ANTHROPIC_API_KEY or OPENAI_API_KEY): {last_error}"
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

    return _llm_chat(system_prompt, user_prompt, max_tokens=1000)


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

    try:
        content = _llm_chat(system_prompt, user_prompt, max_tokens=2000)
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

    try:
        content = _llm_chat(system_prompt, user_prompt, max_tokens=2000)
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

    return _llm_chat(system_prompt, user_prompt, max_tokens=800)


def evaluate_answer(question: str, user_answer: str, correct_answer: str, difficulty: str, standard_number: str) -> Dict[str, Any]:
    difficulty_multiplier = {"easy": 0.8, "medium": 1.0, "hard": 1.2}
    multiplier = difficulty_multiplier.get(difficulty.lower(), 1.0)
    
    system_prompt = """You are an expert LVV certification examiner. Evaluate the trainee's answer against the correct answer.
Consider partial correctness - if they demonstrate understanding even with minor errors, give partial credit.
Be constructive in your feedback."""

    user_prompt = f"""Evaluate this answer for LVV Standard {standard_number}:

QUESTION: {question}
CORRECT ANSWER: {correct_answer}
TRAINEE'S ANSWER: {user_answer}
DIFFICULTY: {difficulty}

Respond with a JSON object:
{{
    "is_correct": true/false (true if substantially correct),
    "score": 0-100 (consider partial credit),
    "explanation": "Detailed feedback explaining what was correct/incorrect",
    "citation": "Reference to the relevant section of {standard_number}"
}}

Be fair but rigorous - this is professional certification training."""

    try:
        content = _llm_chat(system_prompt, user_prompt, max_tokens=500)
        start = content.find('{')
        end = content.rfind('}') + 1
        if start != -1 and end > start:
            result = json.loads(content[start:end])
            result['score'] = min(100, int(result.get('score', 0) * multiplier))
            return result
    except Exception:
        pass
    
    is_correct = user_answer.lower().strip() in correct_answer.lower() or correct_answer.lower() in user_answer.lower()
    return {
        "is_correct": is_correct,
        "score": 100 if is_correct else 0,
        "explanation": f"The correct answer is: {correct_answer}",
        "citation": f"Reference: LVV Standard {standard_number}"
    }


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

    try:
        content = _llm_chat(system_prompt, user_prompt, max_tokens=2000)
        start = content.find('[')
        end = content.rfind(']') + 1
        if start != -1 and end > start:
            return json.loads(content[start:end])
    except Exception:
        pass

    return []


# --------------------------------------------------------------------------- #
# Teach-back (Feynman method): the trainee explains a standard in their own
# words; the AI judges accuracy STRICTLY against retrieved source excerpts so it
# cannot reward fluent-but-wrong answers or hallucinate requirements.
# --------------------------------------------------------------------------- #
_TEACH_STOPWORDS = {
    "which", "their", "there", "these", "those", "about", "would", "could",
    "should", "where", "while", "being", "other", "first", "after", "before",
    "standard", "section", "requirements", "requirement", "vehicle", "must",
    "shall", "lvvta", "lvv", "where", "without",
}


def _key_terms(text: str, limit: int = 12) -> List[str]:
    """Distinctive terms drawn straight from the source text (never invented)."""
    words = re.findall(r"[a-zA-Z][a-zA-Z\-]{4,}", (text or "").lower())
    freq: Dict[str, int] = {}
    for w in words:
        if w in _TEACH_STOPWORDS:
            continue
        freq[w] = freq.get(w, 0) + 1
    ranked = sorted(freq.items(), key=lambda kv: (-kv[1], kv[0]))
    return [w for w, _ in ranked[:limit]]


def evaluate_teachback(topic: str, learner_explanation: str, context: str,
                       standard_number: str, key_points: List[str] = None) -> Dict[str, Any]:
    """Grade a trainee's own-words explanation against the SOURCE EXCERPTS only.

    Anti-hallucination contract: the model is told to use only the provided
    excerpts and to flag insufficient context rather than guess. If the AI is
    unavailable, the deterministic fallback scores purely on lexical coverage of
    source-derived key terms, so it can never invent requirements."""
    has_context = bool(context and context.strip())
    has_explanation = bool(learner_explanation and learner_explanation.strip())

    if has_context and has_explanation:
        system_prompt = (
            "You are an LVV certification examiner using the Feynman teach-back method. "
            "Assess the trainee's explanation ONLY against the SOURCE EXCERPTS provided. "
            "Do NOT use any outside or prior knowledge. If the excerpts do not contain "
            "enough information to verify a point, set insufficient_context true and do "
            "not guess. Never invent requirements, numbers, or clauses not in the excerpts."
        )
        kp = ("\nKEY POINTS A CORRECT EXPLANATION SHOULD COVER:\n- " + "\n- ".join(key_points)) if key_points else ""
        user_prompt = f"""TOPIC: {topic}
STANDARD: {standard_number}

SOURCE EXCERPTS (the only ground truth you may use):
\"\"\"
{context}
\"\"\"{kp}

TRAINEE'S OWN-WORDS EXPLANATION:
\"\"\"
{learner_explanation}
\"\"\"

Compare the explanation to the SOURCE EXCERPTS and respond with a JSON object:
{{
  "accuracy_score": 0-100,
  "is_accurate": true/false,
  "covered_points": ["points the trainee got right, each grounded in the excerpts"],
  "gaps": ["key points from the excerpts the trainee missed"],
  "misconceptions": ["statements the trainee made that contradict the excerpts"],
  "feedback": "2-4 sentences of constructive, grounded feedback",
  "insufficient_context": true/false
}}

Only include items you can support with the SOURCE EXCERPTS."""
        try:
            content = _llm_chat(system_prompt, user_prompt, max_tokens=700)
            start = content.find('{')
            end = content.rfind('}') + 1
            if start != -1 and end > start:
                result = json.loads(content[start:end])
                result.setdefault("covered_points", [])
                result.setdefault("gaps", [])
                result.setdefault("misconceptions", [])
                result.setdefault("feedback", "")
                result.setdefault("insufficient_context", False)
                result["accuracy_score"] = max(0, min(100, int(result.get("accuracy_score", 0))))
                result["is_accurate"] = bool(result.get("is_accurate", result["accuracy_score"] >= 70))
                result["citations"] = [standard_number]
                result["method"] = "ai"
                return result
        except Exception:
            pass

    # Deterministic, grounded fallback: lexical coverage of source key terms.
    expected = (_key_terms(" ".join(key_points)) if key_points else _key_terms(context))
    explanation_l = (learner_explanation or "").lower()
    covered = [t for t in expected if t in explanation_l]
    gaps = [t for t in expected if t not in explanation_l]
    score = int(len(covered) / len(expected) * 100) if expected else 0
    return {
        "accuracy_score": score,
        "is_accurate": score >= 70,
        "covered_points": covered,
        "gaps": gaps,
        "misconceptions": [],
        "feedback": (
            f"Automated lexical check against the standard's key terms "
            f"({len(covered)}/{len(expected)} covered). Connect the AI service for a full grounded assessment."
            if expected else
            "No source content was available to grade this explanation."
        ),
        "citations": [standard_number],
        "insufficient_context": not has_context,
        "method": "lexical-fallback",
    }


def build_teach_tree(standard_number: str, title: str, context: str,
                     max_aspects: int = 5) -> List[Dict[str, Any]]:
    """Break a standard into teach-back aspects, each a prompt for the trainee to
    explain in their own words. Grounded in the source; the deterministic
    fallback derives aspects from the source text without inventing topics."""
    if context and context.strip():
        system_prompt = (
            "You design teach-back prompts for LVV certification training. Using ONLY "
            "the provided source excerpts, identify the key processes/requirements a "
            "trainee should be able to explain. Do not invent topics not in the excerpts."
        )
        user_prompt = f"""STANDARD: {standard_number} - {title}

SOURCE EXCERPTS:
\"\"\"
{context}
\"\"\"

Produce up to {max_aspects} teach-back aspects as a JSON array:
[
  {{
    "aspect": "short name of the process/requirement",
    "prompt": "In your own words, explain ... (ask WHY/HOW this works and what it protects)",
    "key_points": ["specific points a correct explanation must mention, grounded in the excerpts"]
  }}
]

Only use information present in the SOURCE EXCERPTS."""
        try:
            content = _llm_chat(system_prompt, user_prompt, max_tokens=1200)
            start = content.find('[')
            end = content.rfind(']') + 1
            if start != -1 and end > start:
                aspects = json.loads(content[start:end])
                if aspects:
                    return aspects[:max_aspects]
        except Exception:
            pass

    # Fallback: derive aspects from notable source sentences (no invented topics).
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", context or "") if len(s.strip()) > 40]
    aspects: List[Dict[str, Any]] = []
    for sent in sentences[:max_aspects]:
        terms = _key_terms(sent, limit=5)
        aspects.append({
            "aspect": (terms[0].title() if terms else "Key Requirement"),
            "prompt": f"In your own words, explain the purpose of this requirement from {standard_number}: \"{sent[:160]}\"",
            "key_points": terms,
        })
    if not aspects:
        aspects.append({
            "aspect": title or standard_number,
            "prompt": f"In your own words, explain what the {title or standard_number} standard is for and who it protects.",
            "key_points": _key_terms(f"{title} {context}", limit=5),
        })
    return aspects
