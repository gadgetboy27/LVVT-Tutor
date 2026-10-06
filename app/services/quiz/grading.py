"""MCQ grading shared by the practice exam and the report card."""

_LETTERS = "ABCDEF"


def correct_index(question: dict) -> int:
    """Index of the correct option. correct_answer may be a letter ("B"), the full
    option text, or "B) text" — mirrors gradeMCQ in static/js/quiz.js."""
    options = question.get("options") or []
    ca = str(question.get("correct_answer") or "").strip()
    if not options or not ca:
        return -1
    for i, o in enumerate(options):
        if o.strip() == ca:
            return i
    if len(ca) == 1 and ca.upper() in _LETTERS[:len(options)]:
        return _LETTERS.index(ca.upper())
    for i, o in enumerate(options):
        if o.strip().lower().startswith(ca.lower() + ")"):
            return i
    low = ca.lower()
    for i, o in enumerate(options):
        if low in o.lower():
            return i
    return -1


def is_answer_correct(question: dict, user_answer: str) -> bool:
    """user_answer is the chosen option letter ("A".."F") or the option text."""
    idx = correct_index(question)
    if idx < 0 or not user_answer:
        return False
    ua = user_answer.strip()
    if len(ua) == 1 and ua.upper() in _LETTERS:
        return _LETTERS.index(ua.upper()) == idx
    options = question.get("options") or []
    return idx < len(options) and options[idx].strip().lower() == ua.lower()
